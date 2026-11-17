# MOD017 own-league score scope — 2026-11-16

The score subquery now uses an EXISTS semijoin against LeagueMember/League to restrict SUM input by user, matching league/member pair, stage and optional supplied league IDs. Outer projection/joins/order, Week-id-only join/weekNumber>=0, NULL handling and COALESCE remain unchanged. EXISTS avoids eligibility-row multiplication. Empty supplied list still returns[] without SQL; None remains unrestricted membership scope. No API/pagination/cache/lifecycle/transaction/index/schema change.

## Verification

Actual SQLite query tests first reproduced the missing inner scope while semantic controls passed.4focused tests and full guarded backend827/827 pass. Audit helpers60/60 pass, including failure-manifest protection and strict output-type comparison. Existing routed own-list/auth and scoped-lifecycle integration remain green.

[Current manifest](evidence/mod-017-own-scope-current-2026-11-16.json) points to [native PASS](evidence/mod-017-own-scope-6841f069396249aaa3f2859566314d66.json): actual PostgreSQL17.6/schema001+MOD006/008/010 at100/1000/5000leagues,39old/new comparison records,6alternating iterations per variant (one warmup+5saved samples),72EXPLAIN ANALYZE/BUFFERS plans; empty scopes produce no SQL/plan.12current source hashes match. PostgreSQL settings recorded; no planner override/index introduced. Previous successful preliminary artifact1f4d96e5a7384309a56425b913ef9255 is preserved; final run adds strict types/settings provenance.

A separate72case minimal semantic fixture verifies all/active/completed/unknown stages, hot/sparse/absent users, None/empty/nonempty IDs, point0 versus missing/null fallback, week0/negative exclusion, commissioner-only omission and overlapping/missing current weeks. A further foreign-week control preserves the old Week-id-only join rather than silently repairing data. Full fields/types/key-order/multiplicity match repository code pinned to7d6cde8467d490dc9a94c6f434acb10ac761d9da/SHA509efe07fd1c05916b7a775abe7ef378a5c95e622db96e2af23e53c373165df4. This semantic fixture is deliberately separate from baseline integrity/performance fixtures.

SQL orders only leagueId/draftOrder. The verifier checks that exact ordered key sequence and compares all rows/types as multisets within equal-key groups; it does not invent a currentWeekId tie-breaker. In this run even the raw observed row sequences match in all72cases. Invalid legacy duplicate membership is characterized by the unit fixture; real primary-key constraints remain intact.

## Measured work and tradeoffs

At5000leagues, sparse user2/all: old aggregation input480,000scores versus new12; new plan reads12scores through existing WeeklyTeamScore_identity_key. Median full repository read36.44→3.28ms in this local warm fixture. Sparse supplied-ID lookup was already scoped by its league predicate: old96scores/new12, medians0.77→0.74ms.

Hot user1/all: aggregation input480,000→60,000eligible scores, median87.55→69.73ms. **Both hot plans still scan480,000scores**; scoped grouping is not eliminated global I/O. Hot supplied5000IDs median92.88→90.81ms. No material unexplained hot regression found across the three sizes.

Absent/all at5000leagues skips score execution in both plans; median1.41→2.04ms shows extra planning/query-shape overhead. These synthetic alternating warm samples are not statistical confidence or production latency promises. Timings include fetch/mapping and SQL parsing/planning; EXPLAIN adds overhead separately. Parallel aggregate child rows are reported as actual rows×loops, with rounding tolerance; scanned/grouped rows and buffers remain separately captured. Underlying global score/ownership index decisions remain separate.

## Cleanup and limits

New failure-aware runner uses existing schema/seed/marked-loopback/UUID utilities, never the oldest fixed-output main. Historical raw artifacts untouched. Owned database count0 inspected; exact task container886d47ef6aac0370f9a9549fca895c79a3c4cb8c7d6d7115098cb865a89bf847 labels/127.0.0.1:55439/no persistent mounts verified. Exact container removed, remaining task containers0; other services/Docker/cache retained. No configured DB/app/provider/browser/production RLS or workload acceptance. Work uncommitted/undeployed; fresh final review found no critical/important/minor issues.

Final reviewer independently passed4score-scope/8lifecycle/3audit tests, verified12current source hashes,39comparisons/72plans/72semantic cases and correct performance limits. Reviewer declined fresh native/resource cleanup, production RLS/workload performance and index selection; author observed native/cleanup, other scopes unclaimed. Rulings retained the authorized checkout/uncommitted ledger and compared complete typed rows within equal SQL sort-key groups; no undocumented tie order or production performance guarantee is introduced.
