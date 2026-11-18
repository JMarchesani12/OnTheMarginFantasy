# MOD-024 operational contract and deployment handoff — 2026-11-06

This is source-verified behavior and a runbook, not a hosted rollout record.
No hosted service, environment variable, scheduler or suspended service was changed.
The separate Render service reported suspended remains intentionally suspended.

## Repository-observed processes

| Process | Invocation from api | Observed behavior | Hosted evidence |
| --- | --- | --- | --- |
| Web | ./start.sh | gunicorn -c gunicorn_conf.py -k eventlet -w1; wsgi applies monkey patching, runtime composes app/listener | Actual Render command/revision/role unknown |
| Development | python3 dev.py | Reload supervisor skips listener; serving child owns it | Local entry only |
| Draft timeout | python3 -m worker.draftTimeoutWorker | Continuous deadline polling; idle wait ≤30s, active minimum0.5s, failure wait2s | Actual supervisor/restart policy unknown |
| Live scoreboard | python3 -m cronJobs.cronIngestScoreboard | Central today; also yesterday before03:00; per-league failures continue and CLI exits1 | Actual cadence unknown |
| Future schedules | python3 -m cronJobs.cronRefreshSchedules | Default21-day horizon; daily is the existing recommendation; per-day failure continues and CLI exits1 | Actual cadence unknown |
| Weekly completion | python3 -m cronJobs.cronComputeWeeklyScores | Retry-safe weekly closure/pending application; existing scoped report/exit1 for failure/block | Actual cadence unknown |
| Season finalization | python3 -m cronJobs.cronComputeFinalScoreboard | Atomic validated sport-season finalization; existing report/exit1 for failure/block | Actual cadence unknown |

These are real-work commands, not smoke tests; do not invoke them just to verify startup.
One-shot adapters suppress concurrent invocations of the same command with a
nonblocking PostgreSQL session advisory lock. A duplicate logs already_running,
exits0 and performs no service/provider work. Different command types retain domain
transaction/ownership coordination. Separate pools need capacity for one gate
connection plus domain work; do not configure a one-connection pool for these jobs.
Use session-preserving/direct database connections for these guards. Transaction
poolers cannot preserve PostgreSQL session advisory locks and LISTEN state and are
not a supported deployment for this runtime contract. Connection loss can be
observed only at checks: already running independent domain transactions cannot
be recalled, so this is best-effort single flight, not exactly-once execution.
A detected loss fails the run and never reconnects its gate. Failed unlock or
interrupted setup discards the physical connection rather than leaking a lock
through the application pool. Process disconnect releases the session lock.
Multiple timeout workers may poll; existing ownership/state locks and fresh
clock checks determine one committed transition, without a separate worker lease.

## Connection selection and private configuration review

SUPABASE_DB_URL builds the application engine. The listener now derives its dedicated,
unpooled connection from that injected engine and preserves dialect SSL options.
It does not use DATABASE_URL as a second source. If DATABASE_URL is present it must
parse and match effective host/port/database/role, including URL query overrides and hostaddr/service transport selectors.
Different passwords do not change this target comparison; only engine credentials
are used. Malformed/mismatched values fail before background startup with a fixed
configuration error. Never print either URL or expose comparison inputs in logs.

Different proxy/direct hostnames are not inferred to be the same database. Before
rollout, privately inspect the real web process's variable names/targets/connection
mode; remove the obsolete DATABASE_URL only after confirming the intended engine
endpoint supports persistent LISTEN/session locks. No configuration is changed here.
Missing connection timeout defaults to5s; explicit timeout must be1–30s. Default
TCP keepalives are enabled (idle30s/interval10s/count3), preserving explicit options.
Timeout/pooler/role compatibility still needs a real deployment smoke check.
The supported repository engine factory configures connection options through the
URL. Arbitrary injected engine creator hooks/connect_args are not reproduced by
the listener: extensions using non-URL SSL/auth/creator behavior need an explicit
adapter before deployment.

## Liveness, readiness and recovery

/health retains {ok:true}/200. /ready is public, no-store, and performs no request-time
database/provider query. It returns only ok and listener enabled/state/category:

- Disabled listener:200/disabled, preserving intentional disablement.
- Required but unstarted, starting, retrying, degraded or stopped:503.
- Connected transport, finished room resync, no failed pending deliveries:200.

These describe this process only; they do not attest to cron schedules, last job
success, external provider health, privileges of another actor, or another worker.
Existing REST error envelopes stay unchanged; /ready's intentional503 has its
fixed operational body plus X-Request-ID. Do not configure a deployment to restart
it repeatedly solely because readiness is temporarily503 without deciding that
platform policy separately. Liveness and readiness serve different purposes.

Listener connection/LISTEN/select/poll/idle-probe faults close owned resources and
retry with1,2,4,8,16,30s capped delays, indefinitely. Successful stable operation
resets backoff after15s. Poll waits are at most1s; idle probes run every15s, so a
silent failure may not be observed immediately. Failed snapshot wakeups coalesce
by league and retry independently with1→30s delays; other leagues continue. Pending
IDs cap at256. Overflow forces reconnect plus rotating bounded-batch resync of current room
subscriptions; a persistent failing prefix cannot starve healthy later rooms. Every reconnect resync and delivery uses MOD023's current member/
identity/session authorization gate. There is no durable event replay guarantee.

In an authorized deployment smoke check, verify /health200; /ready starting503 then
connected200 (or disabled200). Induce a test-only listener disconnect, verify safe
retry logs and readiness503, then recovery/resync200. Confirm a removed member gets
no private update. SIGTERM the test worker/process, verify listener session closes
and timeout loop stops; restart through the platform's chosen supervisor. Do this
in a disposable environment, not by running production jobs as probes.

Development applies eventlet monkey-patching before runtime/application imports,
matching production. A controlled real-eventlet scheduling regression with fake
connection I/O verifies the listener yields to another socket background task.
Definition imports still perform no monkey-patching.

Shutdown is cooperative: development finally and Gunicorn worker_exit stop the
listener; worker SIGTERM/SIGINT sets its stop event. Stop-aware waits exit promptly,
resources close, and listener delivery rechecks stop after authorization DB I/O.
It cannot preempt arbitrary blocking driver I/O or recall an in-flight payload.
No request teardown stops a process-level task. No app preload/multiple Socket.IO
workers/broker topology change is included. Listener instances do not restart after
explicit stop; restart the serving process to create a fresh instance.

## Logs and remaining hosted verification

Operational events are allowlisted JSON on stderr with operation/event/runId,
fixed category, and safe integer/count/date fields. Weekly/final stdout remains its
single legacy JSON report; partial/error outcomes retain nonzero exits. Raw driver/
provider exception text, DSNs, notification/snapshot payloads, contacts and tokens
are excluded. Provider parser rejection no longer prints bodies/tracebacks. Broad
bootstrap/checkpoint logging and provider retry policy remain outside this card.

The2026-10-29 configured-role assessment (postgres NOSUPERUSER/BYPASSRLS) is historical
and was not a verified Render role mapping. See mod-004-runtime-handoff.md for the
remaining read-only inventory: service IDs/types/commands/revisions, suspension,
actual web/worker/job roles, schedules and supervision/restart policy. No connected
Render service tools were available for this task. Do not claim deployed supervision
or scheduler coverage from repository source or a historical activity snapshot.

Priority6 can close in application/synthetic verification scope after MOD024 tests
and review. Hosted verification/rollout, MOD015 composite-constraint follow-up and
historical snapshot/remapping policy remain explicit independent work.
