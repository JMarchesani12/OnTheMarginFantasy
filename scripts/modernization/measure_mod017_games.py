"""Synthetic game/schedule plans, fixed marked localhost; no application changes."""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4
import psycopg2
from sqlalchemy import create_engine,text
import measure_mod017 as base
from measure_mod017_transactions import Capture,validate_result,verify_cleanup,save_json
from endpoints.schedule.read_repository import ScheduleReadRepository

TBD='api/migrations/20261030_game_kickoff_tbd.sql'
CANDIDATES={
 'game_season_date':['CREATE INDEX mod017_game_season_date ON "GameResult" ("sportSeasonId",date,"externalGameId")'],
 'game_home_away':['CREATE INDEX mod017_game_home ON "GameResult" ("sportSeasonId","homeTeamId",date,"externalGameId")','CREATE INDEX mod017_game_away ON "GameResult" ("sportSeasonId","awayTeamId",date,"externalGameId")'],
}

def game_facts(n):
    seasons,games_per_season={100:(20,500),1000:(50,2000),5000:(100,5000)}[n]
    return dict(seasons=seasons,games_per_season=games_per_season,games=seasons*games_per_season,teams=512,default_conferences=32,current_season=2026)


def expected_games(count,teams,window=None):
    total=0
    for i in range(1,count+1):
        home=(i-1)%512+1;away=(home+255)%512+1
        offset=0 if i==1 else i%91-77
        if (home in teams or away in teams) and (window is None or window[0]<=offset<=window[1]):total+=1
    return total


def conference_teams(conference,season):
    if not 1<=conference<=32:return set()
    teams=set(range((conference-1)*16+1,conference*16+1))
    if season==2026:
        if conference==1:teams.discard(1)
        if conference==2:teams.add(1)
    return teams


def capture_queries(n,anchor):
    repo=ScheduleReadRepository();facts=game_facts(n);count=facts['games_per_season'];league=n//2+1;member=(league-1)*8+1
    clock=datetime.fromisoformat(anchor);cases=[]
    def add(name,params,expected,method):
        conn=Capture();method(conn,params)
        cases.append(dict(name=name,family='games',expected_rows=expected,sql=conn.statement,params=params))
    for name,week,owner in [('current',13,member),('history',2,member),('unknown',13,99999999),('missing_week',99,member)]:
        window=((week-13)*7-1,(week-13)*7+6)
        expected=0 if name in ['unknown','missing_week'] else expected_games(count,{1,2,3,4},window)
        add('member_'+name,dict(leagueId=league,weekNumber=week,memberId=owner),expected,repo.member_games)
    for name,team,year,lid in [('current_owner',1,2026,league),('current_no_owner',1,2026,None),('past_season',1,2025,None),('unknown',99999,2026,league),('missing_season',1,1800,league)]:
        expected=expected_games(count,{team}) if year in [2026,2025] and team<=512 else 0
        add('team_'+name,dict(sportTeamId=team,seasonYear=year,leagueId=lid,weekNumber=13),expected,repo.team_season_games)
    for name,conference in [('one',1),('two',2),('missing',99999)]:
        params=dict(sportConferenceId=conference,seasonYear=2026,leagueId=league,weekNumber=13,weekStart=clock-timedelta(days=1),weekEnd=clock+timedelta(days=6))
        add('conference_'+name,params,expected_games(count,conference_teams(conference,2026),(-1,6)),repo.conference_games)
    return cases


def seed_games(conn,n,anchor):
    facts=game_facts(n)
    conn.exec_driver_sql((base.ROOT/TBD).read_text());conn.commit()
    statements=[
      "INSERT INTO \"School\" (id,name) SELECT i,'School '||i FROM generate_series(33,512) i",
      "INSERT INTO \"SportTeam\" (id,\"schoolId\",\"sportId\",\"displayName\") SELECT i,i,1,'Sport team '||i FROM generate_series(33,512) i",
      "INSERT INTO \"Conference\" (id,name) SELECT i,'Conference '||i FROM generate_series(1,32) i",
      'INSERT INTO "SportConference" (id,"conferenceId","sportId","maxTeamsPerOwner") SELECT i,i,1,4 FROM generate_series(1,32) i',
      'INSERT INTO "ConferenceMembership" ("sportTeamId","sportConferenceId","sportId","seasonYear") SELECT i,1+(i-1)/16,1,NULL FROM generate_series(1,512) i',
      'INSERT INTO "ConferenceMembership" ("sportTeamId","sportConferenceId","sportId","seasonYear") VALUES (1,2,1,2026)',
      f'''INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") SELECT 2027-s,1,2027-s,make_date(2027-s,1,1),make_date(2027-s,12,31) FROM generate_series(1,{facts['seasons']}) s''',
      f'''INSERT INTO "GameResult" (id,sport,"externalGameId",date,"homeTeamId","awayTeamId","homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName","sportSeasonId","timeTBD")
       SELECT (s-1)*{facts['games_per_season']}+i,1,'season-'||(2027-s)||'-game-'||lpad(i::text,6,'0'),
       CAST(:anchor AS timestamptz)-(s-1)*interval '1 year'+CASE WHEN i=1 THEN 0 ELSE i%91-77 END*interval '1 day',
       1+(i-1)%512,1+((i-1)%512+256)%512,i%45,i%40,1+(i-1)%512,1+((i-1)%512+256)%512,
       'Sport team '||(1+(i-1)%512),'Sport team '||(1+((i-1)%512+256)%512),2027-s,(i%20=0)
       FROM generate_series(1,{facts['seasons']}) s CROSS JOIN generate_series(1,{facts['games_per_season']}) i''',
    ]
    for statement in statements:conn.execute(text(statement),{'anchor':anchor})
    conn.commit();conn.exec_driver_sql('ANALYZE');conn.commit()
    observed={table:conn.exec_driver_sql(f'SELECT count(*) FROM "{table}"').scalar_one() for table in ['GameResult','SportTeam','SportSeason','ConferenceMembership']}
    if observed!={'GameResult':facts['games'],'SportTeam':512,'SportSeason':facts['seasons'],'ConferenceMembership':513}:raise AssertionError('Game fixture counts mismatch')
    facts['observed_counts']=observed;facts['anchor_game_exercises_moved_team']=True
    return facts


def measure(conn,case):
    result=base.measure(conn,case);validate_result(case,result);return result


def run_tier(admin,n,report):
    record=None
    try:
        with base.owned_database(admin) as database:
            record=dict(name=database,cleanup='pending');report['databases'].append(record)
            engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=database,**base.LOCAL))
            try:
                with engine.connect() as conn:
                    base.schema(conn);facts=base.seed(conn,n);facts['games']=seed_games(conn,n,facts['anchor'])
                    cases=capture_queries(n,facts['anchor']);indexes=base.catalog(conn)
                    settings={k:conn.exec_driver_sql('SHOW '+k).scalar_one() for k in ['server_version','shared_buffers','work_mem','effective_cache_size','random_page_cost','seq_page_cost','jit','jit_above_cost','jit_inline_above_cost','jit_optimize_above_cost','max_parallel_workers_per_gather','statement_timeout','lock_timeout']}
                    measurements={'baseline':[measure(conn,c) for c in cases]};fingerprints={r['name']:r['result'] for r in measurements['baseline']};experiments={}
                    for name,ddls in CANDIDATES.items():
                        builds=[]
                        for ddl in ddls:
                            start=time.perf_counter();conn.exec_driver_sql(ddl);builds.append((time.perf_counter()-start)*1000)
                        conn.exec_driver_sql('ANALYZE');conn.commit()
                        measurements[name]=[measure(conn,c) for c in cases]
                        for result in measurements[name]:base.assert_equivalent(fingerprints[result['name']],result['result'])
                        candidates=[i for i in base.catalog(conn) if i['name'].startswith('mod017_game_')]
                        experiments[name]=dict(ddls=ddls,individual_build_ms=builds,indexes=candidates,total_index_bytes=sum(i['bytes'] for i in candidates))
                        for index in candidates:conn.exec_driver_sql('DROP INDEX "'+index['name']+'"')
                        conn.commit()
                    sizes={table:conn.exec_driver_sql(f'SELECT pg_total_relation_size(\'"{table}"\')').scalar_one() for table in ['GameResult','SportTeam','ConferenceMembership','LeagueTeamSlot']}
                    return dict(tier=n,fixture=facts,settings=settings,baseline_indexes=indexes,experiments=experiments,measurements=measurements,relation_bytes=sizes)
            finally:engine.dispose()
    finally:
        if record is not None:verify_cleanup(admin,record)


def run(directory,manifest,tiers,connect=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);run_id=uuid4().hex;artifact=directory/f'mod-017-games-{run_id}.json'
    inputs=[base.BASELINE,*base.MIGRATIONS,TBD,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_transactions.py','scripts/modernization/measure_mod017_games.py','api/endpoints/schedule/read_repository.py','api/utils/conference_membership.py']
    report=dict(date='2026-11-13',run_id=run_id,started_at=datetime.now(timezone.utc).isoformat(),result='RUNNING',scope='Synthetic game/schedule measurements only; optimization deferred',tiers=[],databases=[],cleanup='no database created',provenance={},limits=['One sport,512teams,20/50/100seasons; current-season fraction5%/2%/1%,not production estimates','Deterministic pair/date distribution plus one anchor game,not real sports schedule','Prior schema/RLS/cache/writecost/concurrency/provider limits remain; no rollout or SQL rewrite'])
    def persist():
        save_json(artifact,report);save_json(Path(manifest),dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist();admin=None
    try:
        report['provenance']={p:hashlib.sha256((base.ROOT/p).read_bytes()).hexdigest() for p in inputs}
        admin=connect() if connect else psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        for n in tiers:
            print(f'MOD017 games tier {n}: starting',flush=True);report['tiers'].append(run_tier(admin,n,report));persist();print(f'MOD017 games tier {n}: PASS',flush=True)
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
    directory=base.ROOT/'docs/modernization/evidence';run(directory,directory/'mod-017-games-current-2026-11-13.json',args.tier or base.SIZES)
if __name__=='__main__':main()
