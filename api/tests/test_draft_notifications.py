"""Transaction-local publication, with native commit semantics checked separately."""
import json
import unittest
from endpoints.draft.control_service import DraftControlService
import test_draft_control_authorization as controls
from test_transaction_service import ConnectionOwner


class DraftNotificationTests(unittest.TestCase):
    def setUp(self):
        self.base = controls.DraftControlAuthorizationTests()
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.db = self.base.db
        self.engine = ConnectionOwner(self.db)
        self.service = DraftControlService(self.engine)
        self.messages = []
        self.db.connection.create_function('pg_notify', 2, lambda ch, msg: self.messages.append((ch, json.loads(msg))))

    def test_each_control_publishes_on_its_transaction(self):
        for action in ('order', 'start', 'pause', 'resume', 'finalize'):
            with self.subTest(action=action):
                self.base.prepare(action)
                self.messages.clear()
                if action == 'order':
                    self.service.set_order_for_job(10, [12, 11])
                else:
                    getattr(self.service, action + '_for_job')(10)
                self.assertEqual(self.messages, [('draft_updated', {'leagueId': 10, 'reason': 'draft_' + action})])

    def test_notification_failure_rolls_back_each_control(self):
        for action in ('order', 'start', 'pause', 'resume', 'finalize'):
            with self.subTest(action=action):
                self.base.prepare(action)
                before = self.base.state()
                def fail(sql):
                    if 'pg_notify' in sql:
                        raise RuntimeError('synthetic publication failure')
                self.db.before_query = fail
                with self.assertRaisesRegex(RuntimeError, 'publication'):
                    if action == 'order':
                        self.service.set_order_for_job(10, [12, 11])
                    else:
                        getattr(self.service, action + '_for_job')(10)
                self.db.before_query = None
                self.assertEqual(self.base.state(), before)

    def test_denied_control_publishes_nothing(self):
        self.base.prepare('start')
        with self.assertRaises(PermissionError):
            self.service.start_for_legacy_user_id(10, 2)
        self.assertEqual(self.messages, [])

    def test_skip_rotation_and_clock_extension_publish_and_rollback(self):
        from endpoints.draft.pick_service import DraftPickService
        from endpoints.draft.pick_repository import DraftPickRepository
        from sqlalchemy import text
        class TimeoutRepository(DraftPickRepository):
            # Only adapt PostgreSQL interval syntax for the synthetic SQLite adapter.
            def timeout_expired(self, conn, params):
                return conn.execute(text('SELECT 1 AS "isExpired"'), {})
            def timeout_rotate_turns(self, conn, params):
                # Native verifier exercises the actual CTE; this adapter preserves its resulting turn change.
                return conn.execute(text('UPDATE "DraftTurn" SET "memberId"=11 WHERE "leagueId"=:leagueId AND "overallPickNumber"=2'), params)
        for last, reason in ((False, 'auto_skip'), (True, 'auto_skip_extend')):
            for fail in (False, True):
                with self.subTest(last=last, fail=fail):
                    self.base.prepare('pause')
                    self.db.connection.execute('UPDATE "DraftState" SET status=\'live\', "expiresAt"=\'2020-01-01\', "currentOverallPickNumber"=? WHERE "leagueId"=10', (4 if last else 2,))
                    self.db.connection.commit()
                    self.messages.clear()
                    before = self.base.state()
                    def inject(sql):
                        if fail and 'pg_notify' in sql:
                            raise RuntimeError('synthetic publication failure')
                    self.db.before_query = inject
                    service = DraftPickService(self.engine, TimeoutRepository())
                    if fail:
                        with self.assertRaises(RuntimeError): service.process_timeout_for_job(10)
                        self.db.before_query = None
                        self.assertEqual(self.base.state(), before)
                    else:
                        result = service.process_timeout_for_job(10)
                        self.assertFalse(result['draftComplete'])
                        self.assertEqual(self.messages, [('draft_updated', {'leagueId':10,'reason':reason})])

    def test_nonterminal_live_pick_publishes_and_notification_fault_restores_pick(self):
        from actors import UserActor
        from endpoints.draft.pick_service import DraftPickService
        for fail in (False,True):
            with self.subTest(fail=fail):
                self.db.connection.execute('DELETE FROM "LeagueTeamSlot"')
                self.db.connection.execute('DELETE FROM "DraftPick" WHERE id>1')
                self.db.connection.execute('UPDATE "DraftState" SET "currentOverallPickNumber"=2,"currentMemberId"=12,"expiresAt"=NULL WHERE "leagueId"=10')
                self.db.connection.commit()
                self.messages.clear()
                before=self.base.state()
                def inject(sql):
                    if fail and 'pg_notify' in sql: raise RuntimeError('synthetic publication failure')
                self.db.before_query=inject
                call=lambda: DraftPickService(self.engine).pick_live(UserActor(2,'bob'),10,12,102)
                if fail:
                    with self.assertRaises(RuntimeError):call()
                    self.db.before_query=None
                    self.assertEqual(self.base.state(),before)
                else:
                    self.assertFalse(call()['draftComplete'])
                    self.assertEqual(self.messages,[('draft_updated',{'leagueId':10,'reason':'draft_pick'})])
