# Disposable PostgreSQL assessment

`assess_postgres.py` verifies MOD-004/005/009 using installed Python dependencies
and the cached Supabase PostgreSQL image. It never reads `.env`, accepts no DSN,
and connects only to `127.0.0.1:55439`. It refuses a server without the explicit
assessment marker. Do not point a tunnel or a configured database at that port.

Run from the repository root. The commands below create a new task-owned
container with no persistent volumes, using trust authentication for synthetic
data and a port published only on loopback. They do not reuse existing Supabase
containers. Stop only the container named here when finished.

```sh
docker run -d --rm --name otm-modernization-assessment-20261029 \
  -p 127.0.0.1:55439:5432 --user postgres --entrypoint /bin/bash \
  public.ecr.aws/supabase/postgres:17.6.1.084 -lc \
  'initdb -D /tmp/otm-pgdata --auth=trust --no-locale >/tmp/otm-init.log && echo "host all all 0.0.0.0/0 trust" >> /tmp/otm-pgdata/pg_hba.conf && exec postgres -D /tmp/otm-pgdata -c listen_addresses=* -c unix_socket_directories=/tmp'

docker exec otm-modernization-assessment-20261029 pg_isready -h /tmp
# Continue after readiness succeeds.
docker exec otm-modernization-assessment-20261029 psql -h /tmp -U postgres -d postgres \
  -c "COMMENT ON DATABASE postgres IS 'otm-modernization-assessment-20261029-synthetic-only';"
python3 scripts/modernization/assess_postgres.py
docker stop otm-modernization-assessment-20261029
```

The harness creates random-named databases and dedicated NOLOGIN fixture roles,
then drops only the databases/roles it successfully created. A collision fails
rather than reusing or deleting a pre-existing role. Cleanup occurs on ordinary
exceptions; an externally killed process may require inspecting the task-owned
container or simply stopping/removing it.

Outputs in `docs/modernization/evidence/`:

- `public-schema-assessment-candidate.sql`: deduplicated/dependency-ordered source
  tables and indexes, with no inferred column or constraint changes. Requires
  separately provided Auth/extension prerequisites; it is not an approved
  deployment baseline or migration.
- `postgres-assessment-2026-10-29.json`: collected source/deployed definition
  differences, two historical migration fixtures, synthetic role outcomes and
  deterministic direct/dispatcher concurrent trade results. Includes input hashes.

Inputs include the dated deployed catalog and separately collected
`rls-auto-enable-2026-10-29.json`. The harness replays that observed function and
event-trigger registration locally, verifies public table creation enables RLS,
and reproduces the relevant broad table grants/User SELECT policy. Role names
are synthetic equivalents, not provider-created roles. `auth.users` and
`auth.uid()` are minimal SQL fixtures; this does not validate the full Supabase
Auth service, PostgREST, role membership graph, API exposure, platform upgrades,
sequence state, all column type modifiers, or deployment configuration.

Historical upgrade fixtures cover only an absent subdivision table and old-only
or correct-only SportSeason start column. They are not evidence that these were
actual historical deployments. The missing basketball migration is not recreated.
No automatic policy/grant changes or production execution are part of this tool.

## Versioned baseline and privilege proposal tests

### MOD-038 transaction pilot

With the same marked disposable loopback server ready, run
`python3 scripts/modernization/verify_transaction_pilot.py`. It creates/removes a
random synthetic database and reuses only the direct/dispatcher concurrent-trade
checks, then verifies native PostgreSQL transaction-list JSON projections,
member/commissioner access, denials and query-time revocation. It never loads
`.env`, accepts no DSN and refuses an unmarked server. Results and source hashes
are written to `docs/modernization/evidence/mod-038-pilot-postgres-2026-10-29.json`.
No schema/access reassessment output is overwritten. Stop only the task-owned
container when finished.

### MOD-038 roster continuation

With the same marked disposable loopback server ready, run
`python3 scripts/modernization/verify_roster_pilot.py`. It creates/removes its own
random database and checks native roster projections, locked-week/pending-move
semantics, seasonal conferences, tier fallback, resource denials and query-time
revocation/target-member removal. It accepts no DSN and never loads `.env`.
Results and source hashes are written separately to
`docs/modernization/evidence/mod-038-roster-postgres-2026-10-29.json` without
overwriting the transaction pilot report. Stop only the task-owned container
afterward.

### MOD-038 profile continuation

With the same marked disposable loopback server ready, run
`python3 scripts/modernization/verify_profile_pilot.py`. It creates/removes a
random synthetic database and verifies profile read/update projections, bound
values, field filtering, access denials, legacy facade behavior and rollback on
real statement and deferred-commit failures. It never loads `.env` or accepts a
DSN. Report/source hashes are written separately to
`docs/modernization/evidence/mod-038-profile-postgres-2026-10-29.json`. Stop only
the task-owned container afterward.

### MOD-038 profile creation and UUID persistence

With the same marked disposable server ready, run
`python3 scripts/modernization/verify_profile_creation.py`. It reruns profile
read/update checks, then creates synthetic Auth/User fixtures to verify native
creation, email/FK failures, duplicate-subject ambiguity, insert statement/commit
rollback and legacy UUID/creation compatibility. Minimal Auth fixtures do not
establish full provider acceptance. The runner removes its random database and
writes `docs/modernization/evidence/mod-038-profile-creation-postgres-2026-10-29.json`
with current source hashes. Earlier profile reports remain historical. It never
loads `.env` or accepts a DSN. Stop only the task-owned container afterward.

### MOD-038 weekly-points scoring read

With the marked disposable server ready, run
`python3 scripts/modernization/verify_scoring_read.py`. It creates/removes a
random database and checks native expanding-list SQL, score dates/numerics and
ordering, league access, empty-list policy and separate-connection revocation
before the final check. It writes
`docs/modernization/evidence/mod-038-scoring-read-postgres-2026-10-29.json` without
overwriting earlier reports. It accepts no DSN and never loads `.env`. Stop only
the task-owned container afterward.

### MOD-038 remaining scoring

With the marked disposable server ready, run
`python3 scripts/modernization/verify_scoring_complete.py`. It reruns weekly-read
checks, then verifies score replacement and real statement/deferred-commit
rollback, week zero/convergence, bonus/season tiebreak query families, actor
revocation and final-period guards. Schedule read facts are injected; no provider
requests are made. It creates/removes only its random database and writes
`docs/modernization/evidence/mod-038-scoring-complete-postgres-2026-10-29.json`.
Earlier scoring reports remain historical. No `.env` or arbitrary DSN is used.
Stop only the task-owned container afterward.

### MOD-038 admission listing and cancellation

With the marked disposable server ready, run
`python3 scripts/modernization/verify_admission_slice.py`. It creates/removes its
random database and verifies commissioner listing/revocation, owner cancellation,
URL scope, update/commit rollback and competing cancellation row-lock/replay
behavior through service and facade. Results/source hashes go to
`docs/modernization/evidence/mod-038-admission-postgres-2026-10-29.json`.
No `.env` or arbitrary DSN is used. Stop only the task-owned container afterward.

### MOD-038 admission creation and denial

With the marked disposable server ready, run
`python3 scripts/modernization/verify_admission_create_deny.py` sequentially with
other assessment suites. It reruns listing/cancellation checks, then resets only
its own random database schema for creation/repeat, real FK/statement/commit
failures, denial authority/resolver/rollback and competing league→request locks
through service and facade. Trusted/private helper compatibility is included.
Results/source hashes go to
`docs/modernization/evidence/mod-038-admission-create-deny-postgres-2026-10-29.json`,
superseding earlier admission source hashes while retaining historical reports.
It accepts no configured DSN or `.env`; it removes its database. Stop only the
task-owned container afterward. Approval/capacity and concurrent-creation
uniqueness are outside this verification.

### MOD-038 complete admission, including approval

With the marked disposable server ready, run
`python3 scripts/modernization/verify_admission_approval.py` sequentially with
other assessment suites. It reruns all preceding admission checks, then resets
only its random database schema to verify approval authority/projections,
membership/draft-order/count/round/JSON behavior, real uniqueness/FK failures,
post-write/deferred-commit rollback and observed competing approval lock waits.
Same-request replay and distinct-request allocation run through service and
legacy facade. Results/source hashes go to
`docs/modernization/evidence/mod-038-admission-complete-postgres-2026-10-29.json`,
superseding previous admission hashes while retaining historical reports.
No configured DSN or `.env` is accepted. The harness removes its database;
stop only the task-owned container afterward. No new capacity policy or
concurrent-creation uniqueness guarantee is implied.

### MOD-038 member profile updates

With the marked disposable server ready, run
`python3 scripts/modernization/verify_member_profile.py` sequentially with other
assessment suites. It reruns all admission checks, then resets only its owned
random database schema for member projection/owner scope/bound values, trusted
allowlist, executed-update/deferred-commit rollback and observed ownership
revocation during row-lock waits through service and facade. Results/source
hashes go to `docs/modernization/evidence/mod-038-member-profile-postgres-2026-10-30.json`,
superseding prior admission hashes while retaining historical reports. No
configured DSN or `.env` is accepted. The harness removes its database; stop
only the task-owned container afterward. Member removal is outside this slice.

### MOD-038 member removal and draft-order shifting

With the marked disposable server ready, run
`python3 scripts/modernization/verify_member_removal.py` sequentially with other
assessment suites. It reruns admission and member-profile checks before resetting
only its own random database schema for removal protection/projection/shift/count,
real FK/post-write/deferred-commit rollback and observed contention. Same-target
replay, distinct removals and approval after removal run through service/facade.
Results/source hashes go to
`docs/modernization/evidence/mod-038-member-removal-postgres-2026-10-30.json`,
superseding previous member/admission hashes while retaining historical reports.
No configured DSN or `.env` is accepted. The harness removes its database; stop
only the task-owned container afterward. No removal-policy redesign is implied.

### MOD-038 commissioner league deletion

With the marked disposable server ready, run
`python3 scripts/modernization/verify_league_delete.py` sequentially with other
assessment suites. It reruns all admission/member checks, then resets only its
owned random schema for deletion authority/projection, synthetic direct/multilevel
cascades, FK restriction, post-delete/deferred-commit rollback and suppressed-delete
guard. Service/facade lock waits cover competing deletion and authority revocation.
Results/source hashes go to
`docs/modernization/evidence/mod-038-league-delete-postgres-2026-10-30.json`,
superseding previous member/admission hashes while retaining historical reports.
No configured DSN or `.env` is accepted. The harness removes its database; stop
only the task-owned container afterward. No configured application data is deleted.

### MOD-038 league settings and metadata updates

With the marked disposable server ready, run
`python3 scripts/modernization/verify_league_settings.py` sequentially with other
assessment suites. It reruns league deletion/member/admission checks, then resets
only its own random schema for native update CTE/JSON/projection/deadlines,
statement/post-update/deferred-commit rollback, separate-connection late authority
change and trusted/private/helper compatibility. Original lowercase PostgreSQL
sportinfo alias and empty-Sport post-commit result guards are preserved explicitly.
Results/source hashes go to
`docs/modernization/evidence/mod-038-league-settings-postgres-2026-10-30.json`,
superseding previous league/member/admission hashes while retaining historical
reports. No configured DSN or `.env` is accepted. It removes its database; stop
only the task-owned container afterward. No lost-update or merge guarantee added.

### MOD-038 league creation

With the marked disposable server ready, run
`python3 scripts/modernization/verify_league_creation.py` sequentially with other
assessment suites. It reruns settings/deletion/member/admission checks before
resetting only its owned random schema for native creation CTE/JSON/projection,
league/member FK/post-write/deferred-commit rollback, missing projection and
post-commit initializer visibility/failure from a separate connection. The supplied
initializer creates a synthetic Week; ScheduleModel algorithms are unchanged,
not reimplemented by this fixture. Results/source hashes go to
`docs/modernization/evidence/mod-038-league-creation-postgres-2026-10-30.json`,
superseding prior league/member/admission hashes while retaining historical reports.
No configured DSN or `.env` is accepted. It removes its database; stop only the
task-owned container afterward. Initializer failure still preserves saved creation.

### MOD-038 league rules read

With the marked disposable server ready, run
`python3 scripts/modernization/verify_league_rules_read.py` sequentially with other
assessment suites. It reruns creation/settings/deletion/member/admission checks
before resetting only its own random schema for native rules/tier fallback/sport
isolation/deadlines, denied/missing no-team-query, trusted compatibility and
separate-connection membership revocation before scoped SELECT. Results/source
hashes go to `docs/modernization/evidence/mod-038-league-rules-read-postgres-2026-10-30.json`,
superseding prior league/member/admission hashes while retaining historical reports.
No configured DSN or `.env` is accepted. It removes its database; stop only the
task-owned container afterward. No new post-SELECT/snapshot guarantee is claimed.

### MOD-038 league conference reads

With the marked disposable server ready, run
`python3 scripts/modernization/verify_league_conferences.py` sequentially with other
assessment suites. It reruns all earlier league/member/admission checks, then
resets only its own random schema for conference season/null counts, sport
isolation, zero/order/projection/empty results, guarded missing-season reads and
separate-connection membership revocation with skipped aggregation. Results/source
hashes go to `docs/modernization/evidence/mod-038-league-conferences-postgres-2026-10-30.json`,
superseding prior league/member/admission hashes while retaining historical reports.
No configured DSN or `.env` is accepted. It removes its database; stop only the
task-owned container afterward. No stronger post-SELECT guarantee is added.

### MOD-038 league discovery/access/previews/search

With the marked disposable server ready, run
`python3 scripts/modernization/verify_league_discovery.py` sequentially with other
assessment suites. It reruns all earlier league/member/admission checks, then
resets only its random schema and creates pg_trgm in that owned synthetic DB
for real ranking/tie order/filter/pagination/bounds, metadata/preview projection
and independent visibility/membership revocation including the pre-query gap.
Results/source hashes go to
`docs/modernization/evidence/mod-038-league-discovery-postgres-2026-10-30.json`,
superseding prior hashes while retaining historical reports. No configured DSN
or `.env` is accepted. It removes its database; stop only the task-owned container
afterward. Anonymous public search and existing wildcard behavior are preserved.

### MOD-038 league details and own listings

Run `python3 scripts/modernization/verify_league_details.py` on the marked
synthetic server, sequentially with other suites. It reruns preceding league/member/
admission checks before resetting only its owned schema for native interval/week
selection, scores/stages/membership/projections, original overlap behavior and
explicit pre-read synchronization/revocation. Lifecycle algorithm remains unchanged.
Results/source hashes: `docs/modernization/evidence/mod-038-league-details-postgres-2026-10-30.json`.
This supersedes prior league hashes while retaining history. No configured DSN/.env;
it removes its random database. Stop only the task-owned container afterward.

### MOD-038 member lists and daily summaries

Run `python3 scripts/modernization/verify_member_summary.py` on the marked
synthetic server, sequentially with other suites. It reruns previous suites then
resets its own schema for actual member/week/score SQL, public timezone lookup,
week-zero/local/naive/aware date totals, null-start/no-week behavior, supplied game
failure and pre-query membership revocation. Scheduling game algorithms are
unchanged; supplied facts verify summary orchestration. Results/source hashes:
`docs/modernization/evidence/mod-038-member-summary-postgres-2026-10-30.json`.
Prior hashes superseded; history retained. No configured DSN/.env; random database
removed. Stop only the task-owned container afterward.

### MOD-038 complete league, including lifecycle

Run `python3 scripts/modernization/verify_league_lifecycle.py` on the marked
synthetic server, sequentially with other suites. It reruns all preceding league/
member/admission checks before resetting its owned schema for lifecycle matrix,
date boundaries/precedence, five post-phase/actual statement/deferred-commit
rollback and real model/read callback integration. Results/source hashes:
`docs/modernization/evidence/mod-038-league-complete-postgres-2026-10-30.json`.
This supersedes prior league evidence hashes, retaining history. No configured
DSN/.env; random DB removed. Stop only the task-owned container afterward.
Existing global read-time synchronization and timestamp behavior are preserved.

### MOD-040 complete league package organization

Run `python3 scripts/modernization/verify_league_folders.py` on the marked
synthetic server, sequentially with other suites. It reruns all previous league/
member/admission/lifecycle verification through legacy imports after grouping.
Results and complete canonical/alias/package manifest:
`docs/modernization/evidence/mod-040-league-folders-postgres-2026-10-30.json`.
Prior league source hashes are superseded; history retained. No configured DSN/
.env; owned random database removed. Stop only the task-owned container afterward.

### MOD-038 draft state snapshot

Run `python3 scripts/modernization/verify_draft_snapshot.py` on the marked synthetic
server, sequentially with other suites. It creates/removes its random database
and tests actual snapshot/repair/turn SQL, member-only authorization, season joins,
native JSON/timestamps, missing/trusted states, repair/caller/deferred-commit
rollback and pre-query membership revocation. Results/source hashes:
`docs/modernization/evidence/mod-038-draft-snapshot-postgres-2026-10-30.json`.
No configured DSN/.env. Stop only the task-owned container afterward. Picks,
controls, timeouts and realtime publication are outside this slice.

### MOD-038 draft finalization

Run `python3 scripts/modernization/verify_draft_finalization.py` on the marked
synthetic server, sequentially with other suites. It reruns draft snapshot checks
then verifies central finalization SQL, date boundaries/no-season/lastPickAt,
authority checks with separate revocation, post-write/statement/deferred-commit
and caller rollback, trusted/legacy paths. Results/source hashes:
`docs/modernization/evidence/mod-038-draft-finalization-postgres-2026-10-30.json`.
Prior draft source hashes superseded; history retained. No configured DSN/.env;
owned random DB removed. Stop only the task-owned container afterward.

### Baseline suite

After the same marked container is ready, run this separate suite sequentially
with other assessment suites:

```sh
python3 -m unittest discover -s scripts/modernization/tests -p test_baseline.py
```

It creates random-named fixture databases and platform-named NOLOGIN roles, all
removed afterward. No .env is loaded. See the [baseline runbook](../../db/baselines/20261029/README.md)
and [unapplied proposal/recovery](../../db/proposals/README.md). The frozen baseline
preserves the observed access behavior; it does not apply the tightening proposal.

## Real provider coverage

[Supabase provider acceptance](SUPABASE_PROVIDER.md) provisions a distinct local
Auth/PostgREST project, tests the same frozen baseline and historical/adoption
paths with real platform definitions, and verifies HTTP role behavior and
privilege recovery. It also demonstrates the normal postgres actor cannot change
supabase_admin defaults; the complete proposal needs a separately authorized
platform maintenance actor. No hosted changes or role elevation are performed.
