"""MOD-014 atomic finalization on a new marked task-owned loopback PostgreSQL DB."""
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from assess_postgres import LOCAL,ROOT,engine_for
from endpoints.scoring.service import ScoringService
from endpoints.scoring.finalization_service import SeasonFinalizationService
from endpoints.scoring.finalization_repository import SeasonFinalizationRepository
from endpoints.scoring.weekly_service import WeeklyCompletionService
from endpoints.schedule.read_service import ScheduleReadService
from endpoints.transaction.workflow_service import TransactionWorkflowService
from verify_mod010 import race
from verify_mod013 import tests as prior_weekly_tests
from verify_scoring_complete import remaining_tests as prior_scoring_tests

NOW=dt.datetime(2026,11,5,12,tzinfo=dt.timezone.utc)


class StrictOwner:
    def __init__(self,owner):self.owner=owner;self.active=False
    @contextmanager
    def begin(self):
        assert not self.active,'Nested acquisition'
        self.active=True
        try:
            with self.owner.begin() as conn:yield conn
        finally:self.active=False
    def connect(self):
        assert not self.active,'Detached read'
        return self.owner.connect()


def tests(engine,database):
    def query(statement,**params):
        with engine.begin() as conn:
            result=conn.execute(text(statement),params) if params else conn.exec_driver_sql(statement)
            return [dict(row) for row in result.mappings()] if result.returns_rows else []
    def reset():
        with engine.begin() as conn:
            conn.exec_driver_sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public; DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY); CREATE EXTENSION pg_trgm WITH SCHEMA public;')
            conn.exec_driver_sql((ROOT/'db/baselines/20261029/001_schema.sql').read_text())
            conn.exec_driver_sql((ROOT/'api/migrations/20261030_game_kickoff_tbd.sql').read_text())
        for filename in ('20261104_user_identity_unique.sql','20261104_week_score_identity.sql','20261104_ownership_integrity.sql'):
            raw=engine.raw_connection()
            try:
                with raw.cursor() as cursor:cursor.execute((ROOT/'api/migrations'/filename).read_text())
                raw.commit()
            finally:raw.close()
        query('''INSERT INTO "User" (id,email) VALUES (1,'alice@example.test'),(2,'bob@example.test');
            INSERT INTO "Sport" (id,name,"maxDraftRounds") VALUES (1,'Basketball',4),(2,'Football',4);
            INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") VALUES
            (1,1,2026,'2026-01-01','2026-10-31'),(2,2,2026,'2026-01-01','2026-10-31');
            INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner,"seasonYear") VALUES
            (10,'First',1,2,'In-Season','{"bonuses":{"playoffDepth":{"first":3,"second":2},"conferenceChampion":{"first":2},"conferenceBottom":{"last":-1}}}',1,2026),
            (20,'Same season',1,1,'In-Season','{}',2,2026),(30,'Other season',2,1,'In-Season','{}',1,2026),
            (40,'Other year',1,1,'Pre-Draft','{}',1,2027);
            INSERT INTO "LeagueMember" (id,"leagueId","userId","teamName","draftOrder") VALUES
            (11,10,1,'A',1),(12,10,2,'B',2),(21,20,2,'Same',1),(31,30,1,'Other',1);
            INSERT INTO "School" (id,name) VALUES (1,'Synthetic');
            INSERT INTO "SportTeam" (id,"schoolId","sportId","displayName",tier) VALUES (101,1,1,'A',1),(102,1,1,'B',1),(103,1,1,'C',1),(201,1,2,'Other',1);
            INSERT INTO "Conference" (id,name) VALUES (1,'Conference');
            INSERT INTO "SportConference" (id,"conferenceId","sportId","maxTeamsPerOwner") VALUES (500,1,1,3);
            INSERT INTO "ConferenceMembership" ("sportTeamId","sportConferenceId","sportId","seasonYear") VALUES (101,500,1,2026),(102,500,1,2026),(103,500,1,2026);
            INSERT INTO "Week" (id,"leagueId","weekNumber","startDate","endDate","isLocked","scoringComplete") VALUES
            (100,10,1,'2026-10-01','2026-10-07',true,true),(101,10,2,'2026-10-08','2026-10-14',true,true),
            (200,20,1,'2026-10-01','2026-10-07',true,true),(300,30,1,'2026-10-01','2026-10-07',true,true);
            INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia") VALUES
            (10,11,101,1,'Draft'),(10,12,102,1,'Draft'),(20,21,103,1,'Draft'),(30,31,201,1,'Draft');
            INSERT INTO "SeasonPhase" (id,"sportSeasonId",type,name,rules,"startDate","endDate") VALUES
            (10,1,'PrimaryPlayoffs','Primary','{"primaryPostseason":true}','2026-10-01','2026-10-31'),
            (20,1,'SegmentPlayoffs','Segment','{}','2026-10-01','2026-10-31');
            INSERT INTO "GameResult" (sport,"externalGameId",date,"homeTeamId","awayTeamId","homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName","sportSeasonId","seasonPhaseId","roundOrder") VALUES
            (1,'depthA','2026-10-03',101,103,20,10,101,103,'A','C',1,10,3),
            (1,'depthB','2026-10-04',102,103,10,20,102,103,'B','C',1,10,2),
            (1,'primaryH2H','2026-10-05',101,102,10,20,101,102,'A','B',1,10,1),
            (1,'segment','2026-10-06',101,102,10,20,101,102,'A','B',1,20,1);
            INSERT INTO "WeeklyTeamScore" ("leagueId","weekId","memberId","pointsAwarded","pointDifferential",rank) VALUES
            (10,100,11,2,5,1),(10,100,12,1,-5,2),(10,101,11,2,-5,2),(10,101,12,3,5,1),
            (20,200,21,1,0,1),(30,300,31,1,0,1);''')
    def service(owner=engine,repository=None):
        strict=StrictOwner(owner)
        return SeasonFinalizationService(strict,ScoringService(strict,ScheduleReadService(strict)),repository)
    def state():
        return {table:query(f'SELECT * FROM "{table}" ORDER BY id') for table in ('League','SportSeason','WeeklyTeamScore','LeagueTeamSlot')}
    def scoped(current,season=1):
        return ([r for r in current['League'] if r['id'] in ((10,20) if season==1 else (30,))],
                [r for r in current['SportSeason'] if r['id']==season])

    reset();strict=StrictOwner(engine);scoring=ScoringService(strict,None)
    with strict.begin() as conn:
        standings=scoring.get_season_standings_for_job(10,conn=conn)
        assert {m['memberId']:m['bonusPoints'] for m in standings['members']}=={11:2,12:4},standings
        group=[{'memberId':11,'totalPoints':4},{'memberId':12,'totalPoints':4}]
        for method,expected in (('_tb_season_playoff_depth',[11,12]),('_tb_season_num_segment_champs',[12,11]),
                                ('_tb_season_playoff_head_to_head',[12,11]),('_tb_season_segment_postseason_head_to_head',[12,11]),
                                ('_tb_season_latest_non_tied_week',[12,11])):
            assert [r['memberId'] for r in getattr(scoring,method)(10,group,conn=conn)]==expected,method
    before=state();result=service().run(NOW)
    assert result=={'finalized':[1,2],'skipped':[],'blocked':[],'failures':[]},result
    after=state();assert before['WeeklyTeamScore']==after['WeeklyTeamScore'] and before['LeagueTeamSlot']==after['LeagueTeamSlot']
    assert next(r for r in after['League'] if r['id']==40)==next(r for r in before['League'] if r['id']==40)
    assert service().run(NOW)=={'finalized':[],'skipped':[],'blocked':[],'failures':[]};assert state()==after

    boundaries={
        'incomplete_week':'UPDATE "Week" SET "scoringComplete"=false WHERE id=200',
        'future_week':'UPDATE "Week" SET "endDate"=\'2026-12-01\' WHERE id=100',
        'null_date':'UPDATE "Week" SET "endDate"=NULL WHERE id=100',
        'empty_calendar':'DELETE FROM "Week" WHERE "leagueId"=20',
        'missing_period':'DELETE FROM "Week" WHERE id=100',
        'empty_membership':'DELETE FROM "LeagueMember" WHERE "leagueId"=20',
        'pending':'''INSERT INTO "Transaction" ("leagueId","weekId",type,"memberFromId","memberToId",status,"fromTeamIds","toTeamIds") VALUES (10,101,'FREE_AGENT',11,11,'PENDING_APPLY','[101]','[103]')'''}
    for boundary,edit in boundaries.items():
        reset();query(edit);before=state();result=service().run(NOW)
        assert result['finalized']==[2] and result['blocked'] and not result['failures'],(boundary,result)
        assert scoped(state())==scoped(before),boundary
    reset();query('UPDATE "SportSeason" SET "seasonEnd"=\'2026-11-05\' WHERE id=1');assert service().run(NOW)['finalized']==[2]
    reset();query('UPDATE "League" SET status=\'Completed\' WHERE id=10');query('UPDATE "Week" SET "scoringComplete"=false WHERE id=100')
    assert service().run(NOW)['blocked'][0]['reason']=='weeks_not_ready'

    for marker in ("SET status='Completed'",'SET "seasonFinalized"=true'):
        reset();before=state();hit=False
        def fail(conn,cursor,statement,params,context,many):
            nonlocal hit
            if marker in statement and not hit:hit=True;raise RuntimeError('synthetic SQL secret')
        event.listen(engine,'after_cursor_execute',fail)
        try:result=service().run(NOW)
        finally:event.remove(engine,'after_cursor_execute',fail)
        assert hit and result['finalized']==[2] and result['failures']==[{'sportSeasonId':1,'category':'RuntimeError'}],result
        assert scoped(state())==scoped(before)
        assert service().run(NOW)['finalized']==[1]
    for table,condition in (('League',"NEW.sport=1 AND NEW.status='Completed'"),('SportSeason','NEW.id=1 AND NEW."seasonFinalized"')):
        reset();before=state()
        query(f'''CREATE FUNCTION reject_commit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF {condition} THEN RAISE EXCEPTION 'synthetic deferred failure' USING ERRCODE='23514'; END IF;
            RETURN NEW; END $$;
            CREATE CONSTRAINT TRIGGER reject_commit AFTER UPDATE ON "{table}" DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reject_commit();''')
        result=service().run(NOW);assert result['finalized']==[2] and result['failures'],result
        assert scoped(state())==scoped(before)
        query(f'DROP TRIGGER reject_commit ON "{table}"');assert service().run(NOW)['finalized']==[1]

    reset();observer=engine_for(database,'mod014-scope-observer');inserted=False
    def insert_scope(conn,cursor,statement,params,context,many):
        nonlocal inserted
        if 'COALESCE(SUM(wts."pointsAwarded"), 0)' in statement and not inserted:
            inserted=True
            with observer.begin() as other:
                other.exec_driver_sql('''INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner,"seasonYear")
                    VALUES (50,'Concurrent scope',1,1,'In-Season','{}',1,2026)''')
    event.listen(engine,'after_cursor_execute',insert_scope)
    try:result=service().run(NOW)
    finally:event.remove(engine,'after_cursor_execute',insert_scope);observer.dispose()
    assert inserted and result['finalized']==[2] and result['blocked'][0]['reason']=='scope_changed',result
    assert query('SELECT status FROM "League" WHERE id=10')[0]['status']=='In-Season'
    query('DELETE FROM "League" WHERE id=50');assert service().run(NOW)['finalized']==[1]

    reset();reports={}
    def finalize(owner,label,repository=None):
        reports[label]=service(owner,repository).run(NOW)
        assert not reports[label]['failures'] and not reports[label]['blocked'],reports[label]
    races={}
    races['same_season_finalizers']=race(engine,database,lambda owner:finalize(owner,'first'),lambda owner:finalize(owner,'second'),"SET status='Completed'",expected_second='ok')
    assert sorted(reports['first']['finalized']+reports['second']['finalized'])==[1,2]
    assert reports['second']['skipped'],reports
    class OnlyOtherSeason(SeasonFinalizationRepository):
        def candidates(self,conn,today):return [i for i in super().candidates(conn,today) if i==2]
    reset()
    races['independent_season']=race(engine,database,lambda owner:finalize(owner,'first'),lambda owner:finalize(owner,'second',OnlyOtherSeason()),"SET status='Completed'",expected_second='ok',require_wait=False)
    assert reports['second']['finalized']==[2]
    # Weekly coordinator waits on ownership rather than changing a season during
    # its standings validation. Its finalized flags are not scoring progress.
    reset();query('UPDATE "Week" SET "scoringComplete"=false WHERE id=101')
    def weekly(owner):
        strict=StrictOwner(owner)
        reports['weekly']=WeeklyCompletionService(strict,ScoringService(strict,ScheduleReadService(strict)),TransactionWorkflowService(strict)).run(NOW)
        assert not reports['weekly']['failures'] and not reports['weekly']['blocked'],reports['weekly']
    races['weekly_then_finalizer']=race(engine,database,weekly,lambda owner:finalize(owner,'second'),'INSERT INTO "WeeklyTeamScore"',expected_second='ok')
    assert reports['second']['finalized']==[1,2]
    reset()
    races['finalizer_then_pending_submission']=race(engine,database,lambda owner:finalize(owner,'first'),
        lambda owner:TransactionWorkflowService(owner).free_agency_for_job(10,100,1,11,103,101),
        "SET status='Completed'",expected_second='rejected')
    return {'computed_standings_all_bonus_tiebreak_supplied_reads':'PASS','atomic_scope_replay_no_score_or_roster_writes':'PASS',
            'detected_concurrent_scope_change':'PASS','readiness_boundaries':list(boundaries),'statement_deferred_commit_rollback_retry':'PASS','races':races}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_mod014_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cursor.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'mod014-owner');result=tests(engine,name)
        result['prior_weekly']=prior_weekly_tests(engine,name)
        result['prior_scoring']=prior_scoring_tests(engine,name)
        files=['api/endpoints/scoring/'+file for file in ('finalization_service.py','finalization_repository.py','service.py','repository.py','rules.py','scoringEndpoints.py','weekly_service.py','weekly_repository.py')]
        files+=['api/cronJobs/cronComputeFinalScoreboard.py','api/utils/ownership.py','api/utils/authorization.py',
                'api/endpoints/transaction/workflow_service.py','api/endpoints/transaction/service.py',
                'scripts/modernization/verify_mod014.py','scripts/modernization/verify_mod013.py','scripts/modernization/verify_scoring_complete.py',
                'api/migrations/20261030_game_kickoff_tbd.sql','api/migrations/20261104_user_identity_unique.sql',
                'api/migrations/20261104_week_score_identity.sql','api/migrations/20261104_ownership_integrity.sql',
                'api/tests/test_season_finalization.py','api/tests/test_operational_trusted_contract.py',
                'db/baselines/20261029/001_schema.sql']
        report={'result':'PASS','scope':'Owned marked loopback PostgreSQL only; no configured jobs or leagues','tests':result,
                'sha256':{file:hashlib.sha256((ROOT/file).read_bytes()).hexdigest() for file in files}}
        (ROOT/'docs/modernization/evidence/mod-014-postgres-2026-11-05.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cursor:cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()
if __name__=='__main__':main()
