# Shared Scoreboard Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans, preserving native inline execution and one fresh final review. User owns commits; do not stage/commit/push/deploy.

**Goal:** In live ingestion, share season/date/group work across leagues while preserving ordered corrections, committed partial progress and per-league outcomes.

**Architecture:** A job-local coordinator lazily resolves each league, memoizes a season/date outcome and processes unique configured groups in order. It compares each parsed event with the last successful deep-copied payload and delegates actual writes to existing ingestion helpers. Cron owns gate/date/report/log policy; existing league/season/bootstrap/refresh wrappers stay unchanged.

**Tech Stack:** Existing Python/SQLAlchemy/ESPN parser, canned fetches, guarded unittest and owned marked-local PostgreSQL17.6. No dependencies, provider traffic or migrations.

**Spec:** [Combined design](../specs/2026-11-16-mod-022-shared-scoreboard-design.md). User selected later-valid-wins/identical-skip and requested design/plan together; await combined review before product changes.

## Global Constraints

- Preserve America/Chicago today/previous-day-before03:00 selection, active-league SQL, input report order and processed/failures shapes.
- Later conflicting parsed payload wins; identical consecutive applied payload skips. Aold→Anew→Aold writes3times. Memo advances only after successful commit.
- Each actual game write retains existing mapping/phase selection/reference locks and independent commit; earlier writes survive later failure.
- Shared ordinary failures fan out without automatic same-run retry; other units continue. GateLost stops globally through outer cron handling.
- Invocation-local results/config/last-payload data only. No cross-run cache, HTTP retry/backoff, bootstrap/checkpoint/output/scheduler/SQL/index redesign.
- Full parsed metadata participates in comparison, including tournament/phase hints. No lossy persisted-field fingerprint.
- No configured DSN/app/provider; immutable historical raw evidence and verified owned resources. No production latency/quota claim.

## Review Focus

- Reverted or phase-only corrections cannot be suppressed by an ever-seen-ID/hash set or mutable payload reference.
- A failed shared unit reports failure for every matching valid league while preserving earlier commits and unrelated-season continuation.
- Invalid league metadata, changed provider identity and different season/sport/date cannot leak cached outcomes or game IDs across units.
- GateLost must bypass both metadata/unit error caching and cron per-league handlers; no unsafe exception/payload logging.
- Date/report ordering and legacy wrapper/refresh/bootstrap behavior stay intact despite shared execution and duplicate group normalization.

## Files and interfaces

- Create `api/endpoints/schedule/shared_ingestion_service.py`: `SharedScoreboardIngestionService(ingestion_service,check_gate)` with `iter_league_outcomes(league_ids,target_date)` yielding league-order dictionaries `{leagueId,date,summary,error}`. summary is None or scalar copied dictionary; error is None or original Exception, never serialized. Cron turns these into existing safe report/log entries. No default callback that silently disables gate checks.
- Coordinator private methods `_resolve_league_unit(league_id,target_date)` (same-league sport/season consistency validation and immutable config key), `_ingest_unit(context,target_date)` (ordered group fetch/parse/write summary) and `_config_for_sport(sport_id)` (once-per-invocation normalized unique groups/effective URL/keyword). Keep caches on this per-main object only. No need to change existing ingestion repository or introduce a broad public context framework.
- Consume canonical ingestion `_get_league`, `_get_sport_season_for_league`, `_get_sport_api_config`, `_new_client`, `_insert_or_update_game` with their current transaction/client behavior. Check returned season sport matches league sport before shared association. Keep effective base service.espn_base_url, not ignored baseUrlName. Freeze group list as first-occurrence ordered tuple. Empty groups succeeds with0events/writes.
- Unit key `(sportId,sportSeasonId,date,effectiveBaseUrl,apiKeyword,orderedUniqueGroups)`; group fetch once per ID in that key. A failed normal unit result is memoized; metadata failure is per league and cannot poison a different unit. Config memo populated only on successful normalization.
- Full parsed game deepcopy is captured before handing it to the writer; commit success then advances last-applied memo. Preserve raw-event count before parsing; skip None/falsey external IDs. Canonical external ID is exact str value. No mutation of provider payloads or retained reference to reusable parser dictionaries.
- Modify `api/cronJobs/cronIngestScoreboard.py`: instantiate coordinator once inside acquired gate, keep current date selection/service construction and outer safe handling. For each date, gate.check→active leagues→iterate coordinator outcomes in original order→existing report/safe_event entries. Ordinary outcome errors are reported, not raised into global failure. GateLost propagates from iterator; outer convention remains failure{leagueId:None}. Existing final gate.check retained.
- Create `api/tests/test_shared_scoreboard_ingestion.py`; update `test_operational_jobs.py` boundary mocks and add actual coordinator+cron integration tests. Keep `test_schedule_ingestion_service.py` legacy wrapper expectations intact.
- Version `scripts/modernization/measure_mod022_ingestion.py`/`tests/test_mod022_ingestion.py`; create `verify_mod022_shared_ingestion.py`, native helper tests and implementation report. Keep historical league/season measurements explicitly labelled reference paths, not relabelled new behavior.

## Task 1 — Shared coordinator with duplicate and failure contracts

**Interfaces:** Produces ordered per-league outcomes consumed by Task2; actual per-game writer remains canonical.

- [x] RED actual-coordinator tests `test_same_season_leagues_share_fetches_and_writes`, `test_later_revision_and_reversion_are_applied`, `test_phase_only_change_is_not_identical`, `test_mutable_parser_output_is_copied`, `test_failure_memo_advances_only_after_commit`. Literal fixture groups10=A,B,invalid and20=A,C with16leagues:2fetches,3writes,16successes/eventsSeen5. Aold/Anew across groups:4writes includingB/C; Aold→Anew→Aold alone:3writes/finalold. Use real ESPN extraction where payloads are complete; canned parser rows only for mutation/error boundaries.
- [x] RED scope tests `test_shared_failure_fans_out_and_other_season_continues`, `test_invalid_metadata_only_fails_that_league`, `test_sport_season_date_and_provider_keys_are_isolated`, `test_new_invocation_refetches_after_failure`, `test_duplicate_groups_normalize_in_first_order`. InputA1,B1,A2 outcomes stayA1,B1,A2; repeated group10 processed once and raw count reflects unique group response. Missing ID/invalid event counted raw but not written; empty groups0calls. Assert memoized summary copies cannot be mutated by another league consumer.
- [x] Run `python3 api/tests/run_isolated.py test_shared_scoreboard_ingestion.py`; expected RED for absent coordinator and then actual duplicate/fanout behavior, not unrelated import/setup errors.
- [x] Implement named coordinator methods above; do not switch existing wrappers to season helper. Cache only completed success/ordinary failure; compare full last-successful deep copy, not all earlier fingerprints. Explicitly rethrow GateLost before generic catches. No automatic retry/transport changes.
- [x] Add `test_gate_loss_stops_fetch_write_and_association` at each callback boundary (metadata loop/group fetch/actual upsert/cached-outcome report): earlier committed writes remain, no following work, GateLost escapes iterator. Normal provider/upsert errors are cached and fan out; original error category remains available for safe logging.
- [x] Rerun focused coordinator suite; expected PASS with exact calls/order/data. Record RED→GREEN and fixture distinctions; no configured runtime/network.

## Task 2 — Live cron integration and reporting compatibility

**Interfaces:** Consumes Task1 outcome iterator; produces existing public job report/log shapes and date/gate behavior.

- [x] RED tests around actual cron main with fake gate/service and fixed clock: `test_live_ingest_reports_shared_success_in_input_order`, `test_shared_failure_reports_all_dependents_then_continues`, `test_today_and_yesterday_are_distinct_units_before_three`, `test_busy_or_lost_gate_prevents_more_work`, `test_safe_logs_never_include_payload_or_exception_text`. Include exactly03:00 (today only) and02:59 (today then yesterday), America/Chicago dates, no inferred league-local windows.
- [x] Run `python3 api/tests/run_isolated.py test_operational_jobs.py`; expected new integration assertions RED on current per-league loop. Update only appropriate old orchestration mocks to coordinator boundary; keep real coordinator/parser tests independently.
- [x] Wire coordinator in live cron only. Preserve get_active_leagues_for_date helper, configured-engine fallback, run identity, safe_event started/completed/failed/skip, top-level exit behavior and active selection. Unit errors do not become global stop; GateLost does. No raw outcome/error object appended to public report.
- [x] Add/retain legacy service tests: season first-wins summary/fetch wrapper unchanged; league raw per-event behavior unchanged; refresh/bootstrap callers still use named legacy methods. No provider factory at import/constructor. Job test engine injection must not import runtime/configured app.
- [x] Run separately `python3 api/tests/run_isolated.py test_shared_scoreboard_ingestion.py`, `python3 api/tests/run_isolated.py test_operational_jobs.py`, `python3 api/tests/run_isolated.py test_schedule_ingestion_service.py`, then `python3 api/tests/run_isolated.py`; expected every focused/full suite PASS. Record actual counts/errors.

## Task 3 — Versioned measurement and PostgreSQL acceptance

**Interfaces:** Consumes actual Task2 cron/coordinator plus unchanged canonical parser/reference/upsert; produces deterministic count/state/failure evidence.

- [x] RED audit tests pin16same-season leagues/2groups→2logical fetches/3upserts for identical overlap, rather than32/64. Count raw eventsSeen5 per league; conflictingA/B/invalid+Anew/C gives4upserts and finalAnew. Keep legacy league/season formula helpers explicitly historical. Do not promise an unchanged exact SQL total before inventorying new metadata calls.
- [x] Test real fixture metadata refresh after status override: actual100active/0completed, inherited67/33 only under a named pre_override field. Preserve old raw data/hash. Add provider-key/error-fanout/sample-count/cleanup assertions before rerunning old helper.
- [x] Run `python3 -m unittest discover -s scripts/modernization/tests -p 'test_mod022*.py'`; expected RED on old orchestration/count/status assumptions. Version current output shared-ingestion-v2, unique IDs/new manifest and RUNNING persisted before provenance/connect; unknown SQL categories fail. Existing reference paths remain labelled and immutable.
- [x] Add `verify_mod022_shared_ingestion.py` on marked disposable PostgreSQL17.6/schema001+current integrity/timeTBD migrations. Use actual coordinator/service/parser/reference/upsert with requests.Session.request forbidden and only canned fetch overrides. Validate current pinned baseline c9f135bb372e4c84d82ec23158c9424968645159 league path from immutable source/hash or equivalent independently literal field oracle; never compute expected game rows through new dedup code.
- [x] Native workloads1/4/16same-season leagues: overlap and explicit second correction sweep. Assert exact logical fetch keys, actual upsert counts, per-league raw summaries/report ordering and complete stored fields (sport/season/phase/date/TBD/team IDs/external IDs/names/scores/broadcast). Corrections preserve within-fixture GameResult identities; do not compare generated IDs across separately seeded fixtures as business equality.
- [x] Native conflicts and phase semantics: later conflict, Aold→Anew→Aold, identical duplicate, reordered groups, duplicate configured groups, invalid/missing IDs, mapped/unmapped teams, tournament metadata-only changes, phase overrides/conference-based selection and invalid references. Prove actual per-write locks/phase lookup still execute for every nonidentical revision; skipped identical payloads intentionally retain previous mapping until a later actual write/new run.
- [x] Native failure/rerun: group20 fails after committedA/B, all associated league outcomes fail, unrelated season/date succeeds; new invocation refetches and converges toA/B/C with stable IDs. Inject per-game reference/upsert/deferred commit failure after prior success and verify committed prefix remains, failed unit not reported processed, memo not advanced, next run recovers. Do not add whole-day rollback/checkpoints or automatic transport retries.
- [x] Native multi-season/sport/date isolation plus metadata failures and controlled config change between invocations; no payload/unit cache crosses identity/run. Exercise actual cron main with injected owned engine/clock/gate where safe; distinguish a synthetic gate callback from actual advisory-gate acceptance. GateLost must stop subsequent unit actions/reporting; no misleading cached success after loss.
- [x] Run native helper(s) only on exact owned marked127.0.0.1:55439; expected PASS for full fields/identity/counts/fanout/partial progress/retry/metadata. Verify actual counters, source hashes, zero owned DBs/roles, exact container labels/no persistent mounts, then remove only that container. Preserve failure artifacts; no provider/configured Supabase services.
- [x] Run `python3 -m unittest discover -s scripts/modernization/tests -p 'test_mod0*.py'`, `python3 api/tests/run_isolated.py` and `git diff --check`; expected PASS with actual counts. No unrelated frontend/browser/index/native suites. Record timing caveats and logical fetch versus transport attempts; no production speedup claim.

## Task 4 — Review and closeout

- [x] Write `docs/modernization/mod-022-shared-scoreboard-implementation.md`/summary JSON: chosen duplicate order, config/unit snapshot, unique-group normalization/raw-count exception, full field/phase parity, shared failure fanout, gate/partial-commit limits, actual tests/counters, resource cleanup and uncommitted/undeployed status. Update roadmap/backlog without implying bootstrap/transport/retry policy is repaired.
- [x] One fresh final scoped review via executing-plans, including spec/plan/Review Focus verbatim/ledger rulings/current evidence. Regrade by effect; one material RED→GREEN fix pass/full impacted checks, no rereview. Document deferred minors and reviewer-declined areas.
- [x] Preserve user index/work; no stage/commit/push/deploy. Retain owned uncommitted ledger. Transport retry, bootstrap/checkpoint completion and SQL batching remain separate designs.

## Self-review and handoff

Spec coverage: Task1 identity/duplicate/config/ordinary failure/GateLost; Task2 actual live cron/date/order/safe reports and legacy compatibility; Task3 actual persisted fields/partial commits/phase/reference/failure/counts/resource hygiene; Task4 review/evidence/release limits. Interfaces and outcome keys match cron consumer; errors are internal only. Every Review Focus input has explicit tests. Aold→Anew→Aold and phase-only corrections cannot pass with a seen-ID/fingerprint set; group failure does not retry through the next same-season league; GateLost is never a cached ordinary failure. SQL totals await actual trace rather than reusing season helper29 indiscriminately.

Combined design/plan prepared as requested; fresh design builder check found no important unanswered questions. Native inline method remains selected. User approved combined plan; implementation/review complete. See report/ledger for evidence and deferred minor.
