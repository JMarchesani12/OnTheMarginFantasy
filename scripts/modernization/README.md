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

### Baseline suite run

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
