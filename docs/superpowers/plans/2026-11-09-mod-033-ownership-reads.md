# MOD-033 Ownership Reads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Share six draft/free-agency repository reads without changing their semantics or connection/result contracts.
**Architecture:** `utils/ownership_reads.py` executes fixed, bound SQL on a supplied connection. Named existence/scalar-distinct/grouped-row helpers share the active-week predicate and effective conference construction. Existing repositories adapt their original params and return raw results without consuming them; services are byte-identical.
**Tech Stack:** Python, SQLAlchemy, guarded unittest runner and existing SQLite SQL/result fixture adapter.
**Spec:** docs/superpowers/specs/2026-11-09-mod-033-ownership-reads-design.md

## Global Constraints

- No service/write/lock/cap/timing changes, engine/transaction creation, cache, schema changes, commit or deployment.
- Keep six repository signatures/results: draft live_team_ownership/manual_team_ownership/member_conference_count and workflow team_owned/member_team_owned/member_conference_counts.
- Preserve scalar draft DISTINCT/int/zero and grouped free-agent row counts/empty results, effective season membership and raw legacy league-existence behavior.
- Preserve prior uncommitted audit work in existing audit workspace; MOD033A policy matrix stays green.

## Review Focus

- Duplicate legacy intervals must count once for draft, twice for grouped free agency.
- Missing-league raw scalar/grouped behavior must remain unchanged rather than acquiring a new authorization policy.
- Invalid seasonal memberships suppress fallback; cross-sport invalid mappings remain omitted by raw reads and rejected by existing service guards.
- Result objects remain unconsumed and caller connection identity is retained.
- Queued free-agent counts after drops must observe caller writes and roll back if the read fails.

### Task 1: Characterize original repositories

Files: new `api/tests/test_ownership_reads.py`; ignored baseline hashes/artifacts in this plan workspace.
Interfaces: original six repository methods and existing SQL adapter; test expectations are literal outcomes, not copied count algorithms/SQL.
- [x] Build fixture matrix for league/member/team isolation, week0/boundaries/history/empty/future intervals, seasonal override/default/future/null, missing/invalid/cross-sport mappings, duplicate intervals and orphan league rows.
- [x] Run characterization on unchanged repositories; expect PASS and record original source hashes/test count.
- [x] Snapshot service/cap/ownership-lock hashes and untouched repository method source for later exact comparisons.

### Task 2: Extract and delegate

Files: new `api/utils/ownership_reads.py`; modify `api/endpoints/draft/pick_repository.py`, `api/endpoints/transaction/workflow_repository.py`; extend scoped test module.
Interfaces: `team_ownership_rows(conn, league_id, team_id, week_number, member_id=None)` returns raw result; `distinct_conference_count_rows(conn, league_id, member_id, week_number, conference_id)` returns scalar cnt result; `grouped_conference_count_rows(conn, league_id, member_id, week_number)` returns conference/count rows. No helper opens/consumes/locks/commits anything.
- [x] Write/run failing delegation tests for all six wrappers: exact args/connection, raw result identity, exception propagation and one execute per real read.
- [x] Implement helpers using fixed active-week predicate and existing conference_sql, preserving the distinct scalar and grouped query variants including missing-league semantics.
- [x] Delegate only the six methods, retaining original signatures/dispatch and other queries unchanged.
- [x] Run scoped characterization/delegation tests; expect PASS.

### Task 3: Integration and invariants

Files: extend `api/tests/test_ownership_reads.py`; add `scripts/modernization/verify_mod033.py` after user-enabled native testing; no service edits.
Interfaces: existing DraftPickService and TransactionWorkflowService entrypoints plus shared module functions from Task2.
- [x] Test actual live/manual allocation and free-agent reservation/application use supplied connection with correct post-drop count timing/history.
- [x] Test injected grouped read failure after slot closure propagates and leaves pending status/history rolled back.
- [x] Run scoped suite, MOD033A23 cap tests and full credential-free backend; expect PASS.
- [x] Verify service/cap/mutex hashes, untouched repository methods, helper import dependencies and whitespace. Inspect task-owned native availability only; document unavailable PostgreSQL rather than starting daemons/using configured DBs.

### Task 4: Review and evidence

Files: new MOD033 evidence JSON; backlog/verification/API domain docs updates.
- [x] Fresh final reviewer checks exact extraction scope against spec/plan/ledger; exclude earlier pilots.
- [x] Fix Critical/Important findings once using RED→GREEN tests and full green suite; record minors/declined scope rulings.
- [x] Record baseline/after outputs, test counts, query/connection/result invariants, unchanged source hashes and native limitations.
- [x] Mark bounded MOD033/remaining Priority7 scope complete; keep auto/trade migration/alternate retirement as explicit follow-ups and all changes uncommitted/undeployed.
