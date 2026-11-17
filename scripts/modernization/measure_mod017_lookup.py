"""Audit-only team lookup/ranking and conference counts on marked localhost."""
import argparse
from datetime import datetime,timezone
import hashlib,json,time
from pathlib import Path
from uuid import uuid4
import psycopg2
from sqlalchemy import create_engine,text
import measure_mod017 as base
from measure_mod017_transactions import Capture,validate_result,verify_cleanup,save_json
from endpoints.schedule.read_repository import ScheduleReadRepository
from endpoints.schedule.read_service import ScheduleReadService
from utils.ownership_reads import distinct_conference_count_rows,grouped_conference_count_rows

CANDIDATES={
 'team_sport_name':'CREATE INDEX mod017_lookup_team_name ON "SportTeam" ("sportId","displayName")',
 'conference_leading':'CREATE INDEX mod017_lookup_conference ON "ConferenceMembership" ("sportConferenceId","seasonYear","sportTeamId") INCLUDE ("sportId")',
 'ownership_member':'CREATE INDEX mod017_lookup_ownership ON "LeagueTeamSlot" ("leagueId","memberId","sportTeamId") INCLUDE ("acquiredWeek","droppedWeek")',
}
def team_count(n):return {100:512,1000:2048,5000:8192}[n]
def normalize_rows(family,rows):return sorted(rows,key=lambda row:row['sportConferenceId']) if family=='group' else rows


def capture_queries(n):
    repo=ScheduleReadRepository();league=n//2+1;history=league+1;member=(league-1)*8+1;historic_member=(history-1)*8+1;cases=[]
    def add(name,family,expected,fn,values=None):
        conn=Capture();fn(conn)
        cases.append(dict(name=name,family=family,expected_rows=expected,expected_values=values,sql=conn.statement,params=conn.params))
    for name,lid,year,sport in [('current',league,2026,1),('history',history,2025,1),('missing_sport',league,2026,99999)]:
        params=dict(leagueId=lid,sport=sport,seasonYear=year,weekNumber=13)
        add('lookup_'+name,'lookup',team_count(n) if sport==1 else 0,lambda c,p=params:repo.search_teams(c,p))
    for name,lid,mid,conf,value in [('current_one',league,member,1,3),('current_two',league,member,2,1),('history_one',history,historic_member,1,4),('unknown_member',league,99999999,1,0),('missing_league',n+100,member,1,0)]:
        add('distinct_'+name,'distinct',1,lambda c,l=lid,m=mid,f=conf:distinct_conference_count_rows(c,l,m,13,f),[{'cnt':value}])
    for name,lid,mid,values in [('current',league,member,[{'sportConferenceId':1,'cnt':3},{'sportConferenceId':2,'cnt':1}]),('history',history,historic_member,[{'sportConferenceId':1,'cnt':4}]),('null',league,None,[]),('unknown',league,99999999,[])]:
        add('group_'+name,'group',len(values),lambda c,l=lid,m=mid:grouped_conference_count_rows(c,l,m,13),values)
    return cases


def seed_lookup(conn,n):
    teams=team_count(n);conferences=teams//16;history=n//2+2
    statements=[
      "INSERT INTO \"Sport\" (id,name) VALUES (2,'Synthetic other')",
      f"INSERT INTO \"School\" (id,name) SELECT i,'School '||i FROM generate_series(33,{teams+32}) i",
      f'''INSERT INTO "SportTeam" (id,"schoolId","sportId","displayName") SELECT i,i,CASE WHEN i<={teams} THEN 1 ELSE 2 END,'Sport team '||lpad(i::text,5,'0') FROM generate_series(33,{teams+32}) i''',
      '''UPDATE "SportTeam" SET "displayName"='Sport team '||lpad(id::text,5,'0')''',
      '''UPDATE "SportTeam" st SET "displayName"=v.name FROM (VALUES (1,'Iowa State'),(2,'Duke'),(3,'State University')) v(id,name) WHERE st.id=v.id''',
      f"INSERT INTO \"Conference\" (id,name) SELECT i,'Conference '||i FROM generate_series(1,{conferences+2}) i",
      f'''INSERT INTO "SportConference" (id,"conferenceId","sportId","maxTeamsPerOwner") SELECT i,i,CASE WHEN i<={conferences} THEN 1 ELSE 2 END,4 FROM generate_series(1,{conferences+2}) i''',
      f'''INSERT INTO "ConferenceMembership" ("sportTeamId","sportConferenceId","sportId","seasonYear") SELECT i,1+(i-1)/16,CASE WHEN i<={teams} THEN 1 ELSE 2 END,NULL FROM generate_series(1,{teams+32}) i''',
      'INSERT INTO "ConferenceMembership" ("sportTeamId","sportConferenceId","sportId","seasonYear") VALUES (1,2,1,2026)',
      f'''UPDATE "League" SET "seasonYear"=2025 WHERE id={history}''',
      f'''UPDATE "Week" SET "startDate"="startDate"-interval '1 year',"endDate"="endDate"-interval '1 year' WHERE "leagueId"={history}''',
    ]
    for statement in statements:conn.execute(text(statement))
    conn.commit();conn.exec_driver_sql('ANALYZE');conn.commit()
    observed={t:conn.exec_driver_sql(f'SELECT count(*) FROM "{t}"').scalar_one() for t in ['SportTeam','ConferenceMembership']}
    if observed!={'SportTeam':teams+32,'ConferenceMembership':teams+33}:raise AssertionError('Lookup fixture count mismatch')
    return dict(teams_in_sport=teams,other_sport_teams=32,historical_league=history,observed=observed,history_owner_ids_unchanged=True)


def verify_lookup(rows,params,n):
    if params['sport']!=1:return
    by_id={row['teamId']:row for row in rows}
    if len(by_id)!=team_count(n):raise AssertionError('Duplicate/missing lookup teams')
    one=by_id[1];expected_conf='Conference 2' if params['seasonYear']==2026 else 'Conference 1'
    if one['conferenceName']!=expected_conf or one['ownerMemberId']!=(params['leagueId']-1)*8+1:raise AssertionError('Lookup conference/owner context changed')
    if one['ownerTeamName']!='Team 1' or one['ownerDisplayName']!='User 1':raise AssertionError('Lookup owner label changed')
    if by_id[team_count(n)]['ownerMemberId'] is not None:raise AssertionError('Unowned lookup team gained an owner')


def measure(conn,case,n):
    statement=text(case['sql']);params=case['params'];conn.execute(statement,params).fetchall()
    plan=conn.execute(text('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+case['sql']),params).scalar_one()[0]
    samples=[];signature=None;raw_order=None
    for _ in range(5):
        start=time.perf_counter();rows=[dict(r) for r in conn.execute(statement,params).mappings().all()];elapsed=(time.perf_counter()-start)*1000
        raw_order=[r.get('sportConferenceId') for r in rows] if case['family']=='group' else None
        if case['family']=='lookup':verify_lookup(rows,params,n)
        current=base.signature(normalize_rows(case['family'],rows))
        if signature is not None:base.assert_equivalent(signature,current)
        signature=current;samples.append(elapsed)
    result=dict(**case,result=signature,observed_group_order=raw_order,client_execute_fetch_ms=dict(samples=samples,median=base.statistics.median(samples),min=min(samples),max=max(samples)),plan=plan)
    validate_result(case,result)
    if case['expected_values'] is not None:base.assert_equivalent(base.signature(case['expected_values']),signature)
    return result


class Buffered:
    def __init__(self,rows):self.rows=rows
    def fetchall(self):return self.rows
    def fetchone(self):return self.rows[0] if self.rows else None

class TrackingRepository(ScheduleReadRepository):
    def __init__(self):self.stats=dict(queries=0,fetched_rows=0,fetched_bytes=0,db_execute_fetch_ms=0)
    def search_league_context(self,conn,params):
        start=time.perf_counter();rows=super().search_league_context(conn,params).fetchall();self.stats['db_execute_fetch_ms']+=(time.perf_counter()-start)*1000;self.stats['queries']+=1;return Buffered(rows)
    def search_teams(self,conn,params):
        start=time.perf_counter();rows=super().search_teams(conn,params).fetchall();self.stats['db_execute_fetch_ms']+=(time.perf_counter()-start)*1000;self.stats['queries']+=1
        self.stats['fetched_rows']=len(rows);self.fetched_data=rows;return Buffered(rows)


def measure_service(engine,n):
    league=n//2+1;cases=[('alias',league,'iowa st',[1]),('exact',league,'du',[2]),('abbreviation',league,'univ',[3]),('prefix',league,'sport team',list(range(4,24))),('miss',league,'zzzz',[]),('short',league,'i',[]),('history',league+1,'iowa st',[1])];records=[]
    for name,lid,query,expected in cases:
        samples=[];stats=[];signature=None
        for iteration in range(6):
            repo=TrackingRepository();service=ScheduleReadService(engine,repository=repo)
            start=time.perf_counter();rows=service.search_teams_for_league(lid,query,20);elapsed=(time.perf_counter()-start)*1000
            repo.stats['fetched_bytes']=len(base.canonical([dict(r._mapping) for r in getattr(repo,'fetched_data',[])]))
            if [r['teamId'] for r in rows]!=expected:raise AssertionError('Search rank/limit changed')
            if repo.stats['queries']!=(0 if name=='short' else 2) or repo.stats['fetched_rows']!=(0 if name=='short' else team_count(n)):raise AssertionError('Lookup query/fetch count changed')
            if name in ['alias','history'] and rows[0]['conferenceName']!=('Conference 1' if name=='history' else 'Conference 2'):raise AssertionError('Service conference label changed')
            current=base.signature(rows)
            if signature is not None:base.assert_equivalent(signature,current)
            signature=current
            if iteration:samples.append(elapsed);stats.append(repo.stats)
        records.append(dict(name=name,league_id=lid,query=query,expected_ids=expected,result=signature,service_ms=dict(samples=samples,median=base.statistics.median(samples),min=min(samples),max=max(samples)),retrieval_samples=stats))
    return records


def run_tier(admin,n,report):
    record=None
    try:
        with base.owned_database(admin) as database:
            record=dict(name=database,cleanup='pending');report['databases'].append(record)
            engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=database,**base.LOCAL))
            try:
                with engine.connect() as conn:
                    base.schema(conn);facts=base.seed(conn,n);facts['lookup']=seed_lookup(conn,n);cases=capture_queries(n);indexes=base.catalog(conn)
                    settings={k:conn.exec_driver_sql('SHOW '+k).scalar_one() for k in ['server_version','shared_buffers','work_mem','effective_cache_size','random_page_cost','jit','jit_above_cost','max_parallel_workers_per_gather','statement_timeout','lock_timeout']}
                    measurements={'baseline':[measure(conn,c,n) for c in cases]};fingerprints={r['name']:r['result'] for r in measurements['baseline']};conn.commit()
                    services={'baseline':measure_service(engine,n)};service_fingerprints={r['name']:r['result'] for r in services['baseline']};experiments={}
                    for name,ddl in CANDIDATES.items():
                        start=time.perf_counter();conn.exec_driver_sql(ddl);build=(time.perf_counter()-start)*1000;conn.exec_driver_sql('ANALYZE');conn.commit()
                        chosen=[c for c in cases if c['family']=='lookup'] if name=='team_sport_name' else cases
                        measurements[name]=[measure(conn,c,n) for c in chosen]
                        for result in measurements[name]:base.assert_equivalent(fingerprints[result['name']],result['result'])
                        conn.commit();services[name]=measure_service(engine,n)
                        for result in services[name]:base.assert_equivalent(service_fingerprints[result['name']],result['result'])
                        index=next(i for i in base.catalog(conn) if i['name']=={'team_sport_name':'mod017_lookup_team_name','conference_leading':'mod017_lookup_conference','ownership_member':'mod017_lookup_ownership'}[name]);experiments[name]=dict(ddl=ddl,build_ms=build,index=index)
                        conn.exec_driver_sql('DROP INDEX "'+index['name']+'"');conn.commit()
                    sizes={t:conn.exec_driver_sql(f'SELECT pg_total_relation_size(\'"{t}"\')').scalar_one() for t in ['SportTeam','ConferenceMembership','LeagueTeamSlot']}
                    return dict(tier=n,fixture=facts,settings=settings,baseline_indexes=indexes,experiments=experiments,measurements=measurements,service_measurements=services,relation_bytes=sizes)
            finally:engine.dispose()
    finally:
        if record is not None:verify_cleanup(admin,record)


def run(directory,manifest,tiers,connect=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);run_id=uuid4().hex;artifact=directory/f'mod-017-lookup-{run_id}.json'
    inputs=[base.BASELINE,*base.MIGRATIONS,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_transactions.py','scripts/modernization/measure_mod017_lookup.py','api/endpoints/schedule/read_repository.py','api/endpoints/schedule/read_service.py','api/utils/ownership_reads.py','api/utils/conference_membership.py']
    report=dict(date='2026-11-13',run_id=run_id,started_at=datetime.now(timezone.utc).isoformat(),result='RUNNING',scope='Synthetic team lookup/count/ranking measurements only; optimization deferred',tiers=[],databases=[],cleanup='no database created',provenance={},limits=['512/2048/8192 sport1teams plus32foreignsportteams,not production estimates','Unique names,one seasonal move,unchanged owner across history; no ties/transfer/skew claim','Prior schema/RLS/cache/writecost/concurrency/provider limits remain; no rollout or SQL rewrite'])
    def persist():
        save_json(artifact,report);save_json(Path(manifest),dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist();admin=None
    try:
        report['provenance']={p:hashlib.sha256((base.ROOT/p).read_bytes()).hexdigest() for p in inputs}
        admin=connect() if connect else psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        for n in tiers:
            print(f'MOD017 lookup tier {n}: starting',flush=True);report['tiers'].append(run_tier(admin,n,report));persist();print(f'MOD017 lookup tier {n}: PASS',flush=True)
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
    directory=base.ROOT/'docs/modernization/evidence';run(directory,directory/'mod-017-lookup-current-2026-11-13.json',args.tier or base.SIZES)
if __name__=='__main__':main()
