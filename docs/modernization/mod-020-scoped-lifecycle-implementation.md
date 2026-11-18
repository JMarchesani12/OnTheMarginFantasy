# MOD020 authorized scoped lifecycle refresh — 2026-11-16

Full-detail and own-league HTTP requests now use an explicit `LeagueLifecycleQueryService`: verified actor → authorized candidates → sorted DraftState/League locks → fresh authorization → five scoped phases → scoped SELECT → commit. Ordinary `LeagueReadService` detail/list methods are read-only and no longer accept a synchronization callback. Public previews, search, rules, conferences and member reads do not acquire lifecycle writes. The explicit trusted global synchronizer remains available without scheduler registration.

Detail refresh covers exactly one authorized commissioner/member league. Own-list refresh covers membership candidates before stage filtering; commissioner-only nonmember leagues remain absent. Final listing is restricted to discovered/refreshed IDs, so concurrent new memberships appear on a later request. Revoked candidates are skipped. All refresh/read work shares one READ COMMITTED transaction and result delivery follows commit. Existing-state draft locks precede League; a newly appearing first DraftState causes whole-transaction rollback/retry once, then a safe409 resource_conflict envelope. Other failures do not auto-retry.

## Policy preserved

Five existing predicates/order and league-local transaction-time calendar rules are unchanged. In particular, a scoped ended-season Completed/live-draft row may still perform Drafting→Completed intermediate writes. This batch removes unrelated work; it does not eliminate every repeated UPDATE or establish background freshness. Transaction-time `now()` remains fixed at transaction start, including a lock wait across a calendar boundary. No index/schema/scheduler/scoring/ingestion/frontend change.

## Verification

- Actual-reader/supplied-connection tests first failed for missing callback-free APIs; scoped coordinator/SQL tests first failed for missing scoped operations. Routed tests reproduced old global-callback wiring. Full guarded backend now793/793; audit helpers54/54. Existing lifecycle/timezone/full-projection/authorization/identity tests remain green.
- [Current manifest](evidence/mod-020-scoped-current-2026-11-16.json) points to [native PASS](evidence/mod-020-scoped-1520c12ec3934eda8565c166807fcf3a.json):100league ten-group fixture on actual PostgreSQL17.6/schema001+MOD006/008/010,16 matching source hashes.
- Eight unadapted measurement cases (detail/denied/missing/mine × dirty/steady), each one warmup+five saved samples: explicit statement sequence, exact all-league status/touched-ID sets and phase counts verified. Sparse dirty detail/mine each update1target row rather than90global matched rows at100leagues; steady each matches0updates rather than20global matched rows in historical baseline. Denied/missing cases issue0updates. These synthetic counts are not production latency/speedup claims.
-34equivalence cases across dirty/steady detail groups, commissioner-only detail, denied/missing and own-list stage filters compare every returned field against the explicit existing global-policy reference. A common fixed `now()` literal gives both sides identical timestamps; other predicates remain actual SQL. Separate unadapted cases above retain real PostgreSQL now(). Exact untouched-row/status/timestamp checks cover unrelated dirty leagues. Own-list scope includes all ten policy groups, including existing ended-season churn.
-7post-phase/read/deferred-commit failures restore the whole previous state; fresh retries succeed. Native lock timeout and restricted-role permission failures propagate without committed changes. Temporary owned role removed.
-5two-connection interleavings observe actual PostgreSQL blocking: existing-state start, finalization, absent-state first start (2attempts), entitlement removal while waiting, and join after discovery (new league excluded). These use actual control/member repository locks and simulated draft/membership writes, not full start/pick/member-removal workflow acceptance. No deadlock in these bounded cases; arbitrary external writers bypassing application locks are outside the contract.
-5controlled UTC/local boundary/null-status cases verify unchanged actual date predicates. Null-status characterization relaxes NOT NULL only in the owned disposable fixture; deployed baseline forbids null status. A prior driver run failed on that fixture constraint, with verified database cleanup; [failed artifact](evidence/mod-020-scoped-cadc086fdb5949a682345e413de8a3b7.json) is preserved. Boundary instants are adapted, not a real-midnight wait or full wall-clock/AT/production claim.

## Internal signature migration

Removed callback arguments from `details`, `details_for_reader_id`, `details_for_job`, `mine` and `mine_for_user_id`; `mine`'s second argument is now stage. New supplied-connection reader methods let the coordinator own the transaction. Repo-local HTTP, unit tests, `verify_league_details.py`, `verify_league_lifecycle.py` and MOD020 measurement helper explicitly select read-only/coordinator/trusted global operations. Obsolete callback use is rejected, not silently executed. External Python consumers are not known; integration should review these internal signature changes. HTTP paths, successful fields/statuses and preview concealment remain unchanged.

The measurement runner is explicitly versioned authorized-scoped-v2 with new current manifest/date, strict sequence assertions and historical global formulas retained as reference. Old raw baseline artifacts are immutable. Canned projection-only route fixtures substitute orchestration only; coordinator policy/SQL/native behavior are tested independently.

## Cleanup and limits

Native runs verified owned UUID database removal; admin inspection found0task databases and0temporary roles. Exact container label/port/mount verification: taskmod020-scoped,synthetictrue,127.0.0.1:55439,no persistent mounts; exact owned container removed; remaining task containers0. No configured Supabase services, provider/app/browser or deployed privileges used. Docker/image cache retained.

No production performance/role/RLS/scheduler/background freshness or full end-to-end concurrent draft workflow guarantee. No commits/push/deploy. Fresh scoped review found no critical/important findings and passed8 lifecycle-query tests, checked whitespace and all16 current source hashes. No material fix pass needed.

## Deferred review notes and rulings

Minor follow-ups: preview/denial tests should explicitly assert the new coordinator is not called (current routes are correctly gated); the older `verify_league_lifecycle.py` return description still says global read-time writes rather than explicit trusted synchronization. Deferred to the next related test/verifier change.

Reviewer did not reproduce live native execution/resource state, production behavior/privileges, full concurrent draft workflows or real midnight delay. Author observed native execution and exact resource cleanup; controlled boundary cases do not claim real delayed-midnight behavior. Commissioner change while waiting lacks a dedicated native case; fresh authorization SQL after League lock was reviewed, and this remains a coverage limitation.

Implementation rulings: reused authorized checkout/uncommitted ledger (integration remains user-owned); corrected multi-pattern runner invocation to its actual single-pattern interface and full-suite counts (no invented aggregate); preserved existing safe API error envelope for409 rather than bypassing middleware; relaxed NOT NULL only in the disposable legacy boundary case; repository-level concurrency simulations prove lock protocol but leave full workflow acceptance separate. No production speedup or deployed safety claim follows from these local checks.
