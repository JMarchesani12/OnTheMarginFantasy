"""Audit-only real weekly scoring on owned localhost; score writes always roll back."""
import argparse
from collections import Counter
from datetime import datetime,timedelta,timezone
import hashlib,time
from pathlib import Path
from uuid import uuid4
import psycopg2
from sqlalchemy import create_engine,text,event
import measure_mod017 as base
from measure_mod017_transactions import verify_cleanup,save_json
from endpoints.scoring.service import ScoringService
from endpoints.schedule.read_service import ScheduleReadService

SIZES=(4,8,16)
SCENARIOS=('unique','unresolved','head_decides','margin','tier_phase')
TBD='api/migrations/20261030_game_kickoff_tbd.sql'


def expected_counts(n,scenario):
    tied=scenario in ['unresolved','head_decides','margin'];fallback=scenario in ['unresolved','margin']
    return dict(week=1,members=1,settings=n*(2 if fallback else 1),member_games=n*(2 if fallback else 1),head_to_head=n*(n-1)//2 if tied else 0,lock=1,delete=1,insert=n)


def expected_scores(n,scenario):
    order=list(range(1,n+1))
    if scenario=='head_decides':order=[1,*range(3,n+1),2]
    if scenario=='margin':order=list(reversed(order))
    return [dict(memberId=1000+m,teamName=f'Audit team {m}',pointDifferential=(n-m+1)*(3 if scenario=='tier_phase' else 1) if scenario in ['unique','tier_phase'] else 5,rank=i,pointsAwarded=n-i+1) for i,m in enumerate(order,1)]


def fixture_games(n,scenario):
    rows=[]
    def add(team,margin,reverse=False,opponent=32):
        rows.append(dict(home=opponent if reverse else team,away=team if reverse else opponent,margin=margin,reverse=reverse))
    for m in range(1,n+1):
        margin=n-m+1 if scenario=='unique' else 4*(n-m+1) if scenario=='tier_phase' else 5
        if scenario=='head_decides':margin=-2 if m==1 else 12 if m==2 else 5
        if scenario=='margin':
            add(m,m+5,m%2==0);add(m,-m,m%2!=0)
        else:add(m,margin,m%2==0)
    if scenario=='head_decides':add(1,7,opponent=2)
    if scenario=='tier_phase':add(n,-4)
    add(1,29,opponent=n+1) # Both teams owned by member1: contributes zero.
    return rows


def classify(statement):
    sql=' '.join(statement.split())
    if sql.startswith('INSERT INTO "WeeklyTeamScore"'):return 'insert'
    if sql.startswith('DELETE FROM "WeeklyTeamScore"'):return 'delete'
    if 'FOR UPDATE' in sql and '"Week"' in sql:return 'lock'
    if 'AS "isFinalPeriod"' in sql:return 'week'
    if 'a_teams AS' in sql:return 'head_to_head'
    if 'member_teams AS' in sql:return 'member_games'
    if 'SELECT id, "sport", "seasonYear", settings FROM "League"' in sql:return 'settings'
    if 'SELECT id, "teamName" FROM "LeagueMember"' in sql:return 'members'
    raise AssertionError('Unclassified scoring statement')


class Tracker:
    def __init__(self):self.enabled=False;self.reset()
    def reset(self):self.counts=Counter();self.cursor_ms=Counter();self.examples={}
    def before(self,conn,cursor,statement,parameters,context,executemany):
        if self.enabled:
            role=classify(statement);context._mod021=(role,time.perf_counter());self.counts[role]+=1
            self.examples.setdefault(role,dict(sql=statement,parameters=parameters,executemany=executemany))
    def after(self,conn,cursor,statement,parameters,context,executemany):
        if self.enabled:
            role,start=context._mod021;self.cursor_ms[role]+=(time.perf_counter()-start)*1000


def seed(conn,n):
    facts=base.seed(conn,100);conn.exec_driver_sql((base.ROOT/TBD).read_text());clock=datetime.fromisoformat(facts['anchor'])
    conn.execute(text('''INSERT INTO "User" (id,email,"displayName") SELECT 1000+i,'audit-'||i||'@example.test','Audit user '||i FROM generate_series(1,:n) i'''),dict(n=n))
    conn.exec_driver_sql('''INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner,"seasonYear") VALUES (101,'Scoring audit',1,8,'In-Season','{"ruleSetVersion":"v1"}',1,2026)''')
    conn.execute(text('UPDATE "League" SET "numPlayers"=:n WHERE id=101'),dict(n=n))
    conn.execute(text('''INSERT INTO "LeagueMember" (id,"leagueId","userId","teamName","draftOrder") SELECT 1000+i,101,1000+i,'Audit team '||i,i FROM generate_series(1,:n) i'''),dict(n=n))
    conn.execute(text('''INSERT INTO "Week" (id,"leagueId","weekNumber","startDate","endDate") VALUES (2000,101,1,:start,:end)'''),dict(start=clock-timedelta(days=14),end=clock-timedelta(days=7)))
    conn.exec_driver_sql('''INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") VALUES (2026,1,2026,'2026-01-01','2026-12-31')''')
    conn.execute(text('''INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia") SELECT 101,1000+i,i,1,'DRAFT' FROM generate_series(1,:n) i'''),dict(n=n))
    conn.execute(text('''INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia") VALUES (101,1001,:team,1,'DRAFT')'''),dict(team=n+1))
    conn.commit();facts.update(target_league=101,week_id=2000,members=n,owned_teams=n+1,background_leagues=100);return facts


def seed_scenario(conn,n,scenario,anchor):
    conn.exec_driver_sql('DELETE FROM "GameResult"');conn.exec_driver_sql('DELETE FROM "SeasonPhase"');conn.exec_driver_sql('UPDATE "SportTeam" SET tier=1')
    if scenario=='tier_phase':
        conn.exec_driver_sql('UPDATE "SportTeam" SET tier=3 WHERE id=32')
        conn.execute(text('''INSERT INTO "SeasonPhase" (id,"sportSeasonId",type,name,"startDate","endDate",rules) VALUES (1,2026,'NationalTournament','Synthetic tournament',:start,:end,jsonb_build_object('positiveOnly',true,'marginMultiplier',1.5))'''),dict(start=datetime.fromisoformat(anchor)-timedelta(days=14),end=datetime.fromisoformat(anchor)-timedelta(days=7)))
    for i,game in enumerate(fixture_games(n,scenario),1):
        delta=-game['margin'] if game['reverse'] else game['margin']
        conn.execute(text('''INSERT INTO "GameResult" (id,sport,"externalGameId",date,"homeTeamId","awayTeamId","homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName","sportSeasonId","seasonPhaseId","timeTBD") VALUES (:id,1,:external,:date,:home,:away,:hs,:aws,:home,:away,:hn,:an,2026,:phase,false)'''),dict(id=i,external=f'{scenario}-{i}',date=datetime.fromisoformat(anchor)-timedelta(days=10),home=game['home'],away=game['away'],hs=100+delta,aws=100,hn=f'Sport team {game["home"]}',an=f'Sport team {game["away"]}',phase=1 if scenario=='tier_phase' else None))
    conn.commit();conn.exec_driver_sql('ANALYZE');conn.commit()


def measure(conn,engine,n,scenario):
    tracker=Tracker();event.listen(engine,'before_cursor_execute',tracker.before);event.listen(engine,'after_cursor_execute',tracker.after)
    scorer=ScoringService(None,ScheduleReadService(None));expected=expected_scores(n,scenario);wanted=expected_counts(n,scenario);samples=[];signature=None;examples={}
    try:
        for iteration in range(6):
            tracker.reset();transaction=conn.begin()
            try:
                tracker.enabled=True;start=time.perf_counter()
                try:result=scorer.compute_weekly_scores_for_job(101,1,conn=conn)
                finally:elapsed=(time.perf_counter()-start)*1000;tracker.enabled=False
                if {k:tracker.counts.get(k,0) for k in wanted}!=wanted or set(tracker.counts)-set(wanted):raise AssertionError('Query role counts differ from independent formula')
                if result['leagueId']!=101 or result['weekNumber']!=1 or result['weekId']!=2000:raise AssertionError('Scoring scope changed')
                signature=base.signature(result['scores']);base.assert_equivalent(base.signature(expected),signature)
                stored=[dict(r) for r in conn.execute(text('SELECT "memberId","pointDifferential",rank,"pointsAwarded" FROM "WeeklyTeamScore" WHERE "leagueId"=101 AND "weekId"=2000 ORDER BY rank')).mappings()]
                base.assert_equivalent(base.signature([{k:r[k] for k in ['memberId','pointDifferential','rank','pointsAwarded']} for r in expected]),base.signature(stored))
                examples.update(tracker.examples)
                if iteration:samples.append(dict(service_ms=elapsed,query_count=sum(tracker.counts.values()),counts=dict(tracker.counts),cursor_execution_ms=dict(tracker.cursor_ms)))
            finally:
                tracker.enabled=False;transaction.rollback()
            remaining=conn.exec_driver_sql('SELECT count(*) FROM "WeeklyTeamScore" WHERE "leagueId"=101').scalar_one();conn.commit()
            if remaining!=0:raise AssertionError('Scored rows survived rollback')
        return dict(scenario=scenario,members=n,expected_counts=wanted,expected_scores=expected,result=signature,samples=samples,median_service_ms=base.statistics.median(s['service_ms'] for s in samples),statement_examples=examples,invocations=6,rollback_verified=True)
    finally:
        tracker.enabled=False;event.remove(engine,'before_cursor_execute',tracker.before);event.remove(engine,'after_cursor_execute',tracker.after)


def run_tier(admin,n,report):
    record=None
    try:
        with base.owned_database(admin) as database:
            record=dict(name=database,cleanup='pending');report['databases'].append(record)
            engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=database,**base.LOCAL))
            try:
                with engine.connect() as conn:
                    base.schema(conn);facts=seed(conn,n);settings={k:conn.exec_driver_sql('SHOW '+k).scalar_one() for k in ['server_version','shared_buffers','work_mem','jit','statement_timeout','lock_timeout']};conn.commit();records=[]
                    for scenario in SCENARIOS:
                        seed_scenario(conn,n,scenario,facts['anchor']);records.append(measure(conn,engine,n,scenario))
                    return dict(members=n,fixture=facts,settings=settings,measurements=records)
            finally:engine.dispose()
    finally:
        if record is not None:verify_cleanup(admin,record)


def run(directory,manifest,tiers,connect=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);run_id=uuid4().hex;artifact=directory/f'mod-021-weekly-{run_id}.json'
    inputs=[base.BASELINE,*base.MIGRATIONS,TBD,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_transactions.py','scripts/modernization/measure_mod021_weekly.py','api/endpoints/scoring/service.py','api/endpoints/scoring/repository.py','api/endpoints/schedule/read_service.py','api/endpoints/schedule/read_repository.py','api/endpoints/schedule/calendar_service.py','api/endpoints/schedule/calendar_repository.py','api/rules/leagueRules.py','api/rules/tournamentRules.py','api/utils/conference_membership.py']
    report=dict(date='2026-11-15',run_id=run_id,started_at=datetime.now(timezone.utc).isoformat(),result='RUNNING',scope='Synthetic weekly scorer orchestration measurements only; optimization deferred',tiers=[],databases=[],cleanup='no database created',provenance={},limits=['One targetleague with4/8/16members,100backgroundleagues,synthetic32teams/five scenarios','Actual rolledbackwrites,not commit/concurrency/job/HTTP/provider measurement','SQL hooks add overhead; cursor timings exclude fetch and are not full service time'])
    def persist():
        save_json(artifact,report);save_json(Path(manifest),dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist();admin=None
    try:
        report['provenance']={p:hashlib.sha256((base.ROOT/p).read_bytes()).hexdigest() for p in inputs}
        admin=connect() if connect else psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        for n in tiers:
            print(f'MOD021 weekly members {n}: starting',flush=True);report['tiers'].append(run_tier(admin,n,report));persist();print(f'MOD021 weekly members {n}: PASS',flush=True)
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
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tier',type=int,choices=SIZES,action='append');args=parser.parse_args()
    directory=base.ROOT/'docs/modernization/evidence';run(directory,directory/'mod-021-weekly-current-2026-11-15.json',args.tier or SIZES)
if __name__=='__main__':main()
