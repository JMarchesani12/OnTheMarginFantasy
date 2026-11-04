"""Ownership/reservation races on an owned marked loopback database only."""
import hashlib
import json
import threading
import time
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL, ROOT, engine_for, PLATFORM, candidate
from actors import UserActor
from endpoints.transaction.workflow_service import TransactionWorkflowService
from endpoints.draft.pick_service import DraftPickService
from verify_transaction_complete import FIXTURE as TRANSACTION_FIXTURE, tests as prior_transaction_tests
from verify_draft_complete import tests as prior_draft_tests


def race(engine, database, first_call, second_call, hold_fragment, expected_first='ok', expected_second='rejected', require_wait=True):
    first, second = engine_for(database, 'mod010-first'), engine_for(database, 'mod010-second')
    held, release = threading.Event(), threading.Event()
    outcomes = {}
    def hold(conn, cursor, statement, params, context, many):
        if hold_fragment in statement:
            held.set()
            if not release.wait(10): raise RuntimeError('Synthetic hold timeout')
    def run(label, owner, call):
        try:
            call(owner)
            outcomes[label] = 'ok'
        except ValueError:
            outcomes[label] = 'rejected'
        except DBAPIError as exc:
            outcomes[label] = 'database_error_' + str(exc.orig.pgcode)
        except Exception as exc:
            outcomes[label] = type(exc).__name__
    event.listen(first, 'after_cursor_execute', hold)
    a = threading.Thread(target=run, args=('first', first, first_call), daemon=True)
    b = threading.Thread(target=run, args=('second', second, second_call), daemon=True)
    a.start()
    try:
        assert held.wait(5), outcomes
        b.start()
        blocked = False
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with engine.connect() as conn:
                blocked = conn.execute(text('''SELECT EXISTS (SELECT 1 FROM pg_stat_activity
                    WHERE application_name='mod010-second' AND wait_event_type='Lock'
                    AND cardinality(pg_blocking_pids(pid))>0)''')).scalar_one()
            if blocked or not b.is_alive(): break
            time.sleep(.02)
    finally:
        release.set()
        a.join(10)
        if b.ident is not None: b.join(10)
        event.remove(first, 'after_cursor_execute', hold)
        first.dispose(); second.dispose()
    assert not a.is_alive() and not b.is_alive()
    assert outcomes == {'first': expected_first, 'second': expected_second}, outcomes
    assert blocked is require_wait, 'Unexpected ownership lock interaction'
    return {'observed_lock_wait': blocked, 'outcomes': outcomes}


def tests(engine, database):
    with engine.begin() as conn: conn.exec_driver_sql(TRANSACTION_FIXTURE)
    reservations = race(engine, database,
        lambda owner: TransactionWorkflowService(owner).free_agency(UserActor(1,'alice'),10,100,1,11,103,101),
        lambda owner: TransactionWorkflowService(owner).free_agency(UserActor(2,'bob'),10,100,1,12,103,102),
        'INSERT INTO "Transaction"')
    with engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM "Transaction"')).scalar_one() == 1
    return {'competing_pending_free_agent_reservations': reservations}



def full_tests(engine, database):
    migration=ROOT/'api/migrations/20261104_ownership_integrity.sql'
    preflight=ROOT/'db/preflights/20261104_ownership_integrity.sql'
    def query(statement, **params):
        with engine.begin() as conn:
            result=conn.execute(text(statement),params) if params else conn.exec_driver_sql(statement)
            return [dict(row) for row in result.mappings()] if result.returns_rows else []
    def file(path, fetch=False):
        raw=engine.raw_connection()
        try:
            with raw.cursor() as cursor:
                cursor.execute(path.read_text().removesuffix('COMMIT;\n') if fetch else path.read_text())
                result=dict(zip([d.name for d in cursor.description],cursor.fetchone())) if fetch else None
            raw.commit();return result
        except Exception:
            raw.rollback();raise
        finally:raw.close()
    def reset(guard=True):
        with engine.begin() as conn:
            conn.exec_driver_sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public; DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY); CREATE EXTENSION pg_trgm WITH SCHEMA public;')
            conn.exec_driver_sql((ROOT/'db/baselines/20261029/001_schema.sql').read_text())
            conn.exec_driver_sql((ROOT/'api/migrations/20261030_game_kickoff_tbd.sql').read_text())
        file(ROOT/'api/migrations/20261104_user_identity_unique.sql')
        file(ROOT/'api/migrations/20261104_week_score_identity.sql')
        query('''INSERT INTO "User" (id,email) VALUES (1,'alice@example.test'),(2,'bob@example.test'),(3,'third@example.test');
            INSERT INTO "Sport" (id,name,"maxDraftRounds") VALUES (1,'Synthetic',4);
            INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") VALUES (1,1,2025,'2025-01-01','2025-12-31');
            INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner,"seasonYear") VALUES
            (10,'First',1,3,'Drafting','{"draft":{"draftType":"SNAKE","selectionTime":60,"numberOfRounds":2,"graceSeconds":0,"timeoutAction":"AUTO-PICK"},"roster":{"maxSwaps":5}}',1,2025),
            (20,'Other',1,1,'Pre-Draft','{}',2,2025);
            INSERT INTO "LeagueMember" (id,"leagueId","userId","teamName","draftOrder") VALUES (11,10,1,'A',1),(12,10,2,'B',2),(13,10,3,'C',3),(21,20,2,'Other',1);
            INSERT INTO "School" (id,name) VALUES (1,'Synthetic');
            INSERT INTO "SportTeam" (id,"schoolId","sportId","displayName") VALUES (101,1,1,'A'),(102,1,1,'B'),(103,1,1,'C'),(104,1,1,'D'),(105,1,1,'E');
            INSERT INTO "Conference" (id,name) VALUES (1,'Conference');
            INSERT INTO "SportConference" (id,"conferenceId","sportId","maxTeamsPerOwner") VALUES (500,1,1,3);
            INSERT INTO "ConferenceMembership" ("sportTeamId","sportConferenceId","sportId","seasonYear") VALUES (101,500,1,2025),(102,500,1,2025),(103,500,1,2025),(104,500,1,2025),(105,500,1,2025);
            INSERT INTO "Week" (id,"leagueId","weekNumber","isLocked") VALUES (100,10,1,false),(101,10,2,false),(200,20,1,false);
            INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia") VALUES (10,11,101,1,'Draft'),(10,12,102,1,'Draft'),(20,21,101,1,'Draft');
            INSERT INTO "DraftState" ("leagueId",status,"currentOverallPickNumber","currentMemberId","expiresAt") VALUES (10,'live',1,11,now()+interval '60 seconds');
            INSERT INTO "DraftTurn" ("leagueId","overallPickNumber","memberId") VALUES (10,1,11),(10,2,12),(10,3,13),(10,4,13),(10,5,12),(10,6,11);''')
        if guard:file(migration)
    def state():
        return {table:query(f'SELECT * FROM "{table}" ORDER BY 1') for table in ('LeagueTeamSlot','Transaction','DraftPick','DraftState')}
    def pending(txid, member, adds, drops=(), week=100, kind='FREE_AGENT', to_member=None):
        query('''INSERT INTO "Transaction" (id,"leagueId","weekId",type,"memberFromId","memberToId",status,"fromTeamIds","toTeamIds")
            VALUES (:id,10,:week,:kind,:member,:to_member,'PENDING_APPLY',CAST(:drops AS jsonb),CAST(:adds AS jsonb))''',
            id=txid,week=week,kind=kind,member=member,to_member=to_member or member,drops=json.dumps(list(drops)),adds=json.dumps(list(adds)))
    def insert_slot(member,team,start,end=None,league=10):
        query('''INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","droppedWeek","acquiredVia")
            VALUES (:league,:member,:team,:start,:end,'Synthetic')''',league=league,member=member,team=team,start=start,end=end)
    def rejected(call, code=None):
        before=state()
        try:call()
        except DBAPIError as exc:
            if code:assert exc.orig.pgcode==code,exc.orig.pgcode
        except ValueError:
            assert code is None
        else:raise AssertionError('Expected ownership conflict')
        assert state()==before,'Conflict changed committed ownership/command state'

    reset();file(migration)
    # Valid empty, adjacent and future ranges coexist; equal endpoints are not
    # ownership and week0 is a supported acquisition default.
    insert_slot(11,103,0,3);insert_slot(12,103,3,5);insert_slot(13,103,5)
    insert_slot(11,103,2,2);insert_slot(12,103,2,2)
    assert file(preflight,True)['overlapping_pairs']==0
    rejected(lambda:insert_slot(11,103,4,6),'23P01')
    rejected(lambda:insert_slot(11,104,-1),'23514')
    rejected(lambda:insert_slot(11,104,3,2),'23514')
    rejected(lambda:insert_slot(21,104,1),'23503')
    # Existing valid future ownership must not be truncated or overwritten by
    # an open-ended manual allocation at an earlier week.
    insert_slot(13,104,5)
    rejected(lambda:DraftPickService(engine).allocate_manual_for_job(10,11,104,acquired_week=1),'23P01')
    for dirty in ('overlap','reversed','member'):
        reset(False)
        if dirty=='overlap':insert_slot(12,101,2)
        elif dirty=='reversed':insert_slot(11,103,3,2)
        else:insert_slot(21,103,1)
        counts=file(preflight,True)
        key={'overlap':'overlapping_pairs','reversed':'reversed_intervals','member':'wrong_member_league_slots'}[dirty]
        assert counts[key]>0
        before=state()
        try:file(migration)
        except psycopg2.Error as exc:assert 'reviewed remediation' in str(exc)
        else:raise AssertionError('Dirty ownership history accepted')
        assert state()==before
        assert query("SELECT conname FROM pg_constraint WHERE conname='LeagueTeamSlot_interval_check'")==[]
    # Replay checks must reject a same-named but weaker interval check.
    reset(False)
    query('ALTER TABLE "LeagueTeamSlot" ADD CONSTRAINT "LeagueTeamSlot_interval_check" CHECK ("acquiredWeek">=-1)')
    try:file(migration)
    except psycopg2.Error as exc:assert 'unexpected definition' in str(exc)
    else:raise AssertionError('Weaker existing interval check accepted')

    races=[]
    for guarded in (False,True):
        for mode in ('manual','live','timeout','different_trades','cap','independent_league'):
            reset(guarded)
            if mode in ('manual','live','timeout'):
                pending(1001,12,[103])
                def first(owner):
                    picker=DraftPickService(owner)
                    if mode=='manual':picker.allocate_manual_for_job(10,11,103,acquired_week=1)
                    elif mode=='live':picker.pick_live_for_job(10,11,103,acquired_week=1)
                    else:
                        picker._choose_random_team_for_auto_pick=lambda **kwargs:103
                        picker.process_timeout_for_job(10)
                if mode=='timeout':query("UPDATE \"DraftState\" SET \"expiresAt\"=now()-interval '120 seconds' WHERE \"leagueId\"=10")
                second=lambda owner:TransactionWorkflowService(owner).apply_free_agent_for_job(1001)
                fragment='INSERT INTO "LeagueTeamSlot"'
            elif mode=='different_trades':
                pending(1001,11,[102],[101],week=101,kind='TRADE',to_member=12)
                pending(1002,11,[],[101],week=101,kind='TRADE',to_member=13)
                first=lambda owner:TransactionWorkflowService(owner).apply_trade(1001)
                second=lambda owner:TransactionWorkflowService(owner).apply_trade(1002)
                fragment='INSERT INTO "LeagueTeamSlot"'
            elif mode=='cap':
                query('UPDATE "SportConference" SET "maxTeamsPerOwner"=2')
                pending(1001,11,[103]);pending(1002,11,[104])
                first=lambda owner:TransactionWorkflowService(owner).apply_free_agent_for_job(1001)
                second=lambda owner:TransactionWorkflowService(owner).apply_free_agent_for_job(1002)
                fragment='INSERT INTO "LeagueTeamSlot"'
            else:
                first=lambda owner:TransactionWorkflowService(owner).free_agency_for_job(10,100,1,11,103,101)
                second=lambda owner:TransactionWorkflowService(owner).free_agency_for_job(20,200,1,21,104,101)
                fragment='INSERT INTO "Transaction"'
            result=race(engine,database,first,second,fragment,expected_second='ok' if mode=='independent_league' else 'rejected',require_wait=mode!='independent_league')
            result.update(mode=mode,database_guard=guarded);races.append(result)
            assert file(preflight,True)['overlapping_pairs']==0
            if mode!='independent_league':
                slots=query('SELECT count(*) AS owners FROM "LeagueTeamSlot" WHERE "leagueId"=10 AND "sportTeamId"=:team AND ("droppedWeek" IS NULL OR "droppedWeek">2) AND "acquiredWeek"<=2',team=101 if mode=='different_trades' else 103)
                assert slots[0]['owners']==1
                rejected(lambda:second(engine))
    reset()
    def direct(owner, member):
        with owner.begin() as conn:
            conn.execute(text('''INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia")
                VALUES (10,:member,103,1,'Direct synthetic')'''), {'member': member})
    exclusion_race=race(engine,database,lambda owner:direct(owner,11),lambda owner:direct(owner,12),
                        'INSERT INTO "LeagueTeamSlot"',expected_second='database_error_23P01')
    assert len(query('SELECT id FROM "LeagueTeamSlot" WHERE "leagueId"=10 AND "sportTeamId"=103'))==1
    # Statement/commit failures preserve both ownership and pending status.
    for deferred in (False,True):
        reset();pending(1001,11,[103],[101])
        query('''CREATE FUNCTION fail_slot() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic ownership failure'; END $$;''')
        query(('CREATE CONSTRAINT TRIGGER fail_slot AFTER INSERT ON "LeagueTeamSlot" DEFERRABLE INITIALLY DEFERRED' if deferred else 'CREATE TRIGGER fail_slot BEFORE INSERT ON "LeagueTeamSlot"')+' FOR EACH ROW EXECUTE FUNCTION fail_slot()')
        rejected(lambda:TransactionWorkflowService(engine).apply_free_agent_for_job(1001))
    return {'schema_empty_adjacent_future_exclusion_check_fk':'PASS','dirty_refusal_and_shape_replay':'PASS',
            'application_statement_commit_rollback':'PASS','cross_command_races':races,'direct_exclusion_race':exclusion_race}

def main():
    admin = psycopg2.connect(dbname='postgres', **LOCAL); admin.autocommit=True
    name='otm_mod010_'+uuid4().hex; created=False; engine=None
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cursor.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'mod010-owner')
        result=tests(engine,name)
        result['integrity']=full_tests(engine,name)
        result['prior_transaction']=prior_transaction_tests(engine,name)
        result['prior_draft']=prior_draft_tests(engine,name)
        with engine.begin() as conn:
            conn.exec_driver_sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public; DROP SCHEMA IF EXISTS auth CASCADE')
            conn.exec_driver_sql(PLATFORM)
            conn.exec_driver_sql(candidate())
            assert conn.execute(text("SELECT count(*) FROM pg_constraint WHERE conrelid='public.\"LeagueTeamSlot\"'::regclass AND conname IN ('LeagueTeamSlot_interval_check','LeagueTeamSlot_no_overlap','LeagueTeamSlot_same_league_member_fkey')")).scalar_one()==3
        result['current_snapshot_initialization']='PASS'
        files=['api/endpoints/transaction/workflow_service.py','api/endpoints/transaction/service.py',
               'api/endpoints/draft/pick_service.py','api/utils/ownership.py',
               'api/migrations/20261104_ownership_integrity.sql','db/preflights/20261104_ownership_integrity.sql',
               'scripts/modernization/verify_mod010.py','db/tables.sql',
               'db/baselines/20261029/001_schema.sql','scripts/modernization/verify_transaction_complete.py',
               'scripts/modernization/verify_draft_complete.py','scripts/modernization/assess_postgres.py']
        report={'result':'PASS','scope':'Owned marked synthetic PostgreSQL; no configured ownership commands',
                'tests':result,'sha256':{file:hashlib.sha256((ROOT/file).read_bytes()).hexdigest() for file in files}}
        (ROOT/'docs/modernization/evidence/mod-010-postgres-2026-11-04.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cursor:cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
