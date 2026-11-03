# MOD-038 Admission Approval Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline with test-first changes and one independent final review.

**Goal:** Complete admission extraction with approval, membership/draft-order allocation and player-count/draft-round updates, preserving behavior.

**Architecture:** AdmissionService owns checked actor/commissioner/state policy and one transaction. AdmissionRepository owns supplied-connection SQL. Existing model methods remain compatibility facades; trusted approval has an explicit job entry point and private helper uses its supplied connection.

**Tech Stack:** Existing Flask, SQLAlchemy/raw SQL, unittest and marked disposable PostgreSQL; no new dependencies.

**Spec:** [Approved incremental hybrid](../specs/2026-10-29-mod-038-layering-design.md); user authorized the final admission slice.

## Global constraints and review focus

- Current checkout, preserve prior uncommitted work, no commits/deployment/hosted access/schema/API changes.
- Preserve League FOR UPDATE → scoped request FOR UPDATE, commissioner before request check, PENDING before writes.
- Preserve membership INSERT with MAX(draftOrder)+1, team fallback, zero points, exact existing player-count/draft-round CTE/JSON semantics (including missing-parent behavior), request resolution and returned projections.
- No new capacity limit, duplicate-membership translation, missing-sport check or concurrent-creation uniqueness guarantee. Existing correctness cards remain separate.
- Trusted model bypass is audit-only actor metadata; HTTP cannot select it. Preserve __new__ db-only callers and private helper transaction ownership.

## Task 1: Extract approval policy and persistence

Files: extend admission_service.py/repository.py, approval delegates in leagueModel.py and approve_join adapter; add test_admission_approval_service.py.

Interfaces: approve_request(actor,league_id,request_id); approve_request_for_legacy_commissioner(user_id,league_id,request_id); approve_request_for_job(league_id,request_id,acting_user_id); approve_request_in_transaction(conn,league_id,request_id,acting_user_id). Repository methods lock_request_for_approval, insert_member, update_capacity, approve_pending, member_for_request.

- [x] Direct-service tests RED: actor before I/O, one transaction, authority/scope/state, member/fallback/order/count/settings/rounds, replay, unique-member failure, rollback and trusted/private compatibility.
- [x] Extract existing SQL and orchestration; HTTP actor service and legacy exception translations; GREEN focused and guarded full backend tests.

## Task 2: Native verification and final review

- [x] Rerun prior admission suites, then native approval fixture/projection/JSON/round rules, real duplicate/FK failures and statement/post-write/deferred-commit rollback.
- [x] Observe real PostgreSQL league/request lock waits for same-request replay and distinct-request order/count serialization; checked and legacy facade paths; trusted/private compatibility.
- [x] AST/dependency checks, one independent final review, any Important fixes test-first; fresh full backend.
- [x] Update progress/backlog/verification/runbook/evidence and hashes; remove only owned random DB/container; preserve uncommitted checkout.

## Execution ledger

- Ruling: Preserve existing capacity semantics and SQL verbatim — approved extraction is behavior-preserving; new limits/schema or broader admission correctness need their own scope.
- Ruling: Existing user consent selects current checkout and uncommitted delivery; do not create worktrees or commits.
- Pre-flight: Task 2 consumes Task 1 service/facade interfaces and repository SQL; names and transaction contract aligned above.

- Task 1: complete. Guarded baseline 419/419; focused RED six missing-operation assertion failures and one passing legacy compatibility case, GREEN 7/7. Full backend 426/426; existing authorization tests unchanged. SQL extracted from captured pre-slice model; non-target methods AST-identical.
- Task 2: complete. Marked-loopback native [evidence](../../modernization/evidence/mod-038-admission-complete-postgres-2026-10-29.json) PASS: prior admission suites rerun, exact projections/timestamps/JSON/rounds/fallback, real unique/FK rollback, post-member/post-capacity/post-resolution and deferred-commit rollback; four competing same/distinct service/facade cases observe league→request locks, replay rejection/consecutive allocation and consistent counts/rounds. Trusted/private supplied-connection compatibility passes.
- Independent final review: no Critical/Important/Minor findings; reviewer focused guarded suite 7/7. No fixes required. Final guarded suite 426/426. Current source hashes and documentation links checked; diff check clean.
- Task-owned random database and container removed. Prior work preserved; current checkout uncommitted. Broader league extraction and MOD-012 correctness remain separate; no new policy/schema or hosted/frontend/dependency/startup/deployment changes.
