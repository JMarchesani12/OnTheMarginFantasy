# MOD021 — weekly head-to-head reads per tied group

## Intent and proposed approach

The rules-context tranche is complete. The next bounded change replaces pairwise database reads inside one weekly tied group with one raw-game/ownership query for that group, on the existing supplied connection. Keep the pair scoring algorithm, fallback, rules context and write transaction intact. The user requested design and implementation plan together; both documents are proposals for combined review before product implementation.

Author recommendation: one query per tied group, returning each eligible game once plus its active home/away owner IDs restricted to the tied members. Alternatives: (1) aggregate all pair totals in SQL, reducing Python work too but changing more of the tie algorithm/join multiplicity; (2) preload every member's adjusted games/tiers/phases, broader than the remaining pair-query bottleneck and a larger snapshot change. Defer both. Continue native inline implementation with one final review; user owns commits/integration.

## Current policy and scope

`apply_weekly_tiebreakers` partitions already ordered members by equal weekly pointDifferential. `_tb_weekly_head_to_head` queries every unordered member pair in each group. It adds raw homeScore-awayScore for each owned home side and the opposite for each owned away side. If all H2H totals are equal, it returns None and biggest-absolute-adjusted-margin fallback runs. Otherwise it sorts the whole group by H2H total descending/member ID, without recursively resolving any remaining H2H subtie. Keep this exact behavior.

Optimize only this H2H helper when conn is supplied, including direct supplied-connection tie-helper calls. No-conn/direct pair APIs keep current dispatch and result shapes; no new batch capability is required of their existing adapters. Production weekly completion/calendar maintenance already supply conn. Do not pass new keywords to no-conn subclass overrides. Supplied adapters need the new named group capability and should fail explicitly if absent, not silently revert through introspection/TypeError catches.

No change to member differential game SQL, tier/phase rules, existing per-call rules context, fallback rereads, HTTP scoring410, final-period guards, ownership mutex, late Week lock, replacement/rollback/commit ownership or season standings.

## Batch query contract

Add a new schedule repository query and supplied-connection service method. Keep existing `head_to_head_games` and `get_head_to_head_games` unchanged for pair callers. The group method takes league ID, week number and distinct integer member IDs and requires a non-None connection. Fewer than2distinct IDs returns an empty result without querying or opening a transaction.

Use the existing pair query's target_week semantics verbatim: Week league/number → League sport/year → matching SportSeason; literal w.startDate/w.endDate, inclusive BETWEEN, existing LIMIT1. In particular, a NULL start yields no H2H rows; do not import member_games' COALESCE seven-day fallback. Preserve no timeTBD filter and no phase/tier adjustments.

An active_owners CTE restricts LeagueTeamSlot to this league, provided members and acquiredWeek<=weekNumber with droppedWeek NULL or >weekNumber. Deduplicate member/team facts to preserve old IN/boolean semantics when source rows repeat. Per GameResult, emit distinct sorted homeMemberIds/awayMemberIds arrays, raw homeScore/awayScore and identifying fields (id,externalGameId,date,homeTeamId,awayTeamId). Keep each GameResult row exactly once; never multiply rows by owner joins or collapse distinct games sharing scores. Require an opposite-side owner pair with distinct members before returning a game. Bind IDs/values; no value interpolation.

Filter GameResult by the same sport, sportSeasonId, inclusive dates and opposite-side ownership existence as the old pair query. Order by date/externalGameId as before. Do not add a new index, date normalization, NULL-score default, team-name resolution or current-ownership lookup. Empty/nonmatching/foreign league-season games stay absent. Negative/malformed/null score behavior must remain consistent: only games eligible for an actual pair reach int(score), and eligible invalid scores still fail rather than silently becoming zero.

## Pair calculation and duplicate/dual ownership

The scorer receives raw rows and builds home/away owner sets once per row. It iterates the same unordered member pairs as before. A row belongs to pair(A,B) exactly when `(A in home and B in away) or (A in away and B in home)`. Include it once even if both branches are true. For each member, add raw diff if it owns home and subtract if it owns away. A member owning both sides contributes0. Games with no cross-member pair contribute nothing; don't parse their scores accidentally.

Do not apply tier/phase-adjusted memberPointDiff to H2H or change H2H precedence. Retain integer accumulation, whole-group sort, no recursive subties, and None on all-equal totals. Python pair enumeration may remain quadratic; this batch removes database round trips, not that CPU complexity. Avoid a new exported algorithm/pure-helper framework unless a small local function is necessary for meaningful tests.

## Explicit snapshot and concurrency policy

This is a deliberate H2H statement snapshot per tied group: all pair comparisons in that group use one query's view of raw game/ownership/week/season facts. Under READ COMMITTED, later groups and fallback member-game reads may see later committed corrections, as existing separate statements can. Do not share rows across groups, weeks, calls, retries or leagues; the rules context remains rules-only and must not become a game cache.

This changes the old possibility of different pair statements seeing different corrections within the same group. It does not make the whole scoring call consistent or historical. No new isolation/locks, earlier Week lock or database-wide snapshot. A full consistent scoring snapshot remains separate policy work. Document/test this boundary rather than claiming concurrent results equal every old possible interleaving.

## Expected measured outcome

Current rules-context-v2 16member counts:37untied,157H2H-decides,173fallback. For one16member tie group,120pair queries become1batch query, giving38H2H-decides and54fallback; untied remains37. For multiple tied groups, one query per group of size>=2, none for singleton groups. Member-game, settings, lock/delete/insert counts stay unchanged. No latency/production speedup promise; capture real counts and reasonable local timings without a latency pass threshold.

## Verification and deferred-note repair within scope

- Actual scorer RED→GREEN must show one group call replaces pair calls and identical literal scores/order, raw H2H beats adjusted fallback, all-equal H2H triggers unchanged fallback, residual H2H subties retain member-ID order, and no-conn pair dispatch stays unchanged.
- Add the previously deferred combined case: one group H2H-decides and another falls back in the same scoring call; assert exactly2batch reads, unchanged within/between-group ranking and no rows from other groups. Test same service/connection across leagues/weeks/retry to catch cache leakage.
- Native SQL: compare each pair's eligibility/booleans/totals with the untouched pair API across orientations, half-open transfers, dual ownership, empty/no cross-pair, duplicate owner facts where an isolated legacy fixture permits them, NULL start, week boundaries, timeTBD, foreign season/sport and null/unmapped teams. Current integrity constraints must remain intact on the main fixture; any relaxed legacy-only fixture is labelled separately.
- Preserve existing week0/final-period, raw H2H/nonrecursive ties, rules-context/live tier-phase, scoring replacement and weekly completion/calendar tests. Preexisting scores and unrelated league/week rows remain exact on success/failure/caller rollback/deferred commit; failure does not cache a group result for retry.
- Native parity against a pinned pre-batch scorer revision, current literal oracles and unchanged pair repository API. Run the existing5scenarios×4/8/16 with explicit count-v3 categories/sequence and new unique artifacts. Keep historical v1/v2 raw outcomes immutable.
- Repair the verifier's previously deferred HEAD-relative historical reference while touching this evidence path: pin the recorded pre-context4efa908be575e2a1ad2c738bf8bb871f2d815abe in the rules-context verifier; use separate pinned pre-batch49cd228ea9c05ab05894fdddeb42c25174d91f6c for new H2H parity. Check availability/hash before services, never silently choose HEAD; historical artifacts unchanged.
- Controlled native correction after first group query proves the first group retains its statement rows and a subsequent group/call can see the correction. No claim of full concurrent snapshot equivalence.

## Release limits and builder discretion

Design/plan only this turn, no product change. Builder chooses CTE layout, bounded fixture sizes and test arrangement subject to exact semantics. Keep scope to one schedule query/service capability, scorer branch, tests/evidence and relevant verifier repair. No all-game batching, member-game cache, insert batching, ownership/transaction redesign, migration/scheduler/real provider or deployment. External Python adapter compatibility and production workloads remain unverified until their own acceptance.

Status: proposed combined design/plan, fresh builder check returned “nothing important left”; implementation plan self-reviewed. User approved combined design/plan; implementation and scoped review completed with evidence/limitations recorded separately.
