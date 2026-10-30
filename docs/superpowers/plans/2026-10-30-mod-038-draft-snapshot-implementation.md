# MOD-038 Draft Snapshot Implementation Plan

> Use superpowers:executing-plans inline, test-first and one independent final review.

**Goal:** Start draft migration with member-authorized state snapshot and completed-state repair, retaining legacy caller transactions.
**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md).
**Architecture:** Snapshot service owns actor/trusted/member policy, repair orchestration, envelope and one transaction unless supplied connection. Repository owns original snapshot/repair/next-turn SQL. Model snapshot/repair/turn helpers remain compatible; HTTP state builds actor. Other draft behavior unchanged.

## Constraints

- Current checkout/prior league work preserved; uncommitted, no schema/dependency/hosted/deployment changes.
- Member-only access (commissioner without membership denied), missing/scoped-out checked PermissionError concealed404, trusted missing ValueError. Scope check precedes repair and all payload reads.
- Preserve completed repair guards/write, single transaction or caller-supplied connection without nested begin/commit, original row accessors, all queries/fields/season joins/order, next unpicked turn skipping existing picks, server UTC timestamp.
- Preserve private helper signatures and use by commands; no notifications added, no stronger final authorization/concurrency/replay guarantee.
- Picks/control/order/timeout/provider workflows remain separate slices. No pass-through layering for sport-only lookup.

## Task 1

- [x] RED service tests actor/access/no-I/O, snapshot projection/turns, no-state/missing, repair/rollback and supplied-connection/trusted legacy behavior.
- [x] Add snapshot_service.py/snapshot_repository.py, three model delegates, HTTP state actor service; GREEN focused/full backend and AST/dependency checks.

Interfaces: snapshot(actor,league_id,conn=None), snapshot_for_job(league_id,conn=None), snapshot_for_reader_id(league_id,user_id,conn=None); repair_completed(league_id,state,conn), next_unpicked_turn(conn,league_id,start_overall).

## Task 2

- [x] Native member/commissioner/outsider scope, JSON/timestamps/projections/season joins/turn skipping, repair rollback after later query and deferred commit, supplied transaction rollback and late pre-query revocation.
- [x] One independent review, final backend, docs/evidence/hash/link/diff checks and owned DB/container cleanup.

## Ledger

- Ruling: Choose draft snapshot as next cohesive domain slice; sport lookup remains cohesive without unnecessary new layers.
- League legacy modules remain small aliases while tests/tools reference them; remove only after caller migration and compatibility verification in a dedicated cleanup.

- Task 1 complete: baseline 489/489; RED five missing-module errors/one passing legacy case, GREEN 6/6; backend 495/495. All other model methods AST-identical; existing tests unchanged; dependency checks pass. Helpers use service(None), avoiding new db dependency on supplied connections.
- Task 2 complete: [native evidence](../../modernization/evidence/mod-038-draft-snapshot-postgres-2026-10-30.json) PASS for original projections/member authority/JSON/timestamps/season joins/turn skips/missing state, post-repair/deferred commit/caller rollback, supplied legacy helpers and separate-connection pre-query revocation.
- Independent final review no findings; focused suite 6/6. No fixes needed. Final backend 495/495; current source hashes, documentation links and diff checked. Owned DB/container removed; prior league work preserved and uncommitted. No hosted/schema/frontend/dependency/startup/deployment changes.
- Draft commands/control/order/timeout and realtime guarantees remain separate. League aliases retained for existing callers until dedicated migration/retirement.
