"""MOD-012 admission and atomic creation on an owned marked loopback DB."""
import hashlib
import json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL, ROOT, engine_for
from actors import UserActor
from endpoints.league.administration.service import LeagueAdminService
from endpoints.league.admission.service import AdmissionService
from endpoints.schedule.calendar_service import ScheduleCalendarService
from verify_mod010 import race
from verify_league_creation import tests as prior_creation_tests
from verify_admission_approval import tests as prior_admission_tests
from verify_schedule_calendar import tests as prior_calendar_tests


def tests(engine, database):
    def query(statement, **params):
        with engine.begin() as conn:
            result=conn.execute(text(statement),params) if params else conn.exec_driver_sql(statement)
            return [dict(row) for row in result.mappings()] if result.returns_rows else []
    def apply(path):
        raw=engine.raw_connection()
        try:
            with raw.cursor() as cursor:cursor.execute(path.read_text())
            raw.commit()
        except Exception:
            raw.rollback();raise
        finally:raw.close()
    def reset():
        with engine.begin() as conn:
            conn.exec_driver_sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public; DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY); CREATE EXTENSION pg_trgm WITH SCHEMA public;')
            conn.exec_driver_sql((ROOT/'db/baselines/20261029/001_schema.sql').read_text())
            conn.exec_driver_sql((ROOT/'api/migrations/20261030_game_kickoff_tbd.sql').read_text())
        for filename in ('20261104_user_identity_unique.sql','20261104_week_score_identity.sql','20261104_ownership_integrity.sql'):
            apply(ROOT/'api/migrations'/filename)
        query('''INSERT INTO "User" (id,email) VALUES (1,'commissioner@example.test'),(2,'second@example.test'),(3,'third@example.test'),(4,'fourth@example.test');
            INSERT INTO "Sport" (id,name,"maxDraftRounds","maxPlayersToHaveMaxRounds") VALUES (1,'Basketball',8,2);
            INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") VALUES (1,1,2026,'2026-11-02','2026-11-22');
            INSERT INTO "SportSeasonSubdivision" (id,"sportSeasonId",code,name,"regularSeasonStart","regularSeasonEnd") VALUES (1,1,'D1','Synthetic','2026-11-02','2026-11-22');
            INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner,"seasonYear") VALUES (10,'Existing',1,1,'Pre-Draft','{"draft":{"numberOfRounds":8},"timezone":"UTC"}',1,2026);
            INSERT INTO "LeagueMember" (id,"leagueId","userId","teamName","draftOrder") VALUES (11,10,1,'Creator',1);
            INSERT INTO "LeagueJoinRequest" (id,"leagueId","userId",status,"teamName") VALUES (101,10,2,'PENDING','Second'),(102,10,3,'PENDING','Third');''')
    def state():
        return {table:query(f'SELECT * FROM "{table}" ORDER BY id') for table in ('League','LeagueMember','LeagueJoinRequest','Week')}

    reset();requests={}
    def request(owner,label):
        row=AdmissionService(owner).create_request(UserActor(4,'fourth'),10,message=label,team_name=label)
        requests[label]=row
    pending_race=race(engine,database,lambda owner:request(owner,'first'),lambda owner:request(owner,'second'),
                      'INSERT INTO "LeagueJoinRequest"',expected_second='ok')
    assert requests['first']==requests['second']
    assert requests['first']['message']=='first'
    assert query('SELECT \"teamName\" FROM \"LeagueJoinRequest\" WHERE \"userId\"=4')[0]['teamName']=='first'
    assert query('SELECT count(*) AS n FROM "LeagueJoinRequest" WHERE "userId"=4')[0]['n']==1
    approvals=[]
    for supplied, same in ((False,False),(False,True),(True,False),(True,True)):
        reset();approved={}
        def approve(owner,label,request_id):
            service=AdmissionService(owner)
            if supplied:
                with owner.begin() as conn:result=service.approve_request_in_transaction(conn,10,request_id,1)
            else:result=service.approve_request(UserActor(1,'commissioner'),10,request_id)
            approved[label]=result['member']
        result=race(engine,database,lambda owner:approve(owner,'first',101),
                    lambda owner:approve(owner,'second',101 if same else 102),
                    'INSERT INTO "LeagueMember"',expected_second='AdmissionRejected' if same else 'ok')
        current=state();size=2 if same else 3
        assert len(current['LeagueMember'])==size
        assert sorted(row['draftOrder'] for row in current['LeagueMember'])==list(range(1,size+1))
        assert current['League'][0]['numPlayers']==size
        assert current['League'][0]['settings']['draft']['numberOfRounds']==(8 if same else 7)
        result.update(supplied_connection=supplied,same_request=same,member_count=size)
        approvals.append(result)

    reset()
    query('UPDATE "League" SET "numPlayers"=99 WHERE id=10')
    AdmissionService(engine).approve_request(UserActor(1,'commissioner'),10,101)
    assert query('SELECT "numPlayers",settings FROM "League" WHERE id=10')[0]=={'numPlayers':2,'settings':{'draft':{'numberOfRounds':8},'timezone':'UTC'}}

    observer=engine_for(database,'mod012-visibility-observer')
    admin=LeagueAdminService(engine);calendar=ScheduleCalendarService(engine)
    def payload():
        return dict(name='Atomic league',sport=1,numPlayers=99,status='Pre-Draft',settings={'timezone':'America/New_York','draft':{'numberOfRounds':8}},
                    draftDate=None,commissioner=1,seasonYear=2026,isDiscoverable=True,teamName='Creator team')
    seen=[]
    def initialize(league_id,conn=None):
        assert conn is not None
        rows=calendar.ensure_weeks_for_job(league_id,conn=conn)
        assert [row['weekNumber'] for row in rows]==[1,2,3]
        with observer.connect() as separate:
            assert separate.execute(text('SELECT count(*) FROM "League" WHERE id=:id'),{'id':league_id}).scalar_one()==0
            assert separate.execute(text('SELECT count(*) FROM "Week" WHERE "leagueId"=:id'),{'id':league_id}).scalar_one()==0
        seen.append(league_id)
        return rows
    try:
        reset();created=admin.create(UserActor(1,'commissioner'),payload(),initialize)
        assert created['numPlayers']==1
        league_id=created['id']
        assert query('SELECT count(*) AS n FROM "LeagueMember" WHERE "leagueId"=:id',id=league_id)[0]['n']==1
        first=calendar.ensure_weeks_for_job(league_id)
        second=calendar.ensure_weeks_for_job(league_id)
        assert first==second and len(first)==3
        # Failure during week insertion or at deferred commit restores all new
        # league/member/week rows. Successful retry creates one usable league.
        for deferred in (False,True):
            reset();before=state()
            query('''CREATE FUNCTION fail_calendar() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN IF NEW."weekNumber"=2 THEN RAISE EXCEPTION 'synthetic calendar failure' USING ERRCODE='23514'; END IF; RETURN NEW; END $$;''')
            query(('CREATE CONSTRAINT TRIGGER fail_calendar AFTER INSERT ON "Week" DEFERRABLE INITIALLY DEFERRED' if deferred else 'CREATE TRIGGER fail_calendar BEFORE INSERT ON "Week"')+' FOR EACH ROW EXECUTE FUNCTION fail_calendar()')
            try:admin.create(UserActor(1,'commissioner'),payload(),initialize)
            except DBAPIError as exc:assert exc.orig.pgcode=='23514'
            else:raise AssertionError('Calendar failure missing')
            assert state()==before,'Calendar/commit failure left partial creation'
            query('DROP TRIGGER fail_calendar ON "Week"')
            retried=admin.create(UserActor(1,'commissioner'),payload(),initialize)
            current=state()
            assert len(current['League'])==2 and len(current['LeagueMember'])==2 and len(current['Week'])==3
            assert retried['numPlayers']==1
            assert len(calendar.ensure_weeks_for_job(retried['id']))==3
        # Missing season metadata fails before returning success and cannot
        # commit an unusable league. Restoring configuration permits retry.
        reset();query('DELETE FROM "SportSeason"');before=state()
        try:admin.create(UserActor(1,'commissioner'),payload(),initialize)
        except ValueError:pass
        else:raise AssertionError('Missing season initialized a league')
        assert state()==before
        query('''INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") VALUES (1,1,2026,'2026-11-02','2026-11-22');
            INSERT INTO "SportSeasonSubdivision" (id,"sportSeasonId",code,name,"regularSeasonStart","regularSeasonEnd") VALUES (1,1,'D1','Synthetic','2026-11-02','2026-11-22');''')
        admin.create(UserActor(1,'commissioner'),payload(),initialize)
        assert len(state()['League'])==2 and len(state()['Week'])==3
    finally:observer.dispose()
    return {'competing_pending_request_reuse':pending_race,'uncapped_approval_races':approvals,
            'derived_current_member_counts':'PASS','atomic_uncommitted_calendar_visibility':'PASS',
            'planning_statement_commit_rollback_retry':'PASS','standalone_calendar_idempotency':'PASS'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_mod012_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cursor.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'mod012-owner')
        result=tests(engine,name)
        result['prior_creation']=prior_creation_tests(engine,name)
        result['prior_admission']=prior_admission_tests(engine,name)
        result['prior_calendar']=prior_calendar_tests(engine)
        files=['api/endpoints/league/admission/service.py','api/endpoints/league/administration/service.py',
               'api/endpoints/schedule/calendar_service.py','api/endpoints/league/admission/repository.py',
               'scripts/modernization/verify_mod012.py','scripts/modernization/verify_league_creation.py',
               'scripts/modernization/verify_admission_approval.py','scripts/modernization/verify_schedule_calendar.py',
               'db/baselines/20261029/001_schema.sql']
        report={'result':'PASS','scope':'Owned marked loopback PostgreSQL only; no configured leagues/admissions/jobs',
                'tests':result,'sha256':{file:hashlib.sha256((ROOT/file).read_bytes()).hexdigest() for file in files}}
        (ROOT/'docs/modernization/evidence/mod-012-postgres-2026-11-04.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cursor:cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
