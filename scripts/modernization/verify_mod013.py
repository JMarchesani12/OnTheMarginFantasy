"""MOD-013 proof on a new, marked, task-owned loopback PostgreSQL database."""
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from assess_postgres import LOCAL,ROOT,engine_for
from actors import UserActor
from endpoints.scoring.service import ScoringService
from endpoints.scoring.weekly_service import WeeklyCompletionService
from endpoints.schedule.read_service import ScheduleReadService
from endpoints.transaction.workflow_service import TransactionWorkflowService
from verify_mod010 import race, full_tests as prior_ownership_tests
from verify_mod008 import tests as prior_week_tests
from verify_scoring_complete import remaining_tests as prior_scoring_tests
from endpoints.scoring.weekly_repository import WeeklyCompletionRepository

NOW=dt.datetime(2026,11,5,tzinfo=dt.timezone.utc)


def tests(engine,database):
    def query(statement,**params):
        with engine.begin() as conn:
            result=conn.execute(text(statement),params) if params else conn.exec_driver_sql(statement)
            return [dict(r) for r in result.mappings()] if result.returns_rows else []
    def reset():
        with engine.begin() as conn:
            conn.exec_driver_sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public; DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY); CREATE EXTENSION pg_trgm WITH SCHEMA public;')
            conn.exec_driver_sql((ROOT/'db/baselines/20261029/001_schema.sql').read_text())
            conn.exec_driver_sql((ROOT/'api/migrations/20261030_game_kickoff_tbd.sql').read_text())
        for filename in ('20261104_user_identity_unique.sql','20261104_week_score_identity.sql','20261104_ownership_integrity.sql'):
            raw=engine.raw_connection()
            try:
                with raw.cursor() as cur:cur.execute((ROOT/'api/migrations'/filename).read_text())
                raw.commit()
            finally:raw.close()
        query('''INSERT INTO "User" (id,email) VALUES (1,'alice@example.test'),(2,'bob@example.test');
            INSERT INTO "Sport" (id,name,"maxDraftRounds") VALUES (1,'Basketball',4);
            INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") VALUES (1,1,2026,'2026-01-01','2026-12-31');
            INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner,"seasonYear") VALUES
            (10,'First',1,2,'Active','{"roster":{"maxSwaps":5}}',1,2026),(20,'Other',1,1,'Active','{}',2,2026);
            INSERT INTO "LeagueMember" (id,"leagueId","userId","teamName","draftOrder") VALUES (11,10,1,'A',1),(12,10,2,'B',2),(21,20,2,'Other',1);
            INSERT INTO "School" (id,name) VALUES (1,'Synthetic');
            INSERT INTO "SportTeam" (id,"schoolId","sportId","displayName",tier) VALUES (101,1,1,'A',1),(102,1,1,'B',1),(103,1,1,'C',1);
            INSERT INTO "Conference" (id,name) VALUES (1,'Conference');
            INSERT INTO "SportConference" (id,"conferenceId","sportId","maxTeamsPerOwner") VALUES (500,1,1,3);
            INSERT INTO "ConferenceMembership" ("sportTeamId","sportConferenceId","sportId","seasonYear") VALUES (101,500,1,2026),(102,500,1,2026),(103,500,1,2026);
            INSERT INTO "Week" (id,"leagueId","weekNumber","startDate","endDate","isLocked") VALUES
            (100,10,1,'2026-10-01','2026-10-07',false),(101,10,2,'2026-10-08','2026-10-14',false),(102,10,3,'2026-10-15','2026-12-31',false),(200,20,1,'2026-10-01','2026-10-07',false);
            INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia") VALUES (10,11,101,1,'Draft'),(10,12,102,1,'Draft'),(20,21,101,1,'Draft');
            INSERT INTO "GameResult" (sport,"externalGameId",date,"homeTeamId","awayTeamId","homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName","sportSeasonId") VALUES
            (1,'first','2026-10-03',101,102,15,10,101,102,'A','B',1),(1,'second','2026-10-10',103,102,19,10,103,102,'C','B',1);''')
    def pending(kind='FREE_AGENT',status='PENDING_APPLY',week=101):
        query('''INSERT INTO "Transaction" (id,"leagueId","weekId",type,"memberFromId","memberToId",status,"fromTeamIds","toTeamIds")
            VALUES (1,10,:week,:kind,11,:recipient,:status,'[101]',CAST(:adds AS jsonb))''',week=week,kind=kind,status=status,recipient=12 if kind=='TRADE' else 11,adds='[102]' if kind=='TRADE' else '[103]')
    class StrictOwner:
        def __init__(self, owner):self.owner=owner;self.active=False
        @contextmanager
        def begin(self):
            assert not self.active, 'Nested connection acquisition'
            self.active=True
            try:
                with self.owner.begin() as conn:yield conn
            finally:self.active=False
        def connect(self):
            assert not self.active, 'Detached read inside supplied transaction'
            return self.owner.connect()
    def service(owner=engine,repository=None):
        strict=StrictOwner(owner)
        return WeeklyCompletionService(strict,ScoringService(strict,ScheduleReadService(strict)),TransactionWorkflowService(strict),repository)
    def state():
        return {table:query(f'SELECT * FROM "{table}" ORDER BY id') for table in ('Week','WeeklyTeamScore','LeagueTeamSlot','Transaction')}

    reset();pending();result=service().run(NOW)
    assert result=={'closed':[100,101,200],'applied':[1],'blocked':[],'failures':[]},result
    assert query('SELECT "pointDifferential" AS pd FROM "WeeklyTeamScore" WHERE "weekId"=101 AND "memberId"=11')[0]['pd']==9
    before=state();assert service().run(NOW)=={'closed':[],'applied':[],'blocked':[],'failures':[]};assert state()==before
    reset();pending();query('UPDATE "Week" SET "scoringComplete"=true WHERE id IN (100,101,200)')
    # A scored target is retained and reported, never applied retroactively.
    result=service().run(NOW);assert result['blocked'][0]['reason']=='target_already_scored';assert result['applied']==[]
    reset();pending();query('UPDATE "Week" SET "scoringComplete"=true WHERE id IN (100,200)');query('UPDATE "Week" SET "endDate"=\'2026-12-01\' WHERE id=101')
    assert service().run(NOW)['applied']==[1]

    # Fault after score insert, completion marker, next lock, or pending insert.
    faults=[]
    for marker in ('INSERT INTO "WeeklyTeamScore"','SET "scoringComplete"','SET "isLocked"','INSERT INTO "LeagueTeamSlot"'):
        reset();pending();before=state();hit=False
        def fail(conn,cursor,statement,params,context,many):
            nonlocal hit
            if marker in statement and not hit:hit=True;raise RuntimeError('synthetic failure')
        event.listen(engine,'after_cursor_execute',fail)
        try:result=service().run(NOW)
        finally:event.remove(engine,'after_cursor_execute',fail)
        assert hit and result['failures'][0]['leagueId']==10 and 200 in result['closed'],result
        after=state()
        for table in ('Week','WeeklyTeamScore','LeagueTeamSlot','Transaction'):
            # Other league may close. League10 changes only after a committed predecessor.
            if marker!='INSERT INTO "LeagueTeamSlot"':
                assert [r for r in after[table] if r.get('leagueId')==10]==[r for r in before[table] if r.get('leagueId')==10],(marker,table)
        assert query('SELECT status FROM "Transaction" WHERE id=1')[0]['status']=='PENDING_APPLY'
        retry=service().run(NOW);assert retry['failures']==[] and retry['applied']==[1],retry
        faults.append(marker)
    for table,condition in (('Week','NEW."scoringComplete"'),('WeeklyTeamScore','TRUE'),('Transaction',"NEW.status='COMPLETED'")):
        reset();pending()
        query(f'''CREATE FUNCTION reject_commit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF NEW."leagueId"=10 AND {condition} THEN RAISE EXCEPTION 'synthetic deferred failure' USING ERRCODE='23514'; END IF;
            RETURN NEW; END $$;
            CREATE CONSTRAINT TRIGGER reject_commit AFTER INSERT OR UPDATE ON "{table}" DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reject_commit();''')
        result=service().run(NOW);assert result['failures'] and 200 in result['closed'],result
        assert query('SELECT status FROM "Transaction" WHERE id=1')[0]['status']=='PENDING_APPLY'
        query(f'DROP TRIGGER reject_commit ON "{table}"');assert service().run(NOW)['applied']==[1]
    reset();pending('TRADE');result=service().run(NOW);assert result['applied']==[1] and not result['failures'],result

    boundaries=[]
    for boundary in ('first_period','missing_predecessor','wrong_league_target','week_zero'):
        reset()
        if boundary=='first_period':pending(week=100)
        elif boundary=='missing_predecessor':
            query('DELETE FROM "Week" WHERE id IN (100,102)')
            query('UPDATE "Week" SET "weekNumber"=3 WHERE id=101')
            pending()
        elif boundary=='wrong_league_target':pending(week=200)
        else:
            query('''INSERT INTO "Week" (id,"leagueId","weekNumber","startDate","endDate","isLocked") VALUES
                (99,10,0,'2026-09-20','2026-09-30',false)''')
            pending(week=100)
        result=service().run(NOW)
        assert not result['failures'] and 200 in result['closed'],result
        if boundary=='week_zero':assert result['applied']==[1] and result['closed'][:3]==[99,100,101],result
        else:
            assert not result['applied'] and not any(w in result['closed'] for w in (100,101)),result
            assert result['blocked'][0]['reason']==('missing_target' if boundary=='wrong_league_target' else 'missing_predecessor'),result
        boundaries.append(boundary)
    # Earlier command stays committed when the next command is invalid. Retry
    # repairs only the remaining pending command, then scores its target.
    reset();pending()
    query('''INSERT INTO "Transaction" (id,"leagueId","weekId",type,"memberFromId","memberToId",status,"fromTeamIds","toTeamIds")
        VALUES (2,10,101,'FREE_AGENT',12,12,'PENDING_APPLY','[102]','[103]')''')
    result=service().run(NOW)
    assert result['applied']==[1] and result['closed']==[100,200] and result['failures'],result
    assert query('SELECT id,status FROM "Transaction" ORDER BY id')==[{'id':1,'status':'COMPLETED'},{'id':2,'status':'PENDING_APPLY'}]
    query('UPDATE "Transaction" SET "toTeamIds"=\'[101]\' WHERE id=2')
    result=service().run(NOW);assert result['applied']==[2] and result['closed']==[101] and not result['failures'],result

    races={}
    reset();pending()
    reports={}
    def run_worker(owner,label,repository=None):
        reports[label]=service(owner,repository).run(NOW)
        assert not reports[label]['failures'] and not reports[label]['blocked'],reports[label]
    races['same_league_workers']=race(engine,database,lambda owner:run_worker(owner,'first'),lambda owner:run_worker(owner,'second'),'INSERT INTO "WeeklyTeamScore"',expected_second='ok')
    assert sorted(reports['first']['closed']+reports['second']['closed'])==[100,101,200]
    assert reports['first']['applied']+reports['second']['applied']==[1]
    assert query('SELECT count(*) AS n FROM "WeeklyTeamScore"')[0]['n']==5
    assert query('SELECT count(*) AS n FROM "LeagueTeamSlot" WHERE "acquiredVia"=\'FREE_AGENT\'')[0]['n']==1
    # ACCEPT must participate in the ownership mutex; otherwise it can enqueue
    # a command after the weekly candidate read but before target closure.
    reset();pending('TRADE','PROPOSED',100)
    races['accept_during_close']=race(engine,database,lambda owner:run_worker(owner,'first'),
        lambda owner:TransactionWorkflowService(owner).respond(UserActor(2,'bob'),10,1,'ACCEPT',12),
        'SELECT id,"weekId" FROM "Transaction"',expected_second='rejected')
    assert query('SELECT status FROM "Transaction" WHERE id=1')[0]['status']=='PROPOSED'
    class OnlyOtherLeague(WeeklyCompletionRepository):
        def candidates(self,conn,now):return [league for league in super().candidates(conn,now) if league==20]
    reset()
    races['independent_league']=race(engine,database,lambda owner:run_worker(owner,'first'),
        lambda owner:run_worker(owner,'second',OnlyOtherLeague()),'INSERT INTO "WeeklyTeamScore"',expected_second='ok',require_wait=False)
    assert reports['second']['closed']==[200]
    reset();query('UPDATE "Week" SET "endDate"=\'2026-12-01\' WHERE id=101')
    races['free_agent_submission_during_close']=race(engine,database,lambda owner:run_worker(owner,'first'),
        lambda owner:TransactionWorkflowService(owner).free_agency(UserActor(1,'alice'),10,100,1,11,103,101),
        'INSERT INTO "WeeklyTeamScore"',expected_second='ok')
    assert query('SELECT "weekId",status FROM "Transaction"')[0]=={'weekId':102,'status':'PENDING_APPLY'}
    # Exercise ties with the real schedule port and strict supplied-connection owner.
    reset();query('DELETE FROM "GameResult"');assert not service().run(NOW)['failures']
    return {'actual_scoring_catchup_replay':'PASS','no_new_scoring_retry':'PASS','scored_target_refusal':'PASS',
            'eligibility_boundaries':boundaries,'partial_command_progress_retry':'PASS','statement_faults':faults,'deferred_score_mark_apply_failures':'PASS','trade_and_free_agent':'PASS','races':races}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_mod013_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'mod013-owner');result=tests(engine,name)
        result['prior_ownership']=prior_ownership_tests(engine,name)
        result['prior_week_keys']=prior_week_tests(engine,name)
        result['prior_scoring']=prior_scoring_tests(engine,name)
        files=['api/utils/ownership.py','api/endpoints/scoring/repository.py','api/endpoints/scoring/rules.py',
               'api/endpoints/schedule/read_repository.py','api/endpoints/schedule/calendar_service.py',
               'api/migrations/20261030_game_kickoff_tbd.sql','api/migrations/20261104_user_identity_unique.sql',
               'api/migrations/20261104_week_score_identity.sql','api/migrations/20261104_ownership_integrity.sql',
               'api/endpoints/scoring/weekly_service.py','api/endpoints/scoring/weekly_repository.py','api/endpoints/scoring/service.py',
               'api/endpoints/schedule/read_service.py','api/endpoints/transaction/service.py','api/endpoints/transaction/workflow_service.py',
               'api/cronJobs/cronComputeWeeklyScores.py','scripts/modernization/verify_mod010.py','scripts/modernization/verify_mod008.py','scripts/modernization/verify_scoring_complete.py','scripts/modernization/verify_mod013.py','db/baselines/20261029/001_schema.sql']
        report={'result':'PASS','scope':'Owned marked loopback PostgreSQL only; no configured jobs or leagues',
                'tests':result,'sha256':{file:hashlib.sha256((ROOT/file).read_bytes()).hexdigest() for file in files}}
        (ROOT/'docs/modernization/evidence/mod-013-postgres-2026-11-05.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()
if __name__=='__main__':main()
