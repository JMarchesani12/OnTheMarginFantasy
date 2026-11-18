# Database snapshots

`capture_snapshot.py` captures public schema definitions, normalized metadata, index validity, ACL/default privileges and aggregate consistency checks in one exported REPEATABLE READ READ ONLY snapshot. It exports no application/Auth rows or sequence current values.

From the repository root, with the backend Python dependencies installed and Docker available:

```sh
python3 scripts/database/capture_snapshot.py --configured-read-only --output db/snapshots/YYYY-MM-DD-description
```

The destination must not already exist. The explicit flag loads api/.env privately, binds its configured project/actor, requires client TLS and uses session-preserving pooler5432 when a configured transaction-pooler6543 endpoint is detected. It does not edit configuration or apply SQL. The PostgreSQL17.6 client image is pinned in the script and must already be cached. Only the invocation's owned client container is removed afterward.

Each successful capture has schema.sql, catalog.json, assessment.json and a checksummed manifest. Secret screening includes configured credentials/passwords and token/DSN patterns. Export failures produce a sanitized FAILED manifest rather than a verified capture. Review definitions and checksums before committing; automated screening is not a substitute for reviewing unusual routine definitions.

Run the credential-free unit checks with:

```sh
python3 -m unittest discover -s scripts/database/tests
```

Snapshots are observations, not migrations or data backups. See [snapshot records](../../db/snapshots/README.md) and [database documentation](../../db/README.md). Existing manifests preserve source paths/hashes from their original capture; moving or retiring tooling does not rewrite that history.
