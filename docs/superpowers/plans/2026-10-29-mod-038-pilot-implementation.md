# MOD-038 Transaction Pilot Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline with test-first changes and one final independent review.

**Goal:** Extract a protected transaction-list read and trusted trade application into domain-local services/repositories while preserving existing HTTP/model/job behavior.

**Architecture:** HTTP resolves UserActor and calls TransactionService. Services own connections, authorization and transactions; TransactionRepository executes SQL on supplied connections. Legacy models delegate and translate domain failures into their established built-in exceptions.

**Tech Stack:** Existing Flask, SQLAlchemy/raw SQL, dataclasses, unittest and disposable PostgreSQL. No new dependencies.

**Spec:** [Approved design](../specs/2026-10-29-mod-038-layering-design.md), approved by the user's instruction to implement.

## Global constraints

- Use the current checkout per the user's established preference; preserve unrelated changes.
- No new framework, deployment, paid service, schema change, listener startup or rate limiter.
- Preserve projections/statuses, scoped authorization, lock order, deadlines, ownership intervals, replay rejection, rollback and None success.
- Separate content extraction from any later import-only folder move. No domain folder move here.

## Review focus

- A missing interactive actor cannot select trusted reads.
- Commissioner read access never grants member write ownership.
- Query-time revocation must still suppress data after an initial access check.
- Advisory dispatcher state cannot replace the locked state check.
- Legacy helper callers and monkeypatches must not silently lose compatibility.

## Task 1: Connection-scoped read and canonical actor

Files: create `api/actors.py`, `api/endpoints/transaction/contracts.py`, `service.py`, `repository.py`, `api/tests/test_transaction_service.py`; modify `api/utils/authorization.py`, `api/endpoints/league/leagueModel.py`, `api/endpoints/transaction/transactionModel.py`, `transactionEndpoints.py`.

Interfaces: frozen UserActor(user_id:int, subject:str). Domain exceptions TransactionAccessDenied, TransactionNotFound, TradeRejected carry internal codes/messages without HTTP status. `TransactionService(engine, repository=None).list_transactions(actor, league_id, status=None)` requires UserActor. `list_transactions_for_job(league_id, status=None)` preserves actual trusted legacy readers. `list_transactions_for_legacy_reader(user_id, league_id, status=None)` is a compatibility-only bridge for existing verified integer-reader calls, without inventing a subject. Repository `league_read_allowed(conn, league_id, user_id)` and `list_transactions(conn, league_id, status=None, reader_user_id=None)` preserve actual SQL and query-time access scope. Pure `league_read_scope` moves out of LeagueModel; its old static method delegates.

- [x] Write direct service tests for required actor, commissioner/member projection, nonmember denial, late revocation and one connection for both queries, using existing disposable fixtures.
- [x] Run `python3 api/tests/run_isolated.py test_transaction_service.py`, observe missing behavior, then implement read service/repository/policy extraction.
- [x] Wire the existing HTTP read to the service with a real actor; retain model facade signatures and trusted None-reader compatibility through explicitly named service entry points.
- [x] Run focused and full isolated backend suites.

## Task 2: Trusted trade apply and minimum validation closure

Files: extend domain contracts/service/repository; modify TransactionModel's apply_trade, _validate_trade and _assert_trade_deadline to compatibility delegates. Retain dispatcher/free-agency paths and unrelated model operations.

Interfaces: service `apply_trade_for_job(transaction_id)->None`, `validate_trade_in_transaction(conn, league_id, week_number, from_member_id, to_member_id, from_team_ids, to_team_ids)->None`, `assert_trade_deadline_in_transaction(conn, league_id)->None`. Repositories supply locked transaction facts, deadline/week facts, ownership/conference facts and close/insert/complete SQL. No repository has an engine or commits. Existing model helper signatures remain intact; translate known domain failures into ValueError only at legacy boundaries.

- [x] Write direct-service replay/state/rollback tests, including a tracked connection that forbids nested connection acquisition during the command and rejects after a failure injected between closure/insertion.
- [x] Run new tests red, then extract SQL without changing predicates, order, lock or query semantics; put decisions in services.
- [x] Run existing HTTP trade-action/proposal/free-agency/trusted job and application-guard suites, plus the full isolated suite.
- [x] Rerun disposable PostgreSQL direct/dispatcher concurrent-apply tests using the existing marked-loopback harness; do not use any configured database. If Docker is unavailable record concurrency acceptance as outstanding, never infer it from SQLite.

## Task 3: Integration review and evidence

- [x] Verify imports under the existing credential/network guard; no service/repository-to-Flask/model/configured-engine dependencies, no cycles in new module edges.
- [x] Have one independent final reviewer examine actor trust, facade compatibility, scoped reads, validation closure, atomicity and SQL lock preservation.
- [x] Fix important findings with a failing regression before code changes; run focused and full suites afterward.
- [x] Update MOD-038 approval, MOD-040 bounded pilot status, progress and verification with fresh results and any remaining limits. Leave changes reviewable in the current checkout without deployment/push.

## Execution ledger

- Baseline: current checkout clean at entry; prior MOD-041 changes have been committed externally since the last turn. No pre-existing working changes to overwrite.
- Ruling: Keep a named legacy-reader bridge requiring an integer user ID, separate from the new actor API and the trusted job API — old model callers have a verified ID but no subject — avoids fabricating an authenticated subject or breaking caller signatures.

- Fresh baseline: guarded backend 359/359 passed. Seven new service tests initially failed on the absent actor/service modules, then passed with real fixture SQL after extraction.
- Extracted protected listing into actor-requiring service and connection-scoped repository; query-time SQL access predicates remain in place. Legacy integer-reader and trusted-reader facades remain explicit and preserve actual existing callers.
- Extracted trusted application plus the minimum deadline/ownership/conference helper closure; existing helpers delegate and translate domain failures to legacy ValueError/PermissionError at compatibility boundaries. No service-to-model back dependency.
- Fresh full isolated suite: 366/366 passes, exit 0. Independent final reviewer separately ran 7/7 service tests and found no Critical/Important/Minor issues or affected monkeypatch callers.
- Disposable PostgreSQL: direct and dispatcher paths both observed lock wait, single transfer, correct ownership intervals and compatible replay rejection. Native read projection, commissioner/member policy and separate-connection membership revocation checks pass. Results/source hashes are in the dated pilot evidence file.
- Docker socket access required sandbox escalation, which was approved. Only a new task-owned cached-image container on loopback port 55439 was used; harness removed its random database and the task-owned container was stopped/removed. Existing containers were untouched. No configured/hosted database access, deployments, dependencies or listener startup.
- Dependency inspection and guarded import/tests verify no new Flask/model/configured-engine imports in actor/service/repository/policy modules. No cycles added in these dependency edges.
- Ruling: Keep tests flat under api/tests to retain existing discovery and fixture imports — domain-local source organization does not require moving existing test fixtures — future test-folder migration remains optional and separately reviewable.
- Final review deferred no minor findings. Existing HTTP trade-response connection behavior and broader MOD-033 ownership/conference consolidation remain explicitly out of this pilot; no new guarantees are claimed for those paths.
- Changes remain reviewable and uncommitted in the requested current checkout. No branch merge, push or publication performed.
