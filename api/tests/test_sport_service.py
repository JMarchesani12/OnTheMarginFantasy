"""Sport catalog: real SQL, public HTTP, projection and connection lifecycle."""
import sqlite3
import unittest
from contextlib import contextmanager

from flask import Flask
from authMiddleware import install_auth_middleware
from endpoints.sport.routes import setup_routes
from endpoints.sport.sportModel import SportModel


class SportDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(':memory:')
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript('''
            CREATE TABLE "Sport" (id INTEGER, name TEXT,
                "maxPlayersToHaveMaxRounds" INTEGER, "maxDraftRounds" INTEGER,
                internal_marker TEXT);
            INSERT INTO "Sport" VALUES (2,'Basketball',12,10,'private'),
                (1,'Football',8,NULL,'private');
        ''')
        self.begins = 0
        self.active = False
        self.outcomes = []
        self.fail = False

    @contextmanager
    def begin(self):
        assert not self.active, 'Nested acquisition'
        self.begins += 1
        self.active = True
        try:
            yield self
        except Exception:
            self.connection.rollback()
            self.outcomes.append('rollback')
            raise
        else:
            self.connection.commit()
            self.outcomes.append('commit')
        finally:
            self.active = False

    def execute(self, statement):
        assert self.active, 'Query outside owned scope'
        if self.fail:
            raise RuntimeError('synthetic private database detail')
        cursor = self.connection.execute(str(statement))

        class Result:
            def mappings(self):
                return self

            def all(self):
                return cursor.fetchall()

        return Result()


class SportServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = SportDatabase()
        self.addCleanup(self.db.connection.close)
        self.expected = [
            {'id': 1, 'name': 'Football', 'maxPlayersToHaveMaxRounds': 8, 'maxDraftRounds': None},
            {'id': 2, 'name': 'Basketball', 'maxPlayersToHaveMaxRounds': 12, 'maxDraftRounds': 10},
        ]

    def service(self):
        from endpoints.sport.service import SportService
        return SportService(self.db)

    def client(self):
        app = Flask(__name__)
        app.config['TESTING'] = True
        install_auth_middleware(app, public_paths={'/api/sports'})
        setup_routes(app, self.db)
        return app.test_client()

    def test_catalog_preserves_plain_projection_and_nulls_in_one_scope(self):
        rows = self.service().list_sports()
        self.assertEqual(sorted(rows, key=lambda row: row['id']), self.expected)
        self.assertTrue(all(type(row) is dict for row in rows))
        self.assertEqual((self.db.begins, self.db.outcomes, self.db.active), (1, ['commit'], False))

    def test_empty_catalog_is_an_empty_list(self):
        self.db.connection.execute('DELETE FROM "Sport"')
        self.assertEqual(self.service().list_sports(), [])

    def test_public_route_returns_exact_catalog_without_credentials(self):
        response = self.client().get('/api/sports')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted(response.json, key=lambda row: row['id']), self.expected)
        self.assertEqual(self.db.begins, 1)

    def test_route_hides_database_failure_and_unwinds_scope(self):
        self.db.fail = True
        response = self.client().get('/api/sports')
        self.assertEqual((response.status_code, response.json), (500, {'message': 'Failed to get sports'}))
        self.assertEqual((self.db.outcomes, self.db.active), (['rollback'], False))

    def test_service_failure_propagates_and_unwinds_scope(self):
        self.db.fail = True
        with self.assertRaisesRegex(RuntimeError, 'synthetic private'):
            self.service().list_sports()
        self.assertEqual((self.db.outcomes, self.db.active), (['rollback'], False))

    def test_legacy_constructor_and_db_only_instance_preserve_results(self):
        for model in (SportModel(self.db), SportModel.__new__(SportModel)):
            model.db = self.db
            self.assertEqual(sorted(model.get_sports(), key=lambda row: row['id']), self.expected)
