"""Denial auth/transition tests: real JWT/routes/SQL, synthetic SQLite only."""
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

OUTSIDER = '00000000-0000-4000-8000-000000000004'


class DenialDatabase(ProfileDatabase):
    fail_after_update = False

    def execute(self, statement, params):
        sql = str(statement).replace('FOR UPDATE', '')
        result = super().execute(sql, params)
        if self.fail_after_update and 'UPDATE "LeagueJoinRequest"' in sql:
            result.mappings().first()
            raise RuntimeError('Synthetic failure after denial UPDATE')
        return result


class JoinRequestDenialAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.db = DenialDatabase()
        self.addCleanup(self.db.connection.close)
        self.db.connection.create_function('now', 0, lambda: '2026-10-28T12:00:00Z')
        self.db.connection.executescript('''
            INSERT INTO "User" (id, uuid, email, "displayName") VALUES
                (3, '00000000-0000-4000-8000-000000000003', 'applicant@example.test', 'Applicant'),
                (4, '00000000-0000-4000-8000-000000000004', 'outsider@example.test', 'Outsider');
            CREATE TABLE "League" (id INTEGER PRIMARY KEY, commissioner INTEGER);
            INSERT INTO "League" VALUES (10, 1), (20, 2);
            CREATE TABLE "LeagueMember" (id INTEGER PRIMARY KEY, "leagueId" INTEGER, "userId" INTEGER);
            INSERT INTO "LeagueMember" VALUES (11, 10, 1), (12, 10, 2), (21, 20, 2);
            CREATE TABLE "LeagueJoinRequest" (id INTEGER PRIMARY KEY, "createdAt" TEXT,
                "leagueId" INTEGER, "userId" INTEGER, status TEXT CHECK (
                    status IN ('PENDING', 'APPROVED', 'DENIED', 'CANCELLED')),
                message TEXT, "teamName" TEXT, "resolvedAt" TEXT, "resolvedByUserId" INTEGER);
            INSERT INTO "LeagueJoinRequest" VALUES
                (101, '2026-10-27', 10, 3, 'PENDING', 'Join A', 'Applicant Team', NULL, NULL),
                (102, '2026-10-27', 10, 4, 'DENIED', 'Denied', 'Other', '2026-10-27', 1),
                (103, '2026-10-27', 10, 4, 'APPROVED', 'Approved', 'Other', '2026-10-27', 1),
                (104, '2026-10-27', 10, 4, 'CANCELLED', 'Cancelled', 'Other', '2026-10-27', NULL),
                (201, '2026-10-27', 20, 1, 'PENDING', 'Join B', 'Alice Other', NULL, NULL);
        ''')
        app = Flask(__name__)
        app.config['TESTING'] = True
        install_auth_middleware(app)
        with patch.dict(os.environ, {'ESPN_BASE_URL': 'https://provider.example.test'}):
            setup_routes(app, self.db)
        self.client = app.test_client()

    def headers(self, subject=ALICE, **overrides):
        claims = dict(sub=subject, aud='authenticated', iss=ISSUER, exp=int(time.time()) + 600)
        claims.update(overrides)
        return {'Authorization': 'Bearer ' + jwt.encode(claims, SUPABASE_JWT_SECRET, algorithm='HS256')}

    def state(self):
        return {table: [dict(row) for row in self.db.connection.execute(f'SELECT * FROM "{table}" ORDER BY id')]
                for table in ('League', 'LeagueMember', 'LeagueJoinRequest')}

    def test_each_commissioner_denies_canonical_pending_request_as_verified_actor(self):
        before = self.state()
        for subject, actor, league_id, request_id, applicant in ((ALICE, 1, 10, 101, 3), (BOB, 2, 20, 201, 1)):
            with self.subTest(league_id=league_id):
                response = self.client.post(f'/api/league/{league_id}/joinRequests/{request_id}/deny',
                    headers=self.headers(subject), json={'actingUserId': actor})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json, {
                    'id': request_id, 'createdAt': '2026-10-27', 'leagueId': league_id, 'userId': applicant,
                    'status': 'DENIED', 'message': 'Join A' if league_id == 10 else 'Join B',
                    'resolvedAt': '2026-10-28T12:00:00Z', 'resolvedByUserId': actor,
                })
                stored = self.db.connection.execute('SELECT * FROM "LeagueJoinRequest" WHERE id = ?', (request_id,)).fetchone()
                self.assertEqual(stored['status'], 'DENIED')
                self.assertEqual(stored['resolvedByUserId'], actor)
        self.assertEqual(self.state()['League'], before['League'])
        self.assertEqual(self.state()['LeagueMember'], before['LeagueMember'])

    def test_forged_actor_and_other_roles_cannot_deny(self):
        before = self.state()
        for subject, actor, league_id, request_id in ((BOB, 1, 10, 101), (OUTSIDER, 1, 10, 101),
                (BOB, 2, 10, 101), (OUTSIDER, 4, 10, 101), (ALICE, 1, 20, 201)):
            with self.subTest(subject=subject, actor=actor, league_id=league_id):
                response = self.client.post(f'/api/league/{league_id}/joinRequests/{request_id}/deny',
                    headers=self.headers(subject), json={'actingUserId': actor})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(self.state(), before)

    def test_url_scope_and_all_resolved_statuses_reject_without_mutation(self):
        before = self.state()
        for request_id in (201, 999, 102, 103, 104):
            with self.subTest(request_id=request_id):
                response = self.client.post(f'/api/league/10/joinRequests/{request_id}/deny',
                    headers=self.headers(), json={'actingUserId': 1, 'leagueId': 20})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.state(), before)

    def test_body_header_query_cannot_redirect_or_change_resolution_actor(self):
        response = self.client.post('/api/league/10/joinRequests/101/deny?leagueId=20&requestId=201',
            headers={**self.headers(), 'X-User-Id': '2'},
            json={'actingUserId': '1', 'leagueId': 20, 'requestId': 201, 'userId': 2,
                  'resolvedByUserId': 2, 'uuid': BOB})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['id'], 101)
        self.assertEqual(response.json['leagueId'], 10)
        self.assertEqual(response.json['resolvedByUserId'], 1)
        self.assertEqual(self.state()['LeagueJoinRequest'][-1]['status'], 'PENDING')

    def test_repeated_denial_does_not_change_resolution(self):
        first = self.client.post('/api/league/10/joinRequests/101/deny', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(first.status_code, 200)
        after = self.state()
        repeat = self.client.post('/api/league/10/joinRequests/101/deny', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(repeat.status_code, 400)
        self.assertEqual(repeat.json, {'message': 'Join request is not pending'})
        self.assertEqual(self.state(), after)

    def test_auth_and_application_identity_failures_cannot_deny(self):
        before = self.state()
        for headers, status in (({}, 401), ({'Authorization': 'Bearer invalid'}, 401),
                (self.headers(exp=1), 401), (self.headers(''), 401),
                (self.headers('00000000-0000-4000-8000-000000000099'), 403)):
            with self.subTest(status=status):
                response = self.client.post('/api/league/10/joinRequests/101/deny', headers=headers, json={'actingUserId': 1})
                self.assertEqual(response.status_code, status)
                self.assertEqual(self.state(), before)
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (5, ALICE))
        self.db.connection.commit()
        response = self.client.post('/api/league/10/joinRequests/101/deny', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})
        self.assertEqual(self.state(), before)

    def test_invalid_actor_shape_and_missing_league_get_json_errors(self):
        before = self.state()
        for body in ([], {}, {'actingUserId': True}, {'actingUserId': 1.5}, {'actingUserId': 'invalid'}):
            with self.subTest(body=body):
                response = self.client.post('/api/league/10/joinRequests/101/deny', headers=self.headers(), json=body)
                self.assertEqual(response.status_code, 400)
                self.assertIsInstance(response.json.get('message'), str)
                self.assertEqual(self.state(), before)
        missing = self.client.post('/api/league/999/joinRequests/101/deny', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json, {'message': 'League 999 not found'})

    def test_failure_after_denial_update_rolls_back_resolution(self):
        before = self.state()
        self.db.fail_after_update = True
        with self.assertLogs(level='ERROR'):
            response = self.client.post('/api/league/10/joinRequests/101/deny', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json, {'message': 'Failed to deny join request'})
        self.assertEqual(self.state(), before)

    def test_trusted_denial_remains_independent_of_http_identity(self):
        from endpoints.league.leagueModel import LeagueModel
        model = LeagueModel.__new__(LeagueModel)
        model.db = self.db
        result = model.deny_join_request(10, 101, 4)
        self.assertEqual(result['status'], 'DENIED')
        self.assertEqual(result['resolvedByUserId'], 4)
