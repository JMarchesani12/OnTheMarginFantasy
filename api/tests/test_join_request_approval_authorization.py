"""Approval identity/transaction tests; synthetic SQLite, no PostgreSQL locking proof."""
import json
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

OUTSIDER = '00000000-0000-4000-8000-000000000004'


class ApprovalDatabase(ProfileDatabase):
    fail_league_update = False

    def execute(self, statement, params):
        sql = str(statement).replace('FOR UPDATE', '')
        if 'WITH locked_league AS' in sql:
            if self.fail_league_update:
                raise RuntimeError('Synthetic failure after membership INSERT')
            sql = (sql.replace("'{}'::jsonb", "'{}'")
                .replace('to_jsonb(c.new_num_rounds)', 'c.new_num_rounds')
                .replace('UPDATE "League" l', 'UPDATE "League" AS l')
                .replace('RETURNING l.id, l."numPlayers", l.settings', 'RETURNING id, "numPlayers", settings'))
        cursor = self.connection.execute(sql, params)

        class Result:
            def mappings(self):
                return self

            def fetchone(self):
                row = cursor.fetchone()
                return SimpleNamespace(_mapping=dict(row)) if row else None

            def first(self):
                row = cursor.fetchone()
                return dict(row) if row else None

            def fetchmany(self, size):
                return [dict(row) for row in cursor.fetchmany(size)]

        return Result()


class JoinRequestApprovalAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.db = ApprovalDatabase()
        self.addCleanup(self.db.connection.close)
        self.db.connection.create_function('now', 0, lambda: '2026-10-28T12:00:00Z')
        self.db.connection.create_function('GREATEST', -1, max)

        def jsonb_set(value, path, replacement, create):
            data = json.loads(value)
            # Fixtures contain draft parent; only this model's path is supported.
            if path != '{draft,numberOfRounds}':
                raise AssertionError('Unsupported synthetic JSON path')
            data['draft']['numberOfRounds'] = replacement
            return json.dumps(data)

        self.db.connection.create_function('jsonb_set', 4, jsonb_set)
        self.db.connection.executescript('''
            INSERT INTO "User" (id, uuid, email, "displayName") VALUES
                (3, '00000000-0000-4000-8000-000000000003', 'applicant@example.test', 'Applicant'),
                (4, '00000000-0000-4000-8000-000000000004', 'outsider@example.test', 'Outsider');
            CREATE TABLE "Sport" (id INTEGER PRIMARY KEY, "maxDraftRounds" INTEGER,
                "maxPlayersToHaveMaxRounds" INTEGER);
            INSERT INTO "Sport" VALUES (1, 8, 8);
            CREATE TABLE "League" (id INTEGER PRIMARY KEY, commissioner INTEGER, sport INTEGER,
                "numPlayers" INTEGER, settings TEXT, "updatedAt" TEXT);
            INSERT INTO "League" VALUES
                (10, 1, 1, 2, '{"draft":{"numberOfRounds":8},"timezone":"UTC"}', 'old'),
                (20, 2, 1, 1, '{"draft":{"numberOfRounds":8},"timezone":"UTC"}', 'old');
            CREATE TABLE "LeagueMember" (id INTEGER PRIMARY KEY, "leagueId" INTEGER,
                "userId" INTEGER, "teamName" TEXT, "draftOrder" INTEGER, "seasonPoints" INTEGER,
                "createdAt" TEXT DEFAULT '2026-10-28T12:00:00Z', UNIQUE ("leagueId", "userId"));
            INSERT INTO "LeagueMember" (id, "leagueId", "userId", "teamName", "draftOrder", "seasonPoints")
                VALUES (11, 10, 1, 'Alice Team', 1, 10), (12, 10, 2, 'Bob Team', 2, 20),
                       (21, 20, 2, 'Bob Other', 1, 30);
            CREATE TABLE "LeagueJoinRequest" (id INTEGER PRIMARY KEY, "createdAt" TEXT,
                "leagueId" INTEGER, "userId" INTEGER, status TEXT, message TEXT,
                "teamName" TEXT, "resolvedAt" TEXT, "resolvedByUserId" INTEGER);
            INSERT INTO "LeagueJoinRequest" VALUES
                (101, '2026-10-27', 10, 3, 'PENDING', 'Join A', 'Applicant Team', NULL, NULL),
                (102, '2026-10-27', 10, 4, 'DENIED', 'Old request', 'Other Team', '2026-10-27', 1),
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

    def test_each_commissioner_approves_url_request_with_verified_resolver(self):
        for subject, actor, league_id, request_id, applicant in ((ALICE, 1, 10, 101, 3), (BOB, 2, 20, 201, 1)):
            with self.subTest(league_id=league_id):
                response = self.client.post(f'/api/league/{league_id}/joinRequests/{request_id}/approve',
                    headers=self.headers(subject), json={'actingUserId': actor})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(set(response.json), {'request', 'member'})
                self.assertEqual(response.json['request'], {
                    'id': request_id, 'createdAt': '2026-10-27', 'leagueId': league_id,
                    'userId': applicant, 'status': 'APPROVED', 'message': 'Join A' if league_id == 10 else 'Join B',
                    'resolvedAt': '2026-10-28T12:00:00Z', 'resolvedByUserId': actor,
                })
                member = response.json['member']
                self.assertEqual(set(member), {'id', 'leagueId', 'userId', 'teamName', 'seasonPoints', 'createdAt'})
                self.assertEqual(member['userId'], applicant)
                self.assertEqual(member['leagueId'], league_id)
                self.assertEqual(member['seasonPoints'], 0)
                stored = self.db.connection.execute('SELECT * FROM "LeagueMember" WHERE id = ?', (member['id'],)).fetchone()
                self.assertEqual(stored['teamName'], 'Applicant Team' if league_id == 10 else 'Alice Other')
                self.assertEqual(stored['draftOrder'], 3 if league_id == 10 else 2)

    def test_forged_commissioner_actor_cannot_mutate_any_state(self):
        before = self.state()
        for subject in (BOB, OUTSIDER):
            with self.subTest(subject=subject):
                response = self.client.post('/api/league/10/joinRequests/101/approve',
                    headers=self.headers(subject), json={'actingUserId': 1})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'error': 'actor_identity_mismatch'})
                self.assertEqual(self.state(), before)

    def test_member_nonmember_and_other_league_commissioner_cannot_approve(self):
        before = self.state()
        for subject, actor, league_id, request_id in ((BOB, 2, 10, 101), (OUTSIDER, 4, 10, 101), (ALICE, 1, 20, 201)):
            with self.subTest(subject=subject):
                response = self.client.post(f'/api/league/{league_id}/joinRequests/{request_id}/approve',
                    headers=self.headers(subject), json={'actingUserId': actor})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(self.state(), before)

    def test_foreign_url_request_and_nonpending_request_cannot_mutate(self):
        before = self.state()
        for request_id in (201, 999, 102):
            with self.subTest(request_id=request_id):
                response = self.client.post(f'/api/league/10/joinRequests/{request_id}/approve',
                    headers=self.headers(), json={'actingUserId': 1, 'leagueId': 20})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.state(), before)

    def test_body_header_and_query_cannot_redirect_or_change_resolution_actor(self):
        response = self.client.post('/api/league/10/joinRequests/101/approve?leagueId=20&requestId=201',
            headers={**self.headers(), 'X-User-Id': '2'},
            json={'actingUserId': '1', 'userId': 2, 'commissioner': 2, 'leagueId': 20,
                  'requestId': 201, 'resolvedByUserId': 2, 'uuid': BOB})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['request']['id'], 101)
        self.assertEqual(response.json['request']['leagueId'], 10)
        self.assertEqual(response.json['request']['resolvedByUserId'], 1)
        self.assertEqual(self.state()['LeagueJoinRequest'][-1]['status'], 'PENDING')

    def test_replay_rejects_without_duplicate_membership_or_further_league_changes(self):
        first = self.client.post('/api/league/10/joinRequests/101/approve', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(first.status_code, 200)
        after = self.state()
        repeat = self.client.post('/api/league/10/joinRequests/101/approve', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(repeat.status_code, 400)
        self.assertEqual(repeat.json, {'message': 'Join request is not pending'})
        self.assertEqual(self.state(), after)

    def test_auth_and_identity_failures_cannot_approve(self):
        before = self.state()
        for headers, status in (({}, 401), ({'Authorization': 'Bearer invalid'}, 401),
                                (self.headers(exp=1), 401), (self.headers(''), 401),
                                (self.headers('00000000-0000-4000-8000-000000000099'), 403)):
            with self.subTest(status=status):
                response = self.client.post('/api/league/10/joinRequests/101/approve', headers=headers, json={'actingUserId': 1})
                self.assertEqual(response.status_code, status)
                self.assertEqual(self.state(), before)
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (5, ALICE))
        self.db.connection.commit()
        response = self.client.post('/api/league/10/joinRequests/101/approve', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})
        self.assertEqual(self.state(), before)

    def test_invalid_actor_and_missing_league_have_safe_json_contracts(self):
        before = self.state()
        for body in ([], {}, {'actingUserId': True}, {'actingUserId': 1.5}, {'actingUserId': 'invalid'}):
            with self.subTest(body=body):
                response = self.client.post('/api/league/10/joinRequests/101/approve', headers=self.headers(), json=body)
                self.assertEqual(response.status_code, 400)
                self.assertIsInstance(response.json.get('message'), str)
                self.assertEqual(self.state(), before)
        missing = self.client.post('/api/league/999/joinRequests/101/approve', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json, {'message': 'League 999 not found'})
        self.assertEqual(self.state(), before)

    def test_failure_after_membership_insert_rolls_back_all_approval_mutations(self):
        before = self.state()
        self.db.fail_league_update = True
        response = self.client.post('/api/league/10/joinRequests/101/approve', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json, {'message': 'Failed to approve join request'})
        self.assertEqual(self.state(), before)


    def test_trusted_model_approval_remains_independent_of_http_principal(self):
        from endpoints.league.leagueModel import LeagueModel
        model = LeagueModel.__new__(LeagueModel)
        model.db = self.db
        # No Flask request context; trusted actor remains audit metadata as before.
        result = model.approve_join_request(10, 101, 4)
        self.assertEqual(result['request']['status'], 'APPROVED')
        self.assertEqual(result['request']['resolvedByUserId'], 4)
        self.assertEqual(result['member']['userId'], 3)
