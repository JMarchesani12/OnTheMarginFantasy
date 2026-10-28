"""Own-request cancellation: real JWT/routes/model and synthetic SQLite rows."""
import os
import time
import unittest
from unittest.mock import patch

import jwt
from flask import Flask

from authMiddleware import install_auth_middleware
from endpoints.league.routes import setup_routes
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
from test_profile_regression import ALICE, BOB, ProfileDatabase

OUTSIDER = '00000000-0000-4000-8000-000000000003'


class CancellationDatabase(ProfileDatabase):
    fail_after_update = False

    def execute(self, statement, params):
        sql = str(statement).replace('FOR UPDATE', '')
        result = super().execute(sql, params)
        if self.fail_after_update and 'UPDATE "LeagueJoinRequest"' in sql:
            result.mappings().first()
            raise RuntimeError('Synthetic failure after cancellation UPDATE')
        return result


class JoinRequestCancellationAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.db = CancellationDatabase()
        self.addCleanup(self.db.connection.close)
        self.db.connection.create_function('now', 0, lambda: '2026-10-28T12:00:00Z')
        self.db.connection.executescript('''
            INSERT INTO "User" (id, uuid, email, "displayName") VALUES
                (3, '00000000-0000-4000-8000-000000000003', 'outsider@example.test', 'Outsider');
            CREATE TABLE "League" (id INTEGER PRIMARY KEY, commissioner INTEGER);
            INSERT INTO "League" VALUES (10, 1), (20, 2);
            CREATE TABLE "LeagueMember" (id INTEGER PRIMARY KEY, "leagueId" INTEGER, "userId" INTEGER);
            INSERT INTO "LeagueMember" VALUES (11, 10, 1), (21, 20, 2);
            CREATE TABLE "LeagueJoinRequest" (id INTEGER PRIMARY KEY, "createdAt" TEXT,
                "leagueId" INTEGER, "userId" INTEGER, status TEXT CHECK (
                    status IN ('PENDING', 'APPROVED', 'DENIED', 'CANCELLED')),
                message TEXT, "teamName" TEXT, "resolvedAt" TEXT, "resolvedByUserId" INTEGER);
            INSERT INTO "LeagueJoinRequest" VALUES
                (101, '2026-10-27', 10, 2, 'PENDING', 'Bob join A', 'Bob Team', NULL, NULL),
                (102, '2026-10-27', 10, 2, 'DENIED', 'Denied', 'Other', '2026-10-27', 1),
                (103, '2026-10-27', 10, 2, 'APPROVED', 'Approved', 'Other', '2026-10-27', 1),
                (104, '2026-10-27', 10, 2, 'CANCELLED', 'Cancelled', 'Other', '2026-10-27', NULL),
                (201, '2026-10-27', 20, 1, 'PENDING', 'Alice join B', 'Alice Team', NULL, NULL);
        ''')
        app = Flask(__name__)
        app.config['TESTING'] = True
        install_auth_middleware(app)
        with patch.dict(os.environ, {'ESPN_BASE_URL': 'https://provider.example.test'}):
            setup_routes(app, self.db)
        self.client = app.test_client()

    def headers(self, subject=BOB, **overrides):
        claims = dict(sub=subject, aud='authenticated', iss=ISSUER, exp=int(time.time()) + 600)
        claims.update(overrides)
        return {'Authorization': 'Bearer ' + jwt.encode(claims, SUPABASE_JWT_SECRET, algorithm='HS256')}

    def state(self):
        return {table: [dict(row) for row in self.db.connection.execute(f'SELECT * FROM "{table}" ORDER BY id')]
                for table in ('League', 'LeagueMember', 'LeagueJoinRequest')}

    def test_both_users_cancel_only_own_canonical_pending_request(self):
        before = self.state()
        for subject, actor, league_id, request_id in ((BOB, 2, 10, 101), (ALICE, 1, 20, 201)):
            with self.subTest(subject=subject):
                response = self.client.post(f'/api/league/{league_id}/joinRequests/{request_id}/cancel',
                    headers=self.headers(subject), json={'userId': actor})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json, {
                    'id': request_id, 'createdAt': '2026-10-27', 'leagueId': league_id,
                    'userId': actor, 'status': 'CANCELLED',
                    'message': 'Bob join A' if actor == 2 else 'Alice join B',
                    'resolvedAt': '2026-10-28T12:00:00Z', 'resolvedByUserId': None,
                })
                stored = self.db.connection.execute('SELECT * FROM "LeagueJoinRequest" WHERE id = ?', (request_id,)).fetchone()
                self.assertEqual(stored['status'], 'CANCELLED')
                self.assertIsNone(stored['resolvedByUserId'])
        self.assertEqual(self.state()['League'], before['League'])
        self.assertEqual(self.state()['LeagueMember'], before['LeagueMember'])

    def test_forged_body_user_cannot_impersonate_request_owner(self):
        before = self.state()
        for subject, forged, league_id, request_id in ((ALICE, 2, 10, 101), (OUTSIDER, 2, 10, 101), (BOB, 1, 20, 201)):
            with self.subTest(subject=subject):
                response = self.client.post(f'/api/league/{league_id}/joinRequests/{request_id}/cancel',
                    headers=self.headers(subject), json={'userId': forged})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'error': 'user_identity_mismatch'})
                self.assertEqual(self.state(), before)

    def test_foreign_owner_including_commissioner_cannot_cancel(self):
        before = self.state()
        for subject, actor in ((ALICE, 1), (OUTSIDER, 3)):
            with self.subTest(subject=subject):
                response = self.client.post('/api/league/10/joinRequests/101/cancel',
                    headers=self.headers(subject), json={'userId': actor})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'message': "Cannot cancel another user's request"})
                self.assertEqual(self.state(), before)

    def test_foreign_league_missing_request_and_all_resolved_statuses_fail_unchanged(self):
        before = self.state()
        for league_id, request_id in ((20, 101), (10, 999), (10, 102), (10, 103), (10, 104)):
            with self.subTest(league_id=league_id, request_id=request_id):
                response = self.client.post(f'/api/league/{league_id}/joinRequests/{request_id}/cancel',
                    headers=self.headers(), json={'userId': 2, 'leagueId': 10})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.state(), before)

    def test_body_query_and_headers_cannot_redirect_or_assign_resolver(self):
        response = self.client.post('/api/league/10/joinRequests/101/cancel?leagueId=20&requestId=201',
            headers={**self.headers(), 'X-User-Id': '1'},
            json={'userId': '2', 'actingUserId': 1, 'leagueId': 20, 'requestId': 201,
                  'resolvedByUserId': 1, 'uuid': ALICE})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['id'], 101)
        self.assertEqual(response.json['leagueId'], 10)
        self.assertIsNone(response.json['resolvedByUserId'])
        self.assertEqual(self.state()['LeagueJoinRequest'][-1]['status'], 'PENDING')

    def test_replay_cannot_change_cancelled_resolution(self):
        first = self.client.post('/api/league/10/joinRequests/101/cancel', headers=self.headers(), json={'userId': 2})
        self.assertEqual(first.status_code, 200)
        after = self.state()
        again = self.client.post('/api/league/10/joinRequests/101/cancel', headers=self.headers(), json={'userId': 2})
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.json, {'message': 'Only pending requests can be cancelled'})
        self.assertEqual(self.state(), after)

    def test_auth_and_identity_failures_cannot_cancel(self):
        before = self.state()
        for headers, status in (({}, 401), ({'Authorization': 'Bearer invalid'}, 401),
                (self.headers(exp=1), 401), (self.headers(''), 401),
                (self.headers('00000000-0000-4000-8000-000000000099'), 403)):
            with self.subTest(status=status):
                response = self.client.post('/api/league/10/joinRequests/101/cancel', headers=headers, json={'userId': 2})
                self.assertEqual(response.status_code, status)
                self.assertEqual(self.state(), before)
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (4, BOB))
        self.db.connection.commit()
        response = self.client.post('/api/league/10/joinRequests/101/cancel', headers=self.headers(), json={'userId': 2})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})
        self.assertEqual(self.state(), before)

    def test_invalid_object_and_actor_have_safe_json_errors(self):
        before = self.state()
        for body in ([], {}, {'userId': True}, {'userId': 2.5}, {'userId': 'invalid'}):
            with self.subTest(body=body):
                response = self.client.post('/api/league/10/joinRequests/101/cancel', headers=self.headers(), json=body)
                self.assertEqual(response.status_code, 400)
                self.assertIsInstance(response.json.get('message'), str)
                self.assertEqual(self.state(), before)

    def test_post_update_failure_rolls_back_cancellation(self):
        before = self.state()
        self.db.fail_after_update = True
        with self.assertLogs(level='ERROR'):
            response = self.client.post('/api/league/10/joinRequests/101/cancel', headers=self.headers(), json={'userId': 2})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json, {'message': 'Failed to cancel join request'})
        self.assertEqual(self.state(), before)

    def test_direct_model_preserves_owner_check_without_http_context(self):
        from endpoints.league.leagueModel import LeagueModel
        model = LeagueModel.__new__(LeagueModel)
        model.db = self.db
        with self.assertRaises(PermissionError):
            model.cancel_join_request(10, 101, 1)
        result = model.cancel_join_request(10, 101, 2)
        self.assertEqual(result['status'], 'CANCELLED')
        self.assertEqual(result['userId'], 2)
