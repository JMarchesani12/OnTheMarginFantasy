# Capacity-based Draft Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement inline. Steps use checkbox syntax for tracking.

**Goal:** Size drafts from actual conference capacity and skip owners without legal picks.
**Architecture:** Shared capacity calculation and persistence for pre-draft membership/start; shared read-only eligibility for turn selection and snapshots. Existing ownership locks and draft finalization remain authoritative.
**Tech Stack:** Python, SQLAlchemy/PostgreSQL, React/TypeScript; isolated SQLite-backed unittest fixtures.
**Spec:** docs/superpowers/specs/2026-11-19-draft-capacity-design.md

## Global Constraints

No mandatory conferences. No protective blocking of valid picks. Keep conference caps. No live resizing. No fake allocations. Preserve authorization and transaction scope.

## Review Focus

- Seasonal membership overrides current membership without double counting.
- More owners than total capacity produces no full round and cannot start.
- Timeout AUTO-PICK and AUTO-SKIP both advance past stuck owners.
- All remaining owners stuck finalizes without inserting a pick.
- Capacity updates preserve unrelated settings and rollback on failure.

### Task 1: Capacity policy and pre-draft integration

**Files:** api/utils/draft_capacity.py; league admission/administration/members services and repositories; draft control service; API tests.
**Interfaces:** calculate_rounds(num_players, max_rounds, conferences) -> int; refresh_draft_capacity(conn, league_id) -> int.
- [x] Write capacity and integration tests; run and confirm expected failures.
- [x] Implement formula using effective season mappings and actual membership counts; wire creation, approval, pre-draft removal, and start.
- [x] Run capacity/admission/control/creation/removal suites.

### Task 2: Legal turn advancement

**Files:** api/endpoints/draft/snapshot_repository.py; pick_service.py; pick_repository.py; API tests; LeagueDraftPage.tsx.
**Interfaces:** next_unpicked_turn keeps (overall, member) or None, now excluding owners without legal choices.
- [x] Write regression tests for scarce-team picks, blocked next owner, all-stuck completion, both timeout actions, and lookahead; confirm failures.
- [x] Add effective-season legal-choice query and reuse it for advancement, timeout processing, and snapshots. Keep valid picks unrestricted.
- [x] Explain optional conferences, maximum roster size, and automatic skips on the draft screen.
- [x] Run full isolated backend suite and frontend build, inspect diff.

## Execution and validation

Implemented inline in the existing workspace; sandbox Git permissions prevented creating a worktree. No commits, deployment, or hosted data changes were made.

Task 1 complete: shared capacity policy, creation, approval, pre-draft removal, and start. Tests cover stale membership counts, season overrides, caps including zero, preserved settings, and insufficient capacity.

Task 2 complete: shared eligibility SQL for snapshots and live/timeout advancement, completion with shorter rosters, unchanged valid picks, and frontend explanation using snapshot round counts. Existing timeout rotation remains distinct from exhaustion.

Fresh review found one scheduling boundary gap: existing stuck turns with null or future clocks were not scheduled immediately. Treated as important because null clocks could stall indefinitely. Added a worker regression (observed RED), then made the worker inspect live owners for exhaustion before consulting clock deadlines (GREEN). Normal live picks skip immediately; existing stuck turns are discovered on the worker's bounded polling cycle (up to 30 seconds).

Validation: `python3 api/tests/run_isolated.py` — 863 passing; `node --test --experimental-strip-types tests/*.test.ts` from front-end — 252 passing; `npm run build` from front-end — passing; `git diff --check` — clean. Isolated SQLite adapters execute real queries but do not prove PostgreSQL lock behavior or hosted worker operation.
