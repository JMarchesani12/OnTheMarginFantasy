"""MOD-025 native SQL/concurrency on a marked disposable loopback server.

Never reads configuration/.env or accepts a DSN. Creates and drops only a
uniquely named synthetic database, following the existing assessment harness.
"""
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
from verify_draft_order import FIXTURE as ORDER_FIXTURE, tests as order_tests
from verify_draft_controls import tests as control_tests
from verify_draft_finalization import tests as finalize_tests
from verify_draft_snapshot import tests as snapshot_tests
from actors import UserActor
from endpoints.draft.control_service import DraftControlService, DraftStartConflict

FIXTURE = ORDER_FIXTURE + '''
UPDATE "League" SET status='Pre-Draft';
'''


def tests(engine, database):
    actor = UserActor(1, 'alice')
    service = DraftControlService(engine)

    def reset():
        with engine.begin() as conn:
            conn.exec_driver_sql(FIXTURE)

    def state():
        with engine.connect() as conn:
            return {table: [dict(row) for row in conn.execute(text(
                f'SELECT * FROM "{table}" ORDER BY 1,2')).mappings()]
                for table in ('League', 'LeagueMember', 'DraftState', 'DraftTurn', 'DraftPick')}

    def reject(operation, error=ValueError):
        before = state()
        try:
            operation()
        except error:
            pass
        else:
            raise AssertionError('Invalid command accepted')
        assert state() == before, 'Rejected command mutated persistent state'

    reset()
    for ids in ([11], [11, 11], [21, 11], [True, 12], [11.0, 12], ['11', 12], []):
        reject(lambda: service.set_order(actor, 10, ids))
    service.set_order(actor, 10, [12, 11])
    started = service.start(actor, 10)
    assert started['state']['currentMemberId'] == 12
    assert [r['memberId'] for r in state()['DraftTurn'] if r['leagueId'] == 10] == [12, 11, 11, 12]
    reject(lambda: service.start(actor, 10), DraftStartConflict)
    service.pause(actor, 10)
    reject(lambda: service.start_for_job(10), DraftStartConflict)
    assert service.resume(actor, 10)['state']['currentMemberId'] == 12
    service.finalize_for_job(10)
    reject(lambda: service.start(actor, 10), DraftStartConflict)

    reset()
    with engine.begin() as conn:
        conn.exec_driver_sql('''INSERT INTO "DraftState"
            ("leagueId",status,"currentOverallPickNumber") VALUES (10,'pre',1);''')
    assert service.start(actor, 10)['state']['status'] == 'live'
    # Preserve a committed pick and cursor/timestamps on replay.
    with engine.begin() as conn:
        conn.exec_driver_sql('''INSERT INTO "DraftPick" VALUES (2,10,now(),1,1,1,11,101);
            UPDATE "DraftState" SET "currentOverallPickNumber"=2,"currentMemberId"=12,
                "lastPickAt"=now() WHERE "leagueId"=10;''')
    reject(lambda: service.start(actor, 10), DraftStartConflict)

    for fragment in ('INSERT INTO "DraftTurn"', 'INSERT INTO "DraftState"', 'UPDATE "League"'):
        reset()
        def fail(conn, cursor, statement, params, context, many):
            if fragment in statement:
                raise RuntimeError('synthetic write failure')
        event.listen(engine, 'after_cursor_execute', fail)
        try:
            reject(lambda: service.start(actor, 10), RuntimeError)
        finally:
            event.remove(engine, 'after_cursor_execute', fail)
    reset()
    with engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION fail_start_commit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic deferred failure'; END $$;
            CREATE CONSTRAINT TRIGGER start_commit AFTER INSERT OR UPDATE ON "DraftState"
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fail_start_commit();''')
    reject(lambda: service.start(actor, 10), DBAPIError)

    races = []
    for first_action, second_action in (('start', 'start'), ('order', 'start'), ('start', 'order'), ('finalize', 'start'), ('finalize', 'order')):
        reset()
        if first_action == 'finalize':
            service.start(actor, 10)
        first = engine_for(database, 'mod025-first')
        second = engine_for(database, 'mod025-second')
        locked, release = threading.Event(), threading.Event()
        outcomes = {}

        def hold(conn, cursor, statement, params, context, many):
            target_lock = ('UPDATE "DraftState"' in statement if first_action == 'finalize' else
                           'SELECT status FROM "League"' in statement and 'FOR UPDATE' in statement)
            if target_lock:
                locked.set()
                if not release.wait(10):
                    raise RuntimeError('Synthetic lock hold timed out')

        def run(label, owner, action):
            try:
                target = DraftControlService(owner)
                if action == 'order':
                    target.set_order(actor, 10, [12, 11])
                elif action == 'finalize':
                    target.finalize_for_job(10)
                else:
                    target.start(actor, 10)
                outcomes[label] = 'ok'
            except DraftStartConflict:
                outcomes[label] = 'start_conflict'
            except ValueError:
                outcomes[label] = 'order_conflict'
            except Exception as exc:
                outcomes[label] = type(exc).__name__

        event.listen(first, 'after_cursor_execute', hold)
        a = threading.Thread(target=run, args=('first', first, first_action), daemon=True)
        b = threading.Thread(target=run, args=('second', second, second_action), daemon=True)
        a.start()
        try:
            assert locked.wait(5), 'First command never locked League'
            b.start()
            blocked = False
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with engine.connect() as conn:
                    blocked = conn.execute(text('''SELECT EXISTS (
                        SELECT 1 FROM pg_stat_activity WHERE application_name='mod025-second'
                        AND wait_event_type='Lock' AND cardinality(pg_blocking_pids(pid)) > 0)''')).scalar_one()
                if blocked:
                    break
                time.sleep(.02)
            assert blocked, 'Competing command did not wait on League lock'
        finally:
            release.set()
            a.join(10)
            if b.ident is not None:
                b.join(10)
            event.remove(first, 'after_cursor_execute', hold)
            first.dispose()
            second.dispose()
        assert not a.is_alive() and not b.is_alive(), 'Worker did not finish'
        expected = 'ok' if first_action == 'order' else 'start_conflict' if second_action == 'start' else 'order_conflict'
        assert outcomes == {'first': 'ok', 'second': expected}, outcomes
        rows = state()
        assert len(rows['DraftTurn']) == 6  # Four league-10 turns, two untouched league-20 turns.
        current = next(row for row in rows['DraftState'] if row['leagueId'] == 10)
        if first_action == 'finalize':
            assert current['status'] == 'complete' and current['currentMemberId'] is None
        else:
            assert current['currentOverallPickNumber'] == 1
            assert current['currentMemberId'] == (12 if first_action == 'order' else 11)
        races.append({'first': first_action, 'second': second_action,
                      'observed_lock_wait': True, 'outcomes': outcomes})
    return {'permutation_and_lifecycle': 'PASS', 'pick_cursor_timer_replay': 'PASS',
            'statement_and_deferred_commit_rollback': 'PASS', 'races': races}


def main():
    admin = psycopg2.connect(dbname='postgres', **LOCAL)
    admin.autocommit = True
    name = 'otm_mod025_' + uuid4().hex
    created, engine = False, None
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cursor.fetchone()[0] == 'otm-modernization-assessment-20261029-synthetic-only', 'Refusing unmarked server'
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            created = True
        engine = engine_for(name, 'mod025-owner')
        result = tests(engine, name)
        result['prior_snapshot'] = snapshot_tests(engine, name)
        result['prior_finalization'] = finalize_tests(engine, name)
        result['prior_controls'] = control_tests(engine, name)
        result['prior_order'] = order_tests(engine, name)
        files = ['api/endpoints/draft/control_service.py', 'api/endpoints/draft/control_repository.py',
                 'scripts/modernization/verify_mod025.py',
                 'scripts/modernization/verify_draft_controls.py', 'scripts/modernization/verify_draft_order.py']
        report = {'result': 'PASS', 'scope': 'Owned marked loopback PostgreSQL only; no configured database',
                  'tests': result, 'sha256': {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files}}
        (ROOT / 'docs/modernization/evidence/mod-025-postgres-2026-11-03.json').write_text(json.dumps(report, indent=2) + '\n')
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
