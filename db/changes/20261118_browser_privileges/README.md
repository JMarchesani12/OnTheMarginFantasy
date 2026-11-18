# MOD-004 owner-only transition — prepared, NOT applied

Version: `20261118_mod004_owner_v1`. The maintainer authorized preparation and local testing. Production execution needs separate approval of this package. Do not run the older two-creator proposal as a substitute.

`apply.sql` removes all PUBLIC/anon/authenticated grants on the 23 current public tables and 21 sequences, including User SELECT. It removes table/sequence browser defaults for postgres only. Service/backend grants, object owners, RLS/policies, functions, function defaults, Auth/storage schemas and supabase_admin defaults remain unchanged. The current app uses authenticated backend profile APIs; the maintainer confirmed no external direct-table consumers. Both production deployments are on `514f115`.

**Remaining limitation:** supabase_admin-created public tables/sequences can still acquire browser grants. Full future-object hardening remains open until an authorized platform path is available. No roles are elevated to overcome that boundary.

## Package and guards

`before.json` is derived from the screened November 18 read-only catalog. `after.json` is the exact intended state. `state-query.sql` returns canonical JSON covering public relations and their owners/ACL/RLS, schema ACL, policies, public/global defaults, browser/service flags and memberships, and explicit column grants. SQL embeds the before/after checks. The manifest pins package contents and input evidence; retain its checksums with the execution receipt.

The SQL owns BEGIN/COMMIT, requests a 3-second lock timeout and 20-second statement timeout, and takes a cooperating transaction advisory lock. Before/after mismatch or surviving effective browser table/sequence privilege raises and aborts. Run with a client that stops on the first error. Do not nest it in another transaction or continue a failed transaction. PostgreSQL 17 or later is required (MAINTAIN privilege included).

**Use a maintenance window without concurrent schema or grant edits.** The advisory lock coordinates only callers using the same key; it cannot freeze unrelated administrators. Review new migrations against the deferred provider defaults.

## Before a separately approved production execution

1. Confirm deployed sign-in/profile loading and draft reconnect/update with an approved test account. No account tokens belong in this repository or chat.
2. Privately confirm the Render API and active jobs use the intended backend role and a direct/session-preserving database endpoint. Connector metadata cannot reveal those environment values. Current configured actor is postgres, NOSUPERUSER and not a supabase_admin member; this does not prove Render's role.
3. Capture a new checksummed schema/catalog snapshot using the existing read-only exporter. Compare `state-query.sql` output to `before.json`; abort and review any difference. Do not edit expected files merely to force acceptance.
4. Confirm manifest checksums and approve the exact SQL hash, target and recovery. Execute only `apply.sql` as the reviewed postgres owner with a stop-on-error client. A failure must be rolled back; do not split/retry individual statements.
5. Verify the exact `after.json` state, effective denial and unchanged service access. Capture an after-change snapshot and a dated execution receipt recording SQL/state hashes, safe target fingerprint, timestamps, transaction outcome and verification. That receipt is the execution ledger; no baseline adoption or database migration table is needed.
6. Repeat the approved-account browser/profile/draft checks. A public /ready 200 is not evidence of profile or draft delivery acceptance.

`recovery.sql` is also a standalone transaction. It accepts only the exact hardened state and restores the observed broad browser ACLs and postgres defaults. It preserves provider defaults and policies. It refuses unrelated ACL/new-object drift; resolve such drift through a separately reviewed recovery rather than bypassing guards. Recovery deliberately restores the old broad access and should only be used for an approved rollback.

## Local acceptance

Run `python3 scripts/modernization/verify_mod004_owner.py` with Docker available and the cached pinned PostgreSQL image. The verifier starts/removes its own randomly named loopback-only container, reads no dotenv and uses synthetic roles/objects. A nonsuperuser postgres owner lacks supabase_admin membership. It executes the exact packaged SQL and records source hashes, control results and owned-container cleanup in a unique evidence file. It does not execute the proposal against a configured or hosted database.
