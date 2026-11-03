# MOD-038 League Creation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-first and one independent final review.

**Goal:** Extract actor/trusted league creation, commissioner membership and post-commit week initialization without behavior changes.

**Architecture:** LeagueAdminService owns actor-bound commissioner, team/settings/timezone policy and one insert transaction. Repository owns original league INSERT CTE and commissioner-member INSERT. Adapter supplies existing ScheduleModel.ensure_weeks_for_league capability explicitly; service imports no model/provider. Model trusted delegate defers schedule attribute access until after validation/commit, preserving db-only invalid-input callers.

**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md), user-authorized next slice.

**Tech stack:** Existing Flask, SQLAlchemy/raw SQL, shared leagueRules, unittest and marked synthetic PostgreSQL.

## Constraints and review focus

- Current checkout, preserve prior changes, uncommitted delivery; no schema/dependency/hosted/deployment changes.
- Actor required before I/O; actor owns commissioner in service, while HTTP keeps legacy commissioner assertion parsing/order.
- Preserve copied input, trimmed required team name, server-pinned version/default UTC/explicit timezone validation, original CTE fields/native sportinfo alias and creatorMemberId.
- League/member insert commit together. Initializer runs once only after commit; failure propagates and leaves saved league/member (existing behavior). No atomic scheduling/retry/idempotency guarantee added.
- Named trusted create uses supplied commissioner, legacy model helper signatures retained. Keep member insert fetchone/_mapping and original result guards/operational errors.
- Share ensure_timezone_in_settings in pure rules with legacy delegate; creation algorithm/rules only moved. Existing schedule engine and generation code unchanged.

## Task 1: Policy/persistence/wiring

- [x] RED service tests: actor/bad name before I/O, actor identity/normalization/defaults/input immutability, explicit timezone/version failures, membership rollback, post-commit callback visibility/failure and legacy compatibility.
- [x] Add service create(actor,league,initialize_weeks) and create_for_job(league,initialize_weeks), repository insert_league/insert_creator_member; shared timezone ensure and model/HTTP delegates.
- [x] Focused GREEN/full backend and AST/dependency checks.

## Task 2: Native/review/evidence

- [x] Native CTE/JSON/timestamps/sport projection, member fields, actual FK/no-result/post-insert/deferred-commit rollback and callback after commit visibility/failure.
- [x] Rerun prior settings/deletion/member/admission native suites; verify scheduling capability boundary without changing scheduling algorithms.
- [x] One independent final review; fresh backend, docs/evidence/hash/link/diff checks and owned DB/container cleanup.

## Execution ledger

- Ruling: Preserve post-commit scheduling as existing contract; an atomic/recoverable creation workflow is separate correctness work.
- Pre-flight: Create consumes explicit scheduling callback; model lambda defers missing schedule attribute until its original execution point, HTTP uses existing public schedule capability. All rules/body assertions retain order.

- Task 1: complete. Guarded baseline 449/449. Focused RED five missing-operation assertions plus one passing legacy case; GREEN 6/6. Full backend 455/455; existing tests unchanged. All other model methods AST-identical except shared ensure helper; admin dependency boundaries verified.
- Task 2: complete. [Native evidence](../../modernization/evidence/mod-038-league-creation-postgres-2026-10-30.json) PASS: CTE/JSON/timestamps/sportinfo/member defaults; real commissioner/member FK, missing projection/post-write/deferred-commit rollback; supplied initializer separately observes committed rows, failure preserves creation; legacy trusted creator. All preceding native suites rerun. Scheduling algorithms unchanged, native fixture verifies capability boundary only. Combined report supersedes prior league/member/admission hashes; historical reports retained.
- Independent final review no Critical/Important/Minor findings; reviewer ran focused guarded suite 6/6. No fixes needed. Final backend 455/455; hashes, links and diff checked.
- Owned random database/container removed. Current checkout uncommitted. No schema/hosted/frontend/dependency/startup/deployment changes. Reads/lifecycle and recovery/idempotency redesign remain separate.
