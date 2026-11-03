"""MOD-003A admission identity using real JWT/routes/SQL on synthetic SQLite."""
import os
import time
import unittest

import jwt
from flask import Flask
from unittest.mock import patch

from authMiddleware import install_auth_middleware
from endpoints.league.routes import setup_routes
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
from test_profile_regression import ALICE, BOB, ProfileDatabase


class JoinRequestAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.db = ProfileDatabase()
        self.addCleanup(self.db.connection.close)
        self.db.connection.executescript('''
            PRAGMA foreign_keys = ON;
            CREATE TABLE "League" (id INTEGER PRIMARY KEY, commissioner INTEGER);
            INSERT INTO "League" VALUES (10, 1), (20, 2);
            CREATE TABLE "LeagueMember" (id INTEGER PRIMARY KEY, "leagueId" INTEGER,
                "userId" INTEGER, "teamName" TEXT);
            INSERT INTO "LeagueMember" VALUES (21, 20, 1, 'Already Member');
            CREATE TABLE "LeagueJoinRequest" (
                id INTEGER PRIMARY KEY, "createdAt" TEXT DEFAULT '2026-10-28T12:00:00Z',
                "leagueId" INTEGER REFERENCES "League"(id), "userId" INTEGER REFERENCES "User"(id),
                status TEXT, message TEXT, "teamName" TEXT, "resolvedAt" TEXT,
                "resolvedByUserId" INTEGER);
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

    def requests(self):
        return [dict(row) for row in self.db.connection.execute('SELECT * FROM "LeagueJoinRequest" ORDER BY id')]

    def test_each_user_creates_only_own_pending_request_with_existing_shape(self):
        for subject, user_id in ((ALICE, 1), (BOB, 2)):
            with self.subTest(subject=subject):
                response = self.client.post('/api/league/10/joinRequest', headers=self.headers(subject),
                    json={'userId': user_id, 'teamName': '  New Team  ', 'message': 'Please join'})
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json, {
                    'id': user_id, 'createdAt': '2026-10-28T12:00:00Z', 'leagueId': 10,
                    'userId': user_id, 'status': 'PENDING', 'message': 'Please join',
                    'resolvedAt': None, 'resolvedByUserId': None,
                })
                stored = self.requests()[-1]
                self.assertEqual(stored['userId'], user_id)
                self.assertEqual(stored['leagueId'], 10)
                self.assertEqual(stored['teamName'], 'New Team')

    def test_foreign_user_ids_cannot_create_requests(self):
        for subject, foreign in ((ALICE, 2), (BOB, 1)):
            with self.subTest(subject=subject):
                response = self.client.post('/api/league/10/joinRequest', headers=self.headers(subject),
                    json={'userId': foreign, 'teamName': 'Forged'})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'error': 'user_identity_mismatch'})
                self.assertEqual(self.requests(), [])

    def test_body_query_and_header_actors_cannot_override_owner_or_url_league(self):
        response = self.client.post('/api/league/10/joinRequest?userId=2&leagueId=20',
            headers={**self.headers(), 'X-User-Id': '2'},
            json={'userId': 1, 'actingUserId': 2, 'uuid': BOB, 'sub': BOB,
                  'leagueId': 20, 'teamName': 'Own Team'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['leagueId'], 10)
        self.assertEqual(response.json['userId'], 1)
        self.assertEqual(self.requests()[0]['leagueId'], 10)
        self.assertEqual(self.requests()[0]['userId'], 1)

    def test_repeat_returns_own_pending_request_without_duplicate_or_overwrite(self):
        first = self.client.post('/api/league/10/joinRequest', headers=self.headers(),
            json={'userId': 1, 'teamName': 'First', 'message': 'First message'})
        second = self.client.post('/api/league/10/joinRequest', headers=self.headers(),
            json={'userId': 1, 'teamName': 'Replacement', 'message': 'Replacement message'})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json, first.json)
        self.assertEqual(len(self.requests()), 1)
        self.assertEqual(self.requests()[0]['teamName'], 'First')

    def test_foreign_pending_request_cannot_be_returned_through_forged_user_id(self):
        first = self.client.post('/api/league/10/joinRequest', headers=self.headers(),
            json={'userId': 1, 'teamName': 'Alice Team', 'message': 'Private request message'})
        before = self.requests()
        response = self.client.post('/api/league/10/joinRequest', headers=self.headers(BOB),
            json={'userId': 1, 'teamName': 'Forged'})
        self.assertEqual(first.status_code, 201)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('message', response.json)
        self.assertEqual(self.requests(), before)

    def test_missing_invalid_expired_and_empty_subject_cannot_create(self):
        for headers in ({}, {'Authorization': 'Bearer invalid'}, self.headers(exp=1), self.headers('')):
            with self.subTest(headers=headers):
                response = self.client.post('/api/league/10/joinRequest', headers=headers,
                    json={'userId': 1, 'teamName': 'Forged'})
                self.assertEqual(response.status_code, 401)
                self.assertEqual(self.requests(), [])

    def test_missing_and_ambiguous_application_identity_cannot_create(self):
        response = self.client.post('/api/league/10/joinRequest',
            headers=self.headers('00000000-0000-4000-8000-000000000099'), json={'userId': 1, 'teamName': 'Forged'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_not_found'})
        self.db.connection.execute('PRAGMA foreign_keys = OFF')
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (3, ALICE))
        self.db.connection.commit()
        response = self.client.post('/api/league/10/joinRequest', headers=self.headers(),
                                    json={'userId': 1, 'teamName': 'Forged'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})
        self.assertEqual(self.requests(), [])

    def test_invalid_shape_actor_and_team_name_are_json_400_without_write(self):
        for payload in ([], {}, {'userId': True, 'teamName': 'New'},
                        {'userId': 1.5, 'teamName': 'New'}, {'userId': 'invalid', 'teamName': 'New'},
                        {'userId': 1, 'teamName': '   '}):
            with self.subTest(payload=payload):
                response = self.client.post('/api/league/10/joinRequest', headers=self.headers(), json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIsInstance(response.json.get('message'), str)
                self.assertEqual(self.requests(), [])

    def test_existing_member_is_rejected_and_numeric_string_actor_still_works(self):
        existing = self.client.post('/api/league/20/joinRequest', headers=self.headers(),
            json={'userId': 1, 'teamName': 'Already Member'})
        self.assertEqual(existing.status_code, 400)
        self.assertEqual(existing.json, {'message': 'Already a member of this league'})
        self.assertEqual(self.requests(), [])
        own = self.client.post('/api/league/10/joinRequest', headers=self.headers(),
            json={'userId': '1', 'teamName': 'Own Team'})
        self.assertEqual(own.status_code, 201)
        self.assertEqual(own.json['userId'], 1)
