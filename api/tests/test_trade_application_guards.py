"""MOD-009 state/rollback evidence; SQLite does not establish row-lock concurrency."""
import unittest
import test_free_agency_authorization as fixture
from test_operational_trusted_contract import ApplyDatabase


class TradeApplicationGuardTests(unittest.TestCase):
    def setUp(self):
        self.base = fixture.FreeAgencyAuthorizationTests()
        self.base.database_type = ApplyDatabase
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.db, self.model = self.base.db, self.base.model
        self.db.connection.executescript('''
            ALTER TABLE League ADD COLUMN tradeDeadline TEXT;
            INSERT INTO "Transaction" VALUES
                (1,10,101,'TRADE',11,12,'PENDING_APPLY','[101]','[102]');
        ''')

    def test_invalid_states_and_types_never_change_ownership(self):
        for method in (self.model.apply_trade, self.model.apply_pending_transaction):
            for kind, status in [('TRADE', s) for s in
                    ('PROPOSED','REJECTED','CANCELLED','VETOED','COMPLETED')] + [('OTHER','PENDING_APPLY'),('FREE_AGENT','COMPLETED')]:
                with self.subTest(method=method.__name__,kind=kind,status=status):
                    self.db.connection.execute('UPDATE "Transaction" SET type=?,status=?',(kind,status))
                    self.db.connection.commit()
                    before = self.base.state()
                    with self.assertRaises(ValueError):
                        method(1)
                    self.assertEqual(self.base.state(), before)

    def test_replay_rejected_and_history_keeps_half_open_boundary(self):
        self.assertIsNone(self.model.apply_pending_transaction(1))
        after = self.base.state()
        self.assertEqual(after['Transaction'][0]['status'], 'COMPLETED')
        slots = after['LeagueTeamSlot']
        self.assertEqual([(r['memberId'],r['sportTeamId'],r['droppedWeek']) for r in slots[:2]],
                         [(11,101,2),(12,102,2)])
        self.assertEqual([(r['memberId'],r['sportTeamId'],r['acquiredWeek']) for r in slots[3:]],
                         [(12,101,2),(11,102,2)])
        for method in (self.model.apply_trade,self.model.apply_pending_transaction):
            with self.assertRaisesRegex(ValueError,'not pending apply'):
                method(1)
            self.assertEqual(self.base.state(),after)

    def test_stale_ownership_and_conference_limit_rejected(self):
        for mutation in ('UPDATE LeagueTeamSlot SET droppedWeek=2 WHERE id=1',
                         'UPDATE SportConference SET maxTeamsPerOwner=0'):
            with self.subTest(mutation=mutation):
                self.db.connection.execute(mutation)
                self.db.connection.commit()
                before = self.base.state()
                with self.assertRaises(ValueError):
                    self.model.apply_trade(1)
                self.assertEqual(self.base.state(),before)
                self.db.connection.execute('UPDATE LeagueTeamSlot SET droppedWeek=NULL')
                self.db.connection.commit()

    def test_failure_after_closure_insert_or_completion_rolls_back(self):
        for marker, occurrence in (('INSERT INTO "LeagueTeamSlot"',1),
                                   ('INSERT INTO "LeagueTeamSlot"',2),('SET status = :status',1)):
            with self.subTest(marker=marker):
                before=self.base.state()
                hits=0
                def fail(sql):
                    nonlocal hits
                    if marker in sql:
                        hits += 1
                    if hits == occurrence:
                        raise RuntimeError('injected application failure')
                self.db.before_query=fail
                with self.assertRaisesRegex(RuntimeError,'injected'):
                    self.model.apply_trade(1)
                self.db.before_query=None
                self.assertEqual(self.base.state(),before)

    def test_missing_transaction_rejected(self):
        before=self.base.state()
        with self.assertRaisesRegex(ValueError,'not found'):
            self.model.apply_trade(999)
        self.assertEqual(self.base.state(),before)

    def test_dispatcher_stale_pending_read_cannot_bypass_locked_guard(self):
        before=self.base.state()['LeagueTeamSlot']
        def cancel_before_lock(sql):
            if 'SELECT * FROM "Transaction"' in ' '.join(sql.split()):
                self.db.connection.execute('UPDATE "Transaction" SET status=? WHERE id=1', ('CANCELLED',))
        self.db.before_query=cancel_before_lock
        with self.assertRaisesRegex(ValueError,'not pending apply'):
            self.model.apply_pending_transaction(1)
        self.db.before_query=None
        self.assertEqual(self.base.state()['LeagueTeamSlot'],before)
