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

## Notification listener, liveness and readiness

The in-process listener is enabled by default. It derives a dedicated, unpooled
connection from the application engine's `SUPABASE_DB_URL`, preserving URL/dialect
SSL options. `DATABASE_URL` is now only an optional legacy consistency assertion:
if set, its effective host/port/database/role must match or startup fails safely.
Never print either value. Proxy/direct aliases are not inferred equal; privately
review the deployed targets before removing an obsolete legacy variable.

`DRAFT_NOTIFY_LISTENER_ENABLED=false` intentionally disables listening. The switch
accepts true/1 and false/0 (case insensitive); invalid values fail startup. It does
not change the separate timeout worker or restart the intentionally suspended
Render service. Preserve that suspension until its actual command is verified.

`/health` stays `{ok:true}`/200. Public `/ready` returns fixed, no-store diagnostics
without querying dependencies:200 when disabled or connected/healthy,503 when a
required listener is absent, starting, retrying, degraded or stopped. This is local
listener readiness, not proof of job schedules/provider health or deployed supervision.

Transport faults retry indefinitely with capped1→30s backoff. Poll waits are≤1s,
idle probes15s; disconnect detection is not instantaneous. Failed league wakeups
retry independently in a bounded set; reconnect refreshes current subscribed rooms
through the MOD023 authorization gate. No durable event replay platform is added.

`create_app(engine=...)` constructs routes/sockets without starting background work;
`runtime.create_web_app()` explicitly starts the enabled listener. The reload parent
skips startup, and repeated startup is idempotent per app. Explicit stop closes the
owned connection and prevents retries/emits; development finally and Gunicorn's
worker_exit hook invoke it. No request teardown stops the listener.

Production retains the single-worker eventlet topology:

```sh
./start.sh
# Equivalent from api after runtime environment is configured:
gunicorn -c gunicorn_conf.py -k eventlet -w 1 -b 0.0.0.0:5050 wsgi:app
```

Do not preload the app or increase Socket.IO worker count without a separate
coordination review. Definition imports stay free of configuration and runtime
side effects; wsgi is an intentional composition/monkey-patching entry point.
See the [MOD024 runbook](../docs/modernization/mod-024-operations.md) for connection
mode requirements, shutdown limits and the outstanding hosted inspection.

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
supplied. Job schedules and calculations are unchanged. The four standard one-shot cron
adapters use per-command PostgreSQL session locks: competing invocations skip
without provider/domain work and exit0. Partial failures exit1; existing weekly/
final JSON reports remain on stdout, safe structured events on stderr. The timeout
worker has stop-aware waits and standalone SIGTERM/SIGINT cleanup. These gates need
session-preserving connections and pool capacity for both gate and domain work;
they are best-effort single flight between checks, not exactly-once execution.

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

## Atomic league initialization (MOD-012)

League creation inserts the league, creator membership and calendar in one
transaction. Initialization callbacks must accept `conn=` and use that connection;
`ScheduleCalendarService.ensure_weeks_for_job(league_id, conn=conn)` supports this.
Calendar planning or insertion failure, including deferred commit failure, rolls
back the whole creation. Retry after correcting the cause; separate successful
POSTs are not deduplicated. Existing partial leagues need explicit investigation.

`numPlayers` is current membership, not capacity. Creation sets it to one and
approval derives it from memberships under the league lock. Membership is uncapped;
the existing draft-round formula remains pending a separate fairness design.
This change requires the updated backend; no MOD-012 SQL migration is needed.

## Weekly completion and retry (MOD-013)

The weekly cron delegates to `WeeklyCompletionService`. Scores, the exact week's
completion flag, and its own/next numbered period's locks commit together. Pending
trades/free-agent changes apply only after their assigned week's predecessor has
successfully closed, before scoring that target. Retries also examine eligible
pending work when no new weeks need scoring. Catch-up runs process periods in order.

Each application commits independently under the shared v1 league ownership mutex.
An application failure preserves the pending command and stops that league for the
run; other leagues continue. Earlier successful applications remain committed and
are skipped on retry. Trade acceptance/veto/cancellation share the mutex so they
cannot enqueue or alter a command while weekly closure/application uses its state.
Standalone scoring/application calls retain their existing contracts; supplied
`conn=` calls leave commit/rollback to their caller. Manual rebuild/rescore safety
remains MOD-016; these job guarantees do not make maintenance history-safe.

The job prints a JSON report with `closed` week IDs, `applied` transaction IDs,
`blocked` reasons and safe failure categories. CLI exit is nonzero if blocked work
or failures remain. Correct the cause through an approved workflow and rerun the
same job; there is no automatic cancellation, retargeting or historical repair.
First-period pending commands (no predecessor), missing calendar periods, wrong-
league targets and already-scored targets are retained/reported for investigation.
Do not bypass these reports by applying ownership changes to scored periods.

MOD-013 needs the updated backend/job code and existing Priority 5 guards, with no
new migration, scheduler, queue, or dependency. No configured job was run during
verification. [Design](../docs/superpowers/specs/2026-11-05-mod-013-design.md),
[native evidence](../docs/modernization/evidence/mod-013-postgres-2026-11-05.json).

## Atomic season finalization (MOD-014)

The final-scoreboard cron delegates to `SeasonFinalizationService`. A sport-season
is eligible only after its inclusive `seasonEnd` date has passed in UTC. Every
matching league, including lifecycle `Completed` leagues, needs a nonempty,
contiguous calendar with ended/completed periods, no `PENDING_APPLY` commands,
and valid nonempty standings covering its current membership. Empty season scopes
or incomplete Pre-Draft leagues block finalization; there is no implicit exemption.

One transaction validates all scoped leagues and commits their completion updates
and `SportSeason.seasonFinalized` together. Season-row locking precedes sorted v1
league ownership mutexes and row locks, serializing competing finalizers and weekly
work. The supplied `conn=` path through trusted season standings and all bonus/
tiebreak helpers owns no separate connection or commit. Standalone/HTTP standings
contracts and formulas remain; bonuses/standings are computed reads, not snapshots.

The CLI prints `finalized`, `skipped`, `blocked` and `failures` and exits nonzero for
blocks/failures. Discovery/startup errors receive category-only reports with null
`sportSeasonId` and a `discovery`/`job` stage; SQL/payload/exception messages are not
printed. A failed season rolls back this run's updates; other seasons continue.
Pre-existing lifecycle completion statuses remain as they were. Correct the cause
and rerun: a successfully finalized season skips, an unfinished season revalidates.
Run weekly recovery first for incomplete periods/pending applications. Finalization
does not apply/cancel/retarget commands or automatically resolve PROPOSED trades.

The marker records validation of the scoped league set, not an immutable seal.
Detected concurrent scope changes refuse completion; future administrative/provider/
historical changes are not prevented. Historical snapshot/maintenance policy remains
MOD-015/016. No new migration, queue or dependency; no configured job ran during
verification. [Design](../docs/superpowers/specs/2026-11-05-mod-014-design.md),
[native evidence](../docs/modernization/evidence/mod-014-postgres-2026-11-05.json).

## Seasonal conference membership (MOD-015)

For the league/requested season, one exact-season membership overrides the default
`seasonYear=NULL` row. Other seasons are ignored. Without a seasonal row, the valid
current row remains fallback; an invalid exact-season row suppresses fallback rather
than hiding dirty configuration. Team, membership and conference sports must agree.
Every draftable team needs an assigned conference, including real-world independents;
there is no implicit independent/uncapped bucket. No assignments were guessed.

Manual/live/timeout picks, trade validation/application and free-agent submission/
application validate affected and retained roster mappings on their transaction.
Missing or cross-sport configuration refuses writes without changing ownership,
commands or draft progress. Auto-pick samples mapped conference buckets only; the
existing no-candidate outcome remains. Configured cap-value semantics and draft-round
scaling are unchanged. Private transaction mapping helpers now require league context;
retired independent-selection helpers have no replacement bypass.

Roster/history/search reads keep existing team/slot/pick rows and response fields.
Missing or league-sport-inconsistent conference metadata stays null; the UI labels
it **Conference unavailable**, not Independent. Configured conference names remain
unchanged and follow their actual caps. Explicit seasonal mappings resist default
moves; historical seasons without one deliberately still follow default fallback.
This is not a historical snapshot guarantee (MOD-016 remains separate).

Game upsert validates and locks its season, optional phase and known participant
team references using the supplied transaction before writing. Nullable external
participants/phases remain supported. This protects that application boundary,
not arbitrary SQL or future parent metadata edits. The read-only
[MOD-015 preflight and constraint proposal](../db/preflights/MOD-015.md) documents
remaining composite-key/nullable-sport decisions. No migration or configured-target
preflight ran, and no historical data was repaired during implementation.

[Consumer inventory and verification](../docs/modernization/mod-015-conference-membership.md).

## Calendar maintenance safeguards (MOD-016)

`rebuild_weeks_and_rescore.py` now previews by default and requires `--apply` for
unused Pre-Draft repair. Every historical/active/finalized case is preview-only,
including historical rescores with unchanged calendar boundaries. The preview
reports exact season/ID scope, before/after period boundaries, retained week IDs,
history counts, ownership/transaction temporal impacts and stored score totals.

Permitted calendar changes, ended-period scoring and flags share one transaction
per league. Season → ownership mutex → existing DraftState → League → Week ordering
matches draft controls; newly appeared state causes refusal without taking its lock
under League. Pristine state requires pick1 and null currentMemberId/expiresAt/
lastPickAt. History/reference checks occur after locks, including foreign-league
references that would otherwise cascade-delete. No transaction/score deletion is
used to bypass those checks. Other selected leagues continue after failure; inspect
the report for partial success. Discovery/startup/commit failures use category-only
reporting, without SQL/exception payloads.

No new migration, history remapping, snapshots, provider run or deployment.
Standalone scoring contracts remain; the new maintenance tool is not a historical
rescore authorization or immutable-input snapshot. [Usage and retry guidance](startSeasonJobs/README.md),
[design](../docs/superpowers/specs/2026-11-06-mod-016-design.md),
[evidence](../docs/modernization/evidence/mod-016-postgres-2026-11-06.json).
