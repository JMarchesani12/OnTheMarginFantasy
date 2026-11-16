# Weekly Scoring Rules Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans with the preserved native inline workflow and one fresh final review. User owns commits/integration; do not stage/commit/push/deploy.

**Goal:** Resolve league rules once per supplied-connection weekly scoring call without changing score outputs or other data-read semantics.

**Architecture:** A private immutable context carries one defensive resolved-rules copy and its league/week/connection identity. The scorer creates it after existing guards, passes it explicitly through member and fallback calculations, and never retains it. ScheduleReadService supplies a named same-connection rule-resolution capability; existing game SQL and no-conn dispatch remain unchanged.

**Tech Stack:** Existing Python/SQLAlchemy, guarded unittest suites and marked disposable PostgreSQL17.6. No dependencies or real provider requests.

**Spec:** [Approved design](../specs/2026-11-16-mod-021-weekly-rules-context-design.md), user approved2026-11-16.

## Global Constraints

- Optimize only `compute_weekly_scores_for_job(...,conn=conn)`; preserve its public signature/return and no-conn behavior.
- Context lifetime is one scoring call, not one transaction, service, week batch or league cache.
- No new isolation/locks, H2H/game batching, game-result reuse, SQL/projection/index/schema changes or HTTP scoring enablement.
- Preserve raw H2H precedence, nonrecursive tie ordering, largest absolute adjusted margin, member-ID order, waterfall points and ownership/tier/phase rules.
- Preserve current guard/error ordering, caller connection, ownership mutex, late Week lock, delete/insert scope and rollback/commit ownership.
- Rules alone are captured. Games/ownership/tiers/phases and schedule SQL league context keep their current statement semantics; do not imply a full input snapshot.
- No configured DSN/app/provider/browser. Native checks use exact owned marked-loopback resources, UUID databases, failure-aware evidence and verified cleanup. Historical raw artifacts immutable.

## Review Focus

- A context from another call/league/week/connection cannot silently affect scoring, including retry on the same service/connection.
- Frozen rules hold during the call while tier/phase facts remain live; tests must not silently establish a full snapshot or change locking.
- No-conn overrides and direct schedule/tie helpers preserve default behavior; unsupported supplied-connection adapters are not hidden by fallback introspection.
- Rejected final periods/empty rosters preserve error precedence and cause no rule reads or partial score replacement.
- Mixed tie groups, ownership transfers, unranked/dual-owned/postseason games and preexisting scores retain exact returned/stored results; old audit count assertions are explicitly versioned.

## File responsibilities and interfaces

- Create `api/endpoints/scoring/weekly_context.py`: private frozen `_WeeklyRulesContext(league_id:int,week_number:int,conn:object,rules:Mapping[str,Any])`. Freeze a defensive copy of the current scalar rule mapping. `require_match(league_id,week_number,conn)->None` rejects mismatches by exact connection identity before I/O. This is internal; callers cannot supply it to the public weekly scorer. No module/instance/transaction cache.
- Modify `api/endpoints/schedule/read_service.py`: `resolve_member_game_rules_for_scoring(league_id:int,conn)->dict` requires non-None supplied connection, uses existing `_get_league(...,conn=conn)` and `resolve_rules`, opens no transaction and has existing missing-league/rules errors. Keep ordinary `get_member_games_for_week` defaults and SQL untouched. Its existing resolved_rules parameter accepts the read-only mapping without mutation.
- Modify `api/endpoints/scoring/service.py`: `_create_weekly_rules_context(league_id,week_number,conn)->_WeeklyRulesContext`; `_get_weekly_member_games(league_id,member_id,week_number,conn=None,*,scoring_context=None)->list[dict]` validates matching context then forwards existing schedule arguments plus resolved_rules only when present. Use it from member differential and biggest-margin fallback.
- Add optional keyword-only `scoring_context=None` after existing conn parameters on `compute_member_point_diff_for_week`, `apply_weekly_tiebreakers`, `_resolve_weekly_ties`, `_tb_weekly_biggest_single_margin`. Propagate it only when non-None. `_tb_weekly_head_to_head` and its calls remain unchanged; do not pass new keywords to no-conn overrides.
- `compute_weekly_scores_for_job` creates one context after week/final guards and nonempty members, before member iteration, only if conn is supplied. Existing lock/replacement code stays in place. No context retained after return/failure.
- Tests: create `api/tests/test_weekly_rules_context.py`; extend existing supplied-connection atomicity, schedule/scoring/tie/postseason/completion/calendar tests only as needed. Known no-conn overrides in `test_scoring_week_zero.py`, `test_scoring_service.py`, `verify_mod008.py` and `verify_scoring_complete.py` must not need a new context capability. Supplied-connection schedule stub in `test_weekly_score_atomicity.py` needs an explicit rule-resolution capability/complete fixture, not a production bypass.
- Measurement/evidence: update `scripts/modernization/measure_mod021_weekly.py` and `scripts/modernization/tests/test_mod021_weekly.py`; create `scripts/modernization/verify_mod021_rules_context.py`, targeted helper tests and implementation report. Confirm filenames before edits; record a ledger ruling if current names differ.

## Task 1 — Immutable context and supplied-connection rules capability

**Interfaces:** Produces context/match check and schedule resolver for Task2.

- [x] Write `test_schedule_resolver_reuses_supplied_connection_and_current_rules`, `test_context_defensive_copy_and_mutation_rejection`, `test_context_mismatch_rejected_before_io`, `test_resolver_missing_league_or_invalid_version_propagates`. Use actual resolve_rules/service with canned repository rows. Assert no engine connect/begin, expected literal rule values from a known fixture, caller mapping mutation isolation, attempted assignment failure and mismatches for league/week/connection. Do not compute expected values through the new context/resolver.
- [x] Run `python3 api/tests/run_isolated.py test_weekly_rules_context.py`; expected RED for absent behavior/capability, not unrelated fixture errors.
- [x] Implement the context and named resolver as specified above. Keep rules mapping immutable and local; identity tokens are validation only, never a cache key. Add no dynamic feature detection or global cache.
- [x] Rerun the same focused command; expected all Task1 tests PASS. Record command/output and RED→GREEN before wiring the scorer.

## Task 2 — One context through the weekly member/fallback flow

**Interfaces:** Consumes Task1 resolver/context; produces unchanged scorer results with exactly1rules resolution for supplied calls and0new resolutions on rejected/no-conn paths.

- [x] Add RED tests `test_supplied_week_uses_one_rules_resolution_for_all_members_and_fallback`, `test_h2h_retains_raw_precedence_without_extra_rules_reads`, `test_same_service_connection_new_week_league_and_retry_get_fresh_context`, `test_guards_and_empty_roster_precede_context_creation`, `test_no_conn_overrides_and_direct_helpers_keep_old_dispatch`. Exercise actual scorer/tie code; canned external schedule rows must distinguish rules versions, member differences and fallback so ignored/misrouted context fails observable score assertions.
- [x] Run `python3 api/tests/run_isolated.py test_weekly_rules_context.py`; expected RED from repeated rule reads/current missing propagation. Require an actual repeated-resolution failure as well as missing-method tests.
- [x] Implement factory/member-game helper/optional keyword propagation and call-local creation. Validation belongs before schedule I/O. Do not resolve again on fallback or send context to raw H2H. Do not add helper keywords when context is absent.
- [x] Migrate owned supplied-connection stubs/fixtures explicitly. Inventory `rg -n 'compute_weekly_scores_for_job|compute_member_point_diff_for_week|apply_weekly_tiebreakers|get_member_games_for_week' api scripts --glob '*.py'` and record affected adapters/overrides. Public signatures and no-conn verification helpers remain compatible; unknown external overrides are an integration limitation.
- [x] Add/retain `test_existing_score_replacement_and_caller_rollback_with_context`, `test_rule_resolution_failure_leaves_old_scores`, and retry after second-insert failure. Assert same supplied connection at every read/write, exact old rows restored after failure, no cross-league/week replacement, no service/engine/transaction-info context retention. Extend `test_weekly_score_atomicity.py` with complete supplied fixtures; preserve existing literal row expectations.
- [x] Run focused context, atomicity and tie suites as separate commands (isolated runner accepts one pattern): `python3 api/tests/run_isolated.py test_weekly_rules_context.py`, then `python3 api/tests/run_isolated.py test_weekly_score_atomicity.py`, then `python3 api/tests/run_isolated.py test_weekly_tiebreak_baseline.py`. Expected each PASS, with no network/configured DB.
- [x] Run `python3 api/tests/run_isolated.py`; expected full backend PASS, including week0/postseason/weekly completion/calendar maintenance/schedule rules. Record actual test count and every failure before proceeding.

## Task 3 — Versioned query-count evidence and native equivalence

**Interfaces:** Consumes actual Task2 scorer and unchanged schedule SQL. Produces current rules-context-v2 count/equivalence evidence; frozen baseline remains historical.

- [x] Add RED audit tests pinning exactly1settings read for successful supplied calls, unchanged member_games/H2H/lock/delete/insert counts, and total37/157/173 at16members (untied/H2H/fallback). Retain old formulas under an explicitly historical name if needed; never relabel old raw outcomes as current. Add tests that reordered/missing rule-resolution traces or a reused context across calls fail current validation.
- [x] Run `python3 -m unittest discover -s scripts/modernization/tests -p 'test_mod021*.py'`; expected RED on current N/2N settings formulas.
- [x] Update helper `expected_counts(n,scenario)` to settings1, keep other counts unchanged. Label new reports `rules-context-v2`; retain unique run IDs/RUNNING before provenance or connecting, exact source hashes, unknown-query rejection, failure cleanup and new current manifest date2026-11-16. Old November15 artifacts/manifests remain historical. No full snapshot/performance claim in report scope.
- [x] Implement `verify_mod021_rules_context.py` using existing marked-host/port/UUID ownership guards and native small fixture utilities. Compare5scenarios×sizes4/8/16: exact independently expected returned scores and stored rows, one settings read, current statement counts and no extra locks/connections. Preserve query-role timing caveats; do not require a latency improvement to pass.
- [x] Native prior-score tests: seed an existing exact week score set plus unrelated league/week rows. Prove successful replacement equality, failure after delete/each insertion/commit or caller rollback restores all previous rows, then retry succeeds and resolves fresh rules. Test context creation failure before replacement. Record whether durable commit or caller rollback was exercised; do not infer one from the other.
- [x] Native semantic extensions: mixed tie groups with raw H2H versus adjusted fallback, historical ownership transfer at half-open week boundary, dual-owned zero, basketball unranked fallback, phase positive-only/multiplier, cross-league and cross-week runs on same connection/service, week0 and final zero/split/future periods. Use independent literal expectations/historical reference; keep algorithm outputs exact and do not use the new context to generate its own oracle.
- [x] Native mutable-input boundary: coordinate two connections with barriers, update a valid rule source after context resolution before later member reads; current call keeps old definition and next invocation reads the new one. Use owned direct SQL only where normal API disallows rule-version edits; disclose the simulated mutation. Separately change tier/phase facts between member queries and verify unchanged live-read behavior. Do not add product/fixture locks that silently prevent the mutation, change isolation or assert a full snapshot. Use bounded timeouts; no real provider.
- [x] Run the native driver on task-owned marked loopback PostgreSQL17.6. Expected PASS for literal score/stored equivalence, current query formulas, atomic replacement/retry and explicit snapshot boundary; exact owned DB cleanup verified. Inspect exact container ID/labels/loopback/no persistent mounts, then remove only that container. Docker/cache/other services retained. Preserve any failed-run artifacts.
- [x] Run `python3 -m unittest discover -s scripts/modernization/tests -p 'test_mod0*.py'` and `python3 api/tests/run_isolated.py`; expected all PASS. Independently verify current hashes, case/sample counts, scope formulas, cleanup and `git diff --check`; no frontend/browser/database benchmark expansion.

## Task 4 — Scoped review and closeout

- [x] Write `docs/modernization/mod-021-weekly-rules-context-implementation.md` plus closeout JSON: actual test/case counts, before/after settings/total statements, preserved H2H/game costs, adapter inventory, rules-only/no-conn/full-snapshot limits, cleanup, uncommitted/undeployed status. Update MOD021 roadmap/backlog finding status without claiming all batching work complete or rewriting raw baseline history.
- [x] One fresh final scoped review via executing-plans; provide spec/plan, Review Focus verbatim, ledger rulings and current evidence. Regrade findings by practical effect; one material RED→GREEN fix pass plus affected/full tests, no rereview. Record deferred minors/declined areas explicitly.
- [x] Leave user changes/index intact, no stage/commit/push/deploy. Keep the owned ledger while uncommitted. Report completion evidence and remaining separate H2H/game batching design.

## Self-review and handoff

Spec coverage: Task1 immutability/capability; Task2 lifetime/guards/propagation/compatibility/atomicity; Task3 exact scores/counts and mutable-input boundary/native cleanup; Task4 evidence/review/release limits. Interfaces match across tasks; context is not a public scorer parameter. Review Focus inputs have owning tests above. No hidden no-conn refactor, direct raw H2H adjustment, cached fallback games, isolation/lock change or broadened scoring policy. Expected fallback total is5+3N+P; at16 it is173, not a claim to remove120pair reads.

Plan self-reviewed against approved design. Native inline method remains selected. User approved the plan; implementation and review completed. Evidence/rulings/deferred coverage are recorded in the implementation report and owned ledger.
