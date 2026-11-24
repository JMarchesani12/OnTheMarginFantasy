# Historical public schema baseline — October 29,2026

Immutable observed baseline, retained as schema provenance and a synthetic integration-test fixture. It was not adopted/installed on the existing application database. It predates subsequent migrations and browser hardening; **do not use its access SQL as the current security policy or replay it on production**.

manifest.json pins ordered001_schema.sql,002_access.sql and expected.json. SQL/reference bytes and checksums remain unchanged. The schema requires PostgreSQL 17, pg_trgm and Supabase Auth/role/platform prerequisites; it does not provision a complete provider environment. Its access file records historical broad browser grants and the observed RLS/event-trigger behavior.

The former one-off initialization/adoption assessment runner is retired. A future fresh-environment deployment requires a reviewed current initialization/migration path; these files alone do not supply one. See [current schema snapshots](../../snapshots/README.md), [applied changes](../../history/README.md) and [database documentation](../../README.md).
