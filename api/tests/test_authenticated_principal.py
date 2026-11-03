"""MOD-001 identity boundary, using the existing guarded runner and fixture."""
import sqlite3
import time
import unittest
from dataclasses import FrozenInstanceError

import jwt
from flask import Flask, jsonify

from authMiddleware import install_auth_middleware
from authenticatedPrincipal import (
    AuthenticatedPrincipal, PrincipalResolutionError, resolve_authenticated_principal,
)
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
from test_profile_regression import ALICE, BOB, ProfileDatabase


class PrincipalDatabase(ProfileDatabase):
    def execute(self, statement, params):
        cursor = self.connection.execute(str(statement), params)

        class Result:
            def mappings(self):
                return self

            def fetchmany(self, size):
                return [dict(row) for row in cursor.fetchmany(size)]

        return Result()


class AuthenticatedPrincipalTests(unittest.TestCase):
    def setUp(self):
        self.db = PrincipalDatabase()
        self.addCleanup(self.db.connection.close)
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        install_auth_middleware(self.app)

        @self.app.post('/principal/<int:actor_id>')
        def principal(actor_id):
            try:
                resolved = resolve_authenticated_principal(self.db)
            except PrincipalResolutionError as error:
                return jsonify(error=error.code), error.status_code
            return jsonify(userId=resolved.user_id, subject=resolved.subject)

        self.client = self.app.test_client()

    def headers(self, subject=ALICE, **overrides):
        claims = dict(sub=subject, aud='authenticated', iss=ISSUER,
                      exp=int(time.time()) + 600)
        claims.update(overrides)
        return {'Authorization': 'Bearer ' + jwt.encode(
            claims, SUPABASE_JWT_SECRET, algorithm='HS256')}

    def test_verified_subject_wins_over_url_body_query_and_headers(self):
        response = self.client.post('/principal/2?userId=2&uuid=' + BOB,
            headers={**self.headers(), 'X-User-Id': '2'},
            json=dict(userId=2, actingUserId=2, uuid=BOB, sub=BOB))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, dict(userId=1, subject=ALICE))
        response = self.client.post('/principal/1', headers=self.headers(BOB))
        self.assertEqual(response.json, dict(userId=2, subject=BOB))

    def test_missing_and_expired_tokens_are_rejected(self):
        for headers in ({}, self.headers(exp=1)):
            with self.subTest(headers=headers):
                self.assertEqual(self.client.post('/principal/1', headers=headers).status_code, 401)

    def test_missing_or_empty_subject_is_explicit(self):
        for subject in (None, '', '   '):
            with self.subTest(subject=subject):
                headers = self.headers(subject)
                # PyJWT rejects null subjects before the resolver; absent and empty
                # subjects can pass JWT verification and must still fail closed.
                if subject is None:
                    claims = dict(aud='authenticated', iss=ISSUER, exp=int(time.time()) + 600)
                    headers = {'Authorization': 'Bearer ' + jwt.encode(
                        claims, SUPABASE_JWT_SECRET, algorithm='HS256')}
                response = self.client.post('/principal/1', headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json, {'error': 'missing_authenticated_subject'})

    def test_missing_application_identity_is_explicit(self):
        response = self.client.post('/principal/1', headers=self.headers(
            '00000000-0000-4000-8000-000000000099'))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_not_found'})

    def test_ambiguous_application_identity_is_explicit(self):
        # Production snapshot permits duplicate UUIDs; loosen only this disposable fixture.
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (3, ALICE))
        self.db.connection.commit()
        response = self.client.post('/principal/1', headers=self.headers())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})

    def test_unverified_request_context_cannot_resolve(self):
        with self.app.test_request_context('/principal/1', json={'sub': ALICE}):
            with self.assertRaises(PrincipalResolutionError) as caught:
                resolve_authenticated_principal(self.db)
            self.assertEqual(caught.exception.code, 'missing_authenticated_subject')

    def test_jobs_and_app_context_have_no_interactive_identity(self):
        for context in (None, self.app.app_context()):
            with self.subTest(context=context):
                if context:
                    context.push()
                try:
                    with self.assertRaises(PrincipalResolutionError) as caught:
                        resolve_authenticated_principal(self.db)
                    self.assertEqual(caught.exception.code, 'interactive_request_required')
                finally:
                    if context:
                        context.pop()

    def test_principal_is_immutable(self):
        principal = AuthenticatedPrincipal(subject=ALICE, user_id=1)
        with self.assertRaises(FrozenInstanceError):
            principal.user_id = 2

    def test_database_errors_propagate_without_identity_fallback(self):
        self.db.connection.close()
        with self.app.test_request_context('/principal/1', headers=self.headers()):
            self.app.preprocess_request()
            with self.assertRaises(sqlite3.ProgrammingError):
                resolve_authenticated_principal(self.db)
