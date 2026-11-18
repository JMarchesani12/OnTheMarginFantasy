# MOD020 read-triggered lifecycle baseline — 2026-11-15

Audit only; actual optimizations remain deferred until audit completion. No application query/status policy/index/scoping/job/deployment change. [Current manifest](evidence/mod-020-lifecycle-current-2026-11-15.json) points to [raw evidence](evidence/mod-020-lifecycle-e8c0ffc2c8894873b6671cef89b36d4d.json). Prior uncommitted ingestion work is preserved.

## Actual boundary and fixture

Run actual LeagueReadService.details_for_reader_id and mine_for_user_id with actual LeagueLifecycleService.synchronize_for_job as callback. Synchronization commits five global UPDATE statements before the scoped SELECT. Native PostgreSQL17.6/schema001 + exact MOD006/008/010; no provider/app runtime/HTTP/job dispatcher/RLS platform invoked.

Four direct service calls: authorized league1 detail (member user2), league1 detail with absent reader, missing-target detail, sparse own-league list for user2 (only league1). These exercise repository reader predicates. **HTTP access/preview checks can reject earlier and are not measured.** Denied/missing direct-service probes do not prove unauthenticated HTTP mutation or an exposed authorization bypass. Route source is recorded for context; it is not executed here.

Three database tiers100/1000/5000 leagues with original8members/13weeks,9600/96000/480000 scores and16k/160k/800k ownership histories. Ten equal groups use(id−1)%10, all UTC. Season dates are relative to observed database day ±30/90days; years2025past/2026current/2027future, year1800missing. Dates are deliberately far from boundaries; no timezone/day-boundary correctness claim. Raw facts label inherited base seed status counts as pre-override; actual prepared initial/final status counts are recorded separately.

| Group | Draft / season | Prepared dirty status | Final status |
| ---: | --- | --- | --- |
|0|none/current|In-Season|Pre-Draft|
|1|live/current|Pre-Draft|Drafting|
|2|paused/current|Pre-Draft|Drafting|
|3|complete/future|Pre-Draft|Post-Draft|
|4|complete/current|Pre-Draft|In-Season|
|5|complete/past|In-Season|Completed|
|6|live/past|Completed|Completed, via Drafting|
|7|none/current|Completed|Completed|
|8|complete/current|In-Season|In-Season|
|9|none/missing|Post-Draft|Pre-Draft|

Dirty mode restores this source-state mix before each call. Steady mode first converges outside measurement. Both set updatedAt to a fixed epoch before measurement so changed timestamp IDs are unambiguous. Setup/convergence/reset/snapshots are excluded from timers/counters; resetting all rows still affects physical layout/cache. This is a controlled read-trigger baseline, not an estimate of production league mix or ongoing write/WAL/vacuum costs.

## Statements and rows updated

Twenty-four size/call/mode records, one warmup+five samples each =144 service invocations. Every invocation has exactly one callback, five UPDATEs and one SELECT. SQL hooks record each phase's cursor.rowcount and fail on unknown categories. Full final all-league statuses, exact timestamp-touched IDs and final status-changed IDs are independently checked. Returned data checks a selected business projection, not the full l.* API contract; projection omits volatile updatedAt while timestamp identity is checked separately. Denied/missing projections are empty, detail/mine each contain one resource.

Letg=N/10. Dirty phase rows(pre,drafting,post,in-season,completed)=(2g,3g,g,g,2g); steady=(0,g,0,0,g).

| Leagues | Dirty summed UPDATE rows | Dirty distinct timestamp changes | Dirty final status changes | Steady summed UPDATE rows | Steady distinct timestamp changes | Steady final status changes |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
|100|90|80|70|20|10|0|
|1,000|900|800|700|200|100|0|
|5,000|4,500|4,000|3,500|1,000|500|0|

These counts are identical across all four direct call types. Group6 is status-convergent but not write-quiescent: mark_drafting changes an ended-season Completed league with a live draft to Drafting; the last mark_completed changes it back. Two matched UPDATE rows per league per callback, one distinct timestamp-touched league, unchanged final status. At5,000leagues this group has500leagues and incurs1,000updates every measured steady call, even though a sparse reader returns only league1. Steady touched IDs7,17,... are unrelated to that target. This is a measured existing behavior, not a new bugfix or proposal to change completed-season policy.

## Instrumented client medians (ms)

| Leagues | Authorized detail dirty total / callback | Authorized detail steady total / callback | Sparse own-league dirty total / callback | Sparse own-league steady total / callback |
| ---: | ---: | ---: | ---: | ---: |
|100|4.123 /2.966|3.555 /2.517|5.093 /2.595|4.949 /2.514|
|1,000|9.549 /8.517|6.530 /5.346|18.933 /5.382|17.912 /4.262|
|5,000|34.035 /32.905|16.280 /15.278|62.882 /25.782|53.315 /17.040|

At5,000leagues denied direct-detail totals35.966ms dirty/19.316ms steady; missing-target29.845/17.845ms. All still trigger global work before their scoped query. Full distributions/captured SQL and14 input hashes retained. Total timing includes actual synchronization transaction/commit and read acquisition/fetch/mapping plus instrumentation overhead; callback interval covers synchronization only. Independent medians must not be subtracted to infer precise read overhead. No EXPLAIN of writes, lock contention/concurrent readers/cold-cache/production latency/statistical confidence claim. Earlier own-league aggregate query work remains relevant separately.

## Audit conclusion

MOD020 now has measured global UPDATE scope/count and a concrete repeated-write case in a converged visible state. Later design should preserve agreed visible lifecycle transitions/completed-season precedence while separating ordinary scoped reads from global writes, and account for ended-season live-draft churn. No scoped transition/job boundary/policy correction/index/query/tuning change was implemented or compared here. Full lifecycle concurrency and deployment timing still need a separate design/validation; no speedup is claimed.

## Verification and cleanup

Five initial tests failed before runner creation. A sixth RED test pins resource signature counting for None/detail/list projections rather than dictionary-key counts. All46 measurement tests pass. Three native tiers/24records/144calls pass callback/statement/phase counts, full final status maps, changed ID sets, selected reader projections, five samples/medians/classified SQL and14 source hashes. Warmup also verifies all invariants. No native failure occurred in this batch; failure-aware RUNNING/PASS/FAILED artifacts and owned UUID cleanup reused.

Zero task databases observed, exact labeled loopback container removed, no persistent mounts, remaining lifecycle taskcontainers0. Docker/image cache retained. No configured DSN/provider/app/HTTP/jobs used. Work uncommitted/undeployed. [Closeout evidence](evidence/mod-020-lifecycle-summary-2026-11-15.json).

Unmeasured: production schema/roles/RLS/traffic/status mix, concurrent transitions/locks/WAL/maintenance, timezone/season boundary cases beyond this fixture, HTTP prechecks and full returned contract. Actual optimization implementation remains deferred; MOD020 implementation and remaining audit work stay open.

Independent final review: Critical0/Important0/Minor1. Reviewer passed46units and independently simulated sequential lifecycle predicates, verifying24records/144invocations (120saved timing samples), all final-state/touched/status-changed signatures and phase/prepared-state counts, selected projections, medians,14source hashes/raw digest and report limits. Deferred minor: runner asserts statement counts but not an explicit execution sequence. Current service source/captured ordering confirms synchronization precedes SELECT; future denied/missing probes could miss a reordering regression. Add a sequence assertion before future reuse. Current baseline remains valid.

Live native reproduction/removal/zero-database observations and historical RED remain author evidence. Production authorization/concurrency/timezone-boundary/optimization policy remain unclaimed. Prior MOD022 work was outside this review.
