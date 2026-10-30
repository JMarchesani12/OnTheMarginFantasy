"""MOD-038 on marked disposable loopback PostgreSQL; never loads .env or a DSN."""
import hashlib
import json
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from sqlalchemy import event, text

from assess_postgres import LOCAL, ROOT, engine_for, trade_tests
from actors import UserActor
from endpoints.transaction.service import TransactionService
from endpoints.transaction.contracts import TransactionAccessDenied


def read_tests(engine, database):
    with engine.begin() as conn:
        conn.exec_driver_sql('''
            ALTER TABLE "League" ADD commissioner bigint;
            UPDATE "League" SET commissioner=1;
            CREATE TABLE "User" (id bigint PRIMARY KEY,"displayName" text);
            INSERT INTO "User" VALUES (4,'Proposer'),(2,'Receiver');
            CREATE TABLE "LeagueMember" (id bigint PRIMARY KEY,"leagueId" bigint,"userId" bigint);
            INSERT INTO "LeagueMember" VALUES (11,10,4),(12,10,2);
            CREATE TABLE "SportTeam" (id bigint PRIMARY KEY,"displayName" text);
            INSERT INTO "SportTeam" VALUES (101,'Alpha'),(102,'Bravo');
            ALTER TABLE "Transaction" ADD "createdAt" timestamptz DEFAULT now();
        ''')
    service = TransactionService(engine)
    for user in (1, 2):  # commissioner without membership, then ordinary member
        rows = service.list_transactions(UserActor(user, f'synthetic-{user}'), 10, 'COMPLETED')
        assert len(rows) == 1 and rows[0]['id'] == 1, rows
        assert rows[0]['fromTeams'] == [{'id': 101, 'displayName': 'Alpha'}], rows
        assert rows[0]['toTeams'] == [{'id': 102, 'displayName': 'Bravo'}], rows
        assert rows[0]['memberFromDisplayName'] == 'Proposer', rows
    for user, league in ((3, 10), (2, 999)):
        try:
            service.list_transactions(UserActor(user, f'synthetic-{user}'), league)
        except TransactionAccessDenied:
            pass
        else:
            raise AssertionError('Unauthorized read was allowed')
    assert service.list_transactions_for_job(999) == []
    revoker = engine_for(database, 'otm-pilot-revoker')
    revoked = False
    def before_data_query(conn, cursor, statement, params, context, many):
        nonlocal revoked
        if 'FROM "Transaction" t' in statement and not revoked:
            revoked = True
            with revoker.begin() as other:
                other.execute(text('DELETE FROM "LeagueMember" WHERE id=12'))
    event.listen(engine, 'before_cursor_execute', before_data_query)
    try:
        assert service.list_transactions(UserActor(2, 'synthetic-2'), 10) == []
        assert revoked
    finally:
        event.remove(engine, 'before_cursor_execute', before_data_query)
        revoker.dispose()
    return {'postgres_json_projection': 'PASS', 'commissioner_without_membership': 'PASS',
            'member_and_denials': 'PASS', 'query_time_revocation': 'PASS'}


def main():
    admin = psycopg2.connect(dbname='postgres', **LOCAL)
    admin.autocommit = True
    name = 'otm_mod038_' + uuid4().hex
    created = False
    engine = None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0] == 'otm-modernization-assessment-20261029-synthetic-only', 'Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            created = True
        engine = engine_for(name, 'otm-mod038-pilot')
        concurrency = trade_tests(engine, name)
        reads = read_tests(engine, name)
        files = ['api/actors.py', 'api/utils/authorization.py',
                 'api/endpoints/transaction/transactionModel.py',
                 'api/endpoints/transaction/transactionEndpoints.py',
                 'api/endpoints/transaction/service.py', 'api/endpoints/transaction/repository.py',
                 'api/endpoints/transaction/contracts.py', 'scripts/modernization/verify_transaction_pilot.py']
        report = {'result': 'PASS', 'scope': 'Synthetic marked loopback PostgreSQL; no configured or hosted database',
                  'trade_concurrency': concurrency, 'transaction_reads': reads,
                  'sha256': {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files}}
        output = ROOT / 'docs/modernization/evidence/mod-038-pilot-postgres-2026-10-29.json'
        output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.cursor() as cur:
                cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()


if __name__ == '__main__':
    main()
