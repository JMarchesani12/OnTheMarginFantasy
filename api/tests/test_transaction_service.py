"""Service pilot contracts using real scoped SQL and disposable fixture state."""
import unittest
from contextlib import contextmanager

from actors import UserActor
from endpoints.transaction.service import TransactionService
from endpoints.transaction.contracts import TransactionAccessDenied, TradeRejected
import test_transaction_read_authorization as reads
import test_trade_application_guards as trades


class ConnectionOwner:
    """Test-only engine proxy: every SQL statement belongs to one active scope."""
    def __init__(self, db):
        self.db = db
        self.connects = self.begins = self.active = 0

    @contextmanager
    def scope(self):
        if self.active:
            raise AssertionError('Nested connection acquisition')
        self.active += 1
        try:
            with self.db as conn:
                yield conn
        finally:
            self.active -= 1

    def connect(self):
        self.connects += 1
        return self.scope()

    def begin(self):
        self.begins += 1
        return self.scope()


class TransactionReadServiceTests(unittest.TestCase):
    def setUp(self):
        base = reads.TransactionReadAuthorizationTests()
        base.setUp()
        self.addCleanup(base.doCleanups)
        self.db = base.db
        self.engine = ConnectionOwner(self.db)
        self.service = TransactionService(self.engine)

    def test_interactive_actor_is_required_before_any_connection(self):
        for actor in (None, 1, {'user_id': 1}):
            with self.subTest(actor=actor):
                with self.assertRaises(TypeError):
                    self.service.list_transactions(actor, 10)
        self.assertEqual(self.engine.connects, 0)

    def test_read_uses_one_connection_preserves_projection_and_commissioner_policy(self):
        rows = self.service.list_transactions(UserActor(2, 'bob'), 10, 'PENDING_APPLY')
        self.assertEqual([r['id'] for r in rows], [3, 2])
        self.assertEqual(rows[0]['fromTeams'], [{'id': 102, 'displayName': 'Bravo'}])
        self.assertEqual(self.engine.connects, 1)
        self.assertEqual(self.engine.begins, 0)
        self.assertEqual(self.service.list_transactions(UserActor(1, 'alice'), 30), [])
        with self.assertRaises(TransactionAccessDenied):
            self.service.list_transactions(UserActor(4, 'nonmember'), 10)

    def test_query_rechecks_revoked_membership(self):
        def revoke(sql):
            if 'FROM "Transaction" t' in sql:
                self.db.before_query = None
                self.db.connection.execute('DELETE FROM LeagueMember WHERE id=12')
        self.db.before_query = revoke
        self.assertEqual(self.service.list_transactions(UserActor(2, 'bob'), 10), [])

    def test_explicit_trusted_reader_preserves_context_free_listing(self):
        self.assertEqual([r['id'] for r in self.service.list_transactions_for_job(20)], [5])
        self.assertEqual(self.service.list_transactions_for_job(999), [])


class TradeApplicationServiceTests(unittest.TestCase):
    def setUp(self):
        base = trades.TradeApplicationGuardTests()
        base.setUp()
        self.addCleanup(base.doCleanups)
        self.db, self.state = base.db, base.base.state
        self.engine = ConnectionOwner(self.db)
        self.service = TransactionService(self.engine)

    def test_trusted_apply_owns_one_transaction_and_rejects_replay(self):
        self.assertIsNone(self.service.apply_trade_for_job(1))
        self.assertEqual(self.engine.begins, 1)
        self.assertEqual(self.engine.connects, 0)
        after = self.state()
        self.assertEqual(after['Transaction'][0]['status'], 'COMPLETED')
        self.assertEqual([(r['memberId'], r['sportTeamId'], r['acquiredWeek']) for r in after['LeagueTeamSlot'][3:]], [(12,101,2),(11,102,2)])
        with self.assertRaises(TradeRejected):
            self.service.apply_trade_for_job(1)
        self.assertEqual(self.state(), after)

    def test_failure_between_closure_and_insert_rolls_back_all_state(self):
        before = self.state()
        def fail(sql):
            if 'INSERT INTO "LeagueTeamSlot"' in sql:
                raise RuntimeError('injected persistence failure')
        self.db.before_query = fail
        with self.assertRaisesRegex(RuntimeError, 'injected persistence'):
            self.service.apply_trade_for_job(1)
        self.db.before_query = None
        self.assertEqual(self.state(), before)

    def test_invalid_type_and_deadline_preserve_ownership(self):
        self.db.connection.execute('UPDATE "Transaction" SET type=\'FREE_AGENT\'')
        self.db.connection.commit()
        before = self.state()
        with self.assertRaises(TradeRejected):
            self.service.apply_trade_for_job(1)
        self.assertEqual(self.state(), before)
        self.db.connection.execute('UPDATE "Transaction" SET type=\'TRADE\'')
        self.db.connection.execute('UPDATE League SET tradeDeadline=\'2020-01-01\'')
        self.db.connection.commit()
        with self.assertRaisesRegex(TradeRejected, 'deadline'):
            self.service.apply_trade_for_job(1)
        self.assertEqual(self.state()['LeagueTeamSlot'], before['LeagueTeamSlot'])
