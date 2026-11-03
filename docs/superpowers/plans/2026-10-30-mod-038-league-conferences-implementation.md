# MOD-038 League Conference Read Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-first and one independent final review.

**Goal:** Extract scoped conference read with season-specific membership counts and unchanged HTTP/model behavior.

**Architecture:** LeagueReadService owns actor/trusted selection, one transaction, league/season validation and result envelope. Repository owns original league scope and sport/season aggregate query. HTTP retains discovery/full-access gates and uses actor service; legacy optional reader remains.

**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md), user authorized next slice.

**Tech stack:** Existing Flask/SQLAlchemy/unittest and marked synthetic PostgreSQL.

## Constraints and review focus

- Current checkout, preserve existing uncommitted changes; no commits/schema/dependencies/hosted/deployment changes.
- Actor before I/O; one begin scope, missing/scoped-out league ValueError before aggregate; missing season remains explicit error. No new post-SELECT recheck.
- Preserve sport isolation, null-season plus matching-season COUNT(*), zero fallback, exact fields/name ordering/maxTeamsPerOwner and response envelope. No membership deduplication/redesign.
- Preserve model signatures/db-only construction and explicit trusted read. HTTP initial discovery denial and existing late scoped-out ValueError→400 unchanged.
- Remaining planned league slices after this: discovery/access/previews/search; details/my leagues; member list/daily summaries; lifecycle synchronization (four).

## Task 1: Policy/persistence

- [x] RED direct tests for actor, season/sport aggregate/order/zero, missing/denied/season-null skip aggregate, query-time revocation and trusted legacy compatibility.
- [x] Extend read service/repository, delegate get_league_conferences and wire full HTTP branch; GREEN focused/full backend.
- [x] AST/dependency checks for untouched model and transport-independent read modules.

Interfaces: conferences(actor,league_id), conferences_for_reader_id(league_id,user_id), conferences_for_job(league_id), internal _conferences; repository conference_league(conn,league_id,reader_user_id=None), season_conferences(conn,sport_id,season_year).

## Task 2: Native/review/evidence

- [x] Native original aggregate/counts/fields/order/sport isolation/null season/empty results and separate-connection revocation before scoped SELECT.
- [x] Rerun all previous league/member/admission native suites; one independent review, fresh backend, docs/evidence/hash/link/diff checks and owned-resource cleanup.

## Execution ledger

- Ruling: Group remaining league work into five slices including this one; four remain afterward, subject to findings.
- Pre-flight: Existing HTTP gate remains authoritative for discovery policy while repository predicate retains query-time scope. Preserve ValueError for late conference scope loss rather than adopting rules-read None behavior.

- Task 1: complete. Guarded baseline 460/460; RED five missing-operation assertions, GREEN 5/5. Full backend 465/465 with existing tests unchanged. Non-conference model AST and read dependency checks pass.
- Task 2: complete. [Native evidence](../../modernization/evidence/mod-038-league-conferences-postgres-2026-10-30.json) PASS for exact season/null counts/zero/order/sport projection, missing/denied/season-null skipping aggregate, empty/trusted/legacy and separate-connection membership revocation service/facade. All earlier native league/member/admission suites rerun; combined report supersedes their hashes, history retained.
- Independent final review no Critical/Important/Minor findings; reviewer focused guarded suite 5/5. No fixes required. Final backend 465/465; current hashes, links and diff checked.
- Owned random database/container removed. Current checkout uncommitted. Four planned league slices remain as listed above; no schema/hosted/frontend/dependency/startup/deployment changes.
