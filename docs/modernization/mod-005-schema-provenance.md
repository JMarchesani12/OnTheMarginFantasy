# MOD-005 schema provenance — 2026-10-29

Status: repository reconciliation, candidate initialization, collected-definition comparison and two explicit historical migration fixtures verified. The assessment candidate is reproducible locally; an approved deployment baseline, migration runner/ledger and supported production upgrade path remain open. No deployed schema changes performed.

## Source provenance

| Artifact | Available Git evidence | Meaning |
| --- | --- | --- |
| db/tables.sql | Added in caba849 (2026-10-25) | Descriptive public schema snapshot; no attached export command, source project identity or dated catalog manifest. |
| db/README.md | Present in available history; tournament migration instruction introduced by 579df15 (2026-10-23) | Its original live-schema claim had no attached verification. Updated to distinguish current catalog evidence from executable migration history. |
| 20260803_create_sport_season_subdivision.sql | Added by 7a3244a (2026-08-03) | Requires public.SportSeason already exists; explicit BEGIN/COMMIT. Table already exists in inspected database; do not replay blindly. |
| 20260803_fix_sport_season_start_column.sql | Added by 7a3244a (2026-08-03) | Conditional esasonStart → seasonStart rename. Handles old-only state; both/neither-column states do not establish a correct baseline. |
| 20261023_basketball_tournament_rules.sql | Referenced by 579df15 in db/README and startSeasonJobs/README; no matching file/path found in available all-ref history | Maintainer recalls almost certainly applying this SQL (2026-10-29), but cannot locate it. Original content and exact application history remain unverified. Existing SeasonPhase.rules supports the intended end state, not the identity of the applied SQL. Do not reconstruct a migration and present it as recovered history. |

Snapshot SHA-256: `bc9d3b208a588bb14146030e86a6a820d5e9f8cc8f491fbe72908bf7189f3bf8`.

Subdivision migration SHA-256: `6d57d486763d56a625c20f4e5cd3ec82b5f94a0aff276e34d764282abc3f824b`.

Rename migration SHA-256: `9d2e1547acb5d50f7f109bfab03f2a955b70d062debd28815d3fcc98e3fd487f`.

No checked-in runner/order/ledger establishes applied ordering. Two migrations share the same date; filenames alone do not establish historical application order. A schema baseline must not be followed by blindly replaying already-incorporated migrations.

## Configured database comparison

[Read-only catalog evidence](evidence/supabase-catalog-2026-10-29.json) records 23 public tables, 180 columns, 83 constraints and 45 indexes. A source scan found 24 CREATE TABLE declarations representing the same 23 distinct table names, and the same 180 distinct table/column names. DraftPick is declared twice in source. This is a name-level comparison, not normalized DDL/type/default/constraint equivalence.

- SeasonPhase.rules exists as JSONB in the inspected database and snapshot. The missing migration's provenance remains unresolved.
- SportSeasonSubdivision exists; SportSeason has seasonStart rather than esasonStart.
- BonusPointEvent is absent from both the snapshot and inspected public-table inventory. README references are historical/conditional, not a reason to create it.
- pg_trgm 1.6 is installed in public; other platform extensions are recorded in the artifact. Snapshot uses gin_trgm_ops without declaring that prerequisite.
- public.User references Supabase auth.users. A blank PostgreSQL instance needs a separately defined Supabase compatibility prerequisite; inventing a replacement auth table is not a production-equivalent baseline.
- No supabase_migrations schema/ledger columns were visible in the inspected catalog. This does not recover Dashboard SQL history or prove that migrations never ran.
- Deployed RLS, policy/grants, extension membership and ensure_rls event-trigger metadata are not represented by tables.sql. See the [access review](mod-004-access-review.md).

## Why tables.sql is not a blank-database migration

It repeats DraftPick, creates foreign keys before some referenced tables exist, omits extension/auth prerequisites, and does not version the observed access-policy/platform mechanisms. Keep it descriptive until a reviewed replacement exists. Existing migrations operate on pre-existing schema and cannot initialize the application by themselves.

## Reproducibility steps identified at initial metadata stage (results below)

1. Recover the missing migration or explicitly document it as unrecoverable history with the maintainer; do not fabricate its original contents. Current evidence resolves the runtime column-presence question, not provenance.
2. Produce a schema-only export/normalized definition comparison for the intended application scope, including identity/sequences/defaults/constraints/indexes and access/platform prerequisites. Inspect routine definitions separately before versioning them; current evidence intentionally excludes bodies.
3. Define a new, explicitly dated baseline with dependency ordering, Supabase prerequisites, reviewed policy/role boundaries and a version/checksum ledger. Keep historical artifacts separate from the new baseline; specify which prior states are supported.
4. Initialize a disposable Supabase-compatible database, verify normalized definitions, and exercise supported upgrade paths. The cached Supabase PostgreSQL image is available; subsequent disposable assessment results are recorded below.

MOD-005 remains open until reproducible initialization and supported-upgrade validation pass. No deployed migrations, private-row exports, deduplication, inferred DDL or production jobs were run.


## Disposable PostgreSQL assessment results

The [assessment harness](../../scripts/modernization/README.md) generated a
[public schema candidate](evidence/public-schema-assessment-candidate.sql) by
removing byte-identical duplicate declarations and ordering tables by their
existing FK dependencies. Index definitions were preserved. No column, default,
constraint or index repair was invented.

On PostgreSQL 17.6, the candidate initializes successfully with explicit synthetic
Auth and pg_trgm prerequisites. Compared with the deployed catalog, all 180
collected column properties (type/UDT, nullability, default, identity fields), all
83 constraint definitions and 45 index definitions match except **27 column
ordinal positions**. Physical ordinal gaps/order can reflect schema history;
these differences do not require rebuilding deployed tables. The comparison does
not cover every type modifier, collation, sequence option/state or object comment.

Both checked-in historical migrations execute successfully on two separately
created fixture states: subdivision table absent with either old-only esasonStart
or correct-only seasonStart. Their resulting collected definitions match the
candidate. Both/neither-column cases, replay against an existing subdivision,
real prior deployment provenance and rollback paths remain unsupported/unverified.

[Results and input hashes](evidence/postgres-assessment-2026-10-29.json) record the
checks. Minimal auth.users/auth.uid SQL fixtures are not a full Supabase platform
baseline. The observed event-trigger definition was separately collected and
replayed locally; see MOD-004. No deployed schema was changed. All task-owned
fixture databases/roles were removed after each run.

The missing migration is now recorded as **maintainer-recalled application,
original SQL unavailable**. Do not block independent assessment on recovering the
file, or present newly authored SQL as its recovered contents. Next: define the
versioned deployment baseline, prerequisites, checksummed ledger and explicit
supported upgrade/recovery policy before calling MOD-005 complete.
