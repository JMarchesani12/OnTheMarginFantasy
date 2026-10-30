# MOD-038 Member List and Daily Summary Plan

> Use superpowers:executing-plans inline, test-first and one independent final review.

**Goal:** Extract full member list/current-week/daily differential orchestration without changing schedule calculations.
**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md).
**Architecture:** Read service owns actor/trusted selection, one read connection for original two queries, timezone/date normalization, game capability calls and member projection. Repository owns scoped member/score and current-week SQL. Adapter supplies public ScheduleModel timezone/game capabilities; old model uses deferred callbacks.

## Constraints

- Current checkout/prior work preserved, uncommitted; no schema/dependencies/hosted/deployment changes.
- Preserve member ordering, score sum/fallback/nonnegative-week filter, scoped SQL on both queries, current-week highest/interval fallback, original fetchone/index access and iteration.
- Preserve timezone callback even empty rows/no week, callbacks after read connection closes, week zero, null start→empty daily dates, naive timestamps treated UTC, inclusive local date range, zero fill and total including undated/out-of-range games.
- Preserve legacy optional reader, game call kwargs, callback errors and original snapshot behavior; no new final recheck/N+1 batching/algorithm fix.
- ScheduleModel gains public get_league_timezone delegate to existing private helper; scheduling SQL/logic unchanged and old mocks remain valid.
- After this, lifecycle is last planned extraction slice. Proposed subsequent import-only organization: admission/, members/, administration/, reads/, lifecycle/; keep route/endpoint composition/facades stable. No folder move in this behavior-preserving extraction.

## Task 1

- [x] RED service tests for actor before I/O/callbacks, no-week projection/legacy, week zero/local-date totals/zero fills, empty/scoped out and callback errors.
- [x] Extend read service/repository and model delegate, public timezone capability and HTTP member branch; GREEN focused/full backend, AST/dependency checks.

Interfaces: members(actor,league_id,timezone_for_league,games_for_member_week), members_for_reader_id(...), members_for_job(...), internal _members. Repository member_rows(conn,league_id,reader_user_id=None), member_current_week(conn,...).

## Task 2

- [x] Native original SQL/scopes/score fallback/current week, local/naive/aware date aggregation, null-start/no-week and revocation; capability boundary verified without reimplementing scheduling algorithms.
- [x] Rerun earlier native suites, one independent review, final backend, docs/hash/link/diff checks and owned-resource cleanup.

## Ledger

- Ruling: Preserve original two-query snapshot and callbacks even for empty results; stronger final authorization/batching is separate work.
- Ruling: Recommend cohesive league subfolders after lifecycle as an independent import-only pass, retaining public imports; no folder changes mixed into this slice.

- Task 1 complete: baseline 476/476; RED five missing-operation assertions/one passing legacy case, GREEN 6/6; backend 482/482. Existing tests unchanged. Non-member league methods and all existing ScheduleModel methods AST-identical; public timezone wrapper only addition.
- Task 2 complete: [native evidence](../../modernization/evidence/mod-038-member-summary-postgres-2026-10-30.json) PASS for actual SQL/score fallback/week zero, timezone/date/zero-fill/undated/out-of-range totals, null-start/no-week, game capability error, pre-query revocation and legacy. All preceding suites rerun; combined report supersedes old hashes, history retained.
- Independent final review no findings; focused guarded suite 6/6. No fixes required. Final backend 482/482; hashes, links, dependency boundaries and diff checked. Owned resources removed; checkout uncommitted; no hosted/schema/frontend/dependency/startup/deployment changes.
- Lifecycle is final planned extraction. Cohesive subfolders recommended afterward as independent import-only pass; no reorganization implemented here.
