"""MOD-023 actual LISTEN/commit/rollback on an owned marked loopback database.

No app factory, configured DSN, worker, listener process or provider is loaded.
"""
import hashlib
import json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL, ROOT, engine_for
from verify_draft_complete import FIXTURE, tests as prior_pick_tests
from verify_draft_order import tests as prior_order_tests
from verify_draft_controls import tests as prior_control_tests
from verify_draft_finalization import tests as prior_finalization_tests
from verify_draft_snapshot import tests as prior_snapshot_tests
from verify_mod010 import tests as prior_ownership_tests
from endpoints.draft.control_service import DraftControlService
from endpoints.draft.pick_service import DraftPickService
from endpoints.draft.snapshot_service import DraftSnapshotService


def tests(engine, database):
    listener = psycopg2.connect(dbname=database, **LOCAL)
    listener.autocommit = True
    with listener.cursor() as cur: cur.execute('LISTEN draft_updated')
    def query(statement):
        with engine.begin() as conn: conn.exec_driver_sql(statement)
    def messages():
        with listener.cursor() as cur: cur.execute('SELECT 1')
        listener.poll()
        result = [json.loads(item.payload) for item in listener.notifies]
        listener.notifies.clear()
        return result
    def state():
        with engine.begin() as conn:
            return {table: [dict(row) for row in conn.execute(text(f'SELECT * FROM "{table}" ORDER BY 1,2')).mappings()]
                    for table in ('League','LeagueMember','DraftState','DraftTurn','DraftPick','LeagueTeamSlot')}
    def prepare(action):
        query(FIXTURE)
        if action in ('start','order'):
            query('''DELETE FROM "DraftPick" WHERE "leagueId"=10; DELETE FROM "DraftTurn" WHERE "leagueId"=10;
                DELETE FROM "DraftState" WHERE "leagueId"=10; UPDATE "League" SET status='Pre-Draft' WHERE id=10;''')
        if action in ('skip','extend','implicit_finalize'):
            query('UPDATE "DraftState" SET "expiresAt"=now()-interval \'5 seconds\' WHERE "leagueId"=10')
        if action == 'extend':
            query('UPDATE "DraftState" SET "currentOverallPickNumber"=4,"currentMemberId"=11 WHERE "leagueId"=10')
        if action == 'implicit_finalize':
            query('DELETE FROM "DraftTurn" WHERE "leagueId"=10 AND "overallPickNumber">1; INSERT INTO "DraftTurn" VALUES (10,2,12)')
            query('INSERT INTO "DraftPick" ("leagueId","overallPickNumber","memberId","sportTeamId") VALUES (10,2,12,102)')
        messages()
    control = DraftControlService(engine)
    picks = DraftPickService(engine)
    def run(action):
        if action == 'order': return control.set_order_for_job(10,[12,11])
        if action in ('skip','extend','implicit_finalize'): return picks.process_timeout_for_job(10)
        return getattr(control, action+'_for_job')(10)
    expected = {'order':'draft_order','start':'draft_start','pause':'draft_pause','resume':'draft_resume',
                'finalize':'draft_finalize','skip':'auto_skip','extend':'auto_skip_extend','implicit_finalize':'draft_finalize'}
    verified = []
    try:
        for action, reason in expected.items():
            prepare(action)
            pending = []
            def before_commit(conn,cursor,statement,params,context,many):
                if 'pg_notify' in statement:
                    pending.append(True)
                    assert not messages(), 'Notification escaped uncommitted transaction'
            event.listen(engine,'after_cursor_execute',before_commit)
            try: run(action)
            finally: event.remove(engine,'after_cursor_execute',before_commit)
            assert pending and messages()==[{'leagueId':10,'reason':reason}],action
            snapshot=DraftSnapshotService(engine).snapshot_for_reader_id(10,2)
            if action in ('finalize','implicit_finalize'): assert snapshot['state']['status']=='complete'
            if action == 'skip':
                assert snapshot['state']['currentMemberId']==12
                assert snapshot['onDeck']['memberId']==11
            if action == 'extend': assert snapshot['state']['expiresAt'] is not None
            # A failure after pg_notify must restore all rows and publish nothing.
            prepare(action); before=state(); hit=[]
            def fail(conn,cursor,statement,params,context,many):
                if 'pg_notify' in statement: hit.append(True); raise RuntimeError('synthetic after-notify fault')
            event.listen(engine,'after_cursor_execute',fail)
            try:
                try: run(action)
                except RuntimeError: pass
                else: raise AssertionError('Expected publication fault')
            finally: event.remove(engine,'after_cursor_execute',fail)
            assert hit and state()==before and not messages(),action
            # Deferred commit rejection after the notification has been queued.
            prepare(action)
            table = 'LeagueMember' if action=='order' else 'League' if action=='start' else 'DraftState'
            query('''CREATE FUNCTION fail_commit() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'synthetic deferred commit fault'; END $$;''')
            query(f'CREATE CONSTRAINT TRIGGER fail_at_commit AFTER UPDATE ON "{table}" DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fail_commit()')
            before=state()
            try: run(action)
            except DBAPIError: pass
            else: raise AssertionError('Expected deferred rejection '+action)
            assert state()==before and not messages(),action
            verified.append(action)
        for clause in ("status='paused'",'"expiresAt"=NULL','"expiresAt"=now()+interval \'60 seconds\'','"currentOverallPickNumber"=5'):
            prepare('skip');query('UPDATE "DraftState" SET '+clause+' WHERE "leagueId"=10');before=state()
            assert picks.process_timeout_for_job(10) is None and state()==before and not messages()
        prepare('start');control.start_for_job(10);messages();before=state()
        try: control.start_for_job(10)
        except ValueError: pass
        else: raise AssertionError('Start replay allowed')
        assert state()==before and not messages()
        return {'commit_only_and_post_notify_rollback_and_deferred_rejection':verified,
                'noop_replay_no_notifications':'PASS','member_snapshots_after_worker_skip_extend_finalize':'PASS'}
    finally: listener.close()


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    database='otm_mod023_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)));created=True
        engine=engine_for(database,'mod023-owner')
        result=tests(engine,database)
        result['previous']={'snapshot':prior_snapshot_tests(engine,database),'controls':prior_control_tests(engine,database),
                            'order':prior_order_tests(engine,database),'finalization':prior_finalization_tests(engine,database),
                            'complete_pick':prior_pick_tests(engine,database), 'ownership':prior_ownership_tests(engine,database)}
        files=['api/endpoints/draft/'+name for name in ('control_service.py','pick_service.py','draftSocket.py','draftBroadcast.py','realtime.py','startDraftNotifyListener.py','draftEndpoints.py','notifyChannel.py')]
        files+=['api/tests/test_draft_contracts.py','api/tests/test_draft_control_authorization.py','api/tests/test_live_pick_authorization.py','api/tests/test_draft_notifications.py','api/tests/test_draft_realtime.py','front-end/src/lib/draftRealtime.ts','front-end/tests/draftRealtime.test.ts','front-end/tests/draftPageLifecycle.test.ts','front-end/src/screens/League/LeagueDraftPage.tsx','front-end/src/api/draft.ts','front-end/src/api/roster.ts','front-end/src/types/draft.ts','scripts/modernization/verify_mod023.py','scripts/modernization/verify_draft_complete.py']
        report={'result':'PASS','scope':'Owned marked loopback PostgreSQL; no configured runtime/worker/listener/provider',
                'tests':result,'sha256':{file:hashlib.sha256((ROOT/file).read_bytes()).hexdigest() for file in files}}
        (ROOT/'docs/modernization/evidence/mod-023-postgres-2026-11-06.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
        print(json.dumps(report,indent=2,default=str))
    finally:
        if engine is not None: engine.dispose()
        if created:
            with admin.cursor() as cur: cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))
        admin.close()
if __name__=='__main__': main()
