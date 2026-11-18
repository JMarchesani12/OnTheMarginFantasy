"""Shared PostgreSQL ownership write mutex; caller owns connection/transaction.

The v1 namespace/key protocol must remain stable across concurrently deployed
writers. Hash collisions only serialize unrelated leagues; they grant no access.
Always acquire before DraftState/Transaction row locks, never on a second engine.
"""
import hashlib
from sqlalchemy import text


def lock_ownership(conn, league_id):
    if isinstance(league_id, bool):
        raise ValueError('league_id must be an integer')
    league_id = int(league_id)
    key = int.from_bytes(hashlib.sha256(f'otm:ownership:v1:{league_id}'.encode('ascii')).digest()[:8], 'big', signed=True)
    conn.execute(text('SELECT pg_advisory_xact_lock(:ownershipKey)'), {'ownershipKey': key})


def transaction_league_hint(conn, transaction_id):
    row = conn.execute(text('SELECT "leagueId" FROM "Transaction" WHERE id=:transactionId'),
                       {'transactionId': transaction_id}).fetchone()
    return row._mapping['leagueId'] if row else None
