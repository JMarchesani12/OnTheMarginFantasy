# Database-owned school aliases

**`public.SchoolAlias` is the runtime source of truth.** It links each alias to an
actual `School.id`, sharing aliases across that school's sports. An abbreviation
may belong to several schools. Aliases are unique within a school by normalized
text; adding or changing one does not rename a school or team.

The configured project migration was applied and verified on **2026-11-19**:
**2,079 aliases, 366 schools, 631 existing teams**. School/team counts were unchanged.
See the [rollout receipt](../../docs/modernization/evidence/school-alias-rollout-2026-11-19.json)
and [runtime verification](../../docs/modernization/evidence/school-alias-runtime-2026-11-19.json).
The application code has not been deployed by this task.

## Runtime reads

Backend lookup reads aliases alongside teams from `SchoolAlias`. The public
`GET /api/team-search/catalog` endpoint returns only team ID, school ID, displayed
team name and aliases. It never exposes alias sources, leagues, owners, or users.
The browser deduplicates concurrent loads and caches this metadata for five
minutes; failed loads can retry. Existing mounted views refresh on reload or a
new catalog load. No alias database request occurs for local search keystrokes.

Browser matching uses **database team IDs**, with name-only fallback restricted
to an unambiguous exact displayed name. JSON is not imported by runtime search.
Normal names/typos remain searchable if alias metadata cannot load; the UI offers
retry. Existing league authorization and sport restrictions remain in place.

`SchoolAlias` has RLS enabled and no direct anon/authenticated table access.
Use the backend API for browser reads; database maintenance uses an authorized
backend/admin connection. When inserting aliases, compute `normalizedAlias` with
`api.utils.team_search.normalize_team_search_text` (with api as the import root,
`utils.team_search.normalize_team_search_text`). Keep existing aliases on conflict.
There is no alias editor or browser write endpoint in this change.

## Seed and migration tools

`api/data/team_search_aliases.json` is **offline seed data only**. It contains 864
provider identities from ESPN public men's/women's basketball and football team
metadata, with source URLs recorded. `overrides.json` contains vetted additional
seed names and their official sources. Editing either file does not change live
search; update `SchoolAlias` for runtime changes.

The importer maps `SportTeam.externalId` to provider identity, then uses the
team's real `schoolId`. It never assumes provider/team/school IDs are equal.
Absent provider schools are skipped, ambiguous provider mappings are rejected,
and current canonical School names are included. Legacy short/team labels were preserved by the consolidation migration before their columns were retired. It creates
no schools or teams. Replay uses `ON CONFLICT DO NOTHING` and preserves manual
aliases and their source.

The migration runner owns one transaction for the additive table and import.
Default mode rolls back all DDL/data; `--apply` commits after verification. It
validates configured project identity and an expected target fingerprint, uses
bounded lock/statement timeouts, and suppresses credentials/connection details.
It is not a general schema-drift repair tool; an existing-table replay validates
columns and named uniqueness, so unrelated manual schema/security changes need
separate review before replay.

```sh
# Current reviewed target only; reads api/.env or existing process configuration.
python3 scripts/team-search/migrate_school_aliases.py --expected-target 4ecd426e8efadd29 --receipt /tmp/school-alias-dry-run.json
# Explicitly authorized commit (already applied on the configured target):
python3 scripts/team-search/migrate_school_aliases.py --expected-target 4ecd426e8efadd29 --apply --receipt /tmp/school-alias-apply.json
```

Other environments require their own identity/preflight. Deploy the schema before
application code. Recover a failed import by transaction rollback; do not drop a
live table to retry because it may contain manually maintained aliases.

To refresh offline seed inputs, download each public source URL in the seed file,
then run:

```sh
python3 scripts/team-search/build_catalog.py /path/to/mens-team-names.json /path/to/womens-team-names.json /path/to/football-team-names.json
```

Keep full provider snapshots outside the repository and review generated changes.
The builder never fetches data, changes runtime aliases, or writes the database.

Python and TypeScript share literal behavior fixtures in
`tests/fixtures/team-search-cases.json`, including explicit test aliases. Exact
matches outrank aliases and partial matches; typo results are shown only if no
strong result satisfies current filters. Short abbreviations never use fuzzy
matching. Queries are bounded to 120 characters and eight tokens.


## One canonical school name

The user selected shorter school names such as **Northern Iowa**. Runtime readers
now resolve labels from `School.name` through `SportTeam.schoolId`; API properties
such as `displayName` remain for compatibility, but no longer require a stored
SportTeam display-name column. Official names and abbreviations stay in
`SchoolAlias`. Provider GameResult name fields remain source records; linked game
labels resolve to School.name and unlinked opponents retain their source name.

The reviewed consolidation plan contains 336 name changes and leaves unmapped
School347 unchanged. Both retired columns must remain on the live database until
all API/job deployments run the compatible code. Frozen baselines/snapshots and
historical verifier fixtures remain historical, rather than being rewritten.

```sh
# Read-only name plan:
python3 scripts/team-search/consolidate_school_names.py --plan --expected-target 4ecd426e8efadd29 --receipt /tmp/school-name-plan.json
# Default: preserve aliases, rename, physically drop columns, verify reads, ROLLBACK:
python3 scripts/team-search/consolidate_school_names.py --expected-target 4ecd426e8efadd29 --receipt /tmp/school-name-dry-run.json
# Commit shorter names only while retaining legacy columns for old deployments:
python3 scripts/team-search/consolidate_school_names.py --apply-names --expected-target 4ecd426e8efadd29 --receipt /tmp/school-name-apply.json
# AFTER verifying compatible API/jobs deployment, commit the destructive phase:
python3 scripts/team-search/consolidate_school_names.py --drop-retired-columns --deployed-revision VERIFIED_DEPLOYED_COMMIT --expected-target 4ecd426e8efadd29 --receipt /tmp/school-name-drop.json
```

The deployed revision is an operator attestation, not an automatic deployment
check; verify every running API, ingestion, and job service before using it.
The runner owns one bounded transaction, preserves old names as aliases, blocks
ambiguous provider mappings in either direction, and drops without CASCADE.
The receipt records before/after names for review and recovery. Canonical names
are changed only by this explicitly invoked maintenance command; the seed importer
and ordinary ingestion do not overwrite independently maintained School names.
