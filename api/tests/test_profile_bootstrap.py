"""Real auth/routes/profile SQL; synthetic data and production auth allowlist."""
import ast
import logging
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import jwt
from flask import Flask

from authMiddleware import install_auth_middleware
from endpoints.user.routes import setup_routes
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
from test_profile_regression import ALICE, BOB, ProfileDatabase

NEW_USER = '00000000-0000-4000-8000-000000000003'


class ProfileBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.db = ProfileDatabase()
        self.addCleanup(self.db.connection.close)
        app = Flask(__name__)
        app.config['TESTING'] = True
        # Read only auth settings, without importing the factory/engine/listener.
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'api.py').read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'install_auth_middleware']
        self.assertEqual(len(calls), 1)
        settings = {kw.arg: ast.literal_eval(kw.value) for kw in calls[0].keywords}
        install_auth_middleware(app, **settings)
        setup_routes(app, self.db)
        self.client = app.test_client()

    def headers(self, subject=ALICE, **overrides):
        claims = dict(sub=subject, email='alice@example.test', aud='authenticated',
                      iss=ISSUER, exp=int(time.time()) + 600)
        claims.update(overrides)
        return {'Authorization': 'Bearer ' + jwt.encode(claims, SUPABASE_JWT_SECRET, algorithm='HS256')}

    def count(self):
        return self.db.connection.execute('SELECT count(*) FROM "User"').fetchone()[0]

    def test_uuid_lookup_requires_valid_auth_in_actual_allowlist(self):
        for headers in ({}, self.headers(exp=1), {'Authorization': 'Bearer broken'}):
            with self.subTest(headers=headers):
                response = self.client.get('/api/user/byUuid/' + ALICE, headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertNotIn('email', response.json)

    def test_own_uuid_lookup_and_foreign_uuid_denial_for_both_users(self):
        for subject, foreign, expected_id in ((ALICE, BOB, 1), (BOB, ALICE, 2)):
            with self.subTest(subject=subject):
                own = self.client.get('/api/user/byUuid/' + subject, headers=self.headers(subject))
                self.assertEqual(own.status_code, 200)
                self.assertEqual(own.json['id'], expected_id)
                denied = self.client.get('/api/user/byUuid/' + foreign, headers=self.headers(subject))
                self.assertEqual(denied.status_code, 404)
                self.assertEqual(denied.json, {'message': 'User not found'})

    def test_missing_profile_can_be_created_from_claims_then_reloaded(self):
        headers = self.headers(NEW_USER, email='new@example.test')
        missing = self.client.get('/api/user/byUuid/' + NEW_USER, headers=headers)
        self.assertEqual(missing.status_code, 404)
        created = self.client.post('/api/user', headers=headers, json={'displayName': ' New '})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json['uuid'], NEW_USER)
        self.assertEqual(created.json['email'], 'new@example.test')
        self.assertEqual(created.json['displayName'], 'New')
        loaded = self.client.get('/api/user/byUuid/' + NEW_USER, headers=headers)
        self.assertEqual(loaded.status_code, 200)
        self.assertEqual(loaded.json, created.json)
        self.assertEqual(self.count(), 3)

    def test_matching_legacy_fields_are_accepted_but_cannot_provision_other_identity(self):
        headers = self.headers(NEW_USER, email='new@example.test')
        for payload in ({'uuid': BOB, 'email': 'new@example.test'},
                        {'uuid': NEW_USER, 'email': 'bob@example.test'}):
            with self.subTest(payload=payload):
                response = self.client.post('/api/user', headers=headers, json=payload)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(self.count(), 2)
                self.assertEqual(self.db.profile(2)['displayName'], 'Bob')
        response = self.client.post('/api/user', headers=headers, json={
            'uuid': NEW_USER, 'email': 'new@example.test', 'displayName': 'New'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['uuid'], NEW_USER)

    def test_existing_profile_cannot_be_reprovisioned_or_changed(self):
        response = self.client.post('/api/user', headers=self.headers(),
                                    json={'displayName': 'Overwritten'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.db.profile(1)['displayName'], 'Alice')

    def test_ambiguous_profile_denies_lookup_and_creation(self):
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (3, ALICE))
        self.db.connection.commit()
        for method, url in (('get', '/api/user/byUuid/' + ALICE), ('post', '/api/user')):
            with self.subTest(method=method):
                response = getattr(self.client, method)(url, headers=self.headers(), json={})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})
                self.assertEqual(self.count(), 3)

    def test_provisioning_requires_valid_subject_and_claim_email(self):
        cases = [({}, 401), (self.headers(exp=1), 401), (self.headers(''), 401),
                 (self.headers(NEW_USER, email=None), 403),
                 (self.headers(NEW_USER, email=' '), 403)]
        for headers, status in cases:
            with self.subTest(headers=headers):
                response = self.client.post('/api/user', headers=headers, json={
                    'email': 'forged@example.test', 'displayName': 'No'})
                self.assertEqual(response.status_code, status)
                self.assertEqual(self.count(), 2)

    def test_provisioning_validates_object_and_name(self):
        for payload in ([], 'invalid', {'displayName': 12}):
            with self.subTest(payload=payload):
                response = self.client.post('/api/user', headers=self.headers(NEW_USER, email='new@example.test'), json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.count(), 2)

    def test_creation_does_not_log_profile_contact_or_token(self):
        with patch.object(logging, 'debug') as debug:
            response = self.client.post('/api/user',
                headers=self.headers(NEW_USER, email='new@example.test'),
                json={'displayName': 'Private Name'})
        self.assertEqual(response.status_code, 201)
        output = str(debug.call_args_list)
        for sensitive in ('new@example.test', 'Private Name', NEW_USER):
            self.assertNotIn(sensitive, output)


    def test_database_constraint_errors_do_not_expose_contact_or_sql(self):
        from sqlalchemy.exc import IntegrityError
        execute = self.db.execute

        def fail_insert(statement, params):
            if 'INSERT INTO' in str(statement):
                raise IntegrityError(str(statement), params,
                                     Exception('private collision new@example.test'))
            return execute(statement, params)

        with patch.object(self.db, 'execute', side_effect=fail_insert):
            response = self.client.post('/api/user',
                headers=self.headers(NEW_USER, email='new@example.test'),
                json={'displayName': 'New'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {'message': 'User creation failed'})
        self.assertEqual(self.count(), 2)
