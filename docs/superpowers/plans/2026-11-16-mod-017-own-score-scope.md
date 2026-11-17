# Own-League Scoped Score Aggregation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans; preserved native inline method, one fresh final review. User owns commits; no staging/push/deploy.

**Goal:** Aggregate only scores for the user's eligible memberships without changing own-list results.
**Architecture:** Add an EXISTS user/stage/optional-ID semijoin inside the current score aggregation; keep outer query and services intact.
**Tech Stack:** Existing Python/SQLAlchemy/PostgreSQL17.6 and guarded unittest/native synthetic tools.
**Spec:** [Design](../specs/2026-11-16-mod-017-own-score-scope-design.md).

## Global Constraints

No index/schema/pagination/cache/API/lifecycle/transaction/score-policy changes. Preserve all fields/types/order/duplicates, week0, existing Week join and NULL/COALESCE semantics. No configured DSN/provider. Historical raw immutable; new failure-aware evidence only. Native resources task-owned marked loopback, exact cleanup. No production speedup claim.

## Review Focus

- Zero sums and missing/null sums retain different fallback behavior, including week0 and negative-week exclusion.
- User/member/league/stage/optional-ID predicates must all agree without multiplying scores through eligibility joins.
- Current-week NULLs, interval fallback and overlapping row multiplicity stay unchanged.
- Sparse/absent aggregation scope improves without an unexplained hot-user regression or mislabeled global scan cost.
- Existing refreshed-set coordinator cannot regain unrefreshed/newly joined leagues through the query rewrite.

## Task 1 — RED semantics and score-scope tests

**Files:** create `api/tests/test_own_league_score_scope.py`; retain `test_own_league_listing.py`, `test_league_details_service.py`, `test_league_lifecycle_queries.py`.
**Interfaces:** consumes actual LeagueReadRepository.own_leagues(conn,user_id,stage,league_ids=None), unchanged signature.

- [x] Add literal result tests: scored0 overrides member total99; no scores uses99; both missing/null falls back0; week0 adds, negative week excluded; other member/league scores excluded; all/active/completed/unknown stages; None/empty/nonempty optional IDs; commissioner without membership absent. Check exact fields/order and overlapping/missing current-week rows using current adapters, adapting SQLAlchemy expanding params honestly where needed.
- [x] Add actual-SQL capture regression requiring user/member/league/stage/optional scope inside score aggregation before GROUP BY, not just outer filtering. Unit result parity alone already passes before the performance fix. Assert bound values rather than literal user/ID interpolation.
- [x] Run `python3 api/tests/run_isolated.py test_own_league_score_scope.py`; expected semantic controls PASS and new aggregation-scope assertion RED on current global subquery. Record actual output.

## Task 2 — Minimal repository rewrite

**Modify:** `api/endpoints/league/reads/repository.py` own_leagues only.
**Interfaces:** consumes Task1 contract; produces unchanged rows with scoped SUM input.

- [x] Add EXISTS against score_member/score_league: score_member.userId=:user_id, score_member.id=wts.memberId and score_member.leagueId=wts.leagueId; same stage predicate and optional bound scope_ids as outer query. Keep existing SUM, Week join, GROUP BY and outer projection/joins/order intact. Construct scope predicates from local aliases only; no user values interpolated. Reuse one expanding ID bind for both occurrences.
- [x] Include duplicate membership/legacy score-reference edge controls only where fixture constraints permit them. Do not add extra Week.leagueId equality or move COALESCE into SUM.
- [x] Run focused score-scope test, then `python3 api/tests/run_isolated.py`; expected full PASS, including routed listings/read authorization/scoped lifecycle coordinator. Record current count; no frontend change/tests.

## Task 3 — Native equivalence and bounded work comparison

**Create:** `scripts/modernization/verify_mod017_own_score_scope.py`, targeted audit tests, implementation report/evidence. Reuse measure_mod017 schema/seed/owned_database utilities, not its fixed-name main/run output.

- [x] Before edits capture immutable pre-rewrite repository revision/source hash (planning baseline7d6cde8467d490dc9a94c6f434acb10ac761d9da). Verified planning source SHA256 `509efe07fd1c05916b7a775abe7ef378a5c95e622db96e2af23e53c373165df4`; require that hash before native DB creation. Load only trusted repository code, no app/runtime; never follow HEAD after integration. Record reference hash and current source hashes.
- [x] Unit-test new runner failure manifest/provenance guard and expected scope/result comparison; RUNNING must replace stale PASS before provenance/connect, cleanup must precede PASS. Capture SQLAlchemy expanding binds using actual compiled/executed SQL, not invalid POSTCOMPILE placeholders.
- [x] Native small semantic fixture compares complete ordered rows to pinned old query on same connection/transaction. Cover literal point/null/week0/negative-week/member/stage cases, optional scope including empty, absent user/commissioner-only, missing/overlapping current-week rows, and unchanged foreign-week join behavior where allowed. New/old values/types/order/multiplicity must match exactly; independently check literal totals, not only mutual equivalence.
- [x] Measure100/1000/5000leagues with existing fixed fixture, hot user1/sparse2/absent plus all/active/completed and supplied scopes for hot full-candidate IDs, sparse singleton and empty. Assert empty scope makes0SQL calls (no EXPLAIN), not a false unscoped plan. One warmup+5samples of old/new reads; record full result fingerprints/counts and EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON), settings and bindings. No EXPLAIN of writes/no index creation.
- [x] Independently count eligible score rows before grouping using user/member/league/stage/scope+existing Week join. Inspect aggregation inputs, scanned rows, buffers and timing separately; report any remaining whole-table scan rather than presenting logical filtering as avoided I/O. Sparse/absent must stop globally grouping unrelated scores. Investigate material hot-user regressions; if unresolved, keep evidence and report instead of silently shipping/adding indexes or planner overrides.
- [x] Run new driver against task-owned marked PostgreSQL17.6/schema001+current integrity migrations on127.0.0.1:55439 only. Expected exact ordered-row parity, scoped aggregation evidence, owned UUID DB removal and unique current artifact. Verify actual case/sample/hash counts and remove exact labeled temporary container, preserving other services/cache and historical raw.
- [x] Run `python3 -m unittest discover -s scripts/modernization/tests -p 'test_mod0*.py'`, `python3 api/tests/run_isolated.py`, `git diff --check`; expected PASS. No redundant unrelated audit/native/browser/provider runs.

## Task 4 — Scoped review and closeout

- [x] Write `docs/modernization/mod-017-own-score-scope-implementation.md`/summary: exact query change, full parity/counts/plans, scoped grouping versus residual scans, hot/sparse tradeoffs, test results, cleanup, uncommitted/undeployed and production limits. Update roadmap/backlog; index selection remains separate.
- [x] One fresh final review with spec/plan/Review Focus/ledger rulings/evidence. Regrade by effect; one material RED→GREEN fix pass/full impacted tests, no rereview; record minors/declined scopes.
- [x] Preserve user index/work and uncommitted ledger. No commit/push/deploy/SQL rollout.

## Self-review

Task1 pins semantic and actual-scope regression; Task2 preserves the public repository/service boundary; Task3 proves PostgreSQL rows/plans and truthful work claims; Task4 owns review/evidence. Review Focus inputs each have tests/inspection above. No implicit lifecycle, authorization or data repair change. Unknown-stage/empty-ID behavior remains existing behavior. No extra Week-league predicate, null-sum default, distinct outer rows or pagination.

User approved combined plan; native implementation and final review completed. Evidence/rulings/tradeoffs are recorded in report and ledger.
