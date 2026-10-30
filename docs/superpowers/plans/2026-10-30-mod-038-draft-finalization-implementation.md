# MOD-038 Draft Finalization Implementation Plan

> Use superpowers:executing-plans inline, test-first and one independent final review.

**Goal:** Extract central draft finalization and checked commissioner force-finalize without changing pick/control contracts.
**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md).
**Architecture:** DraftControlService owns actor/pre+post commissioner checks and owned/supplied transaction scope; repository owns commissioner, final-state and season-derived league updates. Model finalizer/force-finalizer/assert helper delegate; existing control transaction helper and other commands unchanged. HTTP finalize branch uses actor service; existing post-commit snapshot/broadcast unchanged.

## Constraints

- Current checkout, preserve prior changes, uncommitted; no schema/dependencies/hosted/deployment changes.
- Commissioner check before/after writes (integer legacy coercion), no new locks or authority bypass through HTTP flags. Legacy force None denied before I/O.
- Trusted finalization remains separate, optionally supplied connection without nested transaction; state required, exact state clearing/COALESCE lastPick/updatedAt and league status CASE/date/join/no-season None preserved.
- Preserve repeated finalization/timestamp behavior, existing read-time state repair, result/error/JSON/broadcast timing. No replay guard/status redesign/notification added.
- Model assert delegate still supports remaining controls with their pre/post checks; actual repository has no model subclasses/helper overrides.

## Task 1

- [x] RED service tests actor/no I/O, checked/trusted authority, state/result/season/null semantics, failure rollback and caller-owned connection/model compatibility.
- [x] Add control_service.py/control_repository.py; delegate three model methods and HTTP finalize branch. GREEN focused/full backend; AST/dependency checks.

Interfaces: finalize(actor,league_id), force_finalize_for_user_id(league_id,user_id), finalize_for_job(league_id,conn=None), assert_commissioner(conn,league_id,user_id). Repository commissioner/finalize_state/finalize_league(conn,...).

## Task 2

- [x] Native final-state projection/timestamps/date boundaries/no season/missing state, pre/post authority including separate-connection revocation, statement/post-write/deferred-commit and caller rollback.
- [x] Rerun snapshot native checks with current shared model, one independent review, final backend/docs/hash/link/diff checks and owned-resource cleanup.

## Ledger

- Ruling: Extract finalization only. Existing start/pause/resume/order transaction helper stays, using shared assertion facade to avoid duplicate commissioner SQL. Other control/pick/timeout work remains separate.

- Task 1 complete: baseline 495/495; RED five missing-module errors/one passing legacy case, GREEN 6/6; backend 501/501. Existing tests unchanged. Other model methods AST-identical including _draft_control_transaction; control dependency boundaries verified.
- Task 2 complete: [native evidence](../../modernization/evidence/mod-038-draft-finalization-postgres-2026-10-30.json) PASS for date/state/result/no-season/lastPickAt, post-write/real statement/deferred commit/caller rollback, separate pre/post authority loss and legacy supplied connection. Snapshot native suite rerun. New report supersedes earlier draft hashes; historical evidence retained.
- Independent review no findings; focused suite 6/6. No fixes needed. Final backend 501/501; current hashes, links and diff checked. Owned DB/container removed; current checkout uncommitted. No hosted/schema/frontend/dependency/startup/deployment changes.
- Other controls/order/picks/timeouts and stronger replay/locking/realtime policies remain separate.
