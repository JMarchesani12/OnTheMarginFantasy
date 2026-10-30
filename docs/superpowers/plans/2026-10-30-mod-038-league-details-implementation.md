# MOD-038 League Details and Own Listing Plan

> Use superpowers:executing-plans inline, test-first and one independent final review.

**Goal:** Extract full details and own-league listing, preserving query projections, actor scope and sync timing.
**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md).
**Architecture:** Read service owns actor/trusted scope, stage normalization and explicit sync capability before read; supplied-connection repository owns unchanged SQL. Adapter wires existing model sync; model delegates use deferred lambda.

## Constraints

- Current checkout, preserve prior work, uncommitted; no schema/dependencies/hosted/deployment changes.
- Details keeps scoped read, highest matching current week, begin/fetchone/_mapping and None missing. Sync still runs before read, even denied/missing legacy calls.
- Own listing keeps membership-only selection (commissioner alone insufficient), weekly score fallback/negative-week exclusion, all/active/completed normalization and unknown-stage fallback before sync, connect/iteration and logging.
- Preserve overlapping-week duplicate own-list rows, interval fallback and original exact projection. No new deduplication/current-week/authorization policy.
- HTTP discovery/identity assertions unchanged; callbacks execute outside read scope. No model import from service. Sync algorithm unchanged and remains separate.

## Task 1

- [x] RED direct tests for actor/no sync/I/O, detail scope/sync sequencing, own membership/stages/projection and legacy callbacks.
- [x] Extend read service/repository and delegate two model methods; wire HTTP actor calls with public sync capability. GREEN focused/full backend, AST/dependency checks.

Interfaces: details(actor,league_id,sync_statuses), details_for_reader_id(league_id,user_id,sync_statuses), details_for_job(league_id,sync_statuses); mine(actor,sync_statuses,stage='all'), mine_for_user_id(user_id,sync_statuses,stage='all'). Repository details(conn,league_id,reader_user_id=None), own_leagues(conn,user_id,stage).

## Task 2

- [x] Native intervals/highest detail week/overlapping listing rows, score fallback, membership/filter/projection, revocation and explicit committed sync boundary.
- [x] Prior native suites rerun; one independent review, final full backend, docs/hash/link/diff checks and owned resource cleanup.

## Ledger

- Ruling: Preserve global lifecycle side effects via explicit callback; removal of read-time writes remains separate work. Two planned league slices remain after this.

- Task 1 complete: baseline 471/471; RED three missing-operation assertions/two passing legacy cases, GREEN 5/5; full backend 476/476. Existing tests unchanged; non-target model AST and read dependency checks pass.
- Task 2 complete: [native evidence](../../modernization/evidence/mod-038-league-details-postgres-2026-10-30.json) PASS for interval/current-week, original overlaps, scores/stages/membership/projection, committed sync/read boundary, revocation and legacy paths. All preceding suites rerun; current report supersedes their hashes, history retained.
- Independent review no findings, focused suite 5/5; no fixes required. Final backend 476/476; current hashes, links and diff checked. Owned database/container removed; uncommitted checkout; no hosted/schema/frontend/dependency/startup/deployment changes.
- Two planned league slices remain: member lists/daily summaries and lifecycle synchronization.
