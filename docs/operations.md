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

## Automatic conference standings and season bonuses

The prepared migration `api/migrations/20261124_conference_standings.sql` adds backend-only snapshot/final-result storage and GameResult.bonusTournamentCode. Apply it through the existing reviewed database rollout process **before deploying these readers/jobs**. It expects the existing GameResult.isCompleted column, platform roles and backend authority. The migration does not populate results or repair old classifications. It has been exercised against the owned local PostgreSQL integration fixture, not production.

The existing scoreboard ingestion command also collects standings once per unfinalized sport season with leagues. It uses bounded public ESPN requests, verifies returned provider year/group and imports regular-season conference records; no API key is required. Basketball requests the regular season's ending year (project season 2026–27 → ESPN 2027). FBS uses group=80 and FCS group=81; group is singular. Network work happens outside write transactions. Collection shares the ingestion gate, serializes against finalization, and rechecks season membership before committing immutable snapshots.

Inspect/retry a season from `api`:

```sh
PYTHONPATH=. python3 scripts/collect_conference_standings.py --sport-season-id 123
PYTHONPATH=. python3 scripts/collect_conference_standings.py --sport-season-id 123 --apply
```

The first command previews, the second stores validated snapshots. Reports list ready/pending conference IDs; automatic job logs include sportSeasonId, successful count and pending count. During the regular season, snapshots are provisional and no final conference award is assumed. Missing/ambiguous records, incomplete team mappings, unsupported future playoff formats or incomplete national brackets stay pending and block affected season finalization. Known FBS/FCS independent groups receive zero conference awards because they have no conference placement. A public feed may change; a failed fetch is retriable and does not clear good stored data.

Eligible national game identity and roundOrder are written from verified ESPN tournament labels, independently of overlapping dates. Football conference championships and ordinary bowls are not assigned a national-playoff phase merely because of their date. Old games without verified bonusTournamentCode/roundOrder cannot silently earn playoff awards. Preview their source data and existing classifications before a deliberately scoped refresh/reingestion; do not run a forced full bootstrap as a health check. No historical data was rewritten by this change.

Known format coverage: NCAA ending years 2011–2026 except canceled 2020 (68 teams), 2027 (76 teams/12 opening games); CFP seasons 2014–2023 (4 teams), 2024–2026 (12 teams); FCS seasons 2022–2026 (24 teams). New formats require verified round-count/round-label updates. The scorer validates game counts and winner advancement including byes before awarding completed playoff bonuses.

All bonus application is confined to cronComputeFinalScoreboard: collecting standings or reading the scoreboard never awards points, even after a regular season or tournament ends. Completed totals are stored in SeasonBonusResult in the same transaction as season completion. Provider corrections do not alter those totals. Existing completed leagues that predate this table have no frozen snapshot; any historical repair requires separate review. No new production schedule is created and the existing manual-only season finalizer remains manual.

Future playoff participants and fixtures are dynamic. The existing lookahead refresh and live ingestion jobs collect published matchups/results as they become available; do not fabricate or backfill unknown games. Reingestion is relevant only to games already stored without verified bonus identity/round fields. A season with no such existing playoff games needs no playoff backfill. The final-scoreboard-only timing correction needs no additional schema migration.
