"""Public search contract using real route/model SQL and synthetic SQLite rows.

SQLite LIKE substitutes PostgreSQL ILIKE; similarity is fixed to exercise the
secondary name order. This is not a PostgreSQL trigram/ranking validation.
"""
import ast
import os
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from authMiddleware import install_auth_middleware
from endpoints.league.routes import setup_routes


class SearchDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(':memory:')
        self.connection.row_factory = sqlite3.Row
        self.connection.create_function('similarity', 2, lambda name, query: 1)
        self.connection.executescript('''
            CREATE TABLE "User" (id INTEGER PRIMARY KEY, email TEXT, "displayName" TEXT);
            CREATE TABLE "League" (id INTEGER PRIMARY KEY, name TEXT, sport INTEGER,
                "numPlayers" INTEGER, status TEXT, "draftDate" TEXT,
                "isDiscoverable" BOOLEAN, commissioner INTEGER);
            INSERT INTO "User" VALUES (1, 'private-commissioner@example.test', 'Commissioner');
            INSERT INTO "League" VALUES
                (1, 'Margin Alpha', 1, 8, 'Pre-Draft', NULL, true, 1),
                (2, 'Margin Beta', 2, 10, 'Drafting', NULL, true, 1),
                (3, 'Margin Hidden', 1, 8, 'Pre-Draft', NULL, false, 1);
        ''')

    def begin(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, params):
        cursor = self.connection.execute(str(statement).replace(' ILIKE ', ' LIKE '), params)

        class Result:
            def mappings(self):
                return self

            def all(self):
                return [dict(row) for row in cursor.fetchall()]

        return Result()


class PublicLeagueSearchTests(unittest.TestCase):
    def setUp(self):
        self.db = SearchDatabase()
        self.addCleanup(self.db.connection.close)
        app = Flask(__name__)
        app.config['TESTING'] = True
        # Reuse actual public auth settings without executing the app factory.
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'api.py').read_text())
        call, = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'install_auth_middleware']
        install_auth_middleware(app, **{kw.arg: ast.literal_eval(kw.value) for kw in call.keywords})
        with patch.dict(os.environ, {"ESPN_BASE_URL": "https://provider.example.test"}):
            setup_routes(app, self.db)
        self.client = app.test_client()

    def test_anonymous_search_returns_discovery_fields_without_contact_data(self):
        response = self.client.get('/api/leagues/search?q=margin')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json[0], {
            'id': 1, 'name': 'Margin Alpha', 'sport': 1, 'numPlayers': 8,
            'status': 'Pre-Draft', 'draftDate': None, 'isDiscoverable': 1,
            'commissioner': 1, 'commissionerDisplayName': 'Commissioner',
        })
        self.assertEqual([row['id'] for row in response.json], [1, 2])
        for row in response.json:
            self.assertNotIn('commissionerEmail', row)
            self.assertNotIn('email', row)
            self.assertEqual(set(row), set(response.json[0]))
        self.assertNotIn('private-commissioner@example.test', response.get_data(as_text=True))

    def test_sport_filter_and_page_still_work(self):
        filtered = self.client.get('/api/leagues/search?q=Margin&sportId=2')
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual([row['id'] for row in filtered.json], [2])
        page = self.client.get('/api/leagues/search?q=Margin&limit=1&offset=1')
        self.assertEqual(page.status_code, 200)
        self.assertEqual([row['id'] for row in page.json], [2])

    def test_short_or_unmatched_queries_stay_empty(self):
        for query in ('', 'm', 'unmatched'):
            with self.subTest(query=query):
                response = self.client.get('/api/leagues/search', query_string={'q': query})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json, [])

    def test_invalid_parameters_keep_json_error_contract(self):
        response = self.client.get('/api/leagues/search?q=Margin&sportId=bad')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {'message': 'Invalid parameters'})
