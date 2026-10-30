# MOD-038 Roster Domain Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline with test-first changes and one independent final review.

**Goal:** Continue the user-approved incremental hybrid in the roster domain, preserving both existing roster reads and legacy model interfaces.

**Architecture:** RosterService owns resource access, locked-week selection and one connection per use case. RosterRepository owns existing scoped SQL on supplied connections. HTTP calls actor-requiring services; RosterModel delegates and preserves built-in errors and trusted direct callers.

**Tech Stack:** Existing Flask, SQLAlchemy/raw SQL, canonical UserActor, unittest, optional disposable PostgreSQL validation. No new dependencies.

**Spec:** [Approved MOD-038 design](../specs/2026-10-29-mod-038-layering-design.md). User authorized another domain using this same architecture; roster selection is the implementer's choice.

## Scope and alternatives

Roster is selected because it has meaningful week-selection orchestration, multi-query access checks and demonstrated policy reuse. Sport is already a cohesive single query; layering it adds little value. Scoring has wider correctness/lifecycle dependencies and is deferred. This is content extraction within the existing roster directory, not a folder migration or new behavior design.

## Global constraints

- Work in current checkout; preserve all existing transaction pilot changes.
- No schema changes, deployment, rate limiter, dependencies or listener startup.
- Preserve both HTTP route paths, response projections/statuses, SQL filters/order and resource-specific denials.
- Preserve trusted None-reader behavior only in model facades and explicit service job methods, never by omitting a new interactive actor.
- Keep current semantics for a missing requested week, a locked week with no future unlocked week, pending adds/drops, seasonal conferences and tier fallback.

## Review focus

- Commissioner full-read access must not become owned-member write authority.
- Missing actor or body-supplied user/job flags cannot select trusted access.
- Access revocation or target-member removal after initial authorization must still suppress result rows.
- Locked-week forwarding must use the next unlocked week's ID for pending-move filtering.
- Legacy helper signatures and missing-resource/error behavior must remain compatible.

## Task 1: Service and persistence extraction

Files: create `api/endpoints/roster/contracts.py`, `service.py`, `repository.py`, `api/tests/test_roster_service.py`; modify `rosterModel.py`, `rosterEndpoints.py`.

Interfaces: RosterService(engine, repository=None); actor methods `get_member_teams_for_week(actor, league_id, member_id, week_number)` and `get_available_teams_for_week(actor, league_id, week_number)`. Explicit `..._for_job` methods preserve trusted callers. Explicit `..._for_legacy_reader(user_id, ...)` bridges verified integer-only readers without inventing subjects. Domain failures RosterAccessDenied and RosterWeekUnavailable carry internal codes and messages without HTTP status. Repository methods accept conn and obtain facts/projections only. Shared full-read scope comes from utils.authorization, never LeagueModel.

- [x] Write direct service tests using existing disposable roster/available fixtures and a test-only connection owner. Assert required actor before I/O, one connection, read policy, late revocation, locked-week filtering and trusted missing-league semantics.
- [x] Run `python3 api/tests/run_isolated.py test_roster_service.py` red before new implementation.
- [x] Move SQL with predicates/projections/order preserved; service decides access and forwarding. No repository engine/commit.
- [x] Wire HTTP to UserActor services; keep RosterModel method and helper signatures through delegates, translating domain failures to PermissionError/ValueError only at compatibility boundaries.
- [x] Run all existing roster suites and full guarded backend suite.

## Task 2: Native SQL and review

- [x] Extend disposable marked-loopback verification with roster fixtures and native SQL checks for seasonal joins/tier fallback, pending moves, authorization and query-time revocation. Keep transaction evidence untouched by using a separate roster report.
- [x] Use only a new task-owned cached-image container, random test database and existing marker checks; remove both afterward. If infrastructure is unavailable record remaining PostgreSQL acceptance honestly.
- [x] Verify guarded imports and new module dependency boundaries.
- [x] One independent reviewer checks the diff, compatibility callers, actor trust, scoped queries and week semantics; fix important findings with regressions first.
- [x] Record fresh verification, scoped completion and remaining domains in modernization docs. No frontend rerun needed for backend-only content extraction.

## Execution ledger

- Ruling: Select roster as the next domain under the already-approved hybrid — meaningful orchestration and policy reuse justify the layers; sport would add mostly pass-through methods, scoring would widen scope.
- Ruling: Preserve the named legacy-reader bridges and flat test placement from the transaction pilot — avoid fabricated subjects and broken fixture imports; no cross-domain class hierarchy introduced.

- Baseline 366/366 passes. Seven new service tests initially failed on the missing module; after extraction, the real scoped query exposed a missing whitespace separator before the policy predicate. Corrected the query, then all seven passed.
- Both HTTP reads now construct UserActor from the existing resolved principal and call RosterService; the model facade retains legacy methods, helper signatures and PermissionError/ValueError translation. No model-to-service-to-model cycle.
- Full backend suite 373/373 passes, exit 0. Existing roster tests were not changed. Independent review separately ran 26/26 across the new and three existing roster suites and found no Critical/Important issues.
- Final: minor (deferred): HTTP endpoint keeps constructing its compatibility model even though the reads call the service. One unused lightweight object; no connection/engine allocation. Cleanup can remove it in later composition work.
- Native PostgreSQL PASS: locked-week forwarding selects the correct pending-move week, native projections/order, seasonal conferences and sport-local tier fallback preserved, commissioner/member/outsider outcomes preserved, separate-connection revocation and target removal suppress rows, missing future week fails explicitly.
- Local Docker socket required approved sandbox escalation. Used only cached image/new task-owned loopback container; harness removed its own random database and container otm-mod038-roster-20261029 was stopped/removed. No configured/hosted database, existing container changes or deployment.
- Guarded import/dependency inspection passes: service/repository have no Flask, model facade, dotenv or configured-engine imports. Existing transaction pilot source hashes remain unchanged.
- Changes remain uncommitted in the requested current checkout. No frontend files or dependencies changed; no frontend checks rerun for this backend-only extraction.
