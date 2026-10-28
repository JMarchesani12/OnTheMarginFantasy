"""MOD-003A self-service member edits: real JWT/routes/SQL, synthetic rows."""
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


class MemberProfileAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.db = ProfileDatabase()
        self.addCleanup(self.db.connection.close)
        self.db.connection.executescript('''
            INSERT INTO "User" (id, uuid, email, "displayName") VALUES
                (3, '00000000-0000-4000-8000-000000000003', 'outsider@example.test', 'Outsider');
            CREATE TABLE "League" (id INTEGER PRIMARY KEY, commissioner INTEGER);
            INSERT INTO "League" VALUES (10, 1), (20, 2);
            CREATE TABLE "LeagueMember" (
                id INTEGER PRIMARY KEY, "leagueId" INTEGER, "userId" INTEGER,
                "teamName" TEXT, "draftOrder" INTEGER, "seasonPoints" INTEGER,
                "createdAt" TEXT DEFAULT '2026-01-01T00:00:00Z');
            INSERT INTO "LeagueMember" (id, "leagueId", "userId", "teamName", "draftOrder", "seasonPoints")
                VALUES (11, 10, 1, 'Alice Team', 1, 10),
                       (12, 10, 2, 'Bob Team', 2, 20),
                       (21, 20, 2, 'Bob Other Team', 1, 30);
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

    def member(self, member_id):
        row = self.db.connection.execute('SELECT * FROM "LeagueMember" WHERE id = ?', (member_id,)).fetchone()
        return dict(row) if row else None

    def test_commissioner_and_member_can_rename_only_their_own_team(self):
        for subject, member_id in ((ALICE, 11), (BOB, 12), (BOB, 21)):
            with self.subTest(member_id=member_id):
                before = self.member(member_id)
                response = self.client.patch(f'/api/league/leagueMember/{member_id}',
                    headers=self.headers(subject), json={'teamName': 'New Team'})
                expected = {**before, 'teamName': 'New Team'}
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json, expected)
                self.assertEqual(self.member(member_id), expected)

    def test_foreign_member_nonmember_and_cross_league_targets_are_denied(self):
        for subject, target in ((ALICE, 12), (BOB, 11), (OUTSIDER, 11), (ALICE, 21)):
            with self.subTest(subject=subject, target=target):
                before = self.member(target)
                response = self.client.patch(f'/api/league/leagueMember/{target}',
                    headers=self.headers(subject), json={'teamName': 'Stolen'})
                self.assertEqual(self.member(target), before)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json, {'message': 'LeagueMember not found'})

    def test_score_order_and_identity_smuggling_cannot_partially_update(self):
        for extra in ({'seasonPoints': 999}, {'draftOrder': 1}, {'userId': 1},
                      {'actingUserId': 1}, {'leagueId': 20}, {'id': 11}, {'uuid': ALICE}):
            with self.subTest(extra=extra):
                before = self.member(12)
                response = self.client.patch('/api/league/leagueMember/12',
                    headers=self.headers(BOB), json={'teamName': 'Tampered', **extra})
                self.assertEqual(self.member(12), before)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json, {'message': 'Only teamName may be updated'})

    def test_forged_header_query_and_body_cannot_impersonate_owner(self):
        before = self.member(12)
        response = self.client.patch('/api/league/leagueMember/12?userId=2&leagueId=10',
            headers={**self.headers(), 'X-User-Id': '2'}, json={'teamName': 'Forged'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.member(12), before)

    def test_missing_or_expired_auth_cannot_write(self):
        for headers in ({}, self.headers(exp=1)):
            with self.subTest(headers=headers):
                before = self.member(11)
                response = self.client.patch('/api/league/leagueMember/11',
                    headers=headers, json={'teamName': 'Forged'})
                self.assertEqual(response.status_code, 401)
                self.assertEqual(self.member(11), before)

    def test_missing_and_ambiguous_application_identity_cannot_write(self):
        missing = self.client.patch('/api/league/leagueMember/11',
            headers=self.headers('00000000-0000-4000-8000-000000000099'), json={'teamName': 'Forged'})
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(missing.json, {'error': 'application_identity_not_found'})
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (4, ALICE))
        self.db.connection.commit()
        ambiguous = self.client.patch('/api/league/leagueMember/11',
            headers=self.headers(), json={'teamName': 'Forged'})
        self.assertEqual(ambiguous.status_code, 403)
        self.assertEqual(ambiguous.json, {'error': 'application_identity_ambiguous'})
        self.assertEqual(self.member(11)['teamName'], 'Alice Team')

    def test_missing_target_and_invalid_input_fail_without_writes(self):
        missing = self.client.patch('/api/league/leagueMember/999', headers=self.headers(), json={'teamName': 'New'})
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json, {'message': 'LeagueMember not found'})
        for payload in ({}, [], {'teamName': ''}, {'teamName': '   '}, {'teamName': None}, {'teamName': 42}):
            with self.subTest(payload=payload):
                response = self.client.patch('/api/league/leagueMember/11', headers=self.headers(), json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.member(11)['teamName'], 'Alice Team')
