"""Safe wire contracts through the real Flask boundary, without runtime IO."""
import unittest
from flask import Flask, request
from sqlalchemy.exc import IntegrityError
from authMiddleware import install_auth_middleware


class SafeHttpErrorsTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        install_auth_middleware(self.app, public_prefixes=['/'])

        @self.app.post('/json')
        def parse():
            return request.get_json()

        @self.app.get('/conflict')
        def conflict():
            raise IntegrityError('SELECT secret_column', {'password': 'private'}, Exception('private driver details'))

        @self.app.get('/unexpected')
        def unexpected():
            raise RuntimeError('private SQL row and bearer secret')

        @self.app.get('/legacy')
        def legacy():
            return {'message': 'League not found'}, 404

        @self.app.get('/unsafe500')
        def unsafe500():
            return {'message': 'private failure', 'details': 'private SQL'}, 500

        self.client = self.app.test_client()

    def assert_safe(self, response, status, code):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.json['error']['code'], code)
        self.assertIsInstance(response.json['error']['message'], str)
        self.assertEqual(response.json['requestId'], response.headers['X-Request-ID'])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertNotIn('private', response.get_data(as_text=True))
        self.assertNotIn('SELECT', response.get_data(as_text=True))

    def test_malformed_json_is_safe_400(self):
        self.assert_safe(self.client.post('/json', data='{', content_type='application/json'), 400, 'request_invalid')

    def test_method_error_preserves_allow_header(self):
        response = self.client.post('/legacy')
        self.assert_safe(response, 405, 'method_not_allowed')
        self.assertIn('GET', response.headers['Allow'])

    def test_integrity_failure_is_safe_conflict(self):
        self.assert_safe(self.client.get('/conflict'), 409, 'resource_conflict')

    def test_unexpected_failure_is_safe_500(self):
        self.assert_safe(self.client.get('/unexpected'), 500, 'internal_error')

    def test_legacy_concealment_gets_envelope_and_keeps_message(self):
        response = self.client.get('/legacy')
        self.assert_safe(response, 404, 'resource_not_found')
        self.assertEqual(response.json['message'], 'League not found')
        self.assertEqual(response.json['error']['message'], 'League not found')

    def test_caught_server_errors_discard_private_extra_fields(self):
        response = self.client.get('/unsafe500')
        self.assert_safe(response, 500, 'internal_error')
        self.assertEqual(set(response.json), {'error', 'message', 'requestId'})


class EndpointErrorMappingTests(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from endpoints.user.userEndpoints import UserEndpoints
        from endpoints.league.leagueEndpoints import LeagueEndpoints
        from endpoints.roster.rosterEndpoints import RosterEndpoints
        from endpoints.draft.draftEndpoints import DraftEndpoints
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        install_auth_middleware(self.app, public_prefixes=['/'])
        self.user, self.league = UserEndpoints(None), LeagueEndpoints(None)
        self.roster, self.draft = RosterEndpoints(None), DraftEndpoints(None)
        principal = SimpleNamespace(user_id=1, subject='synthetic')
        for module in ('user.userEndpoints', 'league.leagueEndpoints', 'roster.rosterEndpoints', 'draft.draftEndpoints'):
            self.enterContext(patch('endpoints.' + module + '.resolve_authenticated_principal', return_value=principal))
        self.app.add_url_rule('/user', endpoint='user', view_func=lambda: self.user.update_user(1), methods=['PATCH'])
        self.app.add_url_rule('/league', endpoint='league', view_func=lambda: self.league.update_league(10), methods=['PATCH'])
        self.app.add_url_rule('/roster', endpoint='roster', view_func=self.roster.get_member_teams, methods=['POST'])
        self.app.add_url_rule('/start', endpoint='start', view_func=self.draft.start, methods=['POST'])
        self.client = self.app.test_client()

    def test_user_and_league_scalar_types_are_400_before_database_work(self):
        for route, payload in (('/user', {'displayName': []}),
                               ('/league', {'numPlayers': []}),
                               ('/league', {'numPlayers': True}),
                               ('/league', {'name': {}})):
            with self.subTest(route=route, payload=payload):
                response = self.client.patch(route, json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json['error']['code'], 'request_invalid')

    def test_malformed_json_is_400_on_target_adapters(self):
        for route, method in (('/user', 'PATCH'), ('/league', 'PATCH'), ('/roster', 'POST'), ('/start', 'POST')):
            with self.subTest(route=route):
                response = self.client.open(route, method=method, data='{', content_type='application/json')
                self.assertEqual(response.status_code, 400)

    def test_sqlalchemy_integrity_errors_reach_safe_409_on_target_adapters(self):
        def fail(*args, **kwargs):
            raise IntegrityError('SELECT private_column', {'secret': 'private'}, Exception('driver private'))
        self.user.user_service.update_profile = fail
        self.league.league_admin_service.update = fail
        self.roster.roster_service.get_member_teams_for_week = fail
        self.draft.control_service.start = fail
        for route, method, payload in (
            ('/user', 'PATCH', {'displayName': 'Alice'}),
            ('/league', 'PATCH', {'name': 'League'}),
            ('/roster', 'POST', {'leagueId': 10, 'memberId': 11, 'weekNumber': 0}),
            ('/start', 'POST', {'leagueId': 10}),
        ):
            with self.subTest(route=route):
                response = self.client.open(route, method=method, json=payload)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json['error']['code'], 'resource_conflict')
                self.assertNotIn('private', response.get_data(as_text=True))

