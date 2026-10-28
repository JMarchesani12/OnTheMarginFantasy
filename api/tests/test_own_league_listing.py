"""MOD-003A own-league listing with real JWT/route/query on synthetic rows.

Global status sync is substituted; empty Week data and an adapted interval
expression do not validate PostgreSQL date arithmetic or lifecycle transitions.
"""
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from flask import Flask

from authMiddleware import install_auth_middleware
from endpoints.league.leagueModel import LeagueModel
from endpoints.league.routes import setup_routes
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
from test_profile_regression import ALICE, BOB, ProfileDatabase

OUTSIDER = '00000000-0000-4000-8000-000000000003'


class ListingDatabase(ProfileDatabase):
    def connect(self):
        return self

    def execute(self, statement, params):
        sql = str(statement).replace(
            "w.\"endDate\" + interval '1 microsecond' - interval '7 days'",
            "datetime(w.\"endDate\", '-7 days')",
        )
        cursor = self.connection.execute(sql, params)

        class Result:
            def mappings(self):
                return self

            def fetchmany(self, size):
                return [dict(row) for row in cursor.fetchmany(size)]

            def __iter__(self):
                return iter(SimpleNamespace(_mapping=dict(row)) for row in cursor.fetchall())

        return Result()


class OwnLeagueListingTests(unittest.TestCase):
    def setUp(self):
        self.db = ListingDatabase()
        self.addCleanup(self.db.connection.close)
        self.db.connection.create_function('now', 0, lambda: '2026-10-28T12:00:00Z')
        self.db.connection.executescript('''
            INSERT INTO "User" (id, uuid, email, "displayName") VALUES
                (3, '00000000-0000-4000-8000-000000000003', 'outsider@example.test', 'Outsider');
            CREATE TABLE "Sport" (id INTEGER, name TEXT, "maxPlayersToHaveMaxRounds" INTEGER);
            INSERT INTO "Sport" VALUES (1, 'Basketball', 8);
            CREATE TABLE "League" (id INTEGER, "createdAt" TEXT, name TEXT,
                "numPlayers" INTEGER, status TEXT, "updatedAt" TEXT, "draftDate" TEXT,
                "tradeDeadline" TEXT, "freeAgentDeadline" TEXT, "seasonYear" INTEGER,
                settings TEXT, commissioner INTEGER, sport INTEGER);
            INSERT INTO "League" VALUES
                (10, 'created', 'Active League', 8, 'In-Season', 'updated', NULL, NULL, NULL, 2026, '{}', 1, 1),
                (20, 'created', 'Completed League', 8, 'Completed', 'updated', NULL, NULL, NULL, 2025, '{}', 2, 1);
            CREATE TABLE "LeagueMember" (id INTEGER, "leagueId" INTEGER, "userId" INTEGER,
                "teamName" TEXT, "draftOrder" INTEGER, "seasonPoints" INTEGER);
            INSERT INTO "LeagueMember" VALUES
                (11, 10, 1, 'Alice Team', 1, 10),
                (12, 10, 2, 'Bob Team', 2, 20),
                (21, 20, 2, 'Bob Completed', 1, 30);
            CREATE TABLE "Week" (id INTEGER, "leagueId" INTEGER, "weekNumber" INTEGER,
                "startDate" TEXT, "endDate" TEXT);
            CREATE TABLE "WeeklyTeamScore" ("leagueId" INTEGER, "memberId" INTEGER,
                "weekId" INTEGER, "pointsAwarded" INTEGER);
        ''')
        self.status_sync = self.enterContext(patch.object(LeagueModel, 'sync_due_league_statuses'))
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

    def test_own_list_retains_fields_and_member_specific_data(self):
        response = self.client.post('/api/league/byUser', headers=self.headers(), json={'userId': 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [{
            'leagueId': 10, 'leagueCreatedAt': 'created', 'leagueName': 'Active League',
            'numPlayers': 8, 'status': 'In-Season', 'updatedAt': 'updated', 'draftDate': None,
            'tradeDeadline': None, 'freeAgentDeadline': None, 'seasonYear': 2026, 'settings': '{}',
            'commissionerDisplayName': 'Alice', 'commissionerId': 1,
            'sport': 'Basketball', 'maxPlayersToHaveMaxRounds': 8,
            'memberId': 11, 'teamName': 'Alice Team', 'draftOrder': 1, 'seasonPoints': 10,
            'currentWeekId': None, 'currentWeekNumber': None,
            'currentWeekStartDate': None, 'currentWeekEndDate': None,
        }])
        bob = self.client.post('/api/league/byUser', headers=self.headers(BOB), json={'userId': 2})
        self.assertEqual([row['memberId'] for row in bob.json], [12, 21])

    def test_stage_filters_and_unknown_stage_fallback_are_preserved(self):
        for stage, expected in [('active', [12]), ('completed', [21]), ('all', [12, 21]),
                                ('ACTIVE', [12]), ('unknown', [12, 21]), (None, [12, 21])]:
            with self.subTest(stage=stage):
                response = self.client.post('/api/league/byUser', headers=self.headers(BOB),
                                            json={'userId': 2, 'stage': stage})
                self.assertEqual(response.status_code, 200)
                self.assertEqual([row['memberId'] for row in response.json], expected)

    def test_nonmember_receives_empty_own_list(self):
        response = self.client.post('/api/league/byUser', headers=self.headers(OUTSIDER), json={'userId': 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [])

    def test_foreign_user_ids_are_denied_before_model_side_effects(self):
        for subject, foreign in ((ALICE, 2), (BOB, 1), (OUTSIDER, 1)):
            with self.subTest(subject=subject):
                response = self.client.post('/api/league/byUser', headers=self.headers(subject),
                    json={'userId': foreign, 'actingUserId': foreign})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'error': 'user_identity_mismatch'})
                self.status_sync.assert_not_called()

    def test_body_query_and_header_cannot_override_principal(self):
        response = self.client.post('/api/league/byUser?userId=2',
            headers={**self.headers(), 'X-User-Id': '2'},
            json={'userId': 1, 'uuid': BOB, 'sub': BOB, 'actingUserId': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['memberId'] for row in response.json], [11])

    def test_missing_invalid_and_expired_tokens_are_denied(self):
        for headers in ({}, {'Authorization': 'Bearer invalid'}, self.headers(exp=1)):
            with self.subTest(headers=headers):
                response = self.client.post('/api/league/byUser', headers=headers, json={'userId': 1})
                self.assertEqual(response.status_code, 401)
                self.status_sync.assert_not_called()

    def test_missing_ambiguous_and_empty_subject_fail_explicitly(self):
        cases = [(self.headers('00000000-0000-4000-8000-000000000099'), 403, 'application_identity_not_found'),
                 (self.headers(''), 401, 'missing_authenticated_subject')]
        for headers, status, code in cases:
            with self.subTest(code=code):
                response = self.client.post('/api/league/byUser', headers=headers, json={'userId': 1})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json, {'error': code})
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (4, ALICE))
        self.db.connection.commit()
        response = self.client.post('/api/league/byUser', headers=self.headers(), json={'userId': 1})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})
        self.status_sync.assert_not_called()

    def test_missing_or_invalid_input_is_json_400_before_model(self):
        for payload in ({}, {'userId': None}, [], {'userId': True}, {'userId': 1.5},
                        {'userId': 'invalid'}, {'userId': 1, 'stage': []}):
            with self.subTest(payload=payload):
                response = self.client.post('/api/league/byUser', headers=self.headers(), json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIsInstance(response.json.get('message'), str)
                self.status_sync.assert_not_called()

    def test_matching_numeric_string_id_remains_supported(self):
        response = self.client.post('/api/league/byUser', headers=self.headers(), json={'userId': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['memberId'] for row in response.json], [11])
