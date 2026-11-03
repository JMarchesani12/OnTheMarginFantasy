# MOD-038 Admission Creation/Denial Plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-first changes and one independent final review.

**Goal:** Extend admission service/repository ownership to applicant request creation and commissioner denial, preserving existing HTTP/legacy behavior.

**Architecture:** AdmissionService owns actor/state policy and transactions. Creation checks membership then returns the existing pending request or inserts. Interactive denial locks the league and verifies commissioner before locking the request and resolving it; named trusted denial retains its established bypass. Repository methods accept supplied connections and contain only SQL.

**Spec:** [Approved MOD-038 architecture](../specs/2026-10-29-mod-038-layering-design.md) and user's request for the next slice.

**Tech Stack:** Existing Flask, SQLAlchemy, UserActor, unittest and disposable PostgreSQL; no dependencies.

## Constraints and review focus

- Preserve current checkout and previous slices; no approval/capacity/schema/startup changes.
- Creation retains team-name trimming/validation before persistence, membership-first check, existing-pending replay without overwrite, SQL fields/projection and 201 HTTP status on repeat.
- Preserve raw database failures as unexpected operational failures, not new client errors; no new missing-league precheck or uniqueness claim.
- Denial retains League FOR UPDATE → request FOR UPDATE lock order, verified commissioner authority, URL league/request scope, PENDING guard and resolver attribution.
- Trusted model denial intentionally keeps its no-commissioner-check semantics through an explicitly named service entry point, unavailable from HTTP body flags.
- Model/private helper signatures and db-only __new__ callers remain compatible; HTTP identity assertion checks/order/messages stay unchanged.

## Task 1: Policy and persistence

Files: extend league admission_service.py/admission_repository.py, targeted leagueModel.py methods and HTTP join_request/deny_join calls; create tests/test_admission_create_deny_service.py.

Interfaces: `create_request(actor,league_id,message=None,team_name=None)` and named legacy user-ID bridge; `deny_request(actor,league_id,request_id)`, named legacy verified-commissioner bridge, `deny_request_for_job(league_id,request_id,acting_user_id)`, and connection-aware `deny_request_in_transaction(conn,league_id,request_id,acting_user_id)`. Existing AdmissionDenied/AdmissionRejected translated at boundaries. New repository membership/pending/insert/league-lock/request-lock/update methods preserve actual SQL.

- [x] Write direct-service tests for actor requirement, normalized create/replay, member rejection, insertion rollback, commissioner/URL/status denial, attribution/replay, update rollback and trusted compatibility.
- [x] Run focused red, implement extraction and HTTP/model delegates; preserve the private _deny helper's connection contract.
- [x] Run all existing admission authorization suites unchanged and full guarded backend.

## Task 2: Native SQL/review/evidence

- [x] Rerun previous admission list/cancel native checks, then exercise creation/replay/FK failures and insert statement/commit rollback.
- [x] Native denial tests: commissioner/scope/state, resolver fields, post-update/commit rollback, competing league/request lock waits, single transition/replay and legacy trusted bypass.
- [x] Task-owned cached-image marked-loopback server/random DB only; no .env/DSN/hosted access; clean resources afterward.
- [x] Check untouched methods via AST and service/repository dependencies; independent final review, important fixes test-first.
- [x] Record evidence/historical hash supersession and remaining approval scope; leave current checkout uncommitted. No frontend checks required.

## Execution ledger

- Ruling: Extract creation + denial, keep approval separate — these have bounded existing rules/lock paths; admission capacity/approval correctness remains outside this chunk.
- Ruling: Preserve trusted denial bypass only as a named job method and existing facade — actual legacy tests require it — HTTP always constructs UserActor and selects checked denial.

- Baseline: guarded backend 412/412. Focused RED: six missing-method errors and one passing trusted compatibility case; GREEN: all seven new direct-service tests pass. Final guarded backend exit 0, 419/419; existing authorization tests unchanged.
- Native marked-loopback PostgreSQL: creation normalization/repeat/member/FK failures, insert statement/deferred commit rollback; denial authority/scope/resolver, post-update/deferred commit rollback, service/facade observed lock waits with league→request order, one transition/replay rejection; trusted/private helper compatibility. Prior listing/cancellation checks rerun successfully. [Evidence](../../modernization/evidence/mod-038-admission-create-deny-postgres-2026-10-29.json) supersedes previous admission hashes; old reports retained.
- AST comparison: all non-target LeagueModel methods unchanged; dependency checks pass. Independent final reviewer: no Critical/Important/Minor findings; standalone reviewer import lacked SUPABASE_PROJECT_ID, so guarded parent tests provide execution evidence. No review fixes required.
- Random database removed by harness; task-owned container removed. Working changes left uncommitted. Approval/capacity and concurrent-creation uniqueness remain separate; no schema/frontend/dependency/hosted/startup/deployment changes.
