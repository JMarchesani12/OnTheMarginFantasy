"""Scoped own-list aggregation: exact results and native plans on owned localhost."""
from datetime import datetime,timezone
import hashlib,json,subprocess,time,types
from pathlib import Path
from uuid import uuid4
import psycopg2
from sqlalchemy import create_engine,text
import measure_mod017 as base
from measure_mod017_transactions import save_json,verify_cleanup
from endpoints.league.reads.repository import LeagueReadRepository

REFERENCE='7d6cde8467d490dc9a94c6f434acb10ac761d9da'
REFERENCE_HASH='509efe07fd1c05916b7a775abe7ef378a5c95e622db96e2af23e53c373165df4'


def assert_results(old,new):
    # SQL promises only these ORDER BY keys. Retain every row but compare the
    # multiset within equal-key groups; no new tie-breaking policy is introduced.
    key=lambda r:(r['leagueId'],r['draftOrder'])
    if [key(r) for r in old]!=[key(r) for r in new]:raise AssertionError('Ordered own-list key sequence changed')
    canonical=lambda rows:sorted(rows,key=lambda r:(key(r),json.dumps(r,default=str,sort_keys=True)))
    left,right=canonical(old),canonical(new)
    if left!=right or any(type(v) is not type(b[k]) for a,b in zip(left,right) for k,v in a.items()):raise AssertionError('Own-list fields/types/multiplicity changed')


def capture(repo,user,stage,scope):
    class Capture:
        def execute(self,statement,params):self.statement=statement;self.params=params;return []
    c=Capture();repo.own_leagues(c,user,stage,scope)
    return c if hasattr(c,'statement') else None


def nodes(plan):
    yield plan
    for child in plan.get('Plans',[]):yield from nodes(child)


def plan_for(conn,query):
    compiled=query.statement.params(**query.params).compile(dialect=conn.dialect,compile_kwargs={'render_postcompile':True})
    plan=conn.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+str(compiled),compiled.params).scalar_one()[0]
    aggregates=[];scans=[]
    for node in nodes(plan['Plan']):
        if node['Node Type'] in ('Aggregate','Group') and any('wts.' in key for key in node.get('Group Key',[])):
            aggregates.append(dict(mode=node.get('Partial Mode'),rows=node.get('Actual Rows',0),loops=node.get('Actual Loops',0),input_rows=sum(c.get('Actual Rows',0)*c.get('Actual Loops',0) for c in node.get('Plans',[]))))
        if node.get('Relation Name')=='WeeklyTeamScore':scans.append({k:node[k] for k in ('Node Type','Index Name','Actual Rows','Actual Loops','Rows Removed by Filter','Shared Hit Blocks','Shared Read Blocks') if k in node})
    return dict(plan=plan,score_aggregates=aggregates,score_scans=scans,sql=str(compiled),params=compiled.params)


def semantic_checks(engine,Legacy):
    from verify_league_details import FIXTURE
    with engine.begin() as conn:
        conn.exec_driver_sql(FIXTURE)
        conn.exec_driver_sql('''UPDATE "WeeklyTeamScore" SET "pointsAwarded"=-6 WHERE "memberId"=12 AND "weekId"=101;
        INSERT INTO "WeeklyTeamScore" VALUES (10,11,101,NULL);
        UPDATE "LeagueMember" SET "seasonPoints"=NULL WHERE id=21;''')
    records=[]
    with engine.begin() as conn:
        for user in (1,2,3):
            for stage in ('all','active','completed','unknown'):
                for scope in (None,[],[10],[20],[30],[10,20]):
                    old=Legacy().own_leagues(conn,user,stage,scope);new=LeagueReadRepository().own_leagues(conn,user,stage,scope);assert_results(old,new)
                    for row in new:
                        assert row['seasonPoints']==(10 if row['memberId']==11 else 0)
                        if row['leagueId']==20:assert row['currentWeekId'] is None
                    records.append(dict(user=user,stage=stage,scope=scope,rows=len(new),old_observed=base.signature(old),new_observed=base.signature(new)))
        # Exact legacy Week-id-only join behavior: a foreign Week contributes.
        conn.exec_driver_sql('INSERT INTO "Week" VALUES (999,20,0,NULL,NULL); INSERT INTO "WeeklyTeamScore" VALUES (10,12,999,7)')
        old=Legacy().own_leagues(conn,2,'all');new=LeagueReadRepository().own_leagues(conn,2,'all');assert_results(old,new)
        assert all(r['seasonPoints']==7 for r in new if r['memberId']==12)
        return dict(cases=records,foreign_week_join_preserved=True,zero_null_fallbacks=True,overlapping_current_weeks=True,scope='Dedicated minimal legacy SQL fixture; baseline integrity/performance fixtures are separate')


def wanted_leagues(n,user,stage,scope):
    ids=list(range(1,n+1)) if user==1 else [1] if user==2 else []
    return [i for i in ids if (stage!='active' or i%3!=0) and (stage!='completed' or i%3==0) and (scope is None or i in scope)]


def measure(engine,n,Legacy):
    cases=[(f'{name}_{stage}',user,stage,None) for name,user in [('hot',1),('sparse',2),('absent',7*n+9999)] for stage in ('all','active','completed')]
    cases += [('hot_supplied',1,'all',list(range(1,n+1))),('sparse_supplied',2,'all',[1]),('sparse_miss_scope',2,'all',[2]),('empty_scope',1,'all',[])]
    records=[]
    with engine.connect() as conn:
        for name,user,stage,scope in cases:
            samples={'old':[],'new':[]};repos={'old':Legacy(),'new':LeagueReadRepository()};result={}
            for iteration in range(6):
                for variant in (('old','new') if iteration%2==0 else ('new','old')):
                    start=time.perf_counter();result[variant]=repos[variant].own_leagues(conn,user,stage,scope);elapsed=(time.perf_counter()-start)*1000
                    if iteration:samples[variant].append(elapsed)
                assert_results(result['old'],result['new'])
                assert [r['leagueId'] for r in result['new']]==wanted_leagues(n,user,stage,scope)
            plans={}
            for variant,repo in repos.items():
                query=capture(repo,user,stage,scope)
                plans[variant]=plan_for(conn,query) if query else dict(no_sql=True)
            eligible_rows=12*len(wanted_leagues(n,user,stage,scope))
            if scope!=[]:
                raw=[a for a in plans['new']['score_aggregates'] if a['mode']!='Finalize']
                if not raw:raise AssertionError('Unable to identify scoped score aggregation')
                actual=sum(a['input_rows'] for a in raw)
                if abs(actual-eligible_rows)>sum(max(1,a['loops']) for a in raw):raise AssertionError(('Aggregation input differs from eligible scores',name,actual,eligible_rows))
            records.append(dict(name=name,user=user,stage=stage,scope_count=None if scope is None else len(scope),rows=len(result['new']),result=base.signature(result['new']),eligible_score_rows=eligible_rows,samples_ms=samples,median_ms={k:base.statistics.median(v) for k,v in samples.items()},plans=plans))
        conn.rollback()
    return records


def run(directory=None,tiers=(100,1000,5000),connect=None):
    directory=Path(directory or base.ROOT/'docs/modernization/evidence');directory.mkdir(parents=True,exist_ok=True);run_id=uuid4().hex;artifact=directory/f'mod-017-own-scope-{run_id}.json';manifest=directory/'mod-017-own-scope-current-2026-11-16.json'
    report=dict(run_id=run_id,result='RUNNING',started_at=datetime.now(timezone.utc).isoformat(),provenance={},databases=[],tiers=[],cleanup='no database created')
    def persist():save_json(artifact,report);save_json(manifest,dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist();admin=None
    try:
        source=subprocess.check_output(['git','show',REFERENCE+':api/endpoints/league/reads/repository.py'],cwd=base.ROOT)
        assert hashlib.sha256(source).hexdigest()==REFERENCE_HASH
        module=types.ModuleType('pre_scope_repository');exec(compile(source,'pre-scope-repository','exec'),module.__dict__)
        report['reference']=dict(revision=REFERENCE,sha256=REFERENCE_HASH)
        files=[base.BASELINE,*base.MIGRATIONS,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_transactions.py','scripts/modernization/verify_mod017_own_score_scope.py','scripts/modernization/verify_league_details.py','api/endpoints/league/reads/repository.py','api/endpoints/league/reads/service.py','api/endpoints/league/lifecycle/query_service.py','api/utils/conference_membership.py']
        report['provenance']={f:hashlib.sha256((base.ROOT/f).read_bytes()).hexdigest() for f in files}
        admin=connect() if connect else psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        for n in tiers:
            print('Own-score scope tier',n,'starting',flush=True)
            record=None
            try:
                with base.owned_database(admin) as name:
                    record=dict(name=name,cleanup='pending');report['databases'].append(record);persist()
                    engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=name,**base.LOCAL))
                    try:
                        with engine.connect() as conn:
                            base.schema(conn);facts=base.seed(conn,n);conn.exec_driver_sql('ANALYZE');conn.commit()
                            settings={k:conn.exec_driver_sql('SHOW '+k).scalar_one() for k in ['server_version','TimeZone','shared_buffers','work_mem','max_parallel_workers_per_gather','jit','statement_timeout','lock_timeout']};conn.commit()
                        report['tiers'].append(dict(leagues=n,fixture=facts,settings=settings,measurements=measure(engine,n,module.LeagueReadRepository)))
                        if n==tiers[0]:report['semantics']=semantic_checks(engine,module.LeagueReadRepository)
                    finally:engine.dispose()
            finally:
                if record:verify_cleanup(admin,record);persist()
            print('Own-score scope tier',n,'PASS',flush=True)
        assert report['databases'] and all(r['cleanup']=='removed' for r in report['databases']);report['cleanup']='verified';report['result']='PASS';return report
    except BaseException as error:
        report['result']='FAILED';report['error_type']=type(error).__name__;report['error']=str(error)
        if report['databases']:report['cleanup']='verified' if all(r['cleanup']=='removed' for r in report['databases']) else 'unverified'
        raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();persist()
        if admin is not None:admin.close()
        print(artifact.name,report['result'],report['cleanup'],flush=True)
if __name__=='__main__':run()
