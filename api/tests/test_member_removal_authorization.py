"""Commissioner member removal: actual JWT/routes/model SQL, synthetic data."""
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


class RemovalDatabase(ProfileDatabase):
    fail_after_delete = False

    def execute(self, statement, params):
        sql = str(statement).replace('FOR UPDATE', '')
        cursor = self.connection.execute(sql, params)
        if self.fail_after_delete and 'DELETE FROM "LeagueMember"' in sql:
            raise RuntimeError('Synthetic failure after member DELETE')

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

            def all(self):
                return [dict(row) for row in cursor.fetchall()]

        return Result()


class MemberRemovalAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.db = RemovalDatabase()
        self.addCleanup(self.db.connection.close)
        self.db.connection.create_function('now', 0, lambda: '2026-10-28T12:00:00Z')
        self.db.connection.create_function('GREATEST', -1, max)
        self.db.connection.executescript('''
            INSERT INTO "User" (id, uuid, email, "displayName") VALUES
                (3, '00000000-0000-4000-8000-000000000003', 'charlie@example.test', 'Charlie'),
                (4, '00000000-0000-4000-8000-000000000004', 'outsider@example.test', 'Outsider');
            CREATE TABLE "League" (id INTEGER PRIMARY KEY, status TEXT,
                commissioner INTEGER, "numPlayers" INTEGER, "updatedAt" TEXT);
            INSERT INTO "League" VALUES (10, 'Pre-Draft', 1, 3, 'old'), (20, 'Pre-Draft', 2, 2, 'old');
            CREATE TABLE "LeagueMember" (id INTEGER PRIMARY KEY, "leagueId" INTEGER,
                "userId" INTEGER, "teamName" TEXT, "draftOrder" INTEGER, "seasonPoints" INTEGER);
            INSERT INTO "LeagueMember" VALUES
                (11, 10, 1, 'Alice Team', 1, 10), (12, 10, 2, 'Bob Team', 2, 20),
                (13, 10, 3, 'Charlie Team', 3, 30),
                (21, 20, 2, 'Bob Other', 1, 40), (22, 20, 1, 'Alice Other', 2, 50);
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
                for table in ('League', 'LeagueMember')}

    def test_commissioner_removes_scoped_member_with_default_order_shift(self):
        before = self.state()
        response = self.client.delete('/api/league/10/members/12', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {
            'removedMemberId': 12, 'removedDraftOrder': 2, 'members': [
                {'memberId': 11, 'userId': 1, 'teamName': 'Alice Team', 'draftOrder': 1, 'displayName': 'Alice'},
                {'memberId': 13, 'userId': 3, 'teamName': 'Charlie Team', 'draftOrder': 2, 'displayName': 'Charlie'},
            ],
        })
        after = self.state()
        self.assertEqual([row['id'] for row in after['LeagueMember']], [11, 13, 21, 22])
        self.assertEqual(after['LeagueMember'][1]['seasonPoints'], 30)
        self.assertEqual(after['League'][0]['numPlayers'], 2)
        self.assertEqual(after['League'][1], before['League'][1])
        self.assertEqual(after['LeagueMember'][-2:], before['LeagueMember'][-2:])

    def test_false_shift_flag_preserves_remaining_orders(self):
        response = self.client.delete('/api/league/10/members/12', headers=self.headers(),
            json={'actingUserId': '1', 'shiftDraftOrder': False})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([member['draftOrder'] for member in response.json['members']], [1, 3])

    def test_second_commissioner_can_remove_member_in_own_league(self):
        response = self.client.delete('/api/league/20/members/22', headers=self.headers(BOB),
                                      json={'actingUserId': 2, 'shiftDraftOrder': True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['removedMemberId'], 22)
        self.assertEqual([member['memberId'] for member in response.json['members']], [21])

    def test_forged_actor_cannot_remove_other_user(self):
        before = self.state()
        for subject in (BOB, OUTSIDER):
            with self.subTest(subject=subject):
                response = self.client.delete('/api/league/10/members/13', headers=self.headers(subject), json={'actingUserId': 1})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'error': 'actor_identity_mismatch'})
                self.assertEqual(self.state(), before)

    def test_member_nonmember_and_foreign_commissioner_are_denied(self):
        before = self.state()
        for subject, actor, league_id, member_id in ((BOB, 2, 10, 13), (OUTSIDER, 4, 10, 13), (ALICE, 1, 20, 22)):
            with self.subTest(subject=subject):
                response = self.client.delete(f'/api/league/{league_id}/members/{member_id}',
                    headers=self.headers(subject), json={'actingUserId': actor})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'message': 'Only the commissioner can remove members'})
                self.assertEqual(self.state(), before)

    def test_foreign_member_missing_targets_and_commissioner_prohibition(self):
        before = self.state()
        for league_id, member_id, message in ((10, 22, 'Member not found in this league'),
                (10, 999, 'Member not found in this league'), (999, 12, 'League not found'),
                (10, 11, 'Cannot remove the commissioner')):
            with self.subTest(league_id=league_id, member_id=member_id):
                response = self.client.delete(f'/api/league/{league_id}/members/{member_id}',
                    headers=self.headers(), json={'actingUserId': 1})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json, {'message': message})
                self.assertEqual(self.state(), before)

    def test_body_query_and_header_cannot_redirect_target_or_actor(self):
        response = self.client.delete('/api/league/10/members/12?leagueId=20&memberId=22',
            headers={**self.headers(), 'X-User-Id': '2'},
            json={'actingUserId': 1, 'leagueId': 20, 'memberId': 22, 'userId': 2, 'uuid': BOB})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['removedMemberId'], 12)
        self.assertIn(22, [row['id'] for row in self.state()['LeagueMember']])

    def test_auth_and_application_identity_failures_cannot_remove(self):
        before = self.state()
        for headers, status in (({}, 401), ({'Authorization': 'Bearer invalid'}, 401),
                (self.headers(exp=1), 401), (self.headers(''), 401),
                (self.headers('00000000-0000-4000-8000-000000000099'), 403)):
            with self.subTest(status=status):
                response = self.client.delete('/api/league/10/members/12', headers=headers, json={'actingUserId': 1})
                self.assertEqual(response.status_code, status)
                self.assertEqual(self.state(), before)
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (5, ALICE))
        self.db.connection.commit()
        response = self.client.delete('/api/league/10/members/12', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})
        self.assertEqual(self.state(), before)

    def test_invalid_object_actor_and_nonboolean_shift_get_json_400(self):
        before = self.state()
        for body in ([], {}, {'actingUserId': True}, {'actingUserId': 1.5}, {'actingUserId': 'invalid'},
                {'actingUserId': 1, 'shiftDraftOrder': 'false'}, {'actingUserId': 1, 'shiftDraftOrder': 0},
                {'actingUserId': 1, 'shiftDraftOrder': None}):
            with self.subTest(body=body):
                response = self.client.delete('/api/league/10/members/12', headers=self.headers(), json=body)
                self.assertEqual(response.status_code, 400)
                self.assertIsInstance(response.json.get('message'), str)
                self.assertEqual(self.state(), before)

    def test_failure_after_member_delete_rolls_back_members_order_and_count(self):
        before = self.state()
        self.db.fail_after_delete = True
        response = self.client.delete('/api/league/10/members/12', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json, {'message': 'Failed to remove member'})
        self.assertEqual(self.state(), before)

    def test_replay_cannot_shift_again_or_change_league_count(self):
        first = self.client.delete('/api/league/10/members/12', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(first.status_code, 200)
        after = self.state()
        repeat = self.client.delete('/api/league/10/members/12', headers=self.headers(), json={'actingUserId': 1})
        self.assertEqual(repeat.status_code, 400)
        self.assertEqual(self.state(), after)

    def test_direct_model_remains_http_independent_with_commissioner_check(self):
        from endpoints.league.leagueModel import LeagueModel
        model = LeagueModel.__new__(LeagueModel)
        model.db = self.db
        with self.assertRaises(PermissionError):
            model.remove_member_and_shift_draft_order(10, 13, 2)
        result = model.remove_member_and_shift_draft_order(10, 13, 1)
        self.assertEqual(result['removedMemberId'], 13)
