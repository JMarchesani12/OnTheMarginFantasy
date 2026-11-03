"""Commissioner admission listing using real JWT/routes/SQL on synthetic data."""
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from flask import Flask

from authMiddleware import install_auth_middleware
from endpoints.league.routes import setup_routes
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
from test_profile_regression import ALICE, BOB, ProfileDatabase

OUTSIDER = '00000000-0000-4000-8000-000000000003'


class RequestListingDatabase(ProfileDatabase):
    before_listing = None

    def execute(self, statement, params):
        if 'FROM "LeagueJoinRequest" r' in str(statement) and self.before_listing:
            self.before_listing()
            self.before_listing = None
        cursor = self.connection.execute(str(statement), params)

        class Result:
            def mappings(self):
                return self

            def fetchone(self):
                row = cursor.fetchone()
                return SimpleNamespace(_mapping=dict(row)) if row else None

            def fetchmany(self, size):
                return [dict(row) for row in cursor.fetchmany(size)]

            def all(self):
                return [dict(row) for row in cursor.fetchall()]

        return Result()


class JoinRequestListingAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.db = RequestListingDatabase()
        self.addCleanup(self.db.connection.close)
        self.db.connection.executescript('''
            INSERT INTO "User" (id, uuid, email, "displayName") VALUES
                (3, '00000000-0000-4000-8000-000000000003', 'outsider@example.test', 'Outsider');
            CREATE TABLE "League" (id INTEGER PRIMARY KEY, commissioner INTEGER);
            INSERT INTO "League" VALUES (10, 1), (20, 2), (30, 1);
            CREATE TABLE "LeagueMember" (id INTEGER, "leagueId" INTEGER, "userId" INTEGER);
            INSERT INTO "LeagueMember" VALUES (11, 10, 1), (12, 10, 2), (21, 20, 2);
            CREATE TABLE "LeagueJoinRequest" (id INTEGER PRIMARY KEY,
                "createdAt" TEXT, "leagueId" INTEGER, "userId" INTEGER, status TEXT,
                message TEXT, "resolvedAt" TEXT, "resolvedByUserId" INTEGER);
            INSERT INTO "LeagueJoinRequest" VALUES
                (101, '2026-10-27', 10, 2, 'PENDING', 'Bob private message', NULL, NULL),
                (102, '2026-10-28', 10, 3, 'DENIED', 'Outsider private message', '2026-10-28', 1),
                (201, '2026-10-28', 20, 1, 'PENDING', 'Alice private message', NULL, NULL);
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

    def test_commissioners_get_only_url_league_with_existing_fields_and_order(self):
        alice = self.client.post('/api/league/10/joinRequests', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(alice.status_code, 200)
        self.assertEqual([row['id'] for row in alice.json], [102, 101])
        self.assertEqual(alice.json[1], {
            'id': 101, 'createdAt': '2026-10-27', 'leagueId': 10, 'userId': 2,
            'status': 'PENDING', 'message': 'Bob private message', 'resolvedAt': None,
            'resolvedByUserId': None, 'userEmail': 'bob@example.test', 'userDisplayName': 'Bob',
        })
        bob = self.client.post('/api/league/20/joinRequests', headers=self.headers(BOB), json={'actingUserId': 2})
        self.assertEqual(bob.status_code, 200)
        self.assertEqual([row['id'] for row in bob.json], [201])

    def test_status_filter_empty_league_and_numeric_string_actor_are_preserved(self):
        for status, ids in [('PENDING', [101]), ('DENIED', [102]), ('APPROVED', []),
                            ('unknown', []), ('', [102, 101]), (None, [102, 101])]:
            with self.subTest(status=status):
                response = self.client.post('/api/league/10/joinRequests', headers=self.headers(),
                    json={'actingUserId': '1', 'status': status})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([row['id'] for row in response.json], ids)
        empty = self.client.post('/api/league/30/joinRequests', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json, [])

    def test_member_nonmember_and_other_league_commissioner_are_denied(self):
        for subject, actor, target in ((BOB, 2, 10), (OUTSIDER, 3, 10), (ALICE, 1, 20)):
            with self.subTest(subject=subject):
                response = self.client.post(f'/api/league/{target}/joinRequests',
                    headers=self.headers(subject), json={'actingUserId': actor})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'message': 'Only the commissioner can perform this action'})

    def test_forged_commissioner_actor_cannot_expose_applicant_data(self):
        for subject, forged, target in ((BOB, 1, 10), (OUTSIDER, 1, 10), (ALICE, 2, 20)):
            with self.subTest(subject=subject):
                response = self.client.post(f'/api/league/{target}/joinRequests',
                    headers=self.headers(subject), json={'actingUserId': forged})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'error': 'actor_identity_mismatch'})

    def test_body_query_and_header_cannot_redirect_league_or_change_identity(self):
        response = self.client.post('/api/league/10/joinRequests?leagueId=20&actingUserId=2',
            headers={**self.headers(), 'X-User-Id': '2'},
            json={'actingUserId': 1, 'leagueId': 20, 'userId': 2, 'uuid': BOB, 'sub': BOB})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.json], [102, 101])

    def test_commissioner_change_before_final_read_returns_no_applicant_data(self):
        self.db.before_listing = lambda: self.db.connection.execute('UPDATE "League" SET commissioner = 2 WHERE id = 10')
        response = self.client.post('/api/league/10/joinRequests', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [])

    def test_missing_invalid_expired_and_empty_subject_cannot_read(self):
        for headers, code in (({}, 'auth_token_missing'), ({'Authorization': 'Bearer invalid'}, 'auth_token_invalid'), (self.headers(exp=1), 'auth_token_invalid'), (self.headers(''), None)):
            with self.subTest(headers=headers):
                response = self.client.post('/api/league/10/joinRequests', headers=headers, json={'actingUserId': 1})
                self.assertEqual(response.status_code, 401)
                if code:
                    self.assertEqual(set(response.json), {'error', 'requestId'})
                    self.assertEqual(response.json['error']['code'], code)
                else:
                    self.assertEqual(response.json, {'error': 'missing_authenticated_subject'})

    def test_missing_and_ambiguous_application_identity_cannot_read(self):
        response = self.client.post('/api/league/10/joinRequests',
            headers=self.headers('00000000-0000-4000-8000-000000000099'), json={'actingUserId': 1})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_not_found'})
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (4, ALICE))
        self.db.connection.commit()
        response = self.client.post('/api/league/10/joinRequests', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})

    def test_invalid_input_and_missing_league_have_safe_json_contracts(self):
        for payload in ([], {}, {'actingUserId': True}, {'actingUserId': 1.5},
                        {'actingUserId': 'invalid'}, {'actingUserId': 1, 'status': ['PENDING']}):
            with self.subTest(payload=payload):
                response = self.client.post('/api/league/10/joinRequests', headers=self.headers(), json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIsInstance(response.json.get('message'), str)
        missing = self.client.post('/api/league/999/joinRequests', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json, {'message': 'League 999 not found'})
