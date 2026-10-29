"""Live-pick ownership: real JWT, routes and transaction SQL; no deployed DB."""
import datetime as dt
import sqlite3
import unittest
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import test_draft_state_authorization as fixture
from socketioInstance import socketio


class LivePickDatabase(fixture.DraftStateDatabase):
    def execute(self, statement, params):
        sql = str(statement).replace('FOR UPDATE', '').replace(')::int AS cnt', ') AS cnt').replace(
            "now() + (:selectionTime || ' seconds')::interval",
            "datetime(now(), '+' || :selectionTime || ' seconds')")
        try:
            result = super().execute(text(sql), params)
        except sqlite3.IntegrityError as exc:
            raise IntegrityError(sql, params, exc) from exc
        fetchone = result.fetchone

        def row_with_timestamp():
            row = fetchone()
            if row and isinstance(row.get('expiresAt'), str):
                stamp = dt.datetime.fromisoformat(row['expiresAt'])
                row['expiresAt'] = stamp if stamp.tzinfo else stamp.replace(tzinfo=dt.timezone.utc)
            return row
        result.fetchone = row_with_timestamp
        return result


class LivePickAuthorizationTests(unittest.TestCase):
    database_type = LivePickDatabase
    def setUp(self):
        self.fixture = fixture.DraftStateAuthorizationTests()
        self.fixture.database_type = self.database_type
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db, self.client, self.model = self.fixture.db, self.fixture.client, self.fixture.model
        self.headers = self.fixture.headers
        self.db.connection.executescript('''
            UPDATE "League" SET settings = '{"draft":{"draftType":"SNAKE","selectionTime":60,"numberOfRounds":2,"graceSeconds":0}}';
            UPDATE "DraftState" SET "expiresAt" = NULL;
            UPDATE "DraftState" SET status = 'live' WHERE "leagueId" = 20;
            ALTER TABLE "SportConference" ADD COLUMN "maxTeamsPerOwner" INTEGER DEFAULT 2;
            INSERT INTO "SportTeam" VALUES (102, 1, 'Available Team');
            ALTER TABLE "DraftPick" RENAME TO old_pick;
            CREATE TABLE "DraftPick" (id INTEGER PRIMARY KEY AUTOINCREMENT, "leagueId" INTEGER,
                "createdAt" TEXT DEFAULT '2026-10-28T12:00:00Z', "overallPickNumber" INTEGER,
                "roundNumber" INTEGER, "pickInRound" INTEGER, "memberId" INTEGER, "sportTeamId" INTEGER,
                UNIQUE ("leagueId", "overallPickNumber"), UNIQUE ("leagueId", "sportTeamId"));
            INSERT INTO "DraftPick" SELECT * FROM old_pick;
            DROP TABLE old_pick;
            CREATE TABLE "LeagueTeamSlot" (id INTEGER PRIMARY KEY AUTOINCREMENT, "leagueId" INTEGER,
                "memberId" INTEGER, "sportTeamId" INTEGER, "acquiredWeek" INTEGER,
                "acquiredVia" TEXT, "droppedWeek" INTEGER);
        ''')
        self.emit = self.enterContext(patch.object(socketio, 'emit'))
        self.body = {'leagueId': 10, 'memberId': 12, 'sportTeamId': 102}

    def state(self):
        return {table: [dict(row) for row in self.db.connection.execute(f'SELECT * FROM "{table}" ORDER BY 1')]
                for table in ('DraftState', 'DraftPick', 'LeagueTeamSlot', 'LeagueMember')}

    def post(self, body=None, subject=fixture.BOB):
        return self.client.post('/api/draft/pick', json=self.body if body is None else body,
                                headers=self.headers(subject))

    def test_owned_live_picks_preserve_response_slot_defaults_and_matching_broadcast(self):
        for league_id, member_id in ((10, 12), (20, 21)):
            with self.subTest(league_id=league_id):
                self.emit.reset_mock()
                response = self.post({'leagueId': str(league_id), 'memberId': str(member_id), 'sportTeamId': '102'})
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json['leagueId'], league_id)
                self.assertEqual(response.json['memberId'], member_id)
                self.assertFalse(response.json['draftComplete'])
                slot = self.db.connection.execute('SELECT * FROM "LeagueTeamSlot" WHERE id = ?',
                                                  (response.json['leagueTeamSlotId'],)).fetchone()
                self.assertEqual((slot['leagueId'], slot['memberId'], slot['acquiredWeek'], slot['acquiredVia']),
                                 (league_id, member_id, 0, 'Draft'))
                self.emit.assert_called_once()
                args, kwargs = self.emit.call_args
                self.assertEqual(args[0], 'draft:updated')
                self.assertEqual(args[1]['type'], 'pick')
                self.assertEqual(args[1]['pick'], response.json)
                self.assertEqual(args[1]['snapshot']['leagueId'], league_id)
                self.assertEqual(kwargs, {'room': f'draft:{league_id}'})

    def test_commissioner_may_pick_own_turn_and_explicit_week_is_preserved(self):
        self.db.connection.execute('UPDATE "DraftTurn" SET "memberId" = 11 WHERE "leagueId" = 10 AND "overallPickNumber" = 2')
        self.db.connection.execute('UPDATE "DraftState" SET "currentMemberId" = 11 WHERE "leagueId" = 10')
        response = self.post(dict(self.body, memberId=11, weekNumber='3'), fixture.ALICE)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['memberId'], 11)
        slot = self.db.connection.execute('SELECT "acquiredWeek" FROM "LeagueTeamSlot"').fetchone()
        self.assertEqual(slot[0], 3)
        self.emit.assert_called_once()

    def test_foreign_members_cross_league_missing_and_nonmember_cannot_pick(self):
        for subject, league_id, member_id in ((fixture.ALICE, 10, 12), (fixture.OUTSIDER, 10, 12),
                (fixture.BOB, 10, 21), (fixture.BOB, 20, 12), (fixture.ALICE, 20, 21),
                (fixture.ALICE, 30, 11), (fixture.BOB, 999, 12), (fixture.BOB, 10, 999)):
            with self.subTest(subject=subject, league_id=league_id, member_id=member_id):
                before = self.state()
                response = self.post({'leagueId': league_id, 'memberId': member_id, 'sportTeamId': 102}, subject)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json, {'message': 'League member not found'})
                self.assertEqual(self.state(), before)
                self.emit.assert_not_called()

    def test_client_actor_headers_and_trusted_job_flags_never_grant_ownership(self):
        headers = self.headers(fixture.ALICE)
        headers.update({'X-User-Id': '2', 'X-User-Sub': fixture.BOB, 'X-Role': 'commissioner'})
        before = self.state()
        response = self.client.post('/api/draft/pick?userId=2&memberId=12', headers=headers,
            json=dict(self.body, userId=2, actingUserId=2, sub=fixture.BOB, trustedJob=True))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.state(), before)
        self.emit.assert_not_called()

    def test_authentication_and_identity_denials_never_write_or_broadcast(self):
        for headers, status in (({}, 401), (self.headers(exp=1), 401),
                                (self.headers(''), 401), (self.headers(fixture.MISSING), 403)):
            with self.subTest(status=status):
                before = self.state()
                response = self.client.post('/api/draft/pick', json=self.body, headers=headers)
                self.assertEqual(response.status_code, status)
                self.assertIn('error', response.json)
                self.assertEqual(self.state(), before)
                self.emit.assert_not_called()
        self.db.connection.executescript('''
            ALTER TABLE "User" RENAME TO old_user;
            CREATE TABLE "User" AS SELECT * FROM old_user;
            INSERT INTO "User" SELECT 4, uuid, 'duplicate@example.test', 'Duplicate', "createdAt" FROM old_user WHERE id = 2;
        ''')
        response = self.post()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})
        self.emit.assert_not_called()

    def test_owned_wrong_turn_expired_and_unique_conflicts_keep_existing_statuses(self):
        before = self.state()
        response = self.post(dict(self.body, memberId=11), fixture.ALICE)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json, {'message': 'Not your turn'})
        response = self.post(dict(self.body, sportTeamId=101))
        self.assertEqual(response.status_code, 409)
        self.assertIn('conflict', response.json['message'].lower())
        self.assertEqual(self.state(), before)
        self.db.connection.execute('UPDATE "DraftState" SET "expiresAt" = ? WHERE "leagueId" = 10',
                                   ('2000-01-01T00:00:00+00:00',))
        before = self.state()
        response = self.post()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json, {'message': 'Pick window expired'})
        self.assertEqual(self.state(), before)
        self.emit.assert_not_called()

    def test_invalid_shapes_and_identity_resource_types_are_safe_client_errors(self):
        for body in ([], 'text', None, {}, dict(self.body, memberId=True), dict(self.body, leagueId=10.5),
                     dict(self.body, memberId={}), dict(self.body, sportTeamId='bad'), dict(self.body, weekNumber=False)):
            with self.subTest(body=body):
                before = self.state()
                response = self.client.post('/api/draft/pick', json=body, headers=self.headers(fixture.BOB))
                self.assertEqual(response.status_code, 400)
                self.assertIsInstance(response.json.get('message'), str)
                self.assertEqual(self.state(), before)
        self.emit.assert_not_called()

    def test_final_insert_rechecks_ownership_and_rolls_back_on_late_revocation(self):
        before = self.state()
        def revoke(sql):
            if 'INSERT INTO "DraftPick"' in sql:
                self.db.before_query = None
                self.db.connection.execute('UPDATE "LeagueMember" SET "userId" = 1 WHERE id = 12')
        self.db.before_query = revoke
        response = self.post()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {'message': 'League member not found'})
        self.assertEqual(self.state(), before)
        self.emit.assert_not_called()

    def test_failure_after_pick_insert_rolls_back_without_success_event(self):
        before = self.state()
        def fail(sql):
            if 'INSERT INTO "LeagueTeamSlot"' in sql:
                raise RuntimeError('synthetic slot failure')
        self.db.before_query = fail
        response = self.post()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json, {'message': 'Failed to create draft pick'})
        self.assertEqual(self.state(), before)
        self.emit.assert_not_called()

    def test_trusted_model_calls_do_not_require_http_identity(self):
        pick = self.model.create_draft_pick_live(10, 12, 102)
        self.assertEqual(pick['memberId'], 12)
        slot = self.db.connection.execute('SELECT "acquiredWeek" FROM "LeagueTeamSlot"').fetchone()
        self.assertEqual(slot[0], 1)  # Preserve model default, separate from HTTP default 0.
        self.emit.assert_not_called()
