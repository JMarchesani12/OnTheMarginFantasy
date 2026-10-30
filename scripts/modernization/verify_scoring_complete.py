"""All scoring queries/rules on marked disposable PostgreSQL; no .env/DSN."""
import datetime as dt
import hashlib
import json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL,ROOT,engine_for
from verify_scoring_read import scoring_tests
from actors import UserActor
from endpoints.scoring.service import ScoringService
from endpoints.scoring.scoringModel import ScoringModel
from endpoints.scoring.contracts import ScoringReadDenied,ScoringRejected

FIXTURE='''
DROP SCHEMA public CASCADE; CREATE SCHEMA public;
CREATE TABLE "League" (id bigint PRIMARY KEY,commissioner bigint,sport bigint,"seasonYear" bigint,settings jsonb);
INSERT INTO "League" VALUES (10,1,1,2026,'{}'),(20,4,1,2026,'{}'),(30,1,1,2026,'{}');
CREATE TABLE "LeagueMember" (id bigint PRIMARY KEY,"leagueId" bigint,"userId" bigint,"teamName" text);
INSERT INTO "LeagueMember" VALUES (11,10,1,'Alpha'),(12,10,2,'Beta'),(13,10,3,'Gamma'),(21,20,4,'Other');
CREATE TABLE "Week" (id bigint PRIMARY KEY,"leagueId" bigint,"weekNumber" bigint,"startDate" timestamptz,"endDate" timestamptz);
INSERT INTO "Week" VALUES (100,10,0,'2025-10-01','2025-10-07'),(101,10,1,'2025-10-08','2025-10-14'),
    (200,20,0,'2025-10-01','2025-10-07'),(300,30,0,'2025-10-01','2025-10-07');
CREATE TABLE "SportSeason" (id bigint PRIMARY KEY,"sportId" bigint,"seasonYear" bigint);
INSERT INTO "SportSeason" VALUES (1,1,2026);
CREATE TABLE "SeasonPhase" (id bigint PRIMARY KEY,"sportSeasonId" bigint,type text,rules jsonb,"startDate" timestamptz,"endDate" timestamptz);
INSERT INTO "SeasonPhase" VALUES (10,1,'PrimaryPlayoffs','{"primaryPostseason":true}','2025-10-01','2025-10-31'),
    (11,1,'PrimaryPlayoffs','{"primaryPostseason":false}','2025-10-01','2025-10-31'),
    (20,1,'SegmentPlayoffs','{}','2025-10-01','2025-10-31');
CREATE TABLE "LeagueTeamSlot" ("leagueId" bigint,"memberId" bigint,"sportTeamId" bigint);
INSERT INTO "LeagueTeamSlot" VALUES (10,11,101),(10,12,102),(10,13,103),(20,21,201);
CREATE TABLE "GameResult" (id bigint PRIMARY KEY,"sportSeasonId" bigint,"seasonPhaseId" bigint,"roundOrder" bigint,
    "homeTeamId" bigint,"awayTeamId" bigint,"homeScore" bigint,"awayScore" bigint);
INSERT INTO "GameResult" VALUES (1,1,10,3,101,201,20,10),(2,1,10,2,102,201,10,20),
    (3,1,10,1,101,102,10,20),(4,1,11,99,101,102,200,0),(5,1,20,1,101,102,10,20);
CREATE TABLE "WeeklyTeamScore" ("leagueId" bigint,"weekId" bigint,"memberId" bigint,
    "pointDifferential" bigint,rank bigint,"pointsAwarded" numeric);
INSERT INTO "WeeklyTeamScore" VALUES (10,100,11,99,1,9),(10,100,12,88,2,8),
    (10,101,11,66,1,2),(10,101,12,55,2,1),(20,200,21,77,1,7);
'''

class ScheduleFacts:
    def get_member_games_for_week(self,league_id,member_id,week_number):
        return [{'memberPointDiff':{11:5,12:-2,13:0}[member_id]}]
    def get_head_to_head_games(self,**kwargs):
        return [{'homeScore':7,'awayScore':14,'homeOwnedByA':True,'awayOwnedByA':False,
                 'homeOwnedByB':False,'awayOwnedByB':True}]


def remaining_tests(engine,database):
    with engine.begin() as conn: conn.exec_driver_sql(FIXTURE)
    service=ScoringService(engine,ScheduleFacts())
    def rows():
        with engine.connect() as conn:
            return [tuple(r) for r in conn.execute(text('SELECT * FROM "WeeklyTeamScore" ORDER BY "leagueId","weekId","memberId"'))]
    before=rows()
    inserts=0
    def fail_second(conn,cursor,statement,params,context,many):
        nonlocal inserts
        if 'INSERT INTO "WeeklyTeamScore"' in statement:
            inserts+=1
            if inserts==2: raise RuntimeError('synthetic second insert failure')
    event.listen(engine,'before_cursor_execute',fail_second)
    try:
        try: service.compute_weekly_scores_for_job(10,0)
        except RuntimeError as exc: assert 'second insert' in str(exc)
        else: raise AssertionError('Fault did not abort')
    finally: event.remove(engine,'before_cursor_execute',fail_second)
    assert rows()==before,'Delete/partial insertion did not roll back'
    with engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION reject_score_commit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW."leagueId"=10 AND NEW."pointDifferential"=5 THEN
                RAISE EXCEPTION 'synthetic deferred score failure'; END IF; RETURN NEW; END $$;
            CREATE CONSTRAINT TRIGGER score_commit AFTER INSERT ON "WeeklyTeamScore"
                DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reject_score_commit();''')
    try: service.compute_weekly_scores_for_job(10,0)
    except DBAPIError: pass
    else: raise AssertionError('Deferred score commit did not abort')
    assert rows()==before,'Deferred commit failure changed old scores'
    with engine.begin() as conn: conn.exec_driver_sql('DROP TRIGGER score_commit ON "WeeklyTeamScore"')
    for _ in range(2):
        result=service.compute_weekly_scores_for_job(10,0)
        assert [(m['memberId'],m['pointDifferential'],m['rank'],m['pointsAwarded']) for m in result['scores']]==[(11,5,1,3),(13,0,2,2),(12,-2,3,1)],result
    after=rows()
    assert [r for r in after if r[0]!=10 or r[1]!=100]==[r for r in before if r[0]!=10 or r[1]!=100]
    group=[{'memberId':11,'totalPoints':2},{'memberId':12,'totalPoints':2}]
    assert service._get_playoff_depth_by_member(10,[11,12,13])=={11:3,12:2,13:0}
    assert service._get_segment_champ_counts_by_member(10,[11,12,13])=={11:0,12:1,13:0}
    assert service._get_segment_pd_by_member(10,[11,12,13])=={11:-10,12:10,13:0}
    for method,expected in ((service._tb_season_playoff_depth,[11,12]),
                            (service._tb_season_num_segment_champs,[12,11]),
                            (service._tb_season_playoff_head_to_head,[12,11]),
                            (service._tb_season_segment_postseason_head_to_head,[12,11]),
                            (service._tb_season_latest_non_tied_week,[11,12])):
        assert [m['memberId'] for m in method(10,group)]==expected,method.__name__
    assert [m['memberId'] for m in service._resolve_season_ties(10,group)]==[11,12]
    weekly_group=[{'memberId':11,'pointDifferential':10},{'memberId':12,'pointDifferential':10}]
    assert [m['memberId'] for m in service.apply_weekly_tiebreakers(10,0,weekly_group)]==[12,11]
    config={'bonuses':{'playoffDepth':{'first':3,'second':2,'third':1},
        'conferenceChampion':{'first':2,'second':1},'conferenceBottom':{'last':-1},'unknown':{'first':999}}}
    with engine.begin() as conn:
        conn.execute(text('UPDATE "League" SET settings=CAST(:settings AS jsonb) WHERE id=10'),{'settings':json.dumps(config)})
        conn.exec_driver_sql('''DELETE FROM "WeeklyTeamScore" WHERE "leagueId"=10;
            INSERT INTO "WeeklyTeamScore" VALUES (10,100,11,5,1,2),(10,100,12,-2,2,2),(10,100,13,0,3,2);''')
    standings=service.get_season_standings(UserActor(2,'member'),10)
    assert [(m['memberId'],m['weeklyPoints'],m['bonusPoints'],m['totalPoints']) for m in standings['members']]==[(12,2.0,4.0,6.0),(11,2.0,2.0,4.0),(13,2.0,0.0,2.0)],standings
    assert ScoringModel(engine,ScheduleFacts()).compute_end_of_year_season_standings(10)==standings
    try: service.get_season_standings(UserActor(99,'outsider'),10)
    except ScoringReadDenied: pass
    else: raise AssertionError('Outsider standings allowed')
    revoker=engine_for(database,'otm-standings-revoker')
    revoked=False
    def revoke(conn,cursor,statement,params,context,many):
        nonlocal revoked
        if 'WeeklyTeamScore' in statement and not revoked:
            revoked=True
            with revoker.begin() as other: other.execute(text('DELETE FROM "LeagueMember" WHERE id=12'))
    event.listen(engine,'before_cursor_execute',revoke)
    try:
        try: service.get_season_standings(UserActor(2,'member'),10)
        except ScoringReadDenied: pass
        else: raise AssertionError('Revoked standings exposed data')
    finally:
        event.remove(engine,'before_cursor_execute',revoke)
        with revoker.begin() as other: other.execute(text("INSERT INTO \"LeagueMember\" VALUES (12,10,2,'Beta')"))
        revoker.dispose()
    with engine.begin() as conn: conn.exec_driver_sql("UPDATE \"SeasonPhase\" SET type='Exhibition'")
    assert service._get_playoff_depth_by_member(10,[11,12])=={11:0,12:0}
    assert service._get_segment_champ_counts_by_member(10,[11,12])=={11:0,12:0}
    assert service._get_segment_pd_by_member(10,[11,12])=={11:0,12:0}
    assert service._tb_season_playoff_depth(10,group) is None
    with engine.begin() as conn:
        conn.exec_driver_sql('''INSERT INTO "SeasonPhase" VALUES (30,1,'PrimaryPlayoffs',
            '{"scoringPeriod":"BASKETBALL_FINAL"}','2025-10-01','2025-10-20');''')
    try: service.compute_weekly_scores_for_job(10,0)
    except ScoringRejected as exc: assert 'split across weeks' in str(exc)
    else: raise AssertionError('Split final period allowed')
    with engine.begin() as conn:
        conn.exec_driver_sql('''UPDATE "SeasonPhase" SET "startDate"='2099-10-01',"endDate"='2099-10-20' WHERE id=30;
            UPDATE "Week" SET "startDate"='2099-10-01',"endDate"='2099-10-19 23:59:59.999999+00' WHERE id=100;''')
    try: service.compute_weekly_scores_for_job(10,0)
    except ScoringRejected as exc: assert 'until the final scoring period ends' in str(exc)
    else: raise AssertionError('Future final period allowed')
    return {'atomic_replacement_statement_and_commit_rollback':'PASS','scoped_repeat_convergence_week_zero':'PASS',
            'weekly_tiebreaks_and_waterfall':'PASS','all_season_tiebreak_query_families':'PASS',
            'all_bonus_families_and_primary_phase_filter':'PASS','actor_standings_and_revocation':'PASS',
            'empty_phase_facts':'PASS','split_and_future_final_period_guards':'PASS'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL); admin.autocommit=True
    name='otm_scoring_full_'+uuid4().hex; created=False; engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name))); created=True
        engine=engine_for(name,'otm-scoring-full')
        reads=scoring_tests(engine,name)
        results=remaining_tests(engine,name)
        files=['api/endpoints/scoring/'+f for f in ('service.py','repository.py','rules.py','contracts.py','scoringModel.py','scoringEndpoints.py')]
        files+=['api/cronJobs/cronComputeWeeklyScores.py','api/cronJobs/cronComputeFinalScoreboard.py',
                'api/actors.py','api/utils/authorization.py','scripts/modernization/verify_scoring_complete.py','scripts/modernization/verify_scoring_read.py']
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; schedule read port supplied facts, no provider/network calls',
                'weekly_points_rerun':reads,'remaining_scoring':results,
                'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-scoring-complete-postgres-2026-10-29.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None: engine.dispose()
        if created:
            with admin.cursor() as cur: cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__': main()
