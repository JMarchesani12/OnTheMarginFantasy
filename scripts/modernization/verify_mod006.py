"""MOD-006 on owned marked loopback PostgreSQL; no .env/configured DSN.

Creates/drops only a random database, using the existing synthetic harness.
The frozen schema and kickoff migration are applied before MOD-006.
"""
import hashlib
import json
import threading
import time
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from sqlalchemy import event, text
from assess_postgres import LOCAL, ROOT, engine_for
from endpoints.user.service import UserService
from endpoints.user.contracts import ProfileSubject, ProfileAlreadyExists, ProfileCreationRejected
from verify_profile_creation import creation_tests

MIGRATION = ROOT / 'api/migrations/20261104_user_identity_unique.sql'
PREFLIGHT = ROOT / 'db/preflights/20261104_user_identity.sql'
A = '00000000-0000-4000-8000-000000000001'
B = '00000000-0000-4000-8000-000000000002'


def tests(engine, database):
    def reset(legacy=True):
        with engine.begin() as conn:
            conn.exec_driver_sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public; DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY); CREATE EXTENSION pg_trgm WITH SCHEMA public;')
            conn.exec_driver_sql((ROOT / 'db/baselines/20261029/001_schema.sql').read_text())
            conn.exec_driver_sql((ROOT / 'api/migrations/20261030_game_kickoff_tbd.sql').read_text())
            conn.execute(text('INSERT INTO auth.users VALUES (:a),(:b)'), {'a': A, 'b': B})
            if legacy:
                conn.exec_driver_sql('''INSERT INTO "User" (email,"displayName") VALUES
                    ('legacy-a@example.test','Legacy A'),('legacy-b@example.test','Legacy B');''')

    def state():
        with engine.connect() as conn:
            return [dict(row) for row in conn.execute(text('SELECT * FROM "User" ORDER BY id')).mappings()]

    def migrate():
        raw = engine.raw_connection()
        try:
            with raw.cursor() as cursor:
                cursor.execute(MIGRATION.read_text())
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()

    def preflight():
        raw = engine.raw_connection()
        try:
            with raw.cursor() as cursor:
                # Keep the exact SELECT under its read-only transaction, fetch
                # before the terminal COMMIT discards the result description.
                cursor.execute(PREFLIGHT.read_text().removesuffix('COMMIT;\n'))
                columns = [column.name for column in cursor.description]
                row = dict(zip(columns, cursor.fetchone()))
            raw.commit()
            return row
        finally:
            raw.rollback()
            raw.close()

    reset()
    with engine.begin() as conn:
        conn.execute(text('INSERT INTO "User" (uuid,email) VALUES (:id,\'duplicate-a@example.test\'),(:id,\'duplicate-b@example.test\')'), {'id': A})
    assert preflight() == {'total_profiles': 4, 'unlinked_profiles': 2,
                          'duplicate_subject_groups': 1, 'profiles_in_duplicate_groups': 2}
    before = state()
    try:
        migrate()
    except psycopg2.Error as exc:
        assert 'reviewed remediation' in str(exc)
        assert A not in str(exc) and 'example.test' not in str(exc)
    else:
        raise AssertionError('Dirty migration accepted')
    assert state() == before
    with engine.connect() as conn:
        assert not conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.\"User\"'::regclass AND conname='User_uuid_key')")).scalar_one()

    reset()
    before = state()
    migrate()
    migrate()
    assert state() == before
    assert preflight() == {'total_profiles': 2, 'unlinked_profiles': 2,
                          'duplicate_subject_groups': 0, 'profiles_in_duplicate_groups': 0}
    service = UserService(engine)
    alice = service.create_profile(ProfileSubject(A, 'alice@example.test'), 'Alice')
    for operation in (
        lambda: service.create_profile_for_job('other@example.test', 'Other', A),
        lambda: service.create_profile(ProfileSubject(B, 'alice@example.test'), 'Borrow'),
        lambda: service.create_profile(ProfileSubject('00000000-0000-4000-8000-000000000099', 'missing@example.test'), 'Missing'),
    ):
        before = state()
        try:
            operation()
        except ProfileCreationRejected:
            pass
        else:
            raise AssertionError('UUID/email/FK conflict accepted')
        assert state() == before
    assert service.get_profile_by_uuid_for_job(A) == alice
    service.create_profile_for_job('legacy-c@example.test')
    assert len([row for row in state() if row['uuid'] is None]) == 3

    # RLS-filtered counts cannot establish migration readiness. A limited
    # reader must get a deliberate database denial instead of false zeroes.
    role = 'mod006_reader_' + uuid4().hex
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE ROLE "' + role + '" NOLOGIN')
        conn.exec_driver_sql('GRANT USAGE ON SCHEMA public TO "' + role + '"')
        conn.exec_driver_sql('GRANT SELECT ON "User" TO "' + role + '"')
        conn.exec_driver_sql('ALTER TABLE "User" ENABLE ROW LEVEL SECURITY')
    raw = engine.raw_connection()
    try:
        raw.autocommit = True
        with raw.cursor() as cursor:
            cursor.execute('SET ROLE "' + role + '"')
            try:
                cursor.execute(PREFLIGHT.read_text().removesuffix('COMMIT;\n'))
            except psycopg2.errors.InsufficientPrivilege:
                pass
            else:
                raise AssertionError('RLS-filtered preflight misleadingly succeeded')
    finally:
        with raw.cursor() as cursor:
            cursor.execute('ROLLBACK; RESET ROLE')
        raw.close()
        with engine.begin() as conn:
            conn.exec_driver_sql('DROP OWNED BY "' + role + '"')
            conn.exec_driver_sql('DROP ROLE "' + role + '"')

    # Replay must not mistake an unrelated or nulls-not-distinct unique key
    # for the intended nullable-subject policy.
    for constraint in ('UNIQUE (email)', 'UNIQUE NULLS NOT DISTINCT (uuid)'):
        reset(legacy=False)
        with engine.begin() as conn:
            conn.exec_driver_sql('ALTER TABLE "User" ADD CONSTRAINT "User_uuid_key" ' + constraint)
        try:
            migrate()
        except psycopg2.Error as exc:
            assert 'unexpected definition' in str(exc)
        else:
            raise AssertionError('Drifted identity constraint accepted: ' + constraint)

    races = []
    for second_subject, second_email in ((A, 'alice@example.test'), (A, 'peer@example.test'), (B, 'alice@example.test')):
        reset()
        migrate()
        first = engine_for(database, 'mod006-first')
        second = engine_for(database, 'mod006-second')
        inserted, release = threading.Event(), threading.Event()
        outcomes = {}

        def hold(conn, cursor, statement, params, context, many):
            if 'INSERT INTO "User"' in statement:
                inserted.set()
                if not release.wait(10):
                    raise RuntimeError('Synthetic insert hold timeout')

        def run(label, owner, subject, email):
            try:
                UserService(owner).create_profile(ProfileSubject(subject, email), label)
                outcomes[label] = 'created'
            except ProfileAlreadyExists:
                outcomes[label] = 'already_exists'
            except ProfileCreationRejected:
                outcomes[label] = 'rejected'
            except Exception as exc:
                outcomes[label] = type(exc).__name__

        event.listen(first, 'after_cursor_execute', hold)
        a = threading.Thread(target=run, args=('first', first, A, 'alice@example.test'), daemon=True)
        b = threading.Thread(target=run, args=('second', second, second_subject, second_email), daemon=True)
        a.start()
        try:
            assert inserted.wait(5)
            b.start()
            blocked = False
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with engine.connect() as conn:
                    blocked = conn.execute(text('''SELECT EXISTS (SELECT 1 FROM pg_stat_activity
                        WHERE application_name='mod006-second' AND wait_event_type='Lock'
                        AND cardinality(pg_blocking_pids(pid)) > 0)''')).scalar_one()
                if blocked:
                    break
                time.sleep(.02)
            assert blocked, 'Competing insert did not wait for uniqueness resolution'
        finally:
            release.set()
            a.join(10)
            if b.ident is not None:
                b.join(10)
            event.remove(first, 'after_cursor_execute', hold)
            first.dispose()
            second.dispose()
        assert not a.is_alive() and not b.is_alive()
        expected = 'already_exists' if second_subject == A else 'rejected'
        assert outcomes == {'first': 'created', 'second': expected}, outcomes
        rows = state()
        linked = [row for row in rows if row['uuid'] is not None]
        assert len(linked) == 1 and str(linked[0]['uuid']) == A
        assert linked[0]['email'] == 'alice@example.test' and linked[0]['displayName'] == 'first'
        races.append({'same_subject': second_subject == A, 'same_email': second_email == 'alice@example.test',
                      'observed_lock_wait': True, 'outcomes': outcomes})

    return {'baseline_plus_upgrade_replay': 'PASS', 'aggregate_dirty_preflight_and_atomic_refusal': 'PASS',
            'rls_filtered_preflight_fails_closed': 'PASS',
            'constraint_shape_and_null_policy_drift_rejection': 'PASS', 'nullable_legacy_email_fk_policy': 'PASS',
            'concurrent_first_login': races}


def main():
    admin = psycopg2.connect(dbname='postgres', **LOCAL)
    admin.autocommit = True
    name = 'otm_mod006_' + uuid4().hex
    created, engine = False, None
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cursor.fetchone()[0] == 'otm-modernization-assessment-20261029-synthetic-only', 'Refusing unmarked server'
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            created = True
        engine = engine_for(name, 'mod006-owner')
        result = tests(engine, name)
        # Existing pre-migration compatibility suite still covers statement and
        # deferred-commit failure rollback; it intentionally allows legacy dupes.
        with engine.begin() as conn:
            conn.exec_driver_sql('DROP SCHEMA auth CASCADE')
        result['prior_creation_rollback_contracts'] = creation_tests(engine)
        files = ['api/endpoints/user/service.py', 'api/migrations/20261104_user_identity_unique.sql',
                 'db/preflights/20261104_user_identity.sql', 'scripts/modernization/verify_mod006.py',
                 'db/tables.sql', 'db/baselines/20261029/001_schema.sql',
                 'api/migrations/20261030_game_kickoff_tbd.sql', 'scripts/modernization/verify_profile_creation.py']
        report = {'result': 'PASS', 'scope': 'Marked owned disposable loopback PostgreSQL; no configured/hosted access',
                  'tests': result, 'sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}}
        (ROOT / 'docs/modernization/evidence/mod-006-postgres-2026-11-04.json').write_text(json.dumps(report, indent=2) + '\n')
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
