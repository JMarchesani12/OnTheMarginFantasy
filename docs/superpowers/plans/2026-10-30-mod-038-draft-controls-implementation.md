# MOD-038 Draft Start/Pause/Resume Implementation Plan

> Use superpowers:executing-plans inline, test-first and one independent final review.

**Goal:** Extract start/pause/resume, shared draft-settings policy and turn seeding with unchanged legacy contracts.
**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md).
**Architecture:** DraftControlService owns actor/trusted pre/post authority, one control transaction, settings/turn policy and in-transaction trusted snapshot. Repository owns original control/config/turn SQL. Pure rules own settings validation/round math/order; model helper delegates preserve remaining pick/order callers. HTTP broadcasts stay after successful commit.

## Constraints

- Current checkout/prior work preserved, uncommitted; no schema/dependencies/hosted/deployment changes.
- Preserve pre/post commissioner integer equality, trusted omitted actor paths, snapshots on same connection, start config read/validation twice including seeding, resume config-before-state lock, pause no config validation.
- Preserve complete/missing state guards, pause expiry clearing, resume clock, current pick/member, start resetting state and turn ON CONFLICT behavior. No replay/locking redesign.
- Preserve settings/defaults/errors, exact snake/straight math and member mapping; original helper signatures, supplied conn/no engine requirement and db-only callers.
- Validate native missing-order branch; any demonstrated SQL alias bug gets explicit RED→GREEN minimal repair, not silently retained.
- Remaining picks/manual/timeout/conference logic and order controls stay separate.

## Task 1

- [x] RED service tests actor/no I/O, snake/straight seeding, pause/resume guards/clock, authority-before-config, rollback/late authority and legacy helpers.
- [x] Extend service/repository, pure draft_rules, model delegates and HTTP actor control mapping; GREEN focused/full backend; AST/dependency checks.

Interfaces: start/pause/resume(actor,league_id), named *_for_job and *_for_legacy_user_id bridges; draft_settings(conn,league_id), seed_turns(conn,league_id), expected_member(conn,league_id,overall). Shared rules settings_from_league, compute_round_and_pos, draft_order_for_pick.

## Task 2

- [x] Native original generate_series/interval/upsert/turn/row-lock SQL, guard/validation/defaults, rollback/revocation/deferred commit and state/turn locks; prior snapshot/finalization native reruns.
- [x] One independent review, final full backend, docs/current hash/link/diff checks and owned-resource cleanup.

## Ledger

- Ruling: Preserve existing reset/repeated controls; do not implement MOD-025 replay protection here. Seed/settings helpers move because controls consume real policy, and remaining model commands retain delegating helpers.

- Native RED: real PostgreSQL incomplete-order case raised KeyError(missingOrder), because original unquoted alias folds to missingorder. Ruling: quote internal alias as "missingOrder" to preserve intended cross-provider validation; invalid order now produces the intended ValueError/HTTP400, with no valid-start policy change. Native regression rerun required.

- Task 1 complete: baseline 501/501; RED five missing-operation assertions/one passing legacy case, GREEN 6/6; backend 507/507. Existing tests unchanged; other model methods AST-identical; control/rules import boundaries verified.
- Task 2 complete: [native evidence](../../modernization/evidence/mod-038-draft-controls-postgres-2026-10-30.json) PASS for generate_series/interval/upsert/snake/straight, missing/config/complete, write/deferred commit/late authority rollback and two observed service/facade pause→resume row-lock waits. Prior snapshot/finalization suites rerun; combined report supersedes prior draft hashes and preserves historical reports.
- Native correctness RED→GREEN alias repair documented above and reviewed. Independent final review no findings; focused suite 6/6. Final backend 507/507 after repair; source hashes, links and diff checked. Owned resources removed; checkout uncommitted; no hosted/schema/frontend/dependency/startup/deployment changes.
- Order/picks/timeouts and MOD-025 replay redesign remain separate.
