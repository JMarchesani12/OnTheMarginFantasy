"""Commissioner settings PATCH: real auth/routes/model, adapted SQLite query.

PostgreSQL UPDATE CTE/JSON projection is adapted; no live DB/locking claim.
"""
import json
import os
import re
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


class SettingsDatabase(ProfileDatabase):
    before_update = None

    def execute(self, statement, params):
        sql = str(statement)
        is_update = 'WITH updated AS' in sql
        if is_update:
            if self.before_update:
                self.before_update()
                self.before_update = None
            match = re.search(r'WITH updated AS \((.*?)\)\s*SELECT', sql, re.S)
            if not match:
                raise AssertionError('Unsupported update CTE in isolated fixture')
            sql = match.group(1).replace('cast(:settings as jsonb)', ':settings')
        cursor = self.connection.execute(sql, params)

        def convert(row):
            if row is None:
                return None
            values = dict(row)
            if isinstance(values.get('settings'), str):
                values['settings'] = json.loads(values['settings'])
            if is_update:
                sport = self.connection.execute('SELECT * FROM "Sport" WHERE id = ?', (values['sport'],)).fetchone()
                values['sportInfo'] = dict(sport)
            return values

        class Result:
            def mappings(self):
                return self

            def fetchmany(self, size):
                return [convert(row) for row in cursor.fetchmany(size)]

            def fetchone(self):
                values = convert(cursor.fetchone())
                return SimpleNamespace(_mapping=values) if values else None

            def first(self):
                return convert(cursor.fetchone())

        return Result()


class LeagueSettingsAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.db = SettingsDatabase()
        self.addCleanup(self.db.connection.close)
        self.db.connection.create_function('now', 0, lambda: '2026-10-28T12:00:00Z')
        self.db.connection.executescript('''
            INSERT INTO "User" (id, uuid, email, "displayName") VALUES
                (3, '00000000-0000-4000-8000-000000000003', 'outsider@example.test', 'Outsider');
            CREATE TABLE "Sport" (id INTEGER PRIMARY KEY, name TEXT);
            INSERT INTO "Sport" VALUES (1, 'Basketball');
            CREATE TABLE "League" (id INTEGER PRIMARY KEY, "createdAt" TEXT, name TEXT,
                sport INTEGER, "numPlayers" INTEGER, status TEXT, settings TEXT,
                "updatedAt" TEXT, "draftDate" TEXT, "tradeDeadline" TEXT,
                "freeAgentDeadline" TEXT, commissioner INTEGER);
            INSERT INTO "League" VALUES
                (10, 'created', 'Alice League', 1, 8, 'Pre-Draft', '{"ruleSetVersion":"v1","timezone":"UTC"}', 'old', NULL, NULL, NULL, 1),
                (20, 'created', 'Bob League', 1, 8, 'Pre-Draft', '{"ruleSetVersion":"v1","timezone":"UTC"}', 'old', NULL, NULL, NULL, 2);
            CREATE TABLE "LeagueMember" (id INTEGER, "leagueId" INTEGER, "userId" INTEGER);
            INSERT INTO "LeagueMember" VALUES (11, 10, 1), (12, 10, 2), (21, 20, 2);
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

    def league(self, league_id=10):
        return dict(self.db.connection.execute('SELECT * FROM "League" WHERE id = ?', (league_id,)).fetchone())

    def test_each_commissioner_can_save_settings_and_deadlines_in_own_league(self):
        for subject, league_id, commissioner in ((ALICE, 10, 1), (BOB, 20, 2)):
            with self.subTest(league_id=league_id):
                response = self.client.patch(f'/api/league/{league_id}', headers=self.headers(subject), json={
                    'name': 'Updated League', 'numPlayers': 10, 'status': 'Pre-Draft',
                    'draftDate': '2026-11-01T12:00:00Z', 'tradeDeadline': None,
                    'freeAgentDeadline': '2027-01-01T12:00:00Z',
                    'settings': {'timezone': 'UTC', 'bonuses': {}},
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(set(response.json), {'id', 'createdAt', 'name', 'sport', 'numPlayers',
                    'status', 'settings', 'updatedAt', 'draftDate', 'freeAgentDeadline', 'tradeDeadline',
                    'commissioner', 'sportInfo'})
                self.assertEqual(response.json['commissioner'], commissioner)
                self.assertEqual(response.json['settings']['ruleSetVersion'], 'v1')
                self.assertEqual(response.json['sportInfo'], {'id': 1, 'name': 'Basketball'})
                persisted = self.league(league_id)
                self.assertEqual(persisted['name'], 'Updated League')
                self.assertEqual(persisted['draftDate'], '2026-11-01T12:00:00Z')
                self.assertEqual(persisted['numPlayers'], 10)

    def test_member_nonmember_and_other_league_commissioner_are_denied(self):
        for subject, target in ((BOB, 10), (OUTSIDER, 10), (ALICE, 20)):
            with self.subTest(subject=subject, target=target):
                before = self.league(target)
                response = self.client.patch(f'/api/league/{target}', headers=self.headers(subject), json={
                    'name': 'Forged', 'settings': {'timezone': 'UTC'},
                    'actingUserId': before['commissioner'], 'commissioner': before['commissioner'],
                })
                self.assertEqual(self.league(target), before)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'message': 'Only the commissioner can perform this action'})

    def test_commissioner_fields_body_query_and_headers_cannot_transfer_or_impersonate(self):
        response = self.client.patch('/api/league/10?actingUserId=2&leagueId=20',
            headers={**self.headers(), 'X-User-Id': '2'},
            json={'name': 'Own Rename', 'commissioner': 2, 'actingUserId': 2, 'userId': 2,
                  'leagueId': 20, 'sport': 2, 'uuid': BOB})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.league()['commissioner'], 1)
        self.assertEqual(self.league()['sport'], 1)
        self.assertEqual(self.league(20)['name'], 'Bob League')

    def test_commissioner_change_between_read_and_write_prevents_mutation(self):
        before = self.league()
        self.db.before_update = lambda: self.db.connection.execute('UPDATE "League" SET commissioner = 2 WHERE id = 10')
        response = self.client.patch('/api/league/10', headers=self.headers(), json={'name': 'Stale Owner'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.league()['name'], before['name'])
        self.assertEqual(self.league()['updatedAt'], before['updatedAt'])

    def test_missing_invalid_expired_and_empty_subject_fail_without_writes(self):
        for headers in ({}, {'Authorization': 'Bearer invalid'}, self.headers(exp=1), self.headers('')):
            with self.subTest(headers=headers):
                before = self.league()
                response = self.client.patch('/api/league/10', headers=headers, json={'name': 'Forged'})
                self.assertEqual(response.status_code, 401)
                self.assertEqual(self.league(), before)

    def test_missing_and_ambiguous_application_identity_cannot_write(self):
        before = self.league()
        response = self.client.patch('/api/league/10',
            headers=self.headers('00000000-0000-4000-8000-000000000099'), json={'name': 'Forged'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_not_found'})
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (4, ALICE))
        self.db.connection.commit()
        response = self.client.patch('/api/league/10', headers=self.headers(), json={'name': 'Forged'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})
        self.assertEqual(self.league(), before)

    def test_model_validation_and_missing_league_json_contracts_remain(self):
        for payload in ({}, {'settings': []}, {'settings': {'ruleSetVersion': 'v2'}},
                        {'settings': {'timezone': 'Invalid/TestZone'}}):
            with self.subTest(payload=payload):
                before = self.league()
                response = self.client.patch('/api/league/10', headers=self.headers(), json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIsInstance(response.json.get('message'), str)
                self.assertEqual(self.league(), before)
        missing = self.client.patch('/api/league/999', headers=self.headers(), json={'name': 'Missing'})
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json, {'message': 'League 999 not found'})

    def test_non_object_payload_gets_json_400(self):
        before = self.league()
        response = self.client.patch('/api/league/10', headers=self.headers(), json=['invalid'])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.league(), before)

    def test_operational_error_is_safe_json_without_partial_write(self):
        before = self.league()
        execute = self.db.execute

        def fail_league_read(statement, params):
            if 'FROM "League"' in str(statement):
                raise RuntimeError('private SQL/connection detail')
            return execute(statement, params)

        with patch.object(self.db, 'execute', side_effect=fail_league_read):
            response = self.client.patch('/api/league/10', headers=self.headers(), json={'name': 'Failed'})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json, {'message': 'Failed to update league'})
        self.assertEqual(self.league(), before)
