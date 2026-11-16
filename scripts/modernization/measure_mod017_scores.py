"""Audit-only stored-score reads on guarded disposable localhost PostgreSQL."""
import argparse
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import hashlib,time
from pathlib import Path
from uuid import uuid4
import psycopg2
from sqlalchemy import create_engine,text
import measure_mod017 as base
from measure_mod017_transactions import Capture,validate_result,verify_cleanup,save_json
from endpoints.scoring.repository import ScoringRepository
from endpoints.scoring.service import ScoringReadService

WEEKLY='CREATE INDEX mod017_scores_week ON "WeeklyTeamScore" ("leagueId","weekId",rank) INCLUDE ("memberId","pointsAwarded","pointDifferential")'
SEASON='CREATE INDEX mod017_scores_member ON "WeeklyTeamScore" ("leagueId","memberId") INCLUDE ("pointsAwarded")'
CANDIDATES={'weekly':[WEEKLY],'season':[SEASON],'combined':[WEEKLY,SEASON]}

class StatementCapture(Capture):
    def execute(self,statement,params):
        self.original=statement
        return super().execute(statement,params)


def normalize_rows(family,rows):
    return sorted(rows,key=lambda r:r['memberId']) if family in ['season','ranks'] else rows


def expected_weekly(n,anchor,league,weeks):
    if league!=n//2+1:return []
    clock=datetime.fromisoformat(anchor);rows=[]
    for week in sorted(set(weeks)&set(range(1,13))):
        for position in range(1,8):
            rows.append(dict(weekNumber=week,startDate=clock+timedelta(days=(week-13)*7-1),endDate=clock+timedelta(days=(week-13)*7+6),memberId=(league-1)*8+position,teamName=f'Team {position}',pointsAwarded=4*(9-position),pointDifferential=4*(9-position),rank=position))
    return rows


def capture_queries(n,anchor):
    league=n//2+1;member=(league-1)*8+1;week_id=(league-1)*13+12;repo=ScoringRepository();cases=[]
    def add(name,family,expected,fn,inputs=None):
        capture=StatementCapture();fn(capture)
        compiled=capture.original.params(**capture.params).compile(compile_kwargs={'render_postcompile':True})
        cases.append(dict(name=name,family=family,expected_rows=len(expected),expected_values=expected,sql=str(compiled),params=compiled.params,service_inputs=inputs))
    for name,lid,weeks in [('all',league,list(range(1,13))),('one',league,[12]),('sparse',league,[1,6,12]),('duplicate',league,[12,12]),('empty',league,[]),('unscored',league,[13]),('missing',n+100,[12])]:
        add('weekly_'+name,'weekly',expected_weekly(n,anchor,lid,weeks),lambda c,l=lid,w=weeks:repo.weekly_points(c,l,w),dict(league=lid,weeks=weeks))
    values=[dict(memberId=(league-1)*8+m,teamName=f'Team {m}',weeklyPoints=Decimal(48*(9-m)) if m<8 else Decimal(0)) for m in range(1,9)]
    add('season_current','season',values,lambda c:repo.season_points(c,league))
    add('season_missing','season',[],lambda c:repo.season_points(c,n+100))
    for name,lid,wid,ids in [('all',league,week_id,list(range(member,member+8))),('subset',league,week_id,[member,member+7,member+8]),('empty',league,week_id,[]),('unscored',league,week_id+1,[member]),('foreign_week',league,week_id+13,[member]),('missing',n+100,week_id,[member])]:
        expected=[dict(memberId=m,rank=m-member+1) for m in sorted(set(ids)) if member<=m<member+7] if lid==league and wid==week_id else []
        add('ranks_'+name,'ranks',expected,lambda c,l=lid,w=wid,i=ids:repo.weekly_ranks(c,l,w,i))
    return cases


def seed_scores(conn,n):
    league=n//2+1;unscored=(league-1)*8+8
    changed=conn.execute(text('DELETE FROM "WeeklyTeamScore" WHERE "leagueId"=:league AND "memberId"=:member'),dict(league=league,member=unscored)).rowcount
    if changed!=12:raise AssertionError('Expected twelve unscored-member fixture deletions')
    conn.commit();conn.exec_driver_sql('ANALYZE');conn.commit()
    observed=conn.exec_driver_sql('SELECT count(*) FROM "WeeklyTeamScore"').scalar_one()
    if observed!=96*n-12:raise AssertionError('Unexpected score fixture size')
    return dict(initial_score_rows=96*n,score_rows=observed,deleted_rows=changed,unscored_member=unscored,target_league=league,members=8,scored_members=7,scored_weeks=12)


def measure(conn,case):
    statement=text(case['sql']);params=case['params'];conn.execute(statement,params).fetchall()
    plan=conn.execute(text('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+case['sql']),params).scalar_one()[0]
    samples=[];signature=None;observed_order=None
    for _ in range(5):
        start=time.perf_counter();raw=conn.execute(statement,params).mappings().all();elapsed=(time.perf_counter()-start)*1000
        rows=[dict(r) for r in raw];observed_order=[r['memberId'] for r in rows]
        current=base.signature(normalize_rows(case['family'],rows));base.assert_equivalent(base.signature(case['expected_values']),current)
        if signature is not None:base.assert_equivalent(signature,current)
        signature=current;samples.append(elapsed)
    result=dict(**case,result=signature,observed_member_order=observed_order,client_execute_fetch_ms=dict(samples=samples,median=base.statistics.median(samples),min=min(samples),max=max(samples)),plan=plan)
    validate_result(case,result);return result


def measure_service(engine,cases):
    service=ScoringReadService(engine);records=[]
    for case in cases:
        p=case['service_inputs']
        if p is None:continue
        samples=[];signature=None
        for iteration in range(6):
            start=time.perf_counter();rows=service.get_weekly_points_for_job(p['league'],p['weeks']);elapsed=(time.perf_counter()-start)*1000
            signature=base.signature(rows);base.assert_equivalent(base.signature(case['expected_values']),signature)
            if iteration:samples.append(elapsed)
        records.append(dict(name=case['name'],inputs=p,result=signature,service_ms=dict(samples=samples,median=base.statistics.median(samples),min=min(samples),max=max(samples))))
    return records


def run_tier(admin,n,report):
    record=None
    try:
        with base.owned_database(admin) as database:
            record=dict(name=database,cleanup='pending');report['databases'].append(record)
            engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=database,**base.LOCAL))
            try:
                with engine.connect() as conn:
                    base.schema(conn);facts=base.seed(conn,n);facts['scores']=seed_scores(conn,n);cases=capture_queries(n,facts['anchor']);indexes=base.catalog(conn)
                    settings={k:conn.exec_driver_sql('SHOW '+k).scalar_one() for k in ['server_version','shared_buffers','work_mem','effective_cache_size','random_page_cost','jit','jit_above_cost','max_parallel_workers_per_gather','statement_timeout','lock_timeout']}
                    measurements={'baseline':[measure(conn,c) for c in cases]};services={'baseline':measure_service(engine,cases)};experiments={}
                    for name,ddls in CANDIDATES.items():
                        builds=[]
                        for ddl in ddls:
                            start=time.perf_counter();conn.exec_driver_sql(ddl);builds.append((time.perf_counter()-start)*1000)
                        conn.exec_driver_sql('ANALYZE');conn.commit()
                        measurements[name]=[measure(conn,c) for c in cases];services[name]=measure_service(engine,cases)
                        candidates=[i for i in base.catalog(conn) if i['name'].startswith('mod017_scores_')]
                        experiments[name]=dict(ddls=ddls,individual_build_ms=builds,indexes=candidates,total_index_bytes=sum(i['bytes'] for i in candidates))
                        for index in candidates:conn.exec_driver_sql('DROP INDEX "'+index['name']+'"')
                        conn.commit()
                    sizes={t:conn.exec_driver_sql(f'SELECT pg_total_relation_size(\'"{t}"\')').scalar_one() for t in ['WeeklyTeamScore','Week','LeagueMember']}
                    return dict(tier=n,fixture=facts,settings=settings,baseline_indexes=indexes,experiments=experiments,measurements=measurements,service_measurements=services,relation_bytes=sizes)
            finally:engine.dispose()
    finally:
        if record is not None:verify_cleanup(admin,record)


def run(directory,manifest,tiers,connect=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);run_id=uuid4().hex;artifact=directory/f'mod-017-scores-{run_id}.json'
    inputs=[base.BASELINE,*base.MIGRATIONS,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_transactions.py','scripts/modernization/measure_mod017_scores.py','api/endpoints/scoring/repository.py','api/endpoints/scoring/service.py']
    report=dict(date='2026-11-15',run_id=run_id,started_at=datetime.now(timezone.utc).isoformat(),result='RUNNING',scope='Synthetic stored-score query/job-read measurements only; optimization deferred',tiers=[],databases=[],cleanup='no database created',provenance={},limits=['Eight members/league,12scoredweeks; one unscored target member,unique ranks,not production estimates','Unordered results normalized only for evidence; Decimal SUM(bigint) serialized as string','Prior schema/RLS/cache/writecost/concurrency/provider limits remain; no rollout or SQL rewrite'])
    def persist():
        save_json(artifact,report);save_json(Path(manifest),dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist();admin=None
    try:
        report['provenance']={p:hashlib.sha256((base.ROOT/p).read_bytes()).hexdigest() for p in inputs}
        admin=connect() if connect else psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        for n in tiers:
            print(f'MOD017 scores tier {n}: starting',flush=True);report['tiers'].append(run_tier(admin,n,report));persist();print(f'MOD017 scores tier {n}: PASS',flush=True)
        if len(report['databases'])!=len(tiers) or any(r['cleanup']!='removed' for r in report['databases']):raise RuntimeError('Owned cleanup not verified')
        report['cleanup']='verified';report['result']='PASS';return report
    except BaseException as error:
        report['result']='FAILED';report['error_type']=type(error).__name__
        if report['databases']:report['cleanup']='verified' if all(r['cleanup']=='removed' for r in report['databases']) else 'incomplete or unverified'
        raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();persist()
        if admin is not None:admin.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tier',type=int,choices=base.SIZES,action='append');args=parser.parse_args()
    directory=base.ROOT/'docs/modernization/evidence';run(directory,directory/'mod-017-scores-current-2026-11-15.json',args.tier or base.SIZES)
if __name__=='__main__':main()
