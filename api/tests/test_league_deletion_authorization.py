"""Commissioner league deletion: synthetic SQLite cascades, never live data."""
import os
import time
import unittest
from unittest.mock import patch

import jwt
from flask import Flask

from authMiddleware import install_auth_middleware
from endpoints.league.routes import setup_routes
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
from test_member_removal_authorization import RemovalDatabase
from test_profile_regression import ALICE, BOB

OUTSIDER = '00000000-0000-4000-8000-000000000003'


class DeletionDatabase(RemovalDatabase):
    fail_after_league_delete = False

    def execute(self, statement, params):
        result = super().execute(statement, params)
        if self.fail_after_league_delete and 'DELETE FROM "League"' in str(statement):
            result.mappings().first()
            raise RuntimeError('Synthetic failure after league DELETE')
        return result


class LeagueDeletionAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.db = DeletionDatabase()
        self.addCleanup(self.db.connection.close)
        self.db.connection.executescript('''
            PRAGMA foreign_keys = ON;
            INSERT INTO "User" (id, uuid, email, "displayName") VALUES
                (3, '00000000-0000-4000-8000-000000000003', 'outsider@example.test', 'Outsider');
            CREATE TABLE "League" (id INTEGER PRIMARY KEY, name TEXT, commissioner INTEGER);
            INSERT INTO "League" VALUES (10, 'Alice League', 1), (20, 'Bob League', 2);
            CREATE TABLE "LeagueMember" (id INTEGER PRIMARY KEY,
                "leagueId" INTEGER REFERENCES "League"(id) ON DELETE CASCADE, "userId" INTEGER);
            INSERT INTO "LeagueMember" VALUES (11, 10, 1), (12, 10, 2), (21, 20, 2), (22, 20, 1);
            CREATE TABLE "LeagueJoinRequest" (id INTEGER PRIMARY KEY,
                "leagueId" INTEGER REFERENCES "League"(id) ON DELETE CASCADE, "userId" INTEGER);
            INSERT INTO "LeagueJoinRequest" VALUES (101, 10, 3), (201, 20, 3);
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

    def test_each_commissioner_deletes_only_own_url_league_with_existing_response(self):
        for subject, actor, league_id, name in ((ALICE, 1, 10, 'Alice League'), (BOB, '2', 20, 'Bob League')):
            with self.subTest(league_id=league_id):
                before = self.state()
                response = self.client.delete(f'/api/league/{league_id}', headers=self.headers(subject), json={'actingUserId': actor})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json, {'deletedLeagueId': league_id, 'deletedLeagueName': name})
                after = self.state()
                self.assertEqual(after['League'], [row for row in before['League'] if row['id'] != league_id])
                for table in ('LeagueMember', 'LeagueJoinRequest'):
                    self.assertEqual(after[table], [row for row in before[table] if row['leagueId'] != league_id])

    def test_forged_commissioner_actor_cannot_delete(self):
        before = self.state()
        for subject, actor, target in ((BOB, 1, 10), (OUTSIDER, 1, 10), (ALICE, 2, 20)):
            with self.subTest(subject=subject):
                response = self.client.delete(f'/api/league/{target}', headers=self.headers(subject), json={'actingUserId': actor})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'error': 'actor_identity_mismatch'})
                self.assertEqual(self.state(), before)

    def test_member_nonmember_and_other_league_commissioner_cannot_delete(self):
        before = self.state()
        for subject, actor, target in ((BOB, 2, 10), (OUTSIDER, 3, 10), (ALICE, 1, 20)):
            with self.subTest(subject=subject):
                response = self.client.delete(f'/api/league/{target}', headers=self.headers(subject), json={'actingUserId': actor})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'message': 'Only the commissioner can delete this league'})
                self.assertEqual(self.state(), before)

    def test_body_query_headers_cannot_replace_url_league_or_principal(self):
        response = self.client.delete('/api/league/10?leagueId=20&actingUserId=2',
            headers={**self.headers(), 'X-User-Id': '2'},
            json={'actingUserId': 1, 'leagueId': 20, 'commissioner': 2, 'userId': 2, 'uuid': BOB})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'deletedLeagueId': 10, 'deletedLeagueName': 'Alice League'})
        self.assertEqual(self.state()['League'], [{'id': 20, 'name': 'Bob League', 'commissioner': 2}])

    def test_missing_league_and_replay_preserve_error_contract_and_other_data(self):
        before = self.state()
        missing = self.client.delete('/api/league/999', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json, {'message': 'League not found'})
        self.assertEqual(self.state(), before)
        first = self.client.delete('/api/league/10', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(first.status_code, 200)
        after = self.state()
        repeat = self.client.delete('/api/league/10', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(repeat.status_code, 400)
        self.assertEqual(repeat.json, {'message': 'League not found'})
        self.assertEqual(self.state(), after)

    def test_auth_and_application_identity_failures_cannot_delete(self):
        before = self.state()
        for headers, status in (({}, 401), ({'Authorization': 'Bearer invalid'}, 401),
                (self.headers(exp=1), 401), (self.headers(''), 401),
                (self.headers('00000000-0000-4000-8000-000000000099'), 403)):
            with self.subTest(status=status):
                response = self.client.delete('/api/league/10', headers=headers, json={'actingUserId': 1})
                self.assertEqual(response.status_code, status)
                self.assertEqual(self.state(), before)
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (4, ALICE))
        self.db.connection.commit()
        response = self.client.delete('/api/league/10', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})
        self.assertEqual(self.state(), before)

    def test_invalid_actor_or_object_returns_json_400_without_deleting(self):
        before = self.state()
        for body in ([], {}, {'actingUserId': True}, {'actingUserId': 1.5}, {'actingUserId': 'invalid'}):
            with self.subTest(body=body):
                response = self.client.delete('/api/league/10', headers=self.headers(), json=body)
                self.assertEqual(response.status_code, 400)
                self.assertIsInstance(response.json.get('message'), str)
                self.assertEqual(self.state(), before)

    def test_failure_after_delete_rolls_back_league_and_synthetic_cascades(self):
        before = self.state()
        self.db.fail_after_league_delete = True
        response = self.client.delete('/api/league/10', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json, {'message': 'Failed to delete league'})
        self.assertEqual(self.state(), before)

    def test_direct_model_remains_http_independent_and_commissioner_checked(self):
        from endpoints.league.leagueModel import LeagueModel
        model = LeagueModel.__new__(LeagueModel)
        model.db = self.db
        with self.assertRaises(PermissionError):
            model.delete_league(10, 2)
        result = model.delete_league(10, 1)
        self.assertEqual(result, {'deletedLeagueId': 10, 'deletedLeagueName': 'Alice League'})
