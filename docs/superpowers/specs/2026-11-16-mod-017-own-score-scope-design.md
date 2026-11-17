# MOD017 — scope own-league score aggregation

## Change

The own-league query currently aggregates WeeklyTeamScore across all leagues before joining the requested user's memberships. Filter score rows to the requested user's eligible league/member pairs before SUM/GROUP BY. Preserve the outer SELECT/joins/projection/order and optional refreshed-league scope. This is a small query-only change; combined design/plan prepared as requested, no product implementation yet.

Recommended approach: an EXISTS semijoin inside the score subquery against LeagueMember+League, restricted by user, stage and optional league_ids. This avoids multiplying scores and retains the existing outer result shape. An eligible-members CTE could express the same filter but would touch more of the outer query; per-member lateral sums may amplify hot-user probes. Do not add indexes before comparing the bounded rewrite.

## Contract

- Keep actual membership as eligibility; commissioner-only access does not create a listing row. Both user ID and league/member pair must match, including the optional supplied league_ids restriction.
- Apply all/active/completed stage semantics to both scopes. Unknown stage remains current unfiltered behavior; normalization stays in the service. None league_ids means unrestricted membership scope, empty list returns[] without SQL, nonempty scope intersects eligible memberships.
- Preserve every returned field, types, row multiplicity and ORDER BY league ID/draftOrder. Preserve nullable current-week context, interval fallback and existing duplicates when multiple current weeks match; do not “fix” them here.
- Keep existing WeeklyTeamScore→Week join by weekId with weekNumber>=0, including week0. Do not add extra Week.leagueId predicates, change NULL SUM handling or move COALESCE: scored sum0 overrides persisted totals; no/nonvalued sum falls back to member.seasonPoints then0.
- Do not broaden authorization, replace complete lists with pagination, cache results, change lifecycle coordinator/locks/transactions, or change score writes. One SQL statement retains existing statement-snapshot behavior.
- Duplicate eligibility rows must not multiply score sums; EXISTS is intentional. No new persistent table/index/schema/rollout.

## Proof and scope

Unit/route tests pin fields and literal totals for score0/no scores/null fallback, week0/negative weeks, hot/sparse/absent users, stages and optional scopes. Native PostgreSQL compares complete ordered rows against repository source pinned before the rewrite, using the same transaction-time now() for both. Include overlapping/missing current-week matches and foreign member/league/week score fixtures where current constraints permit them, without silently repairing data semantics.

At100/1000/5000synthetic leagues, measure hot/sparse/absent, stages and optional hot full-candidate/sparse/empty scopes with exact result equivalence and EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON). Check score rows reaching aggregation are eligible; distinguish scanned rows from grouped rows and report residual full scans honestly. Require no material unexplained hot-user regression before declaring the rewrite ready. No production speedup claim, planner-setting override or automatic extra index to force a result.

Use a new failure-aware runner rather than the oldest fixed-name MOD017 main. Reuse only marked loopback/UUID/schema/seed utilities. Preserve frozen November11/raw history, emit new RUNNING/PASS/FAILED artifact/source hashes and verify exact cleanup. Current backend/audit suites plus one final scoped review; no frontend/provider/browser rerun.

Production workload/RLS/catalog/timing remains separate. Supported-index comparisons follow stabilized query shapes. User owns commits/integration, native inline workflow preserved. Status: combined design/plan approved; implementation and review completed with evidence and tradeoffs recorded separately.
