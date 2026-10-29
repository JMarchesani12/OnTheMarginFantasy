"""MOD-003B final policy: no HTTP manual allocation or client job bypass."""
import time
import unittest
from unittest.mock import patch

import jwt
from flask import Flask

from authMiddleware import install_auth_middleware
from endpoints.draft.draftModel import DraftModel
from endpoints.draft.routes import setup_routes
from socketioInstance import socketio
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
from test_profile_regression import ALICE, BOB, ProfileDatabase


class HttpManualPickDisabledTests(unittest.TestCase):
    def setUp(self):
        self.db = ProfileDatabase()
        self.addCleanup(self.db.connection.close)
        self.pick = self.enterContext(patch.object(DraftModel, 'create_draft_pick', return_value={'id': 1}))
        self.database = self.enterContext(patch.object(self.db, 'begin', side_effect=AssertionError('HTTP manual picks must not access persistence')))
        self.emit = self.enterContext(patch.object(socketio, 'emit'))
        app = Flask(__name__)
        app.config['TESTING'] = True
        install_auth_middleware(app)
        setup_routes(app, self.db)
        self.client = app.test_client()

    def headers(self, subject=ALICE, **overrides):
        claims = dict(sub=subject, iss=ISSUER, aud='authenticated', exp=int(time.time()) + 600)
        claims.update(overrides)
        token = jwt.encode(claims, SUPABASE_JWT_SECRET, algorithm='HS256')
        return {'Authorization': f'Bearer {token}'}

    def assert_no_execution(self):
        self.pick.assert_not_called()
        self.database.assert_not_called()
        self.emit.assert_not_called()

    def test_authenticated_roles_and_fake_job_flags_are_disabled_for_all_bodies(self):
        bodies = ({'leagueId': 10, 'memberId': 11, 'sportTeamId': 101},
                  {'leagueId': 20, 'memberId': 21, 'sportTeamId': 102, 'actingUserId': 2, 'trustedJob': True},
                  [], {}, 'text', {'memberId': {}, 'leagueId': True})
        for subject in (ALICE, BOB, '00000000-0000-4000-8000-000000000003',
                        '00000000-0000-4000-8000-000000000099'):
            for body in bodies:
                with self.subTest(subject=subject, body=body):
                    headers = self.headers(subject)
                    headers.update({'X-User-Id': '1', 'X-Role': 'commissioner', 'X-Trusted-Job': 'true'})
                    response = self.client.post('/api/draft/pick-manual?actingUserId=1&trustedJob=true',
                                                headers=headers, json=body)
                    self.assertEqual(response.status_code, 410)
                    self.assertEqual(response.json, {'error': 'http_manual_pick_disabled'})
                    self.assert_no_execution()
        response = self.client.post('/api/draft/pick-manual', headers=self.headers(), data='{broken',
                                    content_type='application/json')
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json, {'error': 'http_manual_pick_disabled'})
        self.assert_no_execution()

    def test_anonymous_invalid_and_expired_authentication_still_fail_in_middleware(self):
        for headers in ({}, {'Authorization': 'Bearer not-a-token'}, self.headers(exp=1)):
            with self.subTest(headers=bool(headers)):
                response = self.client.post('/api/draft/pick-manual', headers=headers,
                                            json={'leagueId': 10, 'memberId': 11, 'sportTeamId': 101})
                self.assertEqual(response.status_code, 401)
                self.assertIn('error', response.json)
                self.assert_no_execution()

    def test_preflight_does_not_allocate_or_broadcast(self):
        response = self.client.options('/api/draft/pick-manual')
        self.assertLess(response.status_code, 400)
        self.assert_no_execution()
