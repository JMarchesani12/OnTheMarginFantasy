# MOD-038 Draft Order Control Plan

> Use superpowers:executing-plans inline, test-first and one independent final review.

**Goal:** Extract commissioner/trusted draft-order update without policy redesign.
**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md).
**Architecture:** Control service owns actor/legacy/trusted selection, empty input, pre/post authority, state/member validation, atomic bump/reorder/projection. Repository owns original SQL; model compatibility delegate and HTTP actor call retain contracts.

## Constraints

- Current checkout/prior work retained; uncommitted, no schema/dependency/hosted/deployment changes.
- Preserve empty-input-before-legacy-DB, commissioner pre/post integer checks, state rejection live/paused/complete without new FOR UPDATE, member ANY array count rejecting foreign/duplicate IDs.
- Preserve +100000 bump, unnest/generate_series order SQL, array parameters and exact returned members. Partial member lists remain accepted with omitted orders bumped; full-permutation validation is separate MOD-025 scope.
- No broadcast added for order. Snapshot/control/pick/timeouts behavior unchanged; no new concurrency/replay guarantee.

## Task 1

- [x] RED service tests actor/empty/no I/O, swaps/projection/partial order, member/state/authority guards, rollback and legacy defaults.
- [x] Extend service/repository, model set_draft_order delegate and HTTP actor order branch; GREEN focused/full backend; AST/dependency checks.

Interfaces: set_order(actor,league_id,member_ids), set_order_for_job(...), set_order_for_legacy_user_id(...,user_id). Repository order_state, order_members, bump_orders, assign_order, ordered_members(conn,...).

## Task 2

- [x] Native ANY/unnest/generate_series/bigint arrays, actual unique order index, guards/partial behavior, post-bump/post-assign/member-read/deferred-commit rollback and late authority revocation.
- [x] Rerun prior snapshot/finalization/control suites; one independent review, final backend/docs/hash/link/diff and owned-resource cleanup.

## Ledger

- Ruling: Preserve partial lists, no extra locks or notifications. Correctness/permutation/concurrent start safeguards remain separate.

- Task 1 complete: baseline 507/507; RED four missing-operation assertions/one passing legacy case, GREEN 5/5; full backend 512/512. Existing tests unchanged; other model methods AST-identical and control dependency boundaries verified.
- Task 2 complete: [native evidence](../../modernization/evidence/mod-038-draft-order-postgres-2026-10-30.json) PASS for arrays/ANY/unnest/generate_series under unique-order index, swaps/partial/guards, post-bump/assignment/read/statement/deferred-commit rollback, separate authority loss and trusted/coerced legacy calls. Prior snapshot/finalization/control suites rerun; new report supersedes old draft hashes, history retained.
- Independent review no findings; focused suite 5/5. No fixes required. Final backend 512/512; hashes, links and diff checked. Owned DB/container removed; uncommitted checkout; no hosted/schema/frontend/dependency/startup/deployment changes.
- Picks/timeouts and MOD-025 full-permutation/concurrent-start policy remain separate.
