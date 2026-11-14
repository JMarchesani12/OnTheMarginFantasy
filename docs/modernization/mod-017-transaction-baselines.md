# MOD017 transaction-read baseline — 2026-11-13

This continues the isolated MOD017 investigation, with no production SQL/index changes or rollout. [Current-run manifest](evidence/mod-017-transactions-current-2026-11-13.json) points to the uniquely named raw artifact and its explicit status; [raw plans/samples/catalogs](evidence/mod-017-transactions-753a49d7e8d84dd88ff3f0d04b4af13b.json) preserve this successful run. Previous own-league/ownership evidence and runner remain unchanged.

## Fixture/method

Same cached PostgreSQL17.6 image and fixed marked loopback isolation as the first baseline. Reuse schema001+MOD006/008/010 and deterministic100/1000/5000-league fixture. Add100 transactions and10 votes per league:10,000/100,000/500,000 transactions and1,000/10,000/50,000 votes. Only event100 in every tenth league is PENDING_APPLY:10/100/500 rows, **0.1% pending density**. Nineteen proposed events per league; among trade events,9 proposed plus one pending in the selected tenth league. Arrays hold one team per side, matching the current single-swap form; timestamps are unique within each league. All weeks are marked scoring-complete, isolating pending candidates without a week backlog. This includes a bulk Week update; physical layout/visibility/autovacuum are not controlled production facts.

Capture actual SQL/params from TransactionRepository.list_transactions, TransactionWorkflowRepository.open_trades and WeeklyCompletionRepository.candidates. Cover allowed/denied/missing scopes, all/pending/proposed/absent status, participant/other-member reads and weekly candidates. Keep joins, JSON expansion/aggregation, authorization, ordering and UNION unchanged. Unique fixture timestamps avoid testing the open-trade query's missing tie-breaker; single-element arrays avoid asserting a general unordered-aggregate order contract.

Same warm-up, one EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON) and5 execute/fetch samples per case/configuration. **99 results** satisfy built-in expected counts/sample counts and baseline fingerprints. Canonical JSON size is a result proxy; execute/fetch and server profiling are separate, neither is endpoint latency. No forced plans, cold-cache, concurrency or ongoing write-cost claim.

## Measured medians (client execute/fetch ms)

| Transactions | List all: baseline → time-cover | List pending: baseline → partial | Weekly candidates: baseline → partial |
| ---: | ---: | ---: | ---: |
|10,000|2.290 →1.991|1.122 →0.741|0.833 →0.447|
|100,000|5.313 →3.441|3.988 →0.973|4.731 →1.363|
|500,000|12.055 →2.059|11.936 →0.789|19.574 →3.338|

At500,000 transactions, the `(leagueId,status,createdAt DESC,id DESC)` alternative yields2.462ms for all-status lists and0.875ms for pending lists; `(leagueId,createdAt DESC,id DESC) INCLUDE(status)` yields2.059ms and0.706ms. The small single-run differences do not justify adding both. Full candidates are29,483,008/29,417,472bytes (about28MiB), roughly34% of baseline total Transaction relation86,450,176bytes; measured builds142/97ms on this warm local fixture, not production build predictions.

Partial `(leagueId,id) WHERE status='PENDING_APPLY'` is32,768bytes at500 pending rows and builds in22ms here. Largest pending list server profile11.146ms→0.077ms, shared hits8,877→23; weekly candidates16.730ms→1.715ms, hits10,198→1,431. The remaining Week branch still scans its fixture pages despite producing no candidates. Dense-pending/backlogged-week effects are unmeasured.

Open trades remain expensive: baseline medians186/163/233ms across tiers; status-time candidate186/172/169ms. The recorded plans show substantial JIT compilation (e.g. candidate largest169.989ms JIT vs171.371ms server execution). Parallel-plan JIT timing can aggregate workers and exceed wall time, so do not subtract it as an exact cost. Reducing scanned rows alone does not reliably solve this query. Production JIT settings, cardinalities and prepared-plan behavior are unknown; no tuning/query rewrite was performed.

## Supported next decisions

- Support a separate deployment-informed partial pending-index evaluation for low pending density. This is not evidence of benefit at high pending density or with a large unscored-week backlog.
- A full league-led transaction index supports further evaluation for larger history lists. Status-first and time-first alternatives trade filtered-status lookup against all-status ordering; choose using real workload mix, existing deployed definitions and write/storage cost. Do not add both from these measurements.
- Investigate open-trade plan/JIT/aggregation cost separately before claiming index-only resolution. No behavior, pagination, ordering or server setting change is authorized by this report.

## Reliability/verification/limits

New runner writes a unique artifact and RUNNING manifest before provenance reads or connecting, then explicit PASS/FAILED and per-owned-database cleanup status. Prior successes are preserved. Expected query counts and5 samples are enforced inside the runner, addressing the first runner's two hardening gaps for this new batch only. The old runner remains unchanged with its recorded limits.

Ten combined runner tests pass, including unmarked/unowned refusal from prior tests, exact authorization capture, wrong-count refusal, connection/tier failure status and prior-artifact preservation. All three native tiers pass; all99 outputs/counts/samples independently checked. No configured app/job/provider/DSN/metadata connection, RLS/role equivalence, live traffic, HTTP latency or write/WAL/vacuum/concurrency claim. These remain synthetic two-family-plus-transaction baselines, not full MOD017 closure; games/team/conference/scorer families remain open. Work uncommitted/undeployed.

Final review found one Important reporting gap: source provenance was initially read beforeRUNNING persistence. A missing-source regression reproduced stalePASS, then the fixed runner passed all10 tests and a second complete native run (99records/3tiers), with current provenance/counts/SQL/params/fingerprints verified by the author. No post-fix independent re-review claimed. The first successful artifact remains preserved for history; the manifest/report point to the fixed-run artifact.

Deferred minor: the tier-failure unit patches out run_tier, so it does not exercise removed/still-present/unavailable cleanup-verification branches. Normal native cleanup is observed; no injected-native-failure proof is claimed. Production/live/density/cache/write-cost/role/RLS and actual rollout remain outside review.

Cleanup verified by author: zero MOD017 databases, exact owned-container labels/no persistent mounts checked, container removed, remaining task containers0. Docker/image cache retained. [Closeout evidence/decisions](evidence/mod-017-transactions-summary-2026-11-13.json).
