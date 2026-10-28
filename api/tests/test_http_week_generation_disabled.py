"""Standalone HTTP week generation is disabled; no model call is permitted."""
import os
import time
import unittest
from unittest.mock import patch

import jwt
from flask import Flask

from authMiddleware import install_auth_middleware
from endpoints.schedule.routes import setup_routes
from endpoints.schedule.scheduleModel import ScheduleModel
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
from test_profile_regression import ALICE, BOB, ProfileDatabase


class HttpWeekGenerationDisabledTests(unittest.TestCase):
    def setUp(self):
        self.db = ProfileDatabase()
        self.addCleanup(self.db.connection.close)
        self.ensure = self.enterContext(patch.object(ScheduleModel, 'ensure_weeks_for_league', return_value=[]))
        app = Flask(__name__)
        app.config['TESTING'] = True
        install_auth_middleware(app)
        with patch.dict(os.environ, {'ESPN_BASE_URL': 'https://provider.example.test'}):
            setup_routes(app, self.db)
        self.client = app.test_client()

    def headers(self, subject=ALICE):
        token = jwt.encode(dict(sub=subject, iss=ISSUER, aud='authenticated', exp=int(time.time()) + 600),
                           SUPABASE_JWT_SECRET, algorithm='HS256')
        return {'Authorization': 'Bearer ' + token}

    def test_all_authenticated_http_callers_are_disabled_without_model_execution(self):
        for subject in (ALICE, BOB, '00000000-0000-4000-8000-000000000099'):
            for body in ({'leagueId': 10}, {'leagueId': 20, 'trustedJob': True, 'actingUserId': 1}, [], {}):
                with self.subTest(subject=subject, body=body):
                    response = self.client.post('/api/schedule/createWeeks', headers=self.headers(subject), json=body)
                    self.assertEqual(response.status_code, 410)
                    self.assertEqual(response.json, {'error': 'http_week_generation_disabled'})
                    self.ensure.assert_not_called()

    def test_anonymous_requests_still_require_authentication(self):
        response = self.client.post('/api/schedule/createWeeks', json={'leagueId': 10})
        self.assertEqual(response.status_code, 401)
        self.ensure.assert_not_called()
