"""Audit-only head-to-head plans on marked localhost; no scoring/optimization change."""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib,time
from pathlib import Path
from uuid import uuid4
import psycopg2
from sqlalchemy import create_engine,text
import measure_mod017 as base
import measure_mod017_games as games
from measure_mod017_transactions import Capture,validate_result,verify_cleanup,save_json
from endpoints.schedule.read_repository import ScheduleReadRepository
from endpoints.schedule.read_service import ScheduleReadService

GAME='CREATE INDEX mod017_h2h_game ON "GameResult" ("sportSeasonId",date,"externalGameId")'
OWNER='CREATE INDEX mod017_h2h_owner ON "LeagueTeamSlot" ("leagueId","memberId","sportTeamId") INCLUDE ("acquiredWeek","droppedWeek")'
CANDIDATES={'game_date':[GAME],'ownership':[OWNER],'combined':[GAME,OWNER]}


def game_values(i,anchor):
    home=1+(i-1)%512
    if i<=10:home=1 if i%2 else 5
    away=((home-1)//8)*8+1+(home-1+4)%8
    date=anchor+timedelta(days=i%91-77)
    offsets=[-50,-43,-50,-43,-43,-22,-22,-1,6,6]
    if i<=10:
        date=anchor+timedelta(days=offsets[i-1])
        if i==3:date-=timedelta(microseconds=1)
        if i in [4,10]:date+=timedelta(microseconds=1)
    return home,away,date


def owned(member,league,week,n):
    if league!=n//2+1 or member is None:return set()
    position=member-(league-1)*8
    if not 1<=position<=8:return set()
    teams=set(range((position-1)*4+1,position*4+1))
    if 7<=week<10:
        if position==1:teams.remove(1)
        if position==3:teams.add(1)
    return teams


def expected_rows(n,anchor,params):
    league=params['leagueId'];week=params['weekNumber']
    if league!=n//2+1 or not 1<=week<=13:return []
    a=owned(params['memberA'],league,week,n);b=owned(params['memberB'],league,week,n)
    clock=datetime.fromisoformat(anchor);start=clock+timedelta(days=(week-13)*7-1);end=clock+timedelta(days=(week-13)*7+6)
    rows=[]
    for i in range(1,games.game_facts(n)['games_per_season']+1):
        home,away,date=game_values(i,clock)
        if start<=date<=end and ((home in a and away in b) or (home in b and away in a)):
            rows.append(dict(id=i,externalGameId=f'season-2026-game-{i:06d}',date=date,timeTBD=i%20==0,homeTeamId=home,awayTeamId=away,homeTeamName=f'Sport team {home}',awayTeamName=f'Sport team {away}',homeScore=i%45,awayScore=i%40,homeOwnedByA=home in a,awayOwnedByA=away in a,homeOwnedByB=home in b,awayOwnedByB=away in b))
    return sorted(rows,key=lambda r:(r['date'],r['externalGameId']))


def capture_queries(n,anchor):
    league=n//2+1;a=(league-1)*8+1;b=a+1;c=a+2;repo=ScheduleReadRepository();cases=[]
    for name,lid,week,ma,mb in [('current',league,13,a,b),('swapped',league,13,b,a),('current_ac',league,13,a,c),('before',league,6,a,b),('acquired',league,7,a,b),('during',league,9,c,b),('returned',league,10,a,b),('unknown',league,13,a,99999999),('missing_week',league,99,a,b),('missing_league',n+100,13,a,b),('same_member',league,13,a,a)]:
        params=dict(leagueId=lid,weekNumber=week,memberA=ma,memberB=mb);capture=Capture();repo.head_to_head_games(capture,params);expected=expected_rows(n,anchor,params)
        cases.append(dict(name=name,family='head_to_head',expected_rows=len(expected),expected_values=expected,sql=capture.statement,params=capture.params))
    return cases


def seed_head_to_head(conn,n,anchor):
    facts=games.seed_games(conn,n,anchor);count=facts['games_per_season'];league=n//2+1;member_c=(league-1)*8+3
    # Arithmetic fixture construction, separately enumerated by expected_rows.
    conn.execute(text(f'''WITH pairs AS (
      SELECT id,1+(id-1)%{count} AS i FROM "GameResult"
    ), homes AS (
      SELECT id,i,CASE WHEN i<=10 THEN CASE WHEN i%2=1 THEN 1 ELSE 5 END ELSE 1+(i-1)%512 END AS home FROM pairs
    ), opponents AS (
      SELECT id,home,((home-1)/8)*8+1+(home-1+4)%8 AS away FROM homes
    ) UPDATE "GameResult" gr SET "homeTeamId"=p.home,"awayTeamId"=p.away,
      "homeTeamName"='Sport team '||p.home,"awayTeamName"='Sport team '||p.away,
      "homeTeamExternalId"=p.home,"awayTeamExternalId"=p.away FROM opponents p WHERE gr.id=p.id'''))
    clock=datetime.fromisoformat(anchor)
    # Deliberate endpoint fixture values independent of application SQL.
    for i,days,micros in [(1,-50,0),(2,-43,0),(3,-50,-1),(4,-43,1),(5,-43,0),(6,-22,0),(7,-22,0),(8,-1,0),(9,6,0),(10,6,1)]:
        conn.execute(text('UPDATE "GameResult" SET date=:date WHERE id=:id'),dict(id=i,date=clock+timedelta(days=days,microseconds=micros)))
    changed=conn.execute(text('UPDATE "LeagueTeamSlot" SET "memberId"=:member WHERE "leagueId"=:league AND "sportTeamId"=1 AND "acquiredWeek"=7 AND "droppedWeek"=10'),dict(member=member_c,league=league)).rowcount
    if changed!=1:raise AssertionError('Expected exactly one transfer interval')
    conn.commit();conn.exec_driver_sql('ANALYZE');conn.commit()
    facts.update(pairing='each eight-team block: first four versus last four, both orientations',boundary_games=10,transfer=dict(league=league,team=1,to_member=member_c,acquired=7,dropped=10),transfer_intervals_changed=changed)
    return facts


def measure(conn,case):
    result=base.measure(conn,case);validate_result(case,result);base.assert_equivalent(base.signature(case['expected_values']),result['result']);return result


def measure_service(conn,cases):
    service=ScheduleReadService(None);records=[]
    for case in cases:
        p=case['params'];samples=[];signature=None
        for iteration in range(6):
            start=time.perf_counter();rows=service.get_head_to_head_games(p['leagueId'],p['memberA'],p['memberB'],p['weekNumber'],conn=conn);elapsed=(time.perf_counter()-start)*1000
            signature=base.signature(rows);base.assert_equivalent(base.signature(case['expected_values']),signature)
            if iteration:samples.append(elapsed)
        records.append(dict(name=case['name'],result=signature,service_ms=dict(samples=samples,median=base.statistics.median(samples),min=min(samples),max=max(samples))))
    return records


def run_tier(admin,n,report):
    record=None
    try:
        with base.owned_database(admin) as database:
            record=dict(name=database,cleanup='pending');report['databases'].append(record)
            engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=database,**base.LOCAL))
            try:
                with engine.connect() as conn:
                    base.schema(conn);facts=base.seed(conn,n);facts['games']=seed_head_to_head(conn,n,facts['anchor']);cases=capture_queries(n,facts['anchor']);indexes=base.catalog(conn)
                    settings={k:conn.exec_driver_sql('SHOW '+k).scalar_one() for k in ['server_version','shared_buffers','work_mem','effective_cache_size','random_page_cost','jit','jit_above_cost','jit_inline_above_cost','jit_optimize_above_cost','max_parallel_workers_per_gather','statement_timeout','lock_timeout']}
                    measurements={'baseline':[measure(conn,c) for c in cases]};services={'baseline':measure_service(conn,cases)};experiments={}
                    for name,ddls in CANDIDATES.items():
                        builds=[]
                        for ddl in ddls:
                            start=time.perf_counter();conn.exec_driver_sql(ddl);builds.append((time.perf_counter()-start)*1000)
                        conn.exec_driver_sql('ANALYZE');conn.commit()
                        measurements[name]=[measure(conn,c) for c in cases];services[name]=measure_service(conn,cases)
                        candidates=[i for i in base.catalog(conn) if i['name'].startswith('mod017_h2h_')]
                        experiments[name]=dict(ddls=ddls,individual_build_ms=builds,indexes=candidates,total_index_bytes=sum(i['bytes'] for i in candidates))
                        for index in candidates:conn.exec_driver_sql('DROP INDEX "'+index['name']+'"')
                        conn.commit()
                    sizes={t:conn.exec_driver_sql(f'SELECT pg_total_relation_size(\'"{t}"\')').scalar_one() for t in ['GameResult','LeagueTeamSlot']}
                    return dict(tier=n,fixture=facts,settings=settings,baseline_indexes=indexes,experiments=experiments,measurements=measurements,service_measurements=services,relation_bytes=sizes)
            finally:engine.dispose()
    finally:
        if record is not None:verify_cleanup(admin,record)


def run(directory,manifest,tiers,connect=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);run_id=uuid4().hex;artifact=directory/f'mod-017-h2h-{run_id}.json'
    inputs=[base.BASELINE,*base.MIGRATIONS,games.TBD,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_transactions.py','scripts/modernization/measure_mod017_games.py','scripts/modernization/measure_mod017_h2h.py','api/endpoints/schedule/read_service.py','api/endpoints/schedule/calendar_service.py','api/endpoints/schedule/read_repository.py','api/utils/conference_membership.py']
    report=dict(date='2026-11-15',run_id=run_id,started_at=datetime.now(timezone.utc).isoformat(),result='RUNNING',scope='Synthetic head-to-head query/service measurements only; optimization deferred',tiers=[],databases=[],cleanup='no database created',provenance={},limits=['One sport,512teams,20/50/100seasons; current-season fraction5%/2%/1%,not production estimates','Eight-team block pairing,10boundarygames,one [7,10) transfer,not real sports schedule','Prior schema/RLS/cache/writecost/concurrency/provider limits remain; no rollout or SQL rewrite'])
    def persist():
        save_json(artifact,report);save_json(Path(manifest),dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist();admin=None
    try:
        report['provenance']={p:hashlib.sha256((base.ROOT/p).read_bytes()).hexdigest() for p in inputs}
        admin=connect() if connect else psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        for n in tiers:
            print(f'MOD017 h2h tier {n}: starting',flush=True);report['tiers'].append(run_tier(admin,n,report));persist();print(f'MOD017 h2h tier {n}: PASS',flush=True)
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
    directory=base.ROOT/'docs/modernization/evidence';run(directory,directory/'mod-017-h2h-current-2026-11-15.json',args.tier or base.SIZES)
if __name__=='__main__':main()
