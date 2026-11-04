# Backend startup

The backend is Python/Flask; `npm run dev` starts the separate frontend.
Local isolated checks are verified with Python **3.14.1** and Node **22.22.2**.
CI uses Python **3.14** and Node **22.22.2**. Other runtime versions have not been
validated for this startup change. Production eventlet/Gunicorn operation still
needs a deployment smoke check; isolated tests use fake launch dependencies.

From `api`, create/activate a virtual environment and install dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 dev.py
```

The development server listens on port 5050. Configure `api/.env` or process
environment with `SUPABASE_DB_URL`, `SUPABASE_PROJECT_ID`, and
`SUPABASE_JWT_SECRET`. Process environment takes precedence. Runtime entry points
resolve `.env` relative to the API directory, independent of the current directory.
Never put credentials in checked-in files.

## Notification listener

Web startup retains the in-process PostgreSQL notification listener by default.
It uses `DATABASE_URL`, separately from the application `SUPABASE_DB_URL`.
To run the web server without notification listening:

```sh
DRAFT_NOTIFY_LISTENER_ENABLED=false python3 dev.py
```

The switch accepts `true`/`1` and `false`/`0` (case insensitive); invalid values
fail before startup. Disabling it removes database-driven draft broadcasts from
that web process. It does not suspend or restart a Render service, or disable
the independently invoked draft-timeout worker. Preserve the intentionally
suspended service until its actual command is verified.

`create_app(engine=...)` only constructs the HTTP/socket application; it starts
no listener. `runtime.create_web_app()` explicitly loads configuration, creates
the engine/application and starts the enabled listener. The dev reload supervisor
does not start a listener; its serving child does. Startup is idempotent per app.
Production retains the existing single-worker eventlet topology:

```sh
./start.sh
# Equivalent from api after runtime environment is configured:
gunicorn -k eventlet -w 1 -b 0.0.0.0:5050 wsgi:app
```

`wsgi.py` is an intentional runtime entry point: importing it initializes the web
application and applies eventlet monkey patching. Importing definition modules
(`api`, `db`, `dev`, domain and job modules) does neither. Do not preload the app
in a Gunicorn master or increase worker count without a separate listener and
Socket.IO coordination review.

## Jobs and maintenance commands

Run explicit module entry points from `api` so imports use the established API
module root. These commands perform real work; they are not test commands:

```sh
python3 -m cronJobs.cronComputeWeeklyScores
python3 -m cronJobs.cronComputeFinalScoreboard
python3 -m cronJobs.cronIngestScoreboard
python3 -m worker.draftTimeoutWorker
python3 -m startSeasonJobs.startSeason --config startSeasonJobs/configs/college-football-2026.json
python3 -m scripts.rebuild_weeks_and_rescore --season-year 2026
```

Cron `main(engine=...)` and timeout `run(engine=...)` accept injected engines for
isolated callers. They resolve runtime configuration only when no engine is
supplied. Job schedules, recovery rules and calculations are unchanged.

## Credential-free verification

From the repository root:

```sh
python3 api/tests/run_isolated.py
```

The runner clears runtime environment, disables dotenv, and prohibits engine
creation and network/database connections. Startup tests additionally check
fresh-process imports, fake web/job launches and listener/reloader configuration.
Do not replace this command with app startup or ordinary configured discovery.

Frontend checks, from `front-end` with dependencies installed:

```sh
node --test --experimental-strip-types tests/*.test.ts
npm run build
```

Node 22.22.2 supports the TypeScript stripping used by the tests and tier tools.
Render command/role inspection and hosted startup verification remain separate
read-only/deployment checks. No hosted configuration is changed by this work.

### Keeping future schedules current

The schedule API requires `api/migrations/20261030_game_kickoff_tbd.sql`.
A read-only configured-database check on 2026-11-02 confirmed the required
`boolean NOT NULL DEFAULT false` column already exists; no hosted migration
was run. For other/new databases, see the [baseline upgrade sequence](../db/README.md#current-schema-after-the-mainaudit-integration). ESPN's `timeValid=false` means kickoff is unannounced. These fixtures use
noon Eastern as a date anchor and return `timeTBD=true`; all schedule views show
`TBD` rather than presenting that anchor as kickoff. Confirmed late games retain
their actual timestamps.

From `api`, run `python3 -m cronJobs.cronRefreshSchedules` daily alongside live scoreboard
polling. It refreshes the next 21 days once per sport season, including moved
games and newly announced kickoff times. For a full future football repair use
`--sport-season-id ID --days 100`. Refresh after deploying both API and frontend
so existing placeholders acquire the flag and correct calendar date.

## HTTP errors and input limits

REST errors include `error.code`, `error.message`, and `requestId` matching
`X-Request-ID`. A top-level `message` remains for existing browser consumers.
Legacy string `error` values now live in `error.code`. Errors use `no-store`;
5xx responses contain a generic message without driver/SQL/private details.
Malformed JSON/types return 400, integrity conflicts 409, oversized bodies 413,
and unsupported media types 415 where JSON parsing requires it. Existing
resource concealment and disabled-operation statuses remain intact. Only the
middleware's pre-execution `auth_token_invalid` denial permits browser refresh;
resource conflicts and permission denials do not trigger refresh/replay.

| Input | Ceiling / accepted range |
| --- | --- |
| Request body | 262144 bytes (256 KiB), including unknown-length terminated streams |
| Query string | 8192 bytes |
| Scoring `weekNumbers` | 128 entries |
| Trade `fromTeamIds`, `toTeamIds` | 256 entries per side |
| Public league search `q` | 128 characters |
| Public league search `limit` | 1–50 |
| Public league search `offset` | 0–10000 |

These are operational ceilings; domain ownership, membership, week and trade
rules still apply. Oversized arrays/query values return 400 before domain work;
collections are never silently truncated. No roster/draft read is paginated by
these changes. Gateway rate quotas, trusted proxy topology and distributed
rate enforcement remain a separate decision.

Draft order updates must contain every current league member exactly once.
Start requires a Pre-Draft league, absent/pristine `pre` state and no existing
turns/picks. Repeated starts return 409 with `draft_start_conflict`, preserving
picks, cursor and timers. Paused drafts use the existing resume operation.


## Linked profile provisioning

MOD-006 prepares `20261104_user_identity_unique.sql` to enforce one profile per
non-null auth subject; nullable legacy/job UUIDs and unique email are preserved.
Run the [aggregate preflight and rollout review](../db/preflights/README.md) before
installing it operationally. No automatic schema migration runs at startup.

With the constraint installed, concurrent first login creates one profile; the
loser returns the existing safe 409 rather than a generic constraint failure.
The service rolls back before making one verified-subject lookup. It does not
look up identity by email, retry mutations, return someone else's profile or
update existing values. Email conflicts across subjects remain safe 400 failures.
The application alone cannot guarantee uniqueness on an unmigrated database.


The configured application database's MOD-006 constraint was installed and
verified on2026-11-04 after maintainer authorization and clean aggregate preflight
(14 profiles;0 unlinked/duplicate groups; counts unchanged). See the
[rollout evidence](../docs/modernization/evidence/mod-006-rollout-2026-11-04.json).
This database operation did not deploy backend application code.


## Week and score identity (MOD-008)

Fresh calendar initialization writes the full boundary plan, including football
week0, atomically after a League lock/recheck. Failed inserts leave no partial
plan; retries and competing callers return one canonical set. Existing weeks
are returned without rebuilding historical periods. Date/ranking behavior is
unchanged. Score replacement locks the scoped Week before replacing its complete
score set; a missing period fails before mutation.

The configured database's natural keys and same-league score FKs were installed
and verified on2026-11-04:176 weeks and340 scores, clean/unchanged aggregate
counts. [Migration, preflight and recovery instructions](../db/preflights/MOD-008.md).
No SQL runs automatically at startup. Application locking changes require normal
backend deployment; database constraints alone do not make older multi-transaction
initialization atomic. Job completion/ownership snapshot policy remains separate.


## Ownership writes (MOD-010)

Supported draft/live/manual/timeout, trade application and free-agent reservation/
application share the stable per-league transaction advisory mutex in
`utils/ownership.py`. Acquire it before DraftState/Transaction row locks; pass
that transaction connection to validation/persistence helpers. Private insert
helpers are not independently locked public commands. Free-agent queued work
rechecks actual drops/availability/conference caps before completing; rejected
work remains pending with ownership rolled back. Job timing/veto behavior and
acquisition defaults are unchanged.

The configured database's interval/member/overlap constraints were installed
and verified on2026-11-04 using btree_gist1.7 (1059 slots unchanged, including10
valid empty intervals). [Migration/preflight/recovery details](../db/preflights/MOD-010.md).
Other environments follow the full baseline/additive migration sequence. The
mutex and apply-time validation require normal deployment of all backend/job
writers; this SQL rollout did not deploy application code or execute jobs.
