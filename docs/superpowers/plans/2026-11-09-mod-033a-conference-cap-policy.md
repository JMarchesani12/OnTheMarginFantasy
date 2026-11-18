# MOD-033A Conference Cap Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Zero permits no teams, positive values set the limit, and invalid/missing caps fail as configuration errors across acquisition and reporting.
**Architecture:** A pure cap validator supplies one interpretation to existing draft/transaction boundaries. Reporting validates all active roster count groups before filtering violations, exposing missing effective mappings. Ownership/count SQL extraction stays separate.
**Tech Stack:** Python, SQLAlchemy, existing guarded unittest/SQLite fixtures; optional marked local PostgreSQL verifier.
**Spec:** docs/superpowers/specs/2026-11-09-mod-033a-conference-cap-policy-design.md

## Global Constraints

- Preserve authorization, ownership locks/connections, acquisition timing/history, positive cap behavior and success payloads.
- No unlimited sentinel, retroactive eviction, schema migration, shared ownership-read extraction, commit or deployment.
- Continue inline in established audit workspace; preserve all prior uncommitted work.
- Missing/negative/invalid stored caps are configuration errors; zero is valid and blocks acquisitions.

## Review Focus

- Auto-pick must skip a valid zero bucket but roll back on an encountered invalid cap.
- Trade limit lookup must not silently default a missing limit to 999.
- Invalid caps/mappings cannot vanish through roster-report joins/HAVING.
- Zero-cap drop-only reduction remains legal without forcing existing rosters compliant.
- Application failures after slot closure must roll back and remain pending/retryable.

### Task 1: Shared cap interpretation and draft

Files: create `api/utils/conference_caps.py`, `api/tests/test_conference_cap_policy.py`; modify `api/endpoints/draft/pick_service.py`.
Interfaces: `require_conference_cap(value, conference_id=None) -> int` returns nonnegative int, raises ValueError with configuration message on invalid values.
- [x] Characterize current positive-cap draft/transaction tests using isolated runner.
- [x] Write/run failing tests for policy values and real live/manual zero rejection, auto zero fallback/exhaustion and invalid cap rollback.
- [x] Implement validator; remove draft unlimited bypass; validate auto bucket caps while preserving ordinary no-team behavior and SQL count semantics.
- [x] Run scoped cap suite and draft tests; expect PASS and unchanged failed-command state.

### Task 2: Transaction cap configuration

Files: modify `api/utils/conference_membership.py`, `api/endpoints/transaction/service.py`, `api/endpoints/transaction/workflow_service.py`; add scoped tests in `test_conference_cap_policy.py`.
Interfaces: existing required mapping return maps carry validated caps; transaction incoming limits use explicit validation without a 999 fallback. Service interfaces/ordinary violation errors unchanged.
- [x] Write/run failing tests for invalid/missing caps in free-agent submission/application and trade proposal/acceptance/application; missing incoming limit must reject without writes.
- [x] Validate caps in required mappings and direct free-agent conference-info/application comparisons, plus trade limits actually used for incoming teams. No global validation of unrelated conferences.
- [x] Assert zero and positive full/equal limits, drop-before-add and zero drop-only history reduction, supplied-connection reuse and rollback.
- [x] Run scoped policy plus all transaction authorization/application/workflow tests; expect PASS.

### Task 3: Roster reporting

Files: modify `api/endpoints/transaction/workflow_repository.py` and `workflow_service.py`; add reporting cases to scoped test module.
Interfaces: public `get_week_roster_violations(league_id,week_id)` list shape preserved. Repository returns active roster count groups before cap filtering, including missing effective configuration.
- [x] Write/run failing report tests for zero active/empty roster, negative/NULL caps and missing/invalid-season mappings; valid positive outputs unchanged.
- [x] Use bounded left joins to expose missing effective membership, retain league-season/sport scope, remove SQL HAVING and validate/filter in service. Do not change ownership cardinality/count semantics.
- [x] Run full isolated backend suite; inspect native verifier requirements and run marked local-only checks if available/relevant; record any unavailable coverage without claiming it.

### Task 4: Review and evidence

Files: new MOD-033A evidence JSON, backlog/verification updates.
- [x] Fresh final reviewer reads spec/plan/scoped files/tests and ledger; exclude prior audit pilots.
- [x] Fix Critical/Important findings once with reproducing RED→GREEN tests and green full suite; document deferred Minor findings and scope limits.
- [x] Verify source/import/diff checks and preserve previous MOD-029 source hashes; record commands/counts/source hashes and native coverage limits.
- [x] Mark MOD-033A prerequisite complete and MOD-033 read pilot pending; leave changes and ledger uncommitted/undeployed.
