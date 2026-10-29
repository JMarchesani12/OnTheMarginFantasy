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
