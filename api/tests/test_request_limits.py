"""Bound expensive HTTP inputs before invoking domain work."""
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from flask import Flask, request
from authMiddleware import install_auth_middleware
from endpoints.scoring.scoringEndpoints import ScoringEndpoints
from endpoints.transaction.transactionEndpoints import TransactionEndpoints
from endpoints.league.leagueEndpoints import LeagueEndpoints


class RequestLimitTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        install_auth_middleware(self.app, public_prefixes=['/'])
        self.calls = 0

        @self.app.post('/body')
        def body():
            data = request.get_json()
            self.calls += 1
            return {'accepted': len(data['value'])}

        @self.app.post('/ignore')
        def ignore():
            self.calls += 1
            return {'ok': True}

        scoring = ScoringEndpoints(None, None)
        trade = TransactionEndpoints(None)
        leagues = LeagueEndpoints(None)
        self.app.add_url_rule('/weeks', endpoint='weeks', view_func=lambda: scoring.get_points_awarded_for_weeks(10), methods=['POST'])
        self.app.add_url_rule('/trade', endpoint='trade', view_func=lambda: trade.propose_trade(10, 1), methods=['POST'])
        self.app.add_url_rule('/search', view_func=leagues.search_leagues)
        principal = SimpleNamespace(user_id=1, subject='synthetic')
        for module in ('scoring.scoringEndpoints', 'transaction.transactionEndpoints'):
            self.enterContext(patch('endpoints.' + module + '.resolve_authenticated_principal', return_value=principal))
        # Sentinels make accidental domain execution fail visibly through a 500.
        def forbidden(*args, **kwargs):
            raise AssertionError('Domain work must not run for oversized inputs')
        scoring.scoring_read_service.get_weekly_points = forbidden
        trade.workflow_service.propose = forbidden
        leagues.league_read_service.search_public = forbidden
        self.client = self.app.test_client()

    def test_body_above_limit_rejected_even_if_route_ignores_body(self):
        response = self.client.post('/ignore', data=b'x' * (262144 + 1))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json['error']['code'], 'request_too_large')
        self.assertEqual(self.calls, 0)

    def test_body_at_limit_accepted(self):
        data = b'{"value":"' + b'x' * (262144 - 12) + b'"}'
        self.assertEqual(len(data), 262144)
        self.assertEqual(self.client.post('/body', data=data, content_type='application/json').status_code, 200)
        self.assertEqual(self.calls, 1)

    def test_unknown_length_body_still_has_bound(self):
        data = b'{"value":"' + b'x' * 262144 + b'"}'
        response = self.client.open('/body', method='POST', environ_overrides={
            'wsgi.input': io.BytesIO(data), 'wsgi.input_terminated': True,
            'CONTENT_TYPE': 'application/json', 'CONTENT_LENGTH': None,
        })
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.calls, 0)

    def test_collection_limits_precede_domain_work(self):
        response = self.client.post('/weeks', json={'weekNumbers': list(range(129))})
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/trade', json={
            'fromMemberId': 11, 'toMemberId': 12,
            'fromTeamIds': list(range(257)), 'toTeamIds': [],
        })
        self.assertEqual(response.status_code, 400)

    def test_query_resource_bounds_precede_search(self):
        for query in ('q=' + 'a' * 129, 'q=test&offset=10001', 'q=test&offset=-1',
                      'q=test&limit=51', 'q=test&limit=0'):
            with self.subTest(query=query):
                self.assertEqual(self.client.get('/search?' + query).status_code, 400)
        response = self.client.get('/search?' + 'x' * 8193)
        self.assertEqual(response.status_code, 400)

    def test_unknown_length_body_at_limit_is_accepted(self):
        data = b'{"value":"' + b'x' * (262144 - 12) + b'"}'
        response = self.client.open('/body', method='POST', environ_overrides={
            'wsgi.input': io.BytesIO(data), 'wsgi.input_terminated': True,
            'CONTENT_TYPE': 'application/json', 'CONTENT_LENGTH': None,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.calls, 1)
