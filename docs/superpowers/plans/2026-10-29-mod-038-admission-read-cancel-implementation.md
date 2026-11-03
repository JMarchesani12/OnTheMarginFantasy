# MOD-038 Admission Listing/Cancellation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-first changes and one independent final review.

**Goal:** Introduce league admission service/repository ownership for commissioner listing and own-request cancellation without changing other league operations.

**Architecture:** AdmissionService requires UserActor for new HTTP entry points and owns commissioner/owner/state policy plus one connection/transaction. AdmissionRepository owns scoped SQL and row locks. LeagueModel delegates through named legacy/trusted methods, including its existing private helper signatures; HTTP keeps body identity assertions and response contracts.

**Spec:** [Approved MOD-038 architecture](../specs/2026-10-29-mod-038-layering-design.md) and user's request to continue the next slice.

**Tech Stack:** Existing Flask/SQLAlchemy/UserActor/unittest and disposable PostgreSQL, no dependencies.

## Constraints and review focus

- Current checkout and previous pilots preserved; no folder rename, deployment, schema, listener or rate limiter.
- Listing remains commissioner-only, with missing league 400, wrong commissioner 403, exact projection/status/order and final SQL commissioner predicate. Late revocation retains empty-result behavior.
- Cancellation remains owner-only, league/request scoped, PENDING-only and row locked. Commissioner status grants no cancellation authority over another user's request. Preserve resolution fields and replay rejection.
- New interactive methods never infer trusted access from omitted actors or client job flags.
- Existing model callers include __new__ fixtures assigning only db; delegates must work without constructor-only cached state.
- Creation, approval, denial and admission serialization policy remain separate; no new concurrency guarantee beyond existing cancellation lock semantics.

## Task 1: Service and persistence

Files: create league admission_service.py, admission_repository.py, contracts.py and tests/test_admission_service.py; modify targeted LeagueModel methods and two HTTP handler calls.

Interfaces: AdmissionService(engine,repository=None). `list_requests(actor,league_id,status=None)` and `cancel_request(actor,league_id,request_id)`. Named integer-reader/owner bridges preserve legacy verified IDs; trusted listing is an explicit job method. Private model _list_join_requests retains scope-only behavior without adding a precheck; _get_league_commissioner/_ensure_commissioner signatures stay compatible. Domain AdmissionDenied/AdmissionRejected are translated at HTTP/model boundaries. Repository accepts conn, executes original queries and does not open connections or commit.

- [x] Write real-fixture direct-service tests: actor required before I/O, one read connection, projection/filter/order, commissioner denial/revocation, owner cancellation/replay, wrong owner/league denial and rollback after update.
- [x] Run focused red, implement queries/service and facade/HTTP wiring.
- [x] Preserve model __new__ caller behavior and private listing semantics; run unchanged listing/cancellation/approval/denial/create authorization suites plus full guarded backend.

## Task 2: Native SQL and review

- [x] Native marked-loopback PostgreSQL checks for listing projection/filter/revocation and cancellation scope/owner/state, statement/commit rollback and competing cancellation lock/replay behavior.
- [x] Only new task-owned cached-image container/random DB; remove both afterward, no .env/arbitrary DSN/hosted access.
- [x] Verify untouched model methods via AST, new module dependency boundaries and existing caller/patch paths.
- [x] Independent final review; fix important findings with failing regressions first.
- [x] Update evidence/progress/backlog; keep changes uncommitted. No frontend checks for backend-only extraction.

## Execution ledger

- Ruling: Select listing + cancellation only — distinct commissioner and applicant authority plus bounded SQL/lock paths — approval/admission serialization and other league operations remain unchanged.
- Ruling: Construct lightweight admission service at model delegation boundaries rather than require cached constructor state — existing tests/legacy callers use LeagueModel.__new__ with only db — preserve those actual callers without service-to-model dependencies.

- Baseline guarded backend 406/406 passes. Six direct service tests initially failed on the missing module, then passed with real fixture SQL. Existing listing/cancellation/approval/denial/create and league tests remain unchanged.
- HTTP listing/cancel branches use UserActor and domain-specific error translation; other handler bodies unchanged. Model getter/list/cancel delegates preserve signatures, builtin errors, private scope-only behavior and db-only __new__ callers.
- Full guarded backend 412/412 passes. Independent final reviewer found no Critical/Important/Minor findings; it compared original SQL and callers/patches but did not independently execute tests.
- Native PostgreSQL PASS: listing projection/status/order and separate-connection commissioner revocation; owner/URL/status cancellation rules; rollback after executed UPDATE and deferred commit; observed competing cancellation lock wait, one transition and replay rejection through direct service and legacy facade. Null resolver and private helper semantics preserved.
- AST comparison confirms all non-target LeagueModel methods unchanged. Admission service/repository import no Flask, model or configured engine; repositories own no transactions.
- Approved sandbox escalation used only a new cached-image task-owned loopback container; random database removed by harness and container otm-mod038-admission-20261029 stopped/removed. No hosted DB, schema migration, frontend/dependency, listener or deployment changes.
- Creation/approval/denial and concurrent-admission-capacity policy remain out of scope. Changes remain uncommitted in the requested current checkout; earlier pilot work preserved.
