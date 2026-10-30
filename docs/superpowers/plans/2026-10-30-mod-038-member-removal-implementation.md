# MOD-038 Member Removal Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-first and one independent final review.

**Goal:** Extract commissioner member removal, optional draft-order shifting and count decrement into the member service/repository.

**Architecture:** MemberService requires actor on HTTP-facing operation, checks commissioner under league lock, then member scope and commissioner prohibition under member lock; one transaction owns deletion/optional shift/count/projection. Repository owns supplied-connection SQL, model remains a db-only compatible delegate.

**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md); user authorized this slice.

**Tech stack:** Existing Flask, SQLAlchemy/raw SQL, unittest and marked loopback PostgreSQL.

## Constraints and review focus

- Current checkout, preserve prior uncommitted work; no commits/schema/dependency/hosted/deployment changes.
- Preserve league→member lock order, int-converted legacy commissioner comparison, URL scope, commissioner protection, removed-order int conversion and exact returned fields/order.
- New actor API requires boolean shift before I/O; legacy method retains truthiness and existing error semantics. No trusted authority bypass is introduced.
- Preserve GREATEST count floor, updatedAt and unrelated league data. Removal still does not recompute draft-round settings or add status restrictions; do not silently redesign these rules.
- Real constraint/commit errors propagate and roll back every mutation. Removal, approval and replay lock ordering must remain compatible.

## Task 1: Policy and persistence

- [x] Add direct-service failing tests for actor/shift validation, authority/scope/protection, projection/shift/count/replay, rollback and legacy context-free behavior.
- [x] Extend member_service.py/member_repository.py, replace only remove_member_and_shift_draft_order body and wire HTTP remove_member to actor service.
- [x] Focused GREEN/full backend; AST/dependency checks.

Interfaces: remove(actor,league_id,member_id,shift_draft_order=True); remove_for_legacy_commissioner(league_id,member_id,acting_user_id,shift_draft_order=True). Repository: lock_league_for_removal, lock_member_for_removal, delete_member, shift_after_removal, decrement_count, remaining_members (all supplied connection).

## Task 2: Native and review

- [x] Native scope/protection/projection/shift-off/count floor, actual FK restriction, post-delete/shift/count and deferred-commit rollback.
- [x] Observed league→member lock waits for same/distinct removals through service/facade, and removal followed by approval allocation; preserve unrelated state.
- [x] Rerun member profile and all admission native checks; one final review, fresh backend and docs/evidence/hash/link/diff checks; remove owned DB/container only.

## Execution ledger

- Ruling: Preserve all current removal rules, including no draft-round recalculation/status restriction; correctness redesign remains separate.
- Pre-flight: Native suite consumes the new service and legacy delegate and existing approval service; they share the established league-first transaction lock contract.

- Task 1: complete. Guarded baseline 431/431. RED five missing-operation assertions and one passing legacy case; GREEN six direct-service tests. Full backend 437/437; existing tests unchanged. All other model methods AST-identical and member dependency checks pass.
- Task 2: complete. [Native evidence](../../modernization/evidence/mod-038-member-removal-postgres-2026-10-30.json) PASS: authority/protection/projection/shift/count floor, real FK/post-delete/post-shift/post-count/deferred-commit rollback; six service/facade observed lock-wait cases for same/distinct removals and approval after removal. Prior member profile/admission suites rerun unchanged. Combined report supersedes their hashes; historical reports retained.
- Independent final review no Critical/Important/Minor findings; reviewer ran focused guarded suite 6/6. No fixes needed. Final backend 437/437; source hashes, links and diff checked.
- Owned random database/container removed. Prior work preserved; checkout uncommitted. No schema/hosted/frontend/dependency/startup/deployment changes. Broader league methods and policy redesign remain separate.
