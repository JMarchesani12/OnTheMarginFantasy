"""Existing MOD-011 repairs on actual baseline constraints; owned loopback only."""
import hashlib
import json
import threading
import time
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL, ROOT, engine_for
from actors import UserActor
from endpoints.league.admission.service import AdmissionService
from endpoints.league.admission.contracts import AdmissionDenied, AdmissionRejected
from verify_admission_slice import tests as prior_cancel_tests
from verify_admission_create_deny import current_tests as prior_deny_tests


def tests(engine, database):
    with engine.begin() as conn:
        conn.exec_driver_sql('''DROP SCHEMA public CASCADE; CREATE SCHEMA public;
            CREATE EXTENSION pg_trgm WITH SCHEMA public;
            CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY);''')
        conn.exec_driver_sql((ROOT / 'db/baselines/20261029/001_schema.sql').read_text())
        conn.exec_driver_sql((ROOT / 'api/migrations/20261030_game_kickoff_tbd.sql').read_text())
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cursor:
            cursor.execute((ROOT / 'api/migrations/20261104_user_identity_unique.sql').read_text())
        raw.commit()
    finally:
        raw.close()
    with engine.begin() as conn:
        conn.exec_driver_sql('''INSERT INTO "User" (id,email) VALUES
            (1,'commissioner@example.test'),(2,'applicant@example.test'),
            (3,'other@example.test'),(4,'outsider@example.test');
            INSERT INTO "Sport" (id,name) VALUES (1,'Synthetic');
            INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner,"seasonYear")
            VALUES (10,'First',1,2,'Pre-Draft','{}',1,2026),(20,'Other',1,2,'Pre-Draft','{}',2,2026);''')
    service = AdmissionService(engine)
    commissioner, owner = UserActor(1, 'commissioner'), UserActor(2, 'applicant')

    def reset():
        with engine.begin() as conn:
            conn.exec_driver_sql('''DELETE FROM "LeagueJoinRequest";
                INSERT INTO "LeagueJoinRequest" (id,"leagueId","userId",status,message) VALUES
                (100,10,2,'PENDING','Synthetic pending'),(101,10,2,'APPROVED','Synthetic approved'),
                (200,20,1,'PENDING','Synthetic foreign');''')

    def state():
        with engine.connect() as conn:
            return [dict(row) for row in conn.execute(text('SELECT * FROM "LeagueJoinRequest" ORDER BY id')).mappings()]

    def reject(operation, error=AdmissionRejected, sqlstate=None):
        before = state()
        try:
            operation()
        except error as exc:
            if sqlstate is not None:
                assert getattr(exc.orig, 'pgcode', None) == sqlstate
        else:
            raise AssertionError('Invalid request transition accepted')
        assert state() == before

    for action, actor, status, resolver in (('deny', commissioner, 'DENIED', 1), ('cancel', owner, 'CANCELLED', None)):
        reset()
        method = getattr(service, action + '_request')
        result = method(actor, 10, 100)
        assert set(result) == {'id', 'createdAt', 'leagueId', 'userId', 'status', 'message', 'resolvedAt', 'resolvedByUserId'}
        assert result['id'] == 100 and result['status'] == status and result['resolvedByUserId'] == resolver
        assert (result['leagueId'], result['userId'], result['message']) == (10, 2, 'Synthetic pending')
        assert result['resolvedAt'] is not None
        reject(lambda: method(actor, 10, 100))
        reject(lambda: method(actor, 10, 101))
        reject(lambda: method(actor, 10, 200))
        reset()
        reject(lambda: method(UserActor(4, 'outsider'), 10, 100), AdmissionDenied)
        for invalid in ('pending', 'denied', 'cancelled'):
            def invalid_status():
                with engine.begin() as conn:
                    conn.execute(text('UPDATE "LeagueJoinRequest" SET status=:status WHERE id=100'), {'status': invalid})
            reject(invalid_status, DBAPIError, sqlstate='23514')

        def fail(conn, cursor, statement, params, context, many):
            if 'UPDATE "LeagueJoinRequest"' in statement:
                raise RuntimeError('synthetic post-write failure')
        event.listen(engine, 'after_cursor_execute', fail)
        try:
            reject(lambda: method(actor, 10, 100), RuntimeError)
        finally:
            event.remove(engine, 'after_cursor_execute', fail)
        with engine.begin() as conn:
            conn.exec_driver_sql('''CREATE FUNCTION fail_resolution_commit() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'synthetic deferred failure' USING ERRCODE='23514'; END $$;
                CREATE CONSTRAINT TRIGGER resolution_commit AFTER UPDATE ON "LeagueJoinRequest"
                DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fail_resolution_commit();''')
        reject(lambda: method(actor, 10, 100), DBAPIError, sqlstate='23514')
        with engine.begin() as conn:
            conn.exec_driver_sql('DROP TRIGGER resolution_commit ON "LeagueJoinRequest"; DROP FUNCTION fail_resolution_commit()')

    races = []
    for first_action, second_action in (('deny', 'cancel'), ('cancel', 'deny')):
        reset()
        first, second = engine_for(database, 'mod011-first'), engine_for(database, 'mod011-second')
        written, release = threading.Event(), threading.Event()
        outcomes = {}
        def hold(conn, cursor, statement, params, context, many):
            if 'UPDATE "LeagueJoinRequest"' in statement:
                written.set()
                if not release.wait(10):
                    raise RuntimeError('Synthetic hold timeout')
        def run(label, target, action):
            try:
                actor = commissioner if action == 'deny' else owner
                result = getattr(AdmissionService(target), action + '_request')(actor, 10, 100)
                outcomes[label] = result['status']
            except AdmissionRejected:
                outcomes[label] = 'rejected'
            except Exception as exc:
                outcomes[label] = type(exc).__name__
        event.listen(first, 'after_cursor_execute', hold)
        a = threading.Thread(target=run, args=('first', first, first_action), daemon=True)
        b = threading.Thread(target=run, args=('second', second, second_action), daemon=True)
        a.start()
        try:
            assert written.wait(5)
            b.start()
            blocked = False
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with engine.connect() as conn:
                    blocked = conn.execute(text('''SELECT EXISTS (SELECT 1 FROM pg_stat_activity
                        WHERE application_name='mod011-second' AND wait_event_type='Lock'
                        AND cardinality(pg_blocking_pids(pid))>0)''')).scalar_one()
                if blocked:
                    break
                time.sleep(.02)
            assert blocked, 'No competing resolution lock wait'
        finally:
            release.set()
            a.join(10)
            if b.ident is not None:
                b.join(10)
            event.remove(first, 'after_cursor_execute', hold)
            first.dispose()
            second.dispose()
        expected = 'DENIED' if first_action == 'deny' else 'CANCELLED'
        assert not a.is_alive() and not b.is_alive()
        assert outcomes == {'first': expected, 'second': 'rejected'}, outcomes
        assert state()[0]['status'] == expected
        races.append({'first': first_action, 'second': second_action, 'observed_lock_wait': True, 'outcomes': outcomes})
    return {'actual_baseline_check_fk_and_current_migrations': 'PASS',
            'canonical_status_exact_response_once_only': 'PASS', 'authority_owner_approved_foreign_scope': 'PASS',
            'statement_and_commit_rollback': 'PASS', 'competing_denial_cancellation': races}


def main():
    admin = psycopg2.connect(dbname='postgres', **LOCAL)
    admin.autocommit = True
    name = 'otm_mod011_' + uuid4().hex
    created, engine = False, None
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cursor.fetchone()[0] == 'otm-modernization-assessment-20261029-synthetic-only', 'Refusing unmarked server'
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            created = True
        engine = engine_for(name, 'mod011-owner')
        result = tests(engine, name)
        with engine.begin() as conn:
            conn.exec_driver_sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public')
        result['prior_listing_cancellation'] = prior_cancel_tests(engine, name)
        result['prior_creation_denial'] = prior_deny_tests(engine, name)
        files = ['api/endpoints/league/admission/service.py', 'api/endpoints/league/admission/repository.py',
                 'db/baselines/20261029/001_schema.sql', 'api/migrations/20261030_game_kickoff_tbd.sql',
                 'api/migrations/20261104_user_identity_unique.sql', 'scripts/modernization/verify_mod011.py',
                 'scripts/modernization/verify_admission_slice.py', 'scripts/modernization/verify_admission_create_deny.py']
        report = {'result': 'PASS', 'scope': 'Owned marked disposable PostgreSQL; no hosted admission writes',
                  'tests': result, 'sha256': {file: hashlib.sha256((ROOT / file).read_bytes()).hexdigest() for file in files}}
        (ROOT / 'docs/modernization/evidence/mod-011-postgres-2026-11-04.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()


if __name__ == '__main__':
    main()
