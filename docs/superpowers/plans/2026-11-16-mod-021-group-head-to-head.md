# Weekly Tied-Group Head-to-Head Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans with the preserved native inline method and one fresh final review. User owns commits; do not stage/commit/push/deploy.

**Goal:** Replace per-pair H2H database reads with one raw-game/ownership statement per supplied-connection tied group, preserving static scoring results.

**Architecture:** A new schedule query returns unique eligible games and active owner sets for the requested members. The scorer reconstructs the same pair predicates and raw integer totals in memory, retaining its current group sort/fallback. No-connection pair calls and the existing rules-only context remain unchanged.

**Tech Stack:** Existing Python/SQLAlchemy/PostgreSQL17.6; guarded unit tests and owned marked-local native fixtures only.

**Spec:** [Combined design](../specs/2026-11-16-mod-021-group-head-to-head-design.md). User requested design and plan together; both await combined review before product implementation.

## Global Constraints

- One H2H statement snapshot per tied group; later groups/fallback may observe later commits. No full-run snapshot, new locks/isolation or game caching.
- Optimize only supplied-connection H2H; unchanged public weekly scorer, pair schedule API and no-conn override dispatch.
- Raw scores, inclusive original H2H dates, literal NULL start, season/sport and half-open ownership predicates remain exact. No tier/phase adjustments in H2H.
- Preserve nonrecursive H2H subties, member-ID order, adjusted largest-absolute-margin fallback, waterfall points, final guards and atomic score replacement.
- Do not change member-game SQL, rules context, ownership protocol, write batching, HTTP410, indexes/schema/scheduler/providers.
- Historical raw artifacts immutable; new RUNNING/PASS/FAILED runs, exact source hashes and verified owned UUID cleanup. No configured DSN/app/provider/browser.

## Review Focus

- Owner joins cannot multiply game contributions, and dual/overlapping owner facts preserve old boolean pair inclusion without double counting.
- NULL week starts, unmapped teams and ineligible NULL scores must not gain matches/errors through broader batch retrieval.
- Mixed H2H/fallback groups stay isolated, and partial H2H subties do not gain recursive fallback.
- New statement-snapshot semantics are per group only; retries/weeks/leagues cannot reuse stale batch rows or freeze fallback/tiers/phases.
- No-conn adapters stay compatible; changed supplied adapter contracts and historical verifier baselines are explicit and reproducible after integration.

## Files and interfaces

- `api/endpoints/schedule/read_repository.py`: add `head_to_head_games_for_members(conn,params)` with params leagueId,weekNumber,memberIds. Keep pair SQL unchanged. Target_week mirrors pair SQL; active_owners is distinct(memberId,sportTeamId) for active scoped slots. One row per eligible GameResult, with id/externalGameId/date/homeTeamId/awayTeamId/homeScore/awayScore plus distinct sorted bigint arrays homeMemberIds/awayMemberIds. Use bound `= ANY(:memberIds)` or equivalent existing binding style. Require distinct opposite-side owners; use EXISTS/array subqueries rather than multiplicative joins. No score coercion/default in SQL.
- `api/endpoints/schedule/read_service.py`: add `get_head_to_head_games_for_members(league_id,member_ids,week_number,conn)`; require non-None conn, normalize internal member IDs to distinct integers, return[] without SQL for fewer than2distinct IDs, invoke new repository exactly once and return mapped row dictionaries. No begin/connect and no changes to old pair method.
- `api/endpoints/scoring/service.py`: same `_tb_weekly_head_to_head(league_id,week_number,group,conn=None)` signature. If conn supplied, fetch group rows once and locally derive each pair's old boolean fields/predicate/totals; otherwise keep existing pair calls. Local owner sets/rows only, never context/service/connection caches. Keep integer conversion after eligible-pair selection; sort/None result unchanged. A small private pair-row iterator is allowed if needed to share existing accumulation, but no exported scoring algorithm rewrite.
- Create `api/tests/test_weekly_head_to_head_batch.py`; extend schedule/scorer tests and `test_weekly_rules_context.py`'s canned supplied read repository to return explicit batch arrays. No-conn mocks remain pair-shaped and unchanged.
- Update `scripts/modernization/measure_mod021_weekly.py`/`tests/test_mod021_weekly.py` to H2H-group-v3 counts/sequence; keep old raw reports immutable. Create `scripts/modernization/verify_mod021_head_to_head_batch.py`, helper tests and implementation report.
- Update `scripts/modernization/verify_mod021_rules_context.py` only where necessary to pin its historical revision and rerun against the new supplied H2H path; no unrelated driver refactor.

Pinned reference bytes verified during planning (before any product edits):

- `4efa908be575e2a1ad2c738bf8bb871f2d815abe` scorer SHA256: `1dac609344fd2172312ca60fab7a711225773b3537b812355b001114345a8499`.
- `49cd228ea9c05ab05894fdddeb42c25174d91f6c` scorer SHA256: `5a32ad6a4e9c2eea5266e3828213368a5eb03acec0b9b10e415636cbeada282b`.

## Task 1 — Native-query contract and schedule capability

**Interfaces:** Produces batch schedule method/row contract for Task2; existing pair API stays available for parity.

- [x] Add RED `test_group_method_uses_supplied_connection_once`, `test_small_or_duplicate_group_has_correct_empty_or_unique_scope`, `test_pair_api_contract_unchanged`. Use actual service with canned repository results; assert mapped arrays/raw fields, distinct ID params, no engine acquisition, no query for0/1distinct IDs and explicit missing-conn rejection. Pair API must still receive memberA/memberB and preserve booleans.
- [x] Run `python3 api/tests/run_isolated.py test_weekly_head_to_head_batch.py`; expected RED from missing capability. Record it before code.
- [x] Implement the service and bound SQL above. Preserve exact pair target_week/ownership/window filters and row identity; prefilter only games with a genuine distinct cross-member pair. Score/phase/tier processing remains in existing consumers.
- [x] Add SQL-capture assertions only for safety/structural constraints (bound IDs, no accidental aggregate duplication), then rely on Task3 actual PostgreSQL pair parity for semantics. Do not treat SQLite or string assertions as array/ownership proof.
- [x] Rerun focused batch test; expected Task1 PASS. Record that native SQL semantics remain pending until Task3.

## Task 2 — Scorer branch with pair-equivalent totals

**Interfaces:** Consumes Task1 rows/capability; produces one group read, identical ranking/fallback and unchanged no-conn calls.

- [x] RED actual tie-helper tests `test_supplied_tie_fetches_once_and_matches_raw_pair_totals`, `test_raw_h2h_beats_larger_adjusted_margin`, `test_all_equal_uses_existing_margin_fallback`, `test_partial_h2h_subtie_keeps_member_id_order`, `test_no_conn_still_calls_each_pair`. Derive totals from literal home/away memberships/scores, not the new helper. Include negative margins, dual-owned zero, repeated owner IDs and row qualifying through both OR branches exactly once. An ineligible row with invalid/null scores must not raise; eligible invalid scores retain rejection.
- [x] Add RED `test_two_groups_h2h_then_fallback_are_isolated`: weekly PD5,5,1,1; first group raw H2H favors1over2 despite2's larger adjusted margin; second group has no H2H and largest margin favors4over3. Expect order1,2,4,3, unchanged weekly PDs and waterfall4,3,2,1; exactly2group calls, no pair calls in supplied path. Add foreign-group rows to ensure they cannot affect totals.
- [x] Run `python3 api/tests/run_isolated.py test_weekly_head_to_head_batch.py`; expected RED from pair calls/ranking/query-count contract, not only absent imports.
- [x] Implement the supplied branch, leaving no-conn pair loop intact. Iterate existing unordered member IDs; pair inclusion is opposite-side ownership OR, not raw overlap. Deduplicate owner sets, not distinct GameResult IDs. Keep existing scoring arithmetic/order and fallback boundary. Add no rows to `_WeeklyRulesContext`.
- [x] Update only owned supplied schedule/read doubles to the batch capability. Inventory `rg -n 'get_head_to_head_games|_tb_weekly_head_to_head|compute_weekly_scores_for_job' api scripts --glob '*.py'`; document adapters/subclasses affected. No feature probing or generic TypeError fallback.
- [x] Extend fresh-call tests with same service/connection across groups/weeks/leagues and failure/retry; assert no cached batch on context/service/transaction info. Keep no-conn overrides and existing context tests unchanged in intent.
- [x] Run separately `python3 api/tests/run_isolated.py test_weekly_head_to_head_batch.py`, `python3 api/tests/run_isolated.py test_weekly_rules_context.py`, `python3 api/tests/run_isolated.py test_weekly_tiebreak_baseline.py`, then `python3 api/tests/run_isolated.py`; expected all PASS. Preserve replacement/week0/postseason/completion/calendar coverage; record actual full count.

## Task 3 — Versioned native parity, snapshot boundary and counts

**Interfaces:** Consumes actual Task2 scorer/new SQL, unchanged pair API and pinned historical source; produces current evidence and remaining limits.

- [x] Add RED audit formulas: successful supplied scoring has settings1; head_to_head_group is1 for the original all-tied fixtures and0 for unique/tier_phase; legacy head_to_head reads0. Totals at16:37unique,38H2H-decides,54fallback. At4:13/14/18; at8:21/22/30. Member-games and lock/delete/insert unchanged. Sequence includes one group read at H2H stage; add independently literal two-group trace and reject missing/duplicated/misplaced batch reads.
- [x] Run `python3 -m unittest discover -s scripts/modernization/tests -p 'test_mod021*.py'`; expected RED on current pair formulas/categories. Version helper output H2H-group-v3 with new current manifest, keeping v1/v2 raw artifacts. Classify new SQL explicitly and retain unknown-query rejection; legacy pair category remains available to parity probes.
- [x] Pin old rules verifier source to4efa908be575e2a1ad2c738bf8bb871f2d815abe; new batch verifier source to49cd228ea9c05ab05894fdddeb42c25174d91f6c. Verify each object exists/hash matches expected pre-context/pre-batch capability before native startup, with a regression test that moving HEAD cannot change the reference. No silent git-history fallback or historical artifact rewrite.
- [x] Build bounded marked-local driver with RUNNING persisted before provenance/setup, owned UUID database/drop verification and fresh source hashes. For each original5scenarios×4/8/16members, compare exact returned/stored scores with literals and pinned pre-batch scorer; assert current SQL counts/order, no extra settings/member reads/locks or connections. Retain timing caveats and no latency pass threshold.
- [x] Native pair parity: derive each batch pair's game IDs/flags/totals and compare to untouched old pair API on same stable fixture. Include home/away, half-open transfer, dual-owned, empty/no-cross-pair, foreign member/league/season/sport, week0, start/end inclusive boundaries, NULL start, unmapped teams/timeTBD. Test repeated ownership facts only in an explicitly isolated legacy fixture; preserve integrity constraints in the main fixture. Assert one row per eligible GameResult, not one row per owner join. Eligible invalid scores must fail as before; out-of-pair invalid scores must not be parsed.
- [x] Native mixed groups: literal order1,2,4,3 with first group H2H-decides, second fallback; exactly2batch reads, no cross-group contribution. Add partial H2H subtie where fallback would reverse two equal H2H members but must not run. Cross-week/league same service/connection cannot reuse group data.
- [x] Native controlled correction: after the first group fetch, a second connection commits a raw-game/ownership correction before the next group query; first group uses its fetched rows, next group/call sees the new statement view. Label this deliberate per-group snapshot change; do not compare all old interleavings or add locks/isolation. Use deterministic barriers and bounded timeouts.
- [x] Reuse/extend existing prior-score replacement and rules-context checks: failures after group retrieval, delete/insert/deferred commit or caller rollback retain exact prior/unrelated rows; retry performs a fresh batch. Rules stay captured for the call while later tier/phase/fallback reads stay live. Pin final guard/zero/future/split expectations and require0H2H reads when rejected before ties.
- [x] Run native driver(s) only on the exact task-owned cached PostgreSQL17.6 container/marked127.0.0.1:55439, not configured Supabase. Expected PASS for independent pair/score parity, current counts, atomicity and explicit snapshot boundary. Verify zero owned DBs/roles, inspect labels/no persistent mounts and remove exact task container; retain other services/cache and failed raw evidence.
- [x] Rerun `python3 -m unittest discover -s scripts/modernization/tests -p 'test_mod0*.py'`, `python3 api/tests/run_isolated.py`, current source-hash/case/count checks and `git diff --check`; expected all PASS. No frontend/browser/unrelated index or provider tests.

## Task 4 — Review and closeout

- [x] Write `docs/modernization/mod-021-head-to-head-batch-implementation.md` and summary JSON: before/after actual counts, full parity, snapshot/adapter/non-goal limits, repaired previous minor notes, failures/cleanup, uncommitted/undeployed status. Update MOD021 roadmap/backlog without claiming all game batching or full consistency complete.
- [x] One fresh final scoped review via executing-plans, with spec/plan/Review Focus verbatim/ledger rulings/native evidence. Regrade by effect; one material RED→GREEN fix pass plus impacted/full checks, no rereview; document deferred minors and declined scopes.
- [x] Preserve user staging/changes, no integration/deployment. Retain uncommitted ledger; report remaining separate member-game batching/full-snapshot decisions.

## Self-review and handoff

Coverage: Task1 API/SQL boundary; Task2 exact raw pair algorithm/no-conn/mixed-group compatibility; Task3 native parity/snapshot/retry/counts and reproducible references; Task4 review/evidence. Review Focus inputs have explicit owning tests. Group method/row names match every consumer. Scalar rules context is not broadened, no-conn does not get the batch requirement, NULL-start semantics stay distinct from member-game COALESCE behavior, and one statement per group is explicitly a new snapshot boundary. No production gain or full MOD021 completion claim.

User approved combined design/plan; native implementation/review completed. Deferred minor: mixed-group full literal statement trace remains a follow-up; actual query counts and single-group traces pass. See implementation report/ledger for evidence and limits.
