"""MOD-003B state-read stage: real JWT/routes/snapshot SQL on synthetic SQLite.

Reuse the guarded runner and existing profile/read adapters. Only PostgreSQL's
UUID cast is adapted; no app factory, jobs, socket server or deployed DB runs.
"""
import io
import time
import unittest
from contextlib import redirect_stdout

import jwt
from flask import Flask
from sqlalchemy import text

from authMiddleware import install_auth_middleware
from endpoints.draft.draftModel import DraftModel
from endpoints.draft.routes import setup_routes
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
from test_league_read_authorization import ReadDatabase
from test_profile_regression import ALICE, BOB

OUTSIDER = '00000000-0000-4000-8000-000000000003'
MISSING = '00000000-0000-4000-8000-000000000099'


class DraftRow(dict):
    @property
    def _mapping(self):
        return self


class DraftStateDatabase(ReadDatabase):
    def __init__(self):
        super().__init__()
        self.queries = []

    def execute(self, statement, params):
        sql = str(statement).replace('CAST(:uuid AS uuid)', ':uuid')
        self.queries.append(sql)
        result = super().execute(text(sql), params)
        fetchone = result.fetchone

        def mapped_row():
            row = fetchone()
            return DraftRow(row._mapping) if row is not None else None

        # Snapshot uses mappings().fetchone() as well as ordinary Row._mapping.
        result.fetchone = mapped_row
        return result


class DraftStateAuthorizationTests(unittest.TestCase):
    database_type = DraftStateDatabase
    def setUp(self):
        self.db = self.database_type()
        self.addCleanup(self.db.connection.close)
        self.db.connection.create_function('now', 0, lambda: '2026-10-28T12:00:00Z')
        self.db.connection.executescript('''
            INSERT INTO "User" (id, uuid, email, "displayName") VALUES
                (3, '00000000-0000-4000-8000-000000000003', 'outsider@example.test', 'Outsider');
            CREATE TABLE "League" (id INTEGER PRIMARY KEY, "numPlayers" INTEGER,
                settings TEXT, "seasonYear" INTEGER, commissioner INTEGER, "isDiscoverable" BOOLEAN);
            INSERT INTO "League" VALUES
                (10, 2, '{"draft":{"type":"snake","rounds":2}}', 2026, 1, true),
                (20, 1, '{"draft":{"type":"linear","rounds":2}}', 2026, 2, false),
                (30, 1, '{"draft":{"privateMarker":"hidden"}}', 2026, 1, false);
            CREATE TABLE "LeagueMember" (id INTEGER PRIMARY KEY, "leagueId" INTEGER,
                "userId" INTEGER, "teamName" TEXT, "draftOrder" INTEGER);
            INSERT INTO "LeagueMember" VALUES
                (11, 10, 1, 'Alice Open', 1), (12, 10, 2, 'Bob Open', 2),
                (21, 20, 2, 'Bob Private', 1);
            CREATE TABLE "DraftState" ("leagueId" INTEGER PRIMARY KEY, status TEXT,
                "currentOverallPickNumber" INTEGER, "currentMemberId" INTEGER,
                "expiresAt" TEXT, "lastPickAt" TEXT, "updatedAt" TEXT);
            INSERT INTO "DraftState" VALUES
                (10, 'live', 2, 12, '2026-10-28T12:01:00Z', '2026-10-28T12:00:00Z', 'old'),
                (20, 'paused', 1, 21, NULL, NULL, 'old'),
                (30, 'complete', 1, 11, '2026-10-28T12:01:00Z', NULL, 'old');
            CREATE TABLE "DraftPick" (id INTEGER, "leagueId" INTEGER, "createdAt" TEXT,
                "overallPickNumber" INTEGER, "roundNumber" INTEGER, "pickInRound" INTEGER,
                "memberId" INTEGER, "sportTeamId" INTEGER);
            INSERT INTO "DraftPick" VALUES (1, 10, '2026-10-28T12:00:00Z', 1, 1, 1, 11, 101);
            CREATE TABLE "DraftTurn" ("leagueId" INTEGER, "overallPickNumber" INTEGER, "memberId" INTEGER);
            INSERT INTO "DraftTurn" VALUES (10, 1, 11), (10, 2, 12), (10, 3, 12), (10, 4, 11),
                (20, 1, 21), (20, 2, 21);
            CREATE TABLE "SportTeam" (id INTEGER, "sportId" INTEGER, "displayName" TEXT);
            INSERT INTO "SportTeam" VALUES (101, 1, 'Synthetic Team');
            CREATE TABLE "ConferenceMembership" ("sportTeamId" INTEGER, "sportId" INTEGER,
                "seasonYear" INTEGER, "sportConferenceId" INTEGER);
            INSERT INTO "ConferenceMembership" VALUES (101, 1, 2026, 501);
            CREATE TABLE "SportConference" (id INTEGER, "sportId" INTEGER, "conferenceId" INTEGER);
            INSERT INTO "SportConference" VALUES (501, 1, 401);
            CREATE TABLE "Conference" (id INTEGER, name TEXT);
            INSERT INTO "Conference" VALUES (401, 'Synthetic Conference');
        ''')
        self.model = DraftModel(self.db)
        app = Flask(__name__)
        app.config['TESTING'] = True
        install_auth_middleware(app)
        setup_routes(app, self.db)
        self.client = app.test_client()

    def headers(self, subject=ALICE, *, secret=None, **overrides):
        claims = dict(sub=subject, aud='authenticated', iss=ISSUER, exp=int(time.time()) + 600)
        claims.update(overrides)
        token = jwt.encode(claims, secret or SUPABASE_JWT_SECRET, algorithm='HS256')
        return {'Authorization': f'Bearer {token}'}

    def state_rows(self):
        return [dict(row) for row in self.db.connection.execute('SELECT * FROM "DraftState" ORDER BY "leagueId"')]

    def assert_no_snapshot_queries(self):
        self.assertFalse(any('FROM "DraftState"' in sql or 'UPDATE ' in sql for sql in self.db.queries))

    def test_members_keep_complete_snapshot_contract_and_league_scope(self):
        for subject, league_id in ((ALICE, 10), (BOB, 10), (BOB, 20)):
            with self.subTest(subject=subject, league_id=league_id):
                self.assertTrue(self.model.is_supabase_user_in_league(league_id, subject))
                response = self.client.get(f'/api/draft/state/{league_id}', headers=self.headers(subject))
                self.assertEqual(response.status_code, 200)
                payload = response.json
                self.assertEqual(set(payload), {'leagueId', 'draftSettings', 'serverNow', 'state',
                                                'members', 'picks', 'onDeck', 'inTheHole'})
                self.assertEqual(payload['leagueId'], league_id)
                self.assertEqual(payload['state']['leagueId'], league_id)
                self.assertIsInstance(payload['serverNow'], str)
                if league_id == 10:
                    self.assertEqual(payload['draftSettings'], {'type': 'snake', 'rounds': 2})
                    self.assertEqual(payload['members'], [
                        {'memberId': 11, 'userId': 1, 'teamName': 'Alice Open', 'draftOrder': 1},
                        {'memberId': 12, 'userId': 2, 'teamName': 'Bob Open', 'draftOrder': 2}])
                    self.assertEqual(payload['picks'], [{'id': 1, 'createdAt': '2026-10-28T12:00:00Z',
                        'overallPickNumber': 1, 'roundNumber': 1, 'pickInRound': 1, 'memberId': 11,
                        'memberTeamName': 'Alice Open', 'sportTeamId': 101, 'sportTeamName': 'Synthetic Team',
                        'sportConferenceId': 501, 'conferenceName': 'Synthetic Conference'}])
                    self.assertEqual(payload['onDeck'], {'overallPickNumber': 3, 'memberId': 12, 'memberTeamName': 'Bob Open'})
                    self.assertEqual(payload['inTheHole'], {'overallPickNumber': 4, 'memberId': 11, 'memberTeamName': 'Alice Open'})
                else:
                    self.assertEqual(payload['members'], [{'memberId': 21, 'userId': 2, 'teamName': 'Bob Private', 'draftOrder': 1}])
                    self.assertEqual(payload['picks'], [])
                    self.assertIsNone(payload['inTheHole'])

    def test_nonmembers_missing_and_discoverable_leagues_are_not_draft_previews(self):
        for subject, league_id in ((OUTSIDER, 10), (ALICE, 20), (BOB, 30), (ALICE, 30), (OUTSIDER, 999)):
            with self.subTest(subject=subject, league_id=league_id):
                self.assertFalse(self.model.is_supabase_user_in_league(league_id, subject))
                before = self.state_rows()
                self.db.queries.clear()
                response = self.client.get(f'/api/draft/state/{league_id}', headers=self.headers(subject))
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json, {'message': 'League not found'})
                self.assert_no_snapshot_queries()
                self.assertEqual(self.state_rows(), before)

    def test_client_actor_member_league_and_job_claims_cannot_supply_identity(self):
        headers = self.headers(OUTSIDER)
        headers.update({'X-User-Id': '1', 'X-User-Sub': ALICE, 'X-Role': 'commissioner'})
        response = self.client.get('/api/draft/state/10?leagueId=20&userId=1&memberId=11&view=preview',
            headers=headers, json={'leagueId': 20, 'userId': 1, 'memberId': 11,
                                  'actingUserId': 1, 'trustedJob': True, 'sub': ALICE})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {'message': 'League not found'})
        self.assert_no_snapshot_queries()

    def test_authentication_and_missing_application_identity_fail_before_snapshot(self):
        cases = [({}, 401), ({'Authorization': 'Bearer invalid'}, 401),
                 (self.headers(exp=1), 401), (self.headers(secret='other-test-secret-never-production-2026'), 401),
                 (self.headers(''), 401), (self.headers(MISSING), 403)]
        for headers, status in cases:
            with self.subTest(status=status, authorization=bool(headers)):
                self.db.queries.clear()
                response = self.client.get('/api/draft/state/10', headers=headers)
                self.assertEqual(response.status_code, status)
                self.assertIn('error', response.json)
                self.assert_no_snapshot_queries()
        self.assertEqual(response.json, {'error': 'application_identity_not_found'})

    def test_ambiguous_application_identity_fails_explicitly(self):
        self.db.connection.executescript('''
            ALTER TABLE "User" RENAME TO old_user;
            CREATE TABLE "User" AS SELECT * FROM old_user;
            INSERT INTO "User" SELECT 4, uuid, 'duplicate@example.test', 'Duplicate', "createdAt" FROM old_user WHERE id = 1;
        ''')
        response = self.client.get('/api/draft/state/10', headers=self.headers())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})
        self.assert_no_snapshot_queries()

    def test_permission_is_evaluated_in_initial_snapshot_query_before_repair(self):
        def revoke(sql):
            if '"numPlayers", settings' in sql:
                self.db.before_query = None
                self.db.connection.execute('DELETE FROM "LeagueMember" WHERE id = 11')
        self.db.before_query = revoke
        response = self.client.get('/api/draft/state/10', headers=self.headers())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {'message': 'League not found'})
        self.assert_no_snapshot_queries()

    def test_authorized_completed_state_repair_is_preserved_after_authorization(self):
        self.db.connection.execute('UPDATE "DraftState" SET status = \'complete\' WHERE "leagueId" = 10')
        response = self.client.get('/api/draft/state/10', headers=self.headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['state']['status'], 'complete')
        self.assertIsNone(response.json['state']['currentMemberId'])
        self.assertIsNone(response.json['state']['expiresAt'])
        state = self.state_rows()[0]
        self.assertIsNone(state['currentMemberId'])
        self.assertIsNone(state['expiresAt'])
        self.assertEqual(state['updatedAt'], '2026-10-28T12:00:00Z')

    def test_trusted_snapshot_calls_remain_independent_of_http_context(self):
        snapshot = self.model.get_draft_state_snapshot(20)
        self.assertEqual(snapshot['members'][0]['memberId'], 21)
        snapshot = self.model.get_draft_state_snapshot(20, conn=self.db)
        self.assertEqual(snapshot['state']['status'], 'paused')
        with self.assertRaises(PermissionError):
            self.model.get_draft_state_snapshot(20, reader_user_id=1)

    def test_preflight_does_not_execute_snapshot(self):
        response = self.client.options('/api/draft/state/10', json={'userId': 1})
        self.assertLess(response.status_code, 400)
        self.assertEqual(self.db.queries, [])

    def test_database_failures_have_safe_json_without_raw_logging(self):
        def fail(sql):
            if '"numPlayers", settings' in sql:
                raise RuntimeError('synthetic private SQL details')
        self.db.before_query = fail
        with redirect_stdout(io.StringIO()) as logs:
            response = self.client.get('/api/draft/state/10', headers=self.headers())
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json, {'message': 'Failed to get draft state'})
        self.assertNotIn('synthetic private SQL details', logs.getvalue())
