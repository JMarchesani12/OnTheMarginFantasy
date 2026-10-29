"""Retained trusted model allocation: actual SQLite persistence/notification SQL.

pg_notify is a local function recording SQL invocation, not proof of PostgreSQL
transactional notification delivery. The existing credential-free harness guards
all network/deployed database access.
"""
import json
import unittest

import test_live_pick_authorization as live_fixture


class TrustedManualPickTests(unittest.TestCase):
    def setUp(self):
        self.fixture = live_fixture.LivePickAuthorizationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db, self.model = self.fixture.db, self.fixture.model
        self.db.connection.execute('DELETE FROM "DraftState" WHERE "leagueId" = 10')
        self.db.connection.commit()
        self.notifications = []
        def notify(channel, payload):
            self.notifications.append((channel, json.loads(payload)))
        self.db.connection.create_function('pg_notify', 2, notify)

    def assert_allocation(self, pick, week):
        self.assertEqual((pick['leagueId'], pick['memberId'], pick['sportTeamId']), (10, 12, 102))
        self.assertEqual((pick['overallPickNumber'], pick['roundNumber'], pick['pickInRound']), (2, 1, 2))
        slot = self.db.connection.execute('SELECT * FROM "LeagueTeamSlot" WHERE id = ?',
                                          (pick['leagueTeamSlotId'],)).fetchone()
        self.assertEqual((slot['leagueId'], slot['memberId'], slot['sportTeamId'], slot['acquiredWeek'], slot['acquiredVia']),
                         (10, 12, 102, week, 'Draft'))
        self.assertEqual(self.notifications, [('draft_updated', {'leagueId': 10, 'reason': 'manual_pick'})])
        self.fixture.emit.assert_not_called()

    def test_direct_trusted_call_preserves_default_week_and_notification_without_http(self):
        self.assert_allocation(self.model.create_draft_pick(10, 12, 102), 1)

    def test_direct_trusted_call_preserves_explicit_acquisition_week(self):
        self.assert_allocation(self.model.create_draft_pick(10, 12, 102, acquired_week=4), 4)

    def test_trusted_slot_failure_rolls_back_pick_without_notification(self):
        before = self.fixture.state()
        def fail(sql):
            if 'INSERT INTO "LeagueTeamSlot"' in sql:
                raise RuntimeError('synthetic trusted slot failure')
        self.db.before_query = fail
        with self.assertRaisesRegex(RuntimeError, 'synthetic trusted slot failure'):
            self.model.create_draft_pick(10, 12, 102)
        self.assertEqual(self.fixture.state(), before)
        self.assertEqual(self.notifications, [])
        self.fixture.emit.assert_not_called()
