# MOD-038 Weekly Points Read Plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-first changes and one independent final review.

**Goal:** Extract the weekly-points read from the large scoring model while preserving its HTTP, trusted-call and late-revocation contracts.

**Architecture:** ScoringReadService owns actor authorization, week-list normalization and one read connection; ScoringRepository owns the existing expanding-list SQL and connection-scoped access queries. ScoringModel keeps a compatibility delegate. Only the HTTP points branch calls the new actor service; season standings/calculation remain unchanged.

**Tech Stack:** Existing Flask, SQLAlchemy, UserActor, unittest and disposable PostgreSQL; no dependencies.

**Spec:** [Approved MOD-038 architecture](../specs/2026-10-29-mod-038-layering-design.md) and user's instruction to continue the next chunk.

## Constraints and review focus

- Preserve current checkout user-domain work and all earlier pilots.
- Preserve endpoint payload (including original requested weekNumbers), row fields/order, int/deduplicate/sort/nonnegative normalization and trusted empty-week outcomes.
- Authorization precedes normalization/query and rechecks before returning, including empty/all-negative week lists. Late revocation retains concealed 404, not an empty successful payload.
- Require UserActor for new interactive APIs; verified-integer model bridge and trusted-job method are explicitly named.
- Keep score calculation, season standings, provider dependencies, job recovery, disabled HTTP writes, transaction isolation and schemas unchanged.
- Repository uses supplied connection and fixed SQL; no model, Flask, configured engine or commits.

## Task 1: Service and repository

Files: create scoring `contracts.py`, `service.py`, `repository.py`, `api/tests/test_scoring_read_service.py`; modify `scoringModel.py` and points-only branch of `scoringEndpoints.py`.

Interfaces: ScoringReadService(engine,repository=None). `get_weekly_points(actor,league_id,week_numbers)`, `get_weekly_points_for_legacy_reader(user_id,league_id,week_numbers)`, `get_weekly_points_for_job(league_id,week_numbers)`. ScoringReadDenied is transport-independent; facade maps it to PermissionError and HTTP retains 404 League-not-found. ScoringRepository `league_read_allowed(conn,league_id,user_id)` and `weekly_points(conn,league_id,week_numbers)`.

- [x] Write direct tests with existing scoring fixture: required actor before I/O, one connection, normalization/order, commissioner-only access, denial before score query, revocation after score query, empty-list access checks and trusted reads.
- [x] Run new suite red, implement service/repository, then wire facade and HTTP actor caller without changing other branches.
- [x] Run full guarded backend suite, existing scoring authorization/atomicity/tiebreak/operational tests unchanged.

## Task 2: Native SQL and review

- [x] Add marked-loopback PostgreSQL runner/report for expanding week binds, dates/numerics/projections/order, league isolation, commissioner/member policy, empty-week denial and separate-connection revocation before final check.
- [x] Reuse cached image/task-only container and random database, clean both afterward; no .env/configured/hosted database.
- [x] Inspect new import/dependency boundaries and unchanged scoring calculation AST.
- [x] One independent review; fix important findings with failing regressions first.
- [x] Record evidence and scoped completion. No frontend checks required for backend-only extraction; leave working changes uncommitted.

## Execution ledger

- Ruling: Select weekly-points read only — normalization and pre/post authorization justify a service, while weekly computation and season standings have larger correctness/helper closures — this slice does not migrate all scoring.
- Ruling: Keep pre/post read checks and concealed denial behavior rather than replace them with a new empty-result policy — preserve the established HTTP contract and revocation tests — no stronger snapshot/revocation guarantee is claimed.

- Baseline guarded backend 389/389 passes. Seven direct-service tests initially failed on the missing module; all pass after extraction. Existing scoring/profile/domain tests were not modified.
- HTTP weekly-points branch now uses canonical UserActor; season branch retains the existing model. Model read delegates to explicit trusted/legacy-reader methods and translates the domain denial to PermissionError. Empty trusted reads retain no-I/O behavior.
- Pre/post access checks use one read connection. Denial is raised after the connection closes, preserving the old guard's read-lifecycle semantics and concealed failure contract. No stronger isolation/revocation guarantee is introduced.
- Full guarded backend 396/396 passes, exit 0. Independent review found no Critical/Important/Minor issues; it reviewed source/callers but did not independently execute tests.
- Native PostgreSQL PASS: expanding binds, normalization/order, native dates/numerics/projection, league isolation, commissioner/member access, empty-list checks and separate-connection late revocation for scores and empty lists. Default READ COMMITTED only; no changed isolation policy.
- AST comparison confirms all ScoringModel methods except constructor/target read are unchanged. New service/repository modules import no Flask, model facade, provider or configured engine.
- Approved sandbox escalation used only task-owned cached-image loopback PostgreSQL. Harness removed its random database; container otm-mod038-scoring-20261029 stopped/removed. Earlier pilot code/evidence preserved, no hosted DB/dependency/listener/deployment changes.
- Changes remain uncommitted with earlier user-domain work in the requested checkout. No frontend files or checks changed.
