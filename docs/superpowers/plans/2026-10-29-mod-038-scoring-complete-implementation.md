# MOD-038 Remaining Scoring Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline with test-first changes and one independent final review.

**Goal:** Extract all remaining scoring persistence/calculation/standings/bonus responsibilities, preserve legacy helper overrides and wire jobs directly to services.

**Architecture:** ScoringService owns use cases, transactions and policy, with injected schedule read port. ScoringRepository owns named supplied-connection queries. Pure bonus-award math moves to rules.py. ScoringModel inherits the service as a compatibility facade so existing subclasses/monkeypatches still dispatch to overridden helpers without a service-to-model import. HTTP season reads require UserActor. Weekly/finalization jobs construct ScoringService, never HTTP adapters.

**Tech Stack:** Existing Python/Flask/SQLAlchemy/dataclasses, unittest, marked disposable PostgreSQL; no dependencies.

**Spec:** [Approved MOD-038 architecture](../specs/2026-10-29-mod-038-layering-design.md), explicitly extended to the rest of scoring by the user's request.

## Constraints and review focus

- Preserve scoring formula, waterfall assignment, weekly/season tiebreak ordering, bonus ties/positions and legacy helper overrides/constants/signatures.
- Preserve week-zero, split/future final-period guards and MOD-007 atomic score replacement: compute before write, delete+all inserts in one service transaction.
- Preserve season read pre/post authorization and concealed 404; no new user/job flags.
- Keep schedule/provider reads outside score replacement transaction. Repository owns no connections/commits; service imports no Flask/configured engine/model facade.
- Keep job completion/locking/finalization state transitions and recovery behavior unchanged; MOD-013/014 remain separate. No new schema, isolation, rate limiter, deployment, dependencies or listener startup.
- Do not claim old tests prove PostgreSQL row/result access or new SQL extraction; add native branch coverage.

## Task 1: Core service, rules and persistence

Files: extend scoring service.py/repository.py/contracts.py; create rules.py and tests/test_scoring_service.py; replace scoringModel with compatibility facade.

Interfaces: ScoringService(engine,schedule_model,repository=None); explicit `compute_weekly_scores_for_job(league_id,week_number)`, `get_season_standings(actor,league_id)`, `get_season_standings_for_job(league_id)`, `get_season_standings_for_legacy_reader(user_id,league_id)`. Existing helper names remain on service/facade, dynamic self dispatch retained. ScoringRejected derives from ValueError for compatible domain failure handling. Repository query methods use supplied conn + named data arguments, materialize rows inside scope; all existing SQL/predicates unchanged. Pure bonus functions accept computed member facts/config and return award mappings.

- [x] Write direct-service regressions for weekly rules, week zero, atomic replacement/failure, actor-required season reads, bonuses and season tiebreaks, and facade helper overrides. Run red before core extraction.
- [x] Move SQL to named repository queries and bonus math to pure functions. Keep calculation/helper read connection scopes as service-owned scopes; do not silently coalesce all queries or change isolation.
- [x] Retain score replacement helper signatures and compatibility facade methods/constants; no service-to-model dependency.
- [x] Run all backend tests, keeping existing valid behavior tests unchanged except intentional job composition fixtures.

## Task 2: HTTP and job callers

- [x] Wire season HTTP reads directly to actor service; weekly HTTP scoring remains disabled. Remove no security boundary.
- [x] Weekly/final scoreboard builders return services directly; keep their existing scheduling, completion and error/recovery operations unchanged.
- [x] Update operational tests' injected builder values for the explicit service job interface; add isolated builder/main coverage without importing configured DB/app or starting jobs.

## Task 3: Native SQL, review and evidence

- [x] Native PostgreSQL fixtures cover atomic replacement statement/commit rollback, repeat convergence, week/final guards, standings with every bonus family and season tiebreak query family, week/history scoping and actor revocation.
- [x] Preserve existing read pilot by rerunning its native checks in separate fixture state. Validate actual SQLAlchemy Row access; fix demonstrated compatibility defects with a failing regression and record separately from content moves.
- [x] Verify guarded imports/caller maps, no SQL in model/service, repository no engine/commit, no service-to-model/Flask dependencies.
- [x] One independent final reviewer checks SQL/rules preservation, transaction scope, compatibility hooks, HTTP/jobs and tests. Fix important findings with failing regressions first.
- [x] Record actual results and outstanding limits; remove task-owned synthetic DB/container. Leave current checkout uncommitted with prior work preserved.

## Execution ledger

- Ruling: Inheritance is limited to the domain's legacy model facade — existing subclasses override scoring helpers used by atomicity/week/final tests — avoids hidden callback plumbing or importing a model back into services. No generic base repository/controller is introduced.
- Ruling: Preserve established helper read scopes rather than coalesce all calculation reads — this is extraction, not a snapshot/isolation redesign — only score replacement is promised atomic.

- Baseline guarded backend 396/396 passes. Core/rules/actor tests first failed on missing ScoringService, then passed. SQL extraction retains original literal queries, predicates, parameters and execution order; identical queries consolidated into named repository methods.
- Weekly write remains delete+all inserts in one service transaction after schedule/metadata reads; existing helper override tests continue through the inheritance facade. Bonus award loops are pure functions and preserve tie positions/zero exclusions.
- Ruling: Correct demonstrated SQLAlchemy Row access incompatibility separately from extraction — actual Row objects raise TypeError for string subscripts — three real-Row regressions RED→GREEN cover depth/latest-week metadata using _mapping; formulas are unchanged.
- Job builder tests failed against endpoint construction, then passed with direct ScoringService factories. Weekly/final main functions call explicit service job methods; only the existing operational fixture builder return shape changed. Completion/recovery/state SQL is otherwise unchanged.
- Full guarded backend 406/406 passes. Independent final reviewer found no Critical/Important/Minor issues, independently ran 10 new tests, compared original/repository SQL, and confirmed pure bonus/tie dispatch preservation.
- Native PostgreSQL PASS: prior weekly-read checks rerun; all bonus/tiebreak query families, primary phase filtering, empty-phase facts, native row access, actual atomic replacement statement/commit rollback, repeat convergence/week zero, actor/revocation and split/future final-period guards. Schedule reads are injected domain facts, not live provider tests.
- New full-scoring evidence supersedes earlier scoring-read source hashes; older evidence retained as history. MOD-013/014 completion/failure/recovery and MOD-034 startup remain separate outstanding work.
- Approved sandbox escalation used local cached-image/task-owned loopback container only; harness removed random database and container otm-mod038-scoring-full-20261029 was stopped/removed. No hosted DB, existing-container mutation, schema migration, dependency, listener or deployment.
- Changes remain uncommitted in current checkout; no frontend files/checks changed. Service/rules/model SQL-free and repository engine/commit-free dependency inspections pass.
