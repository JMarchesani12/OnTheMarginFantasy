# MOD022 ingestion baseline — 2026-11-15

Audit measurements only. No application/provider/query/index/dedup/retry/deployment change; all actual optimizations remain deferred until audit completion. [Current manifest](evidence/mod-022-ingestion-current-2026-11-15.json) points to [raw evidence](evidence/mod-022-ingestion-4a99952f31194cf198dd75ad106becc2.json).

## Actual path and controlled inputs

Current cron source calls ingest_league_for_job per active league. This runner replays that service-call shape for1/4/16 same-season leagues and compares the **already existing** ingest_season_for_job once. It does not run cron main, configured runtime, advisory job gate, checkpoint/bootstrap or a new dedup orchestrator. Call selection/gate/timezone/outer-job overhead is outside the measurement.

Actual ScheduleIngestionService, calendar/ingestion repositories and ESPNClient event iteration/extraction execute. Only fetch transport is substituted with canned JSON; requests.Session.request is patched to fail if attempted. No provider network access, live payload, rate/quota/outage/latency/retry/backoff claim. Canned fetch/deepcopy/parser cost is included in local timings, not real HTTP latency.

Native marked-loopback PostgreSQL17.6/schema001 + exact MOD006/008/010 + timeTBD migration.100 background leagues/16k slots/32teams, synthetic active statuses, sport1/groups10,20, season2026, one subdivision and legacy regular phase with empty rules. Six teams have known external IDs; fixed date2026-11-15. Current legacy fallback phase/reference-lock path is exercised, not seasonal conference-based phase selection/overrides. Existing mappings/reference validation and real committed UPSERTs execute in task-owned databases.

Group10 returns A,B plus an unparseable event with no competition; group20 returns identical A plus C. League helper sees5 raw events and upserts4 per league. Season helper filters invalid events and deduplicates external IDs across groups, reporting3 events/3upserts. Complete persisted fields (sport/season/phase/date/team/external IDs/names/scores/TBD/broadcast) independently checked; final rows exactly A/B/C. Correction case makes a second full sweep with AhomeScore99/broadcastCorrection; all three game identities must remain unchanged. Both groups carry the same A revision within each sweep.

This controlled final-state agreement does not establish interchangeable behavior for conflicting duplicate payloads, malformed/missing IDs, multiple sports/seasons/dates or differing failure boundaries. Existing raw-event versus deduped-event summary semantics also differ. Future routing needs an explicit policy/design rather than silently substituting helpers.

## Measured work

Twelve size/path/scenario records (overlap and correction) each have one warmup+five samples:72 workload invocations. Correction contains two sweeps per invocation. Setup/reset/verification reads are excluded from timers/counters. SQL cursor hooks classify service statements, fail on unknown categories and assert independent per-role formulas. Record SQL/parameter examples, provider call keys, distributions and16 source hashes.

One valid event upsert costs9SQL statements here:2 external-team lookups, phase-list read, fallback-phase read, season lock, phase lock,2team locks, UPSERT. League metadata costs4 (league/API config/season/subdivision), existing season helper2 (season/API config). With N leagues per sweep:

| Path | Fetches | Upserts | SQL statements |
| --- | ---: | ---: | ---: |
|League loop|2N|4N|40N|
|Existing season helper once|2|3|29|

Correction doubles these counts. This includes the existing reference-lock safeguards; no measured redundant work was removed.

Instrumented local service median milliseconds (sum of sweep intervals for correction):

| Same-season leagues | League overlap | Season overlap | League correction | Season correction |
| ---: | ---: | ---: | ---: | ---: |
|1|24.90|15.90|47.30|27.29|
|4|84.61|13.77|168.57|29.00|
|16|301.27|14.20|615.07|28.65|

At16 leagues, overlap uses32 canned fetches/64upserts/640SQL through the league loop, versus2/3/29 with one existing season call. This is a bounded workload comparison, not an implemented production speedup. Timers include connection/transaction/commit activity occurring within actual service calls, parser/fixture fetch and counter instrumentation. Verification between correction sweeps is excluded. Fixed-order warm samples, tiny event sets, no statistical confidence/cold-cache/production throughput/durability/WAL/concurrent-lock claim. Real network costs and provider distributions could dominate differently.

## Failure and explicit rerun probes

Two additional correctness/count probes (not latency comparisons) use fixed2leagues for league path versus one season call. One-shot group20 fetch failure follows committed A/B writes from group10. Both retain exactly2 correct partial rows. A caller explicitly reruns the workload after the failure; final rows3 and full fields match. This adds no automatic retry/backoff/checkpoint behavior.

| Path | Exception exposed | Total fetches across failed attempt + rerun | Upserts | SQL |
| --- | --- | ---: | ---: | ---: |
|League,2leagues on rerun|OSError|6|10|102|
|Season once on rerun|RuntimeError wrapper|4|5|49|

The retained partial writes matter for later retry/checkpoint design. These probes do not establish bootstrap completion policy, all outage recovery, grouped-event conflict precedence or atomic ingestion of a whole day.

## Audit conclusion and verification

Repeated league fetches/upserts and per-event mapping/phase queries are demonstrated work to consider in later MOD022 dedup/context design. Existing season-level code already avoids cross-group duplicate upserts in this fixture. No cron routing/dedup/cache/retry/provider/schema change was made, and broader MOD022 remains open. Full bootstrap checkpoints, season refresh, transport retry/backoff and production recovery remain separate.

Five new tests failed before runner existed; all40 measurement tests pass. All3 native sizes/12records/72workload invocations plus2failure/rerun probes pass complete expected fields/counts, correction identity preservation, five samples/medians, categorized SQL, fetch keys and16 provenance hashes. Unique RUNNING/PASS/FAILED artifacts and owned UUID cleanup gates reused. No native failure occurred in this batch.

Zero task databases observed, exact labeled loopback container removed, no persistent mounts, remaining ingestion taskcontainers0. Docker/image cache retained. No configured DSN/app/cron/provider network/checkpoint accessed. Work uncommitted/undeployed. [Closeout evidence](evidence/mod-022-ingestion-summary-2026-11-15.json).

Production/RLS/platform/schema-role equivalence, real payload sizes/provider quotas/HTTP timing, ongoing writes/WAL/vacuum/concurrency, multiple seasons/sports and phase/override edge cases remain unknown. All actual optimization implementation remains deferred until audit completion.

Independent final review: Critical0/Important0/Minor1. Reviewer passed40units/diff check and independently verified12records/60saved samples/72invocations, full expected signatures for overlap/correction/probes, SQL roles/counts/fetchkeys/medians,16source hashes/raw digest and actual parser/reference/upsert execution.

Deferred minor: raw fixture `active_leagues=67`/`completed_leagues=33` are inherited **pre-override base.seed facts**. The runner subsequently sets all100 leagues to In-Season, so actual measured status counts are100active/0completed. Workloads explicitly select league IDs and exclude active-league selection, so this does not affect measured counts/results. Preserve original artifact/hash; refresh/label returned fixture status metadata before future reuse. This note clarifies existing evidence without rewriting its provenance.

Live native reproduction/removal remains author-observed. Production/provider/conflicting-duplicate/broader recovery/checkpoint/routing suitability remains unclaimed. No routing change is approved by these measurements.
