# Observed database snapshots

These are dated **observations**, not migrations, initialization SQL or data backups. Never execute a snapshot against a populated database. Keep `db/baselines/20261029` immutable; snapshots record later observed state without rewriting baseline checksums/history.

## Current captures — November17,2026 America/Chicago

- `2026-11-17/`: before the separately approved ownership index;23public tables,51indexes,93constraints.
- `2026-11-17-after-mod017/`: after that index;23tables,52indexes,93constraints.
- `2026-11-17-after-mod015/`: after separately approved integrity constraints;23tables,56indexes,103validated constraints, required membership sport ID. All nine consistency counts remain0; the ownership index remains valid/ready.

The four additional indexes in the final capture back parent UNIQUE integrity keys; they are not deferred game/transaction performance indexes.

Each directory has `schema.sql`, normalized `catalog.json`, aggregate-only `assessment.json`, and `manifest.json` with result, source revision/hashes, version/TLS/scope and file SHA256 checksums. Catalog and pg_dump share the same exported REPEATABLE READ READ ONLY snapshot. Timestamps in manifests are UTC; directory dates use the user's America/Chicago date. Owner statements/comments/security labels are omitted from SQL; object owners, ACL/default grants, RLS/policies, index validity, constraint validation, routine definitions, extension versions and event-trigger registrations are represented in metadata.

No application/Auth rows or sequence current values are exported. Public-schema selection excludes full Auth/storage/provider state and cluster role/password definitions. A schema-only export does not include all platform prerequisites or every database-level event trigger; consult catalog metadata. The one custom public routine (`rls_auto_enable`) was inspected. These files alone are not a full blank-platform restore plan, and are not evidence of deployed application revisions or browser acceptance.

The original exporter source used by both captures is preserved by its manifest SHA under `exporters/`. A later credential-screening hardening explicitly checks the parsed DB password and every known secret regardless of length, as well as full DSNs and token patterns. Both captures were rescanned successfully under the stronger rule without changing their bytes/checksums. Source copies document provenance; use the current tool at its normal path rather than executing archived copies from this directory.

## Future capture

Using existing locally configured credentials, after reviewing the intended project/actor:

```sh
python3 scripts/modernization/capture_db_snapshot.py \
  --configured-read-only \
  --output db/snapshots/YYYY-MM-DD-unique-label
```

The destination must not already exist, including a previous FAILED capture. The tool explicitly reads `api/.env`; never commit that file or paste a connection URL. It binds the configured project, requires client TLS, uses the same pooler's session-preserving5432port when the configured6543transaction pooler is detected, and does not edit configuration. The cached PostgreSQL17.6 Docker client runs without starting a server and is removed afterward. It accepts no alternate arbitrary DSN or data-export flag. Missing access/image/metadata, an export failure or secret detection leaves a sanitized FAILED manifest, never a verified snapshot. Never feed this tool a transaction-pooler tunnel pretending to be a direct/session endpoint.

Review schema/routine/default definitions before committing, verify every manifest checksum, and keep before/after captures for approved rollouts. Secrets can be embedded in unusual definitions that automated patterns do not recognize; screening supplements review. Connection settings, credentials and application data belong outside Git. Normal database backups/PITR and tested restore procedures remain separate from schema versioning.
