"""MOD-003A creation identity: real JWT/routes/model with synthetic persistence.

SQLite adapts the PostgreSQL INSERT CTE/JSON projection; week initialization is
substituted. These tests do not validate PostgreSQL syntax/types or scheduling.
"""
import json
import os
import re
import time
import unittest
from unittest.mock import patch

import jwt
from flask import Flask

from authMiddleware import install_auth_middleware
from endpoints.league.routes import setup_routes
from endpoints.schedule.scheduleModel import ScheduleModel
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
from test_profile_regression import ALICE, BOB, ProfileDatabase


class CreationDatabase(ProfileDatabase):
    def execute(self, statement, params):
        sql = str(statement)
        if 'WITH created AS' not in sql:
            return super().execute(statement, params)
        # Execute the model's actual INSERT/RETURNING body, then supply the
        # equivalent synthetic sport projection; not a fake authorization check.
        match = re.search(r'WITH created AS \((.*?)\)\s*SELECT', sql, re.S)
        if not match:
            raise AssertionError('Unsupported creation CTE in isolated fixture')
        insert = match.group(1).replace('cast(:settings as jsonb)', ':settings')
        row = self.connection.execute(insert, params).fetchone()
        values = dict(row) if row else None
        if values:
            values['settings'] = json.loads(values['settings'])
            sport = self.connection.execute('SELECT * FROM "Sport" WHERE id = ?', (values['sport'],)).fetchone()
            values['sportInfo'] = dict(sport)

        class Result:
            def mappings(self):
                return self

            def first(self):
                return values

        return Result()


class LeagueCreationAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.db = CreationDatabase()
        self.addCleanup(self.db.connection.close)
        self.db.connection.create_function('now', 0, lambda: '2026-10-28T12:00:00Z')
        self.db.connection.executescript('''
            PRAGMA foreign_keys = ON;
            CREATE TABLE "Sport" (id INTEGER PRIMARY KEY, name TEXT);
            INSERT INTO "Sport" VALUES (1, 'Basketball');
            CREATE TABLE "League" (id INTEGER PRIMARY KEY,
                "createdAt" TEXT DEFAULT '2026-10-28T12:00:00Z', name TEXT, sport INTEGER,
                "numPlayers" INTEGER, status TEXT, settings TEXT, "updatedAt" TEXT,
                "draftDate" TEXT, commissioner INTEGER REFERENCES "User"(id),
                "seasonYear" INTEGER, "isDiscoverable" BOOLEAN);
            CREATE TABLE "LeagueMember" (id INTEGER PRIMARY KEY,
                "leagueId" INTEGER REFERENCES "League"(id), "userId" INTEGER REFERENCES "User"(id),
                "teamName" TEXT, "seasonPoints" INTEGER, "draftOrder" INTEGER);
        ''')
        self.weeks = self.enterContext(patch.object(ScheduleModel, 'ensure_weeks_for_league'))
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

    def payload(self, commissioner=1):
        return dict(name='Margin League', teamName='  Margin Team  ', sport=1, numPlayers=8,
                    status='Pre-Draft', settings={}, draftDate=None, commissioner=commissioner,
                    seasonYear=2026, isDiscoverable=True)

    def assert_no_creation(self):
        for table in ('League', 'LeagueMember'):
            count = self.db.connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            self.assertEqual(count, 0)
        self.weeks.assert_not_called()

    def test_each_user_creates_league_and_initial_membership_as_self(self):
        for subject, user_id in ((ALICE, 1), (BOB, 2)):
            with self.subTest(subject=subject):
                response = self.client.post('/api/league/create', headers=self.headers(subject),
                                             json=self.payload(user_id))
                self.assertEqual(response.status_code, 201)
                created = response.json
                self.assertEqual(created['commissioner'], user_id)
                self.assertEqual(set(created), {'id', 'createdAt', 'name', 'sport', 'numPlayers',
                    'status', 'settings', 'updatedAt', 'draftDate', 'commissioner', 'seasonYear',
                    'isDiscoverable', 'sportInfo', 'creatorMemberId'})
                self.assertEqual(created['sportInfo'], {'id': 1, 'name': 'Basketball'})
                self.assertEqual(created['settings']['timezone'], 'UTC')
                league = self.db.connection.execute('SELECT * FROM "League" WHERE id = ?', (created['id'],)).fetchone()
                member = self.db.connection.execute('SELECT * FROM "LeagueMember" WHERE id = ?', (created['creatorMemberId'],)).fetchone()
                self.assertEqual(league['commissioner'], user_id)
                self.assertEqual(dict(member), {'id': created['creatorMemberId'], 'leagueId': created['id'],
                    'userId': user_id, 'teamName': 'Margin Team', 'seasonPoints': 0, 'draftOrder': 1})
                self.weeks.assert_called_with(created['id'])

    def test_foreign_commissioner_cannot_create_league_or_membership(self):
        for subject, forged in ((ALICE, 2), (BOB, 1)):
            with self.subTest(subject=subject):
                response = self.client.post('/api/league/create', headers=self.headers(subject), json=self.payload(forged))
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'error': 'commissioner_identity_mismatch'})
                self.assert_no_creation()

    def test_extra_actor_fields_and_headers_cannot_override_verified_identity(self):
        payload = {**self.payload(), 'userId': 2, 'actingUserId': 2, 'uuid': BOB, 'sub': BOB}
        response = self.client.post('/api/league/create?commissioner=2',
            headers={**self.headers(), 'X-User-Id': '2'}, json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['commissioner'], 1)
        owner = self.db.connection.execute('SELECT "userId" FROM "LeagueMember"').fetchone()[0]
        self.assertEqual(owner, 1)

    def test_missing_invalid_and_expired_tokens_cannot_create(self):
        for headers in ({}, {'Authorization': 'Bearer invalid'}, self.headers(exp=1)):
            with self.subTest(headers=headers):
                response = self.client.post('/api/league/create', headers=headers, json=self.payload())
                self.assertEqual(response.status_code, 401)
                self.assert_no_creation()

    def test_missing_empty_and_ambiguous_application_identity_cannot_create(self):
        for subject, status, code in (
                ('00000000-0000-4000-8000-000000000099', 403, 'application_identity_not_found'),
                ('', 401, 'missing_authenticated_subject')):
            with self.subTest(code=code):
                response = self.client.post('/api/league/create', headers=self.headers(subject), json=self.payload())
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json, {'error': code})
                self.assert_no_creation()
        # Loosen UUID uniqueness only in this disposable synthetic fixture.
        self.db.connection.execute('PRAGMA foreign_keys = OFF')
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (3, ALICE))
        self.db.connection.commit()
        response = self.client.post('/api/league/create', headers=self.headers(), json=self.payload())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})
        self.assert_no_creation()

    def test_invalid_object_commissioner_and_missing_fields_are_json_400(self):
        missing = self.payload()
        del missing['commissioner']
        for payload in ([], 'invalid', missing, {**self.payload(), 'commissioner': True},
                        {**self.payload(), 'commissioner': 1.5}, {**self.payload(), 'commissioner': 'invalid'}):
            with self.subTest(payload=payload):
                response = self.client.post('/api/league/create', headers=self.headers(), json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIsInstance(response.json.get('message'), str)
                self.assert_no_creation()

    def test_matching_numeric_string_commissioner_remains_supported(self):
        response = self.client.post('/api/league/create', headers=self.headers(), json=self.payload('1'))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['commissioner'], 1)

    def test_invalid_team_name_keeps_existing_model_validation_without_insert(self):
        response = self.client.post('/api/league/create', headers=self.headers(),
            json={**self.payload(), 'teamName': '   '})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {'message': 'Team name is required.'})
        self.assert_no_creation()
