# Observed public baseline — 2026-10-29

This package versions the application's observed public schema and access behavior.
It is a new baseline, not recovered historical migration SQL. It deliberately
preserves observed broad browser grants; proposed tightening lives separately in
`db/proposals/`. Neither this package nor the proposals have been applied to the
configured Supabase database.

## Files and order

`manifest.json` defines the version, ordered SQL files and SHA-256 checksums,
including the expected-state JSON. The ledger records the manifest's SHA-256,
which transitively pins those files. Treat a published version as immutable;
future changes need a separately reviewed version/migration, not edited hashes.

1. `001_schema.sql`: 23 distinct tables and existing indexes, dependency ordered.
   Identical duplicate DraftPick declarations were removed; no data or constraint
   repair was inferred.
2. `002_access.sql`: explicit RLS, own-User SELECT policy, observed table/sequence
   grants, postgres public default grants, and the observed ensure_rls mechanism.
3. `expected.json`: normalized catalog reference for the supported public scope.

The expected reference includes column types/modifiers/collations, defaults,
identity mode, generated flags, sequence options (not current values), constraints,
indexes, internal constraint-trigger enabled states, table/sequence durability,
RLS/policies, table/sequence/schema ACLs, public/global default ACLs,
browser/service role flags and memberships, custom public routines, column ACLs,
public views/table triggers, and ensure_rls metadata/function definition. It ignores
column ordinal positions and ACL entry ordering. Other platform schemas, extension
function ownership/ACLs, publication configuration, every identity sequence
association/comment/storage option, and provider configuration are not a complete
platform baseline here.

## Prerequisites

- PostgreSQL 17; pg_trgm 1.6 installed in public.
- Real Supabase `auth.users` and `auth.uid()` in a deployment. Tests use explicitly
  labeled minimal fixtures; the production package does not create fake Auth.
- Existing anon/authenticated/service_role/supabase_admin roles with the observed
  browser/service flags/memberships; the runner does not create/alter these roles.
- Observed supabase_admin public default grants (the platform prerequisite is
  verified, not changed by installation). postgres default grants are explicit SQL.
- An authorized operational actor able to create application objects, execute the
  baseline's grants, and install the database event trigger. The real local Supabase postgres role successfully installed the observed
  event trigger through existing platform support despite being NOSUPERUSER.
  No role elevation was required. This is verified for the documented local
  provider version, not every hosted platform/release.

## Supported states

**Local initialization:** empty public application table/view/sequence inventory,
Auth/extension prerequisites present, no custom public routines, conflicting
event trigger or migration schema. The runner creates objects, verifies the resulting state, then records one
ledger row in the same caller-owned transaction. It serializes concurrent callers
with an advisory transaction lock and uses a savepoint so caught validation errors
cannot leave committable partial DDL. It does not auto-commit.

**Verified adoption:** all versioned public-state groups already match. Only the
private `app_migrations.baseline` schema/table and one ledger row are created.
It never replays table creation or historical migrations onto an existing schema.
Deployed matching was checked read-only; adoption there has not been performed.

**Replay:** an identical ledger version/checksum and still-matching state returns
already_applied. Drift, conflicting records, changed package contents, unsupported
PostgreSQL/prerequisites or partial schemas fail. The runner is a baseline
installer/adopter, not a general historical migration replay engine. A future
schema/access migration must define its own state/version transition before using
this frozen verifier again.

Original migration files remain historical artifacts. Both are incorporated in the
baseline state and must not be blindly replayed after initialization/adoption.
The missing basketball SQL is recorded as maintainer-recalled application with
original contents unavailable. Its effects are not reconstructed as fake history.

## Run and verify

Use [disposable assessment setup](../../../scripts/modernization/README.md), then:

```sh
python3 -m unittest discover -s scripts/modernization/tests -p test_baseline.py
```

The tests create/clean only new synthetic databases and tracked fixture roles on
the marked local server. Run suites sequentially; platform role names are fixed to
match the expected reference. The CLI supports existing synthetic otm_baseline_*
databases only and verifies the server marker; it accepts no remote DSN or .env.
The Python apply function accepts a caller-provided connection for controlled
integration, but no deployed invocation or migration is authorized by these docs.

## Recovery and deployment boundary

Before commit, any SQL or validation failure rolls back baseline work to its
savepoint; rolling back the outer transaction removes all initialization/ledger
writes. After commit, do not drop public tables to undo a populated baseline. For
adoption, application objects were untouched; correcting a ledger mistake requires
reviewing its row/checksum and current state, not replaying DDL. Preserve the ledger
and use a reviewed forward migration or database restore for later changes.

No broad destructive down-migration is shipped. Production adoption/installation
needs fresh metadata verification, target identity and actor capability checks,
a reviewed backup/recovery procedure, the documented provider prerequisites and explicit user approval. Runtime API/listener/job role alignment remains MOD-004.


## Provider acceptance completed

The [real-provider suite](../../../scripts/modernization/SUPABASE_PROVIDER.md)
passed from a clean separate Supabase stack: initialization as the actual
NOSUPERUSER postgres actor, real Auth/PostgREST profile isolation, two explicit
historical schema upgrade/adoption/replay fixtures and data-preserving grant
recovery. Provider versions and source hashes are recorded in
[sanitized evidence](../../../docs/modernization/evidence/supabase-provider-verification-2026-10-29.json).

This satisfies MOD-005's bounded repository baseline/supported-state acceptance.
The original missing migration remains recorded as unavailable history, not
reconstructed SQL. Production adoption, alternate historical states/provider
versions and data disaster recovery are separate operational work; no hosted
baseline or ledger has been installed.
