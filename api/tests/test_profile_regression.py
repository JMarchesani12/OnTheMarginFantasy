"""J1/K0/K1 baseline using real routes, JWT verification and profile SQL.

SQLite is a disposable executor for this compatible SQL subset, not a
Postgres/RLS substitute. Numeric-ID isolation assertions protect MOD-002 stage 1.
"""
import sqlite3
import sys
import time
import unittest
from pathlib import Path

import jwt
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from authMiddleware import install_auth_middleware
from endpoints.user.routes import setup_routes
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET

ALICE = "00000000-0000-4000-8000-000000000001"
BOB = "00000000-0000-4000-8000-000000000002"


class ProfileDatabase:
    """Small SQLAlchemy result adapter; executes real SQL on in-memory data."""
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('''CREATE TABLE "User" (
            id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, email TEXT UNIQUE,
            "displayName" TEXT, "createdAt" TEXT DEFAULT '2026-01-01T00:00:00Z'
        )''')
        self.connection.executemany(
            'INSERT INTO "User" (id, uuid, email, "displayName") VALUES (?, ?, ?, ?)',
            [(1, ALICE, "alice@example.test", "Alice"),
             (2, BOB, "bob@example.test", "Bob")],
        )
        self.connection.commit()

    def begin(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        self.connection.rollback() if kind else self.connection.commit()
        return False

    def execute(self, statement, params):
        cursor = self.connection.execute(str(statement), params)

        class Result:
            def fetchone(self):
                from types import SimpleNamespace
                row = cursor.fetchone()
                return SimpleNamespace(_mapping=dict(row)) if row else None

            def mappings(self):
                return self

            def fetchmany(self, size):
                return [dict(row) for row in cursor.fetchmany(size)]

            def first(self):
                row = cursor.fetchone()
                return dict(row) if row else None

        return Result()

    def profile(self, user_id):
        row = self.connection.execute('SELECT * FROM "User" WHERE id = ?', (user_id,)).fetchone()
        return dict(row) if row else None


class ProfileRegressionTests(unittest.TestCase):
    def setUp(self):
        self.db = ProfileDatabase()
        self.addCleanup(self.db.connection.close)
        app = Flask(__name__)
        app.config["TESTING"] = True
        # No production factory, engine, dotenv or background listener imported.
        install_auth_middleware(app)
        setup_routes(app, self.db)
        self.client = app.test_client()

    def headers(self, subject=ALICE, *, secret=None, **overrides):
        claims = {"sub": subject, "aud": "authenticated", "iss": ISSUER,
                  "exp": int(time.time()) + 600}
        claims.update(overrides)
        token = jwt.encode(claims, secret or SUPABASE_JWT_SECRET, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    def test_missing_malformed_and_empty_bearers_cannot_read_or_write_profiles(self):
        for authorization in [None, "Basic test", "Bearer ", "Bearer not-a-jwt"]:
            with self.subTest(authorization=authorization):
                headers = {} if authorization is None else {"Authorization": authorization}
                read = self.client.get('/api/user/1', headers=headers)
                write = self.client.patch('/api/user/1', headers=headers, json={"displayName": "Changed"})
                self.assertEqual(read.status_code, 401)
                self.assertEqual(write.status_code, 401)
                self.assertEqual(read.json['error']['code'],
                    'auth_token_invalid' if authorization == 'Bearer not-a-jwt' else 'auth_token_missing')
                self.assertEqual(read.json['requestId'], read.headers['X-Request-ID'])
                self.assertNotIn("email", read.json)
                self.assertEqual(self.db.profile(1)["displayName"], "Alice")

    def test_expiry_signature_issuer_and_audience_are_verified_before_profile_access(self):
        cases = [self.headers(exp=1), self.headers(secret="wrong-synthetic-signing-secret-2026"),
                 self.headers(iss="https://other.example.test/auth/v1"),
                 self.headers(aud="anonymous")]
        for headers in cases:
            with self.subTest(token=cases.index(headers)):
                response = self.client.get('/api/user/1', headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(set(response.json), {'error', 'requestId'})
                self.assertEqual(response.json['error']['code'], 'auth_token_invalid')

    def test_preflight_cannot_execute_a_profile_update(self):
        response = self.client.options('/api/user/1', json={"displayName": "Changed"})
        self.assertLess(response.status_code, 400)
        self.assertEqual(self.db.profile(1)["displayName"], "Alice")

    def test_own_profile_save_and_reload_preserves_identity_and_other_account(self):
        response = self.client.patch('/api/user/1', headers=self.headers(), json={
            "displayName": "Alice Updated", "email": "replacement@example.test",
            "uuid": BOB, "id": 2,
        })
        self.assertEqual(response.status_code, 200)
        reloaded = self.client.get('/api/user/1', headers=self.headers())
        self.assertEqual(reloaded.status_code, 200)
        self.assertEqual(reloaded.json, {
            "id": 1, "uuid": ALICE, "email": "alice@example.test",
            "displayName": "Alice Updated", "createdAt": "2026-01-01T00:00:00Z",
        })
        self.assertEqual(self.db.profile(2)["displayName"], "Bob")
        self.assertEqual(response.json, reloaded.json)

    def test_missing_profile_and_empty_update_have_json_contracts(self):
        missing = self.client.get('/api/user/999', headers=self.headers())
        invalid = self.client.patch('/api/user/1', headers=self.headers(), json={"email": "ignored@example.test"})
        self.assertEqual(missing.status_code, 404)
        self.assertIsInstance(missing.json.get("message"), str)
        self.assertEqual(invalid.status_code, 400)
        self.assertIsInstance(invalid.json.get("message"), str)
        self.assertEqual(self.db.profile(1)["email"], "alice@example.test")

    def test_mod_002_foreign_profile_read_is_denied(self):
        """Known defect: JWT A must not expose B's private profile (BE D01)."""
        response = self.client.get('/api/user/2', headers=self.headers())
        self.assertIn(response.status_code, (403, 404),
                      "MOD-002: Alice's token can read Bob's profile")
        self.assertNotIn("email", response.json)
        self.assertNotIn("uuid", response.json)

    def test_mod_002_foreign_profile_update_is_denied_without_changing_data(self):
        """Known defect: changing URL/body actor must not impersonate B."""
        response = self.client.patch('/api/user/2', headers=self.headers(),
                                     json={"displayName": "Tampered", "userId": 1})
        # Check data first: rejects a response-only fix that still writes B.
        self.assertEqual(self.db.profile(2)["displayName"], "Bob",
                         "MOD-002: Alice's token changed Bob's persisted profile")
        self.assertIn(response.status_code, (403, 404))


    def test_numeric_profile_access_is_bound_to_each_subject(self):
        for subject, own, foreign in ((ALICE, 1, 2), (BOB, 2, 1)):
            with self.subTest(subject=subject):
                headers = {**self.headers(subject), "X-User-Id": str(foreign)}
                own_read = self.client.get(f'/api/user/{own}?userId={foreign}', headers=headers)
                self.assertEqual(own_read.status_code, 200)
                self.assertEqual(own_read.json['id'], own)
                response = self.client.patch(f'/api/user/{foreign}', headers=headers,
                    json={"displayName": "Forged", "userId": foreign, "actingUserId": foreign,
                          "uuid": subject, "id": own})
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json, {"message": "User not found"})
                foreign_read = self.client.get(f'/api/user/{foreign}', headers=headers)
                self.assertEqual(foreign_read.status_code, 404)
                self.assertEqual(foreign_read.json, {"message": "User not found"})
        self.assertEqual(self.db.profile(1)['displayName'], 'Alice')
        self.assertEqual(self.db.profile(2)['displayName'], 'Bob')

    def assert_identity_denial(self, headers, status, code):
        for method in ('get', 'patch'):
            with self.subTest(method=method):
                response = getattr(self.client, method)('/api/user/1', headers=headers,
                    json={"displayName": "Forbidden", "userId": 1})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json, {"error": code})
        self.assertEqual(self.db.profile(1)['displayName'], 'Alice')

    def test_numeric_routes_reject_missing_application_identity(self):
        self.assert_identity_denial(self.headers('00000000-0000-4000-8000-000000000099'),
                                    403, 'application_identity_not_found')

    def test_numeric_routes_reject_ambiguous_application_identity(self):
        self.db.connection.execute('ALTER TABLE "User" RENAME TO original_user')
        self.db.connection.execute('CREATE TABLE "User" AS SELECT * FROM original_user')
        self.db.connection.execute('INSERT INTO "User" (id, uuid) VALUES (?, ?)', (3, ALICE))
        self.db.connection.commit()
        self.assert_identity_denial(self.headers(), 403, 'application_identity_ambiguous')

    def test_numeric_routes_reject_empty_subject(self):
        self.assert_identity_denial(self.headers(''), 401, 'missing_authenticated_subject')

    def test_expired_session_cannot_patch_even_own_profile(self):
        response = self.client.patch('/api/user/1', headers=self.headers(exp=1),
                                     json={"displayName": "Forbidden"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.db.profile(1)['displayName'], 'Alice')
