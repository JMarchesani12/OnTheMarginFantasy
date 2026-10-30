"""Authentication failure contracts on a real Flask/JWT boundary, no engine."""
import time
import unittest
from uuid import UUID

import jwt
from flask import Flask, g
from flask_cors import CORS

from authMiddleware import install_auth_middleware
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET


class HttpAuthBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        CORS(self.app, origins=['https://web.example.test'], expose_headers=['X-Request-ID'])
        install_auth_middleware(self.app, public_paths={'/health', '/api/sports'}, public_prefixes=['/socket.io/'])
        self.writes = 0

        @self.app.post('/api/change')
        def change():
            self.writes += 1
            return {'saved': True}

        @self.app.get('/api/bootstrap')
        def bootstrap():
            return {'subject': g.user['sub']}

        @self.app.get('/health')
        def health():
            return {'ok': True}

        @self.app.get('/api/sports')
        def sports():
            return []

        @self.app.get('/api/hidden')
        def hidden():
            return {'message': 'Trade not found'}, 404

        self.client = self.app.test_client()

    def headers(self, exp=None):
        return {'Authorization': 'Bearer ' + jwt.encode(dict(
            sub='synthetic-no-profile', aud='authenticated', iss=ISSUER,
            exp=exp if exp is not None else int(time.time()) + 600,
        ), SUPABASE_JWT_SECRET, algorithm='HS256')}

    def test_missing_and_invalid_auth_have_distinct_codes_before_mutation(self):
        cases = [({}, 'auth_token_missing'), ({'Authorization': 'Bearer '}, 'auth_token_missing'),
                 ({'Authorization': 'Bearer junk'}, 'auth_token_invalid'),
                 (self.headers(exp=1), 'auth_token_invalid')]
        for headers, code in cases:
            with self.subTest(code=code, headers=headers):
                res = self.client.post('/api/change', headers=headers, json={'job': True})
                self.assertEqual(res.status_code, 401)
                self.assertEqual(res.json['error']['code'], code)
                self.assertEqual(res.json['error']['message'], 'Authentication required')
                self.assertEqual(res.json['requestId'], res.headers['X-Request-ID'])
                UUID(res.json['requestId'])
                self.assertEqual(res.headers['Cache-Control'], 'no-store')
        self.assertEqual(self.writes, 0)

    def test_server_ids_ignore_untrusted_input_and_are_unique_on_success_and_denial(self):
        ids = []
        for headers in ({'X-Request-ID': 'attacker'}, {**self.headers(), 'X-Request-ID': 'attacker'}):
            res = self.client.post('/api/change', headers=headers)
            ids.append(res.headers['X-Request-ID'])
            self.assertNotEqual(ids[-1], 'attacker')
            UUID(ids[-1])
        self.assertNotEqual(*ids)
        self.assertEqual(self.writes, 1)

    def test_subject_only_bootstrap_public_and_preflight_still_work(self):
        self.assertEqual(self.client.get('/api/bootstrap', headers=self.headers()).json, {'subject': 'synthetic-no-profile'})
        self.assertEqual(self.client.get('/health').json, {'ok': True})
        self.assertEqual(self.client.get('/api/sports').json, [])
        res = self.client.options('/api/change', headers={'Origin': 'https://web.example.test', 'Access-Control-Request-Method': 'POST'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers['Access-Control-Allow-Origin'], 'https://web.example.test')
        self.assertEqual(self.writes, 0)

    def test_resource_denial_stays_legacy_404_and_cors_exposes_ids_on_early_denial(self):
        res = self.client.get('/api/hidden', headers=self.headers())
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json, {'message': 'Trade not found'})
        self.assertEqual(res.headers['Cache-Control'], 'no-store')
        denied = self.client.post('/api/change', headers={'Origin': 'https://web.example.test'})
        self.assertEqual(denied.headers['Access-Control-Allow-Origin'], 'https://web.example.test')
        self.assertIn('X-Request-ID', denied.headers['Access-Control-Expose-Headers'])

    def test_authenticated_success_is_not_cached_and_health_payload_is_preserved(self):
        res = self.client.post('/api/change', headers=self.headers())
        self.assertEqual(res.json, {'saved': True})
        self.assertEqual(res.headers['Cache-Control'], 'no-store')
        self.assertEqual(self.client.get('/health').json, {'ok': True})
