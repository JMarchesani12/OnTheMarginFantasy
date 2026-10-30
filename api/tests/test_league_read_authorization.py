"""Remaining league read policy; actual JWT/routes/model, synthetic SQLite.

No current Week rows. PostgreSQL interval syntax is adapted and lifecycle sync
substituted; no date arithmetic, lock, RLS or lifecycle verification claimed.
"""
import json
import os
import time
import unittest
from unittest.mock import patch

import jwt
from flask import Flask

from authMiddleware import install_auth_middleware
from endpoints.league.leagueModel import LeagueModel
from endpoints.league.routes import setup_routes
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
from test_profile_regression import ALICE, BOB, ProfileDatabase

OUTSIDER = '00000000-0000-4000-8000-000000000003'


class ReadRow:
    def __init__(self, values):
        self._mapping = values

    def __getitem__(self, key):
        return list(self._mapping.values())[key] if isinstance(key, int) else self._mapping[key]


class ReadDatabase(ProfileDatabase):
    before_query = None

    def connect(self):
        return self

    def execute(self, statement, params):
        sql = str(statement).replace(
            "w.\"endDate\" + interval '1 microsecond' - interval '7 days'",
            "datetime(w.\"endDate\", '-7 days')")
        if self.before_query:
            self.before_query(sql)
        cursor = self.connection.execute(sql, params)

        def values(row):
            if row is None:
                return None
            result = dict(row)
            if isinstance(result.get('settings'), str):
                result['settings'] = json.loads(result['settings'])
            return result

        class Result:
            def mappings(self):
                return self

            def first(self):
                return values(cursor.fetchone())

            def fetchmany(self, size):
                return [values(row) for row in cursor.fetchmany(size)]

            def fetchone(self):
                row = values(cursor.fetchone())
                return ReadRow(row) if row is not None else None

            def all(self):
                return [values(row) for row in cursor.fetchall()]

            def fetchall(self):
                return [ReadRow(values(row)) for row in cursor.fetchall()]

            def __iter__(self):
                return iter(self.fetchall())

        return Result()


class LeagueReadAuthorizationTests(unittest.TestCase):
    paths = ('', '/rules', '/members', '/conferences')

    def setUp(self):
        self.db = ReadDatabase()
        self.addCleanup(self.db.connection.close)
        self.db.connection.create_function('now', 0, lambda: '2026-10-28T12:00:00Z')
        self.db.connection.executescript('''
            INSERT INTO "User" (id, uuid, email, "displayName") VALUES
                (3, '00000000-0000-4000-8000-000000000003', 'outsider@example.test', 'Outsider');
            CREATE TABLE "League" (id INTEGER PRIMARY KEY, name TEXT, sport INTEGER,
                commissioner INTEGER, "isDiscoverable" BOOLEAN, settings TEXT, "seasonYear" INTEGER,
                "draftDate" TEXT, "tradeDeadline" TEXT, "freeAgentDeadline" TEXT, status TEXT);
            INSERT INTO "League" VALUES
                (10, 'Open League', 1, 1, true, '{"ruleSetVersion":"v1","timezone":"UTC"}', 2026, NULL, NULL, NULL, 'Pre-Draft'),
                (20, 'Private League', 1, 1, false, '{"ruleSetVersion":"v1","timezone":"UTC"}', 2026, NULL, NULL, NULL, 'Pre-Draft'),
                (30, 'Bob League', 1, 2, false, '{"ruleSetVersion":"v1","timezone":"UTC"}', 2026, NULL, NULL, NULL, 'Pre-Draft');
            CREATE TABLE "LeagueMember" (id INTEGER PRIMARY KEY, "createdAt" TEXT DEFAULT 'created',
                "leagueId" INTEGER, "userId" INTEGER, "teamName" TEXT, "draftOrder" INTEGER, "seasonPoints" INTEGER);
            INSERT INTO "LeagueMember" (id, "leagueId", "userId", "teamName", "draftOrder", "seasonPoints") VALUES
                (11, 10, 1, 'Alice Open', 1, 10), (12, 10, 2, 'Bob Open', 2, 20),
                (21, 20, 2, 'Bob Private', 1, 30);
            CREATE TABLE "Week" (id INTEGER, "leagueId" INTEGER, "weekNumber" INTEGER, "startDate" TEXT, "endDate" TEXT);
            CREATE TABLE "WeeklyTeamScore" ("leagueId" INTEGER, "memberId" INTEGER, "weekId" INTEGER, "pointsAwarded" INTEGER);
            CREATE TABLE "SportTeam" (id INTEGER, "sportId" INTEGER, "displayName" TEXT, tier INTEGER);
            INSERT INTO "SportTeam" VALUES (1, 1, 'Synthetic Team', 1);
            CREATE TABLE "Conference" (id INTEGER, name TEXT);
            INSERT INTO "Conference" VALUES (1, 'Synthetic Conference');
            CREATE TABLE "SportConference" (id INTEGER, "conferenceId" INTEGER, "sportId" INTEGER, "maxTeamsPerOwner" INTEGER);
            INSERT INTO "SportConference" VALUES (1, 1, 1, 2);
            CREATE TABLE "ConferenceMembership" ("sportConferenceId" INTEGER, "seasonYear" INTEGER);
            INSERT INTO "ConferenceMembership" VALUES (1, 2026);
        ''')
        self.sync = self.enterContext(patch.object(LeagueModel, 'sync_due_league_statuses'))
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

    def test_members_and_commissioners_keep_full_reads_including_private_leagues(self):
        for subject, league_id in ((ALICE, 10), (BOB, 10), (ALICE, 20), (BOB, 20), (BOB, 30)):
            for path in self.paths:
                with self.subTest(subject=subject, league_id=league_id, path=path):
                    response = self.client.get(f'/api/league/{league_id}{path}', headers=self.headers(subject))
                    self.assertEqual(response.status_code, 200)
                    if path == '':
                        self.assertEqual(response.json['settings']['ruleSetVersion'], 'v1')
                        self.assertIn('commissioner', response.json)
                    elif path == '/rules':
                        self.assertEqual(response.json['version'], 'v1')
                        self.assertEqual(response.json['leagueId'], league_id)
                    elif path == '/members' and response.json:
                        self.assertIn('seasonPoints', response.json[0])
                        self.assertIn('draftOrder', response.json[0])
                    elif path == '/conferences':
                        self.assertEqual(response.json['conferences'][0]['displayName'], 'Synthetic Conference')

    def test_nonmember_discoverable_details_are_only_explicit_preview_fields(self):
        response = self.client.get('/api/league/10', headers=self.headers(OUTSIDER))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'id': 10, 'name': 'Open League', 'sport': 1, 'commissionerDisplayName': 'Alice'})
        self.sync.assert_not_called()

    def test_nonmember_discoverable_member_preview_never_contains_actor_or_scores(self):
        response = self.client.get('/api/league/10/members', headers=self.headers(OUTSIDER))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [
            {'id': 11, 'teamName': 'Alice Open', 'displayName': 'Alice'},
            {'id': 12, 'teamName': 'Bob Open', 'displayName': 'Bob'},
        ])
        self.assertNotIn('example.test', response.get_data(as_text=True))
        self.sync.assert_not_called()

    def test_nonmember_cannot_read_rules_or_conferences_even_when_discoverable(self):
        for path in ('/rules', '/conferences'):
            with self.subTest(path=path):
                response = self.client.get('/api/league/10' + path, headers=self.headers(OUTSIDER))
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'message': 'League membership required'})
        self.sync.assert_not_called()

    def test_private_missing_and_foreign_leagues_never_expose_data(self):
        for subject, league_id in ((OUTSIDER, 20), (ALICE, 30), (OUTSIDER, 999)):
            for path in self.paths:
                with self.subTest(subject=subject, league_id=league_id, path=path):
                    response = self.client.get(f'/api/league/{league_id}{path}', headers=self.headers(subject))
                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(response.json, {'message': 'League not found'})
        self.sync.assert_not_called()

    def test_preview_query_can_only_reduce_member_payload_and_cannot_unlock_private(self):
        own = self.client.get('/api/league/10/members?view=preview', headers=self.headers())
        self.assertEqual(own.status_code, 200)
        self.assertEqual(set(own.json[0]), {'id', 'teamName', 'displayName'})
        denied = self.client.get('/api/league/20/members?view=preview&userId=1',
            headers={**self.headers(OUTSIDER), 'X-User-Id': '1'})
        self.assertEqual(denied.status_code, 404)

    def test_auth_and_identity_errors_on_every_read(self):
        for headers, status, code in (({}, 401, 'auth_token_missing'), (self.headers(exp=1), 401, 'auth_token_invalid'), (self.headers(''), 401, None),
                (self.headers('00000000-0000-4000-8000-000000000099'), 403, None)):
            for path in self.paths:
                with self.subTest(status=status, path=path):
                    response = self.client.get('/api/league/10' + path, headers=headers)
                    self.assertEqual(response.status_code, status)
                    if code:
                        self.assertEqual(set(response.json), {'error', 'requestId'})
                        self.assertEqual(response.json['error']['code'], code)
                    else:
                        self.assertEqual(set(response.json), {'error'})
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (4, ALICE))
        self.db.connection.commit()
        for path in self.paths:
            response = self.client.get('/api/league/10' + path, headers=self.headers())
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})
        self.sync.assert_not_called()

    def test_requesting_full_projection_cannot_elevate_nonmember(self):
        for path in ('', '/members'):
            with self.subTest(path=path):
                response = self.client.get('/api/league/10' + path + '?view=full', headers=self.headers(OUTSIDER))
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'message': 'League membership required'})

    def test_final_full_query_rechecks_membership_after_initial_access_check(self):
        def revoke(sql):
            if 'l.*' in sql:
                self.db.before_query = None
                self.db.connection.execute('DELETE FROM "LeagueMember" WHERE id = 12')
        self.db.before_query = revoke
        response = self.client.get('/api/league/10?view=full', headers=self.headers(BOB))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json, {'message': 'League not found'})

    def test_preview_query_rechecks_discoverability_before_returning_names(self):
        def make_private(sql):
            if 'SELECT lm.id, lm."teamName"' in sql:
                self.db.before_query = None
                self.db.connection.execute('UPDATE "League" SET "isDiscoverable" = false WHERE id = 10')
        self.db.before_query = make_private
        response = self.client.get('/api/league/10/members?view=preview', headers=self.headers(OUTSIDER))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [])

    def test_explicit_details_preview_reduces_even_member_and_commissioner_reads(self):
        for subject, league_id in ((ALICE, 10), (BOB, 10), (ALICE, 20), (BOB, 30)):
            with self.subTest(subject=subject, league_id=league_id):
                response = self.client.get(f'/api/league/{league_id}?view=preview', headers=self.headers(subject))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(set(response.json), {'id', 'name', 'sport', 'commissionerDisplayName'})
                self.assertEqual(response.json['id'], league_id)
        self.sync.assert_not_called()
