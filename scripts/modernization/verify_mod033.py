"""MOD-033 reads on marked disposable loopback PostgreSQL; no configured runtime.

Reuses the exact characterization assertions. Only their fixture DDL/DML gets
quoted identifiers; repository/helper SQL executes natively without rewriting.
Creates/drops only this run's UUID database, never starts containers or accepts DSNs.
"""
import hashlib
import json
import os
import re
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from assess_postgres import LOCAL, ROOT, engine_for
from verify_draft_complete import tests as draft_tests
from verify_transaction_complete import tests as transaction_tests
from verify_mod015 import tests as membership_tests

os.environ['SUPABASE_PROJECT_ID'] = 'regression-test'
os.environ['SUPABASE_JWT_SECRET'] = 'synthetic-test-secret-never-used-outside-tests-2026'
sys.path.insert(0, str(ROOT / 'api/tests'))
import test_ownership_reads as characterization

# SQLite fixture setup accepts unquoted camelCase; PostgreSQL requires quoting.
_IDENTIFIERS = ('LeagueTeamSlot', 'ConferenceMembership', 'SportConference', 'SportTeam',
                'League', 'seasonYear', 'sportId', 'maxTeamsPerOwner', 'sportTeamId',
                'sportConferenceId', 'leagueId', 'memberId', 'acquiredWeek', 'droppedWeek')
_IDENTIFIER_PATTERN = re.compile(r'(?<!")\b(' + '|'.join(_IDENTIFIERS) + r')\b(?!")')


def fixture_sql(statement):
    return _IDENTIFIER_PATTERN.sub(lambda match: '"' + match.group(0) + '"', statement)


class FixtureConnection:
    def __init__(self, conn):
        self.conn = conn

    def executescript(self, statement):
        self.conn.exec_driver_sql(fixture_sql(statement))
        self.conn.commit()

    def execute(self, statement):
        return self.conn.exec_driver_sql(fixture_sql(statement))

    def close(self):
        self.conn.close()


class NativeDatabase:
    def __init__(self, engine):
        self.conn = engine.connect()
        self.conn.exec_driver_sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public;')
        self.conn.commit()
        self.connection = FixtureConnection(self.conn)
        self.queries = []

    def execute(self, statement, params):
        self.queries.append(str(statement))
        return self.conn.execute(statement, params)


def main():
    admin = psycopg2.connect(dbname='postgres', **LOCAL)
    admin.autocommit = True
    database = 'otm_mod033_' + uuid4().hex
    created, engine = False, None
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            if cursor.fetchone()[0] != 'otm-modernization-assessment-20261029-synthetic-only':
                raise RuntimeError('Refusing unmarked server')
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
            created = True
        engine = engine_for(database, 'mod033-read-equivalence')
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(characterization.OwnershipReadCharacterizationTests)
        with patch.object(characterization.fixture, 'LivePickDatabase', side_effect=lambda: NativeDatabase(engine)):
            result = unittest.TextTestRunner(verbosity=2).run(suite)
        if not result.wasSuccessful():
            raise AssertionError('Native ownership characterization failed')
        report = {'result': 'PASS', 'scope': 'Marked task-owned disposable loopback PostgreSQL only',
                  'characterization': {'tests': result.testsRun, 'result': 'PASS',
                                       'productionSQLRewritten': False},
                  'draft': draft_tests(engine, database),
                  'transaction': transaction_tests(engine, database),
                  'seasonMembership': membership_tests(engine, database)}
        paths = ['api/utils/ownership_reads.py', 'api/endpoints/draft/pick_repository.py',
                 'api/endpoints/transaction/workflow_repository.py', 'api/tests/test_ownership_reads.py',
                 'scripts/modernization/verify_mod033.py']
        report['sha256'] = {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths}
        report['cleanup'] = 'UUID database dropped in finally; container cleanup belongs to caller'
        path = ROOT / 'docs/modernization/evidence/mod-033-ownership-reads-postgres-2026-11-09.json'
        path.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'result': 'PASS', 'characterization': result.testsRun,
                          'draft': 'PASS', 'transaction': 'PASS', 'seasonMembership': 'PASS'}))
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))
        admin.close()


if __name__ == '__main__':
    main()
