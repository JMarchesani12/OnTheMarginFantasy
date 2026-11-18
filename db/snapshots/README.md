# Observed schema snapshots

Latest: [2026-11-18-after-browser-privileges](2026-11-18-after-browser-privileges/manifest.json), with 23 public tables,21 sequences,56 indexes and 103 constraints. Browser table/sequence grants and postgres table/sequence defaults are hardened; service/backend ACLs, policies/RLS and provider defaults are preserved.

Retained captures bracket applied changes:

- 2026-11-17-before-ownership-index: before the member-led ownership index.
- 2026-11-17-after-ownership-index: after the index.
- 2026-11-17-after-seasonal-references: after the composite-reference constraints.
- 2026-11-18-before-browser-privileges and 2026-11-18-after-browser-privileges: exact privilege transition boundaries.

Each directory contains schema.sql, catalog.json, assessment.json and a checksummed manifest. These are metadata-only observations, never initialization/migration scripts or application-data backups. Capture scope excludes full Auth/storage/provider state, passwords, application rows and sequence current values. Review unusual definitions even after automated secret screening.

For future captures use [the snapshot tool](../../scripts/database/README.md) with a new destination. Do not rewrite old files/manifests: source paths and hashes identify their original execution checkout even when tools are relocated or retired. Directory names are descriptive; file bytes/checksums were preserved when reorganized. Applied-change receipts are in [history](../history/README.md).
