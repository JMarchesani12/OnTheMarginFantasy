# Versioned database changes

[20261118_browser_privileges](20261118_browser_privileges) is the exact reviewed owner-scoped privilege package, **applied and verified November 18,2026**. See its [execution receipt](../history/20261118_browser_privileges.json).

The package removes PUBLIC/anon/authenticated grants on current public tables/sequences and postgres table/sequence defaults. Backend/service grants, owners, RLS/policies, functions and supabase_admin defaults are preserved. Provider-owned future grants remain a [platform follow-up](../../docs/follow-ups.md).

Keep package SQL, expected-state JSON and manifest bytes immutable. Its internal README/manifest/comments describe preparation-time status; the dated execution receipt is authoritative for application history. The old two-creator proposal and one-off assessment scripts are retired. The manifest's historical input path maps to [the preserved starting catalog](../history/20261118_browser_privileges_before.json); verify its input_sha256 there when checking provenance.

apply.sql and recovery.sql each own a standalone transaction with exact before/after guards. Apply is not a generic migration for arbitrary later schemas and refuses already hardened state. Recovery deliberately restores the exact original broad grants only when the hardened state still matches. New objects/unrelated ACL drift require separately reviewed recovery; never bypass a guard or run individual fragments. No production execution is implied by keeping these files.

The local [browser privilege integration test](../../api/tests/integration/README.md) exercises the exact package against synthetic PostgreSQL. Before any new approved environment change, use fresh catalog/snapshots, confirm platform ownership and backups, and retain a new execution receipt.
