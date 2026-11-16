# MOD021 weekly scoring orchestration baseline — 2026-11-15

Audit measurements only; all actual optimizations remain deferred until audit completion. No application SQL/scoring/rules/index/tuning/batching/deployment change. [Current manifest](evidence/mod-021-weekly-current-2026-11-15.json) points to [successful raw evidence](evidence/mod-021-weekly-e42e1abadead4b60aaf0cc17501e938e.json). Previous uncommitted H2H/stored-score work is preserved.

## Actual path and fixture

Run ScoringService.compute_weekly_scores_for_job with actual ScheduleReadService, calendar/read/scoring repositories and v1 tier/tournament rules. No schedule/repository result substitution. Supply a real caller connection; lock week, delete prior scores and insert every member score. Check returned scores and stored member/differential/rank/points against independent expectations, then roll back and verify target league has zero score rows. No job dispatcher, provider, lifecycle/finalization, HTTP/auth or production database is invoked.

Use marked-loopback PostgreSQL17.6/schema001 + exact MOD006/008/010 + timeTBD migration. Each tier reuses100 background leagues/16,000 ownership histories/9,600 stored scores and32 sport teams, adding league101 with4/8/16 members, one closed week and one team per member. Member1 also owns an extra team, opponent32 is unowned in the target league. Member IDs1001 onward and new users are isolated from background IDs. Sport1/basketball v1, UTC,32teams; no hard league-size limit or realistic production distribution is inferred.

Five independently expected scenarios:

| Case | Differential/order expected |
| --- | --- |
|unique|N..1, member order ascending|
|unresolved|All5; H2H and largest margin tied, member-ID order retained|
|head_decides|All5 after outside-game offsets; raw H2H1 beats2 by7, order1,3..N,2|
|margin|All5 from margins(m+5) and(-m); no H2H result, largest absolute margin gives descending member order|
|tier_phase|Raw4k versus lower-tier opponent → favored margin2k →1.5 tournament multiplier3k; negative game clips to0|

Every case contains a double-owned game contributing zero and both home/away owned-side orientations. All returned team names/differentials/order/ranks/waterfall points and persisted score values are checked. Unresolved equal members still receive distinct rank/points N..1, preserving current rules; no split/recursive tie redesign. Tier/phase case exercises actual favored tier reduction, positive-only clipping and phase multiplier; it does not exhaust every tier/postseason/final-period rule.

Each of15 size/case records has one warmup+five measured invocations:90 successful executions. Warmup is also score/count/rollback checked. Each invocation performs real writes, then rolls back; target league starts with no stored scores. This is not a new proof of replacement of existing scores, committed transaction cost, durability or concurrent-lock correctness. Sequences/WAL/dead-tuple/cache effects can persist inside the owned database even after logical rollback. All databases/container are subsequently removed.

## Query growth

SQLAlchemy cursor hooks observe actual statements only during the scorer call, fail on unknown categories and compare role counts to independent formulas. Fixture setup, result-verification SELECTs, transaction begin/rollback and zero-score checks are excluded. Representative synthetic SQL/parameters and per-role cursor timings retained. No EXPLAIN of write operations or index experiment; earlier isolated query-plan reports remain relevant.

Let N be members and P=N(N−1)/2. Untied cases have one week read, one member read, N league/settings reads, N member-game reads, one lock, one delete and N inserts: **4+3N** statements. A tied group reads every member pair: +P. If H2H cannot distinguish any member, largest-margin fallback repeats league/settings and member-game reads: +2N. No tie optimization occurred.

| Members | Unique / tier-phase | H2H decides | Unresolved / margin fallback | Pairwise H2H reads in tied cases |
| ---: | ---: | ---: | ---: | ---: |
|4|16|22|30|6|
|8|28|56|72|28|
|16|52|172|204|120|

At16 members the unresolved path contains186 ordinary SELECTs, one week lock, one DELETE and16 INSERTs. Even empty pair results still require120 H2H queries. Statement totals are per invocation, not counts across five timing samples. Waterfall writes grow linearly; pairwise reads explain quadratic tied-group growth in this fixture.

## Instrumented service medians (ms)

| Members | Unique | Unresolved | H2H decides | Margin fallback | Tier/phase |
| ---: | ---: | ---: | ---: | ---: | ---: |
|4|12.52|29.00|20.61|24.73|8.89|
|8|17.92|95.63|74.18|97.86|18.36|
|16|32.67|282.00|277.16|296.82|33.10|

Service timer includes Python rules/ties/fetch/mapping, SQL execution and instrumentation overhead; excludes verification/setup/rollback/commit. Cursor intervals exclude fetching and include some hook bookkeeping, so they are not server execution times and should not be subtracted/added as independent latency components. Synthetic local loopback, warm fixed-order samples, no statistical confidence/production latency/cold-cache/write-concurrency claim. Exact sample distributions/settings are in raw evidence; game counts differ between scenarios, so do not attribute every timing difference solely to statement counts.

## Audit conclusion

MOD021 now has a real orchestration query-count baseline supporting later batching/context-sharing design: repeated immutable league/rule reads, fallback game rereads, and per-pair H2H retrieval are concrete work to evaluate. This is evidence for a later design, not authorization for a scoring rewrite or proof of a specific speedup. Any future batching must preserve raw H2H precedence, adjusted-margin fallback, retained IDs, tier/phase/double-ownership behavior and the caller transaction. No index/query/cache/batching implementation or alternative algorithm was tested here.

Full season standings/bonus/tiebreak/final-period/finalization pipelines, zero/future/split final periods, cross-league context reuse, realistic schedules/skew and ingestion remain separate. MOD021 optimization and broader remaining audit cards are open.

## Verification and cleanup

Five initial tests failed before runner creation. First native attempt reached a phase-fixture JSON colon/SQLAlchemy-bind parsing error; sixth regression failed before replacing the literal with jsonb_build_object. [Failed artifact](evidence/mod-021-weekly-66642d05495e4be181aad1799aeacb51.json) records FAILED/verified cleanup; successful run uses a distinct ID. All35 measurement tests pass. Author independently checked15records/90invocations, complete score signatures/query formulas, five samples/medians, SQL category examples and17 provenance hashes. Source/code gates verify stored-row equality and rollback after each invocation.

Zero task databases observed; exact labeled loopback container removed, no persistent mounts, remaining weekly taskcontainers0. Docker/image cache retained. No configured DSN/app/provider/job orchestration accessed. Work uncommitted/undeployed. [Closeout evidence](evidence/mod-021-weekly-summary-2026-11-15.json).

Production/RLS/platform/schema-role equivalence, concurrent lock/WAL/write/vacuum costs, physical cache state, null score inputs, other sports and unmeasured scoring cases remain unknown. Actual performance implementation remains deferred until audit completion.

Independent final review: Critical0/Important0/Minor0. Reviewer passed35 units/diff check, independently checked15records/90recorded invocations/75timing samples/score signatures/query counts/medians/categories/17source hashes/raw digest, and confirmed actual services/rules, fixture expectations and rollback/listener-removal gates. Native reproduction/removal and historical RED remain author-observed; no commit/durability/concurrency/existing-score replacement/full-season/finalization/ingestion/production/optimization benefit claim is established.
