# Deployment and operations

The frontend is hosted on Vercel and the API/jobs on Render, deploying from main. Credentials are provisioned privately in the hosting environment.

## API and listener

Run from api with `./start.sh`. It loads Gunicorn's startup/shutdown hooks, uses one eventlet worker and binds to PORT. The standard `gunicorn.conf.py` shim loads the same hooks for ordinary Gunicorn invocation from api. Keep both hooks in custom configurations.

WSGI import does not construct the Flask application, database engine or listener. The serving worker constructs the runtime after eventlet initialization; post_worker_init starts its listener and worker_exit stops it. Development's reload parent does not start a listener. Do not increase Socket.IO worker count without a coordination design.

SUPABASE_DB_URL supplies the backend engine and dedicated listener connection. Use a direct or session-preserving connection; Supabase's shared session pooler uses 5432, while transaction mode 6543 is unsuitable for LISTEN/session advisory locks. If legacy DATABASE_URL is present, its effective target must match; it is not a second connection source. Do not share either URL in logs or chat.

`/health` returns 200 for liveness. `/ready` is public, no-store and returns 200 when the required listener is connected,503 while starting/disconnected/degraded. An intentionally disabled listener does not block readiness. DRAFT_NOTIFY_LISTENER_ENABLED accepts true/1/false/0. This flag does not control the separate timeout worker.

The listener retries transport failures with capped backoff, refreshes rooms on reconnect and rechecks recipient access before delivery. Connection readiness does not prove authenticated draft delivery; validate that separately in an appropriate test window. Stop closes owned connections and prevents further retries/emits.

## Scheduled jobs

Commands run from api. Render expressions use UTC; local times below use America/Chicago.

| Job | Command | Schedule / policy |
| --- | --- | --- |
| Scoreboard ingestion | `PYTHONPATH=. python3 cronJobs/cronIngestScoreboard.py` | `59 * * * *` |
| Weekly completion | `PYTHONPATH=. python3 cronJobs/cronComputeWeeklyScores.py` | `0 10 * * *`,04:00 CST /05:00 CDT |
| Schedule refresh | `PYTHONPATH=. python3 cronJobs/cronRefreshSchedules.py` | `0 9 * * *`,03:00 CST /04:00 CDT |
| Season finalization | `PYTHONPATH=. python3 cronJobs/cronComputeFinalScoreboard.py` | Supervised manual operation; unscheduled |
| Draft timeout worker | `PYTHONPATH=. python3 worker/draftTimeoutWorker.py` | Intentionally suspended; separate activation decision |

Refresh looks ahead 21 days by default, capped at season end, and updates kickoff announcements/rescheduling. It needs SUPABASE_DB_URL and the intended ESPN_BASE_URL. It supports --days and --sport-season-id for deliberately scoped refreshes. Ingestion uses current Central dates, including the prior day early in the morning. These commands perform real database/provider work; deployment/build success is not a successful run.

One-shot jobs hold per-command session advisory locks. A competing same-job invocation skips without domain/provider work and exits 0. Different jobs retain their domain transaction coordination. Pools need capacity for both a gate connection and domain work. Session loss fails the job rather than reconnecting its gate; this is best-effort single flight, not exactly-once execution.

Failures/blocked work exit 1. Weekly/finalization commands print sanitized JSON reports; structured operational events go to stderr. Inspect the full report: successful units may have committed before another fails. Refresh commits individual game upserts, so retries can follow partial progress. Do not manually trigger a Render cron merely as a health check; triggering while active cancels the existing run. Check run status and failure notifications first.

## Season finalization

The CLI considers **all ended, unfinalized sport-seasons**, without a season-ID argument. Before the first supervised production run, review every candidate season/league, expected standings, closed weeks, pending changes and memberships. Confirm the deployed revision, role/session connection and backup/recovery arrangements. A schema snapshot does not back up completion-status rows.

Each season finalizes atomically only after all of its leagues validate. A blocked/failed season remains retryable while other seasons can complete. Preserve the JSON report and verify completion statuses. Investigate and approve repairs before retry; completed seasons skip. Do not reset statuses or change active-season calendars to force eligibility. Creating a scheduled finalizer requires a separate operating decision.

## Calendar and season maintenance

[Season setup](../api/startSeasonJobs/README.md) documents manifests and resumable bootstrap. The existing-league calendar command is preview-only by default:

```sh
PYTHONPATH=. python3 scripts/rebuild_weeks_and_rescore.py --season-year 2026 --league-id 123
```

Only an eligible unused Pre-Draft league can be changed with --apply. Draft, roster, transaction or score history blocks repair. There is no history/force bypass. Review previews and handle historical remapping separately.

## Database changes and records

See [db](../db/README.md), [preflights](../db/preflights/README.md) and [snapshot tooling](../scripts/database/README.md). Migrations and reviewed SQL are explicit operator actions; web startup/deploy does not apply them. Retain before/after snapshots and an execution receipt. Do not replay applied SQL because it remains in the repository.

Current application tables/sequences deny browser roles direct privileges; backend APIs enforce principal/resource authorization. Supabase Auth is unaffected. Provider-owned future-object defaults remain a documented [follow-up](follow-ups.md), so inspect grants on newly created public objects.
