# MOD-038 Profile Read/Update Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-first changes and one independent final review.

**Goal:** Continue the approved hybrid in the user/profile domain by extracting own-profile reads and updates while preserving bootstrap and existing model behavior.

**Architecture:** UserService requires canonical UserActor, owns resource authorization, allowed update fields and connection/transaction boundaries. UserRepository executes supplied-connection ID reads/updates. UserModel preserves trusted ID-only methods through explicit job entry points; UUID lookup and creation remain existing implementations.

**Tech Stack:** Existing Flask, SQLAlchemy, UserActor, unittest and marked disposable PostgreSQL.

**Spec:** [Approved incremental hybrid](../specs/2026-10-29-mod-038-layering-design.md), continued by the user's instruction to implement another domain.

## Scope and alternatives

Profile ID reads and updates are a small real read/command pair with clear ownership policy. Sport remains a cohesive single query and scoring/schedule have wider correctness/provider dependencies. Do not change account provisioning, unique constraints, the shared principal resolver or token contracts. This is an incremental slice within user, not a claim that creation has migrated.

## Global constraints

- Current checkout and prior transaction/roster changes remain intact.
- Preserve SQL projections, field allowlist, response/error bodies/statuses and validation order; no wire/API/schema changes.
- Preserve private-profile concealment and denial before parsing a foreign target's malformed body.
- Bootstrap UUID lookup still verifies subject and resolves a unique application identity. Creation remains on its existing path and tests.
- No new dependencies, paid infrastructure, production access, listener startup or deployment.

## Review focus

- Missing actor/forged body IDs cannot select trusted access or overwrite another profile.
- Foreign-target denial precedes JSON parsing and invalid update handling.
- Only displayName may be updated; identity/contact fields remain unchanged.
- Existing missing/ambiguous profile and UUID bootstrap outcomes must remain distinct.
- A failed update must roll back and not expose SQL/contact details in HTTP errors.

## Task 1: Profile service/repository

Files: create `api/endpoints/user/contracts.py`, `service.py`, `repository.py`, `api/tests/test_user_service.py`; modify `userModel.py` and `userEndpoints.py`.

Interfaces: UserService(engine, repository=None), `require_profile_owner(actor, user_id)`, `get_profile(actor, user_id)`, `update_profile(actor, user_id, updates)`, explicit `get_profile_for_job(user_id)` and `update_profile_for_job(user_id, updates)`. Domain failures ProfileAccessDenied, ProfileNotFound and ProfileUpdateRejected carry internal codes, no HTTP statuses. Canonical ALLOWED_USER_FIELDS remains exported by userModel for compatibility. Repository `get_by_id(conn,user_id)` returns dict or None; `update(conn,user_id,payload)` only emits columns from the fixed allowlist. Service filters fields and rejects empty allowed updates before opening a transaction.

- [x] Write direct service tests using actual disposable profile SQL: actor required before I/O, foreign denial, read projection, allowed-field filtering, one transaction, empty update denial, missing row and persistence failure rollback.
- [x] Run `python3 api/tests/run_isolated.py test_user_service.py` red, then implement the smallest extraction preserving current SQL/results.
- [x] Keep model signatures/built-in ValueError compatibility. HTTP ID read and resolved UUID read use actor service. PATCH invokes the service's owner check before body parsing and service update rechecks policy.
- [x] Run all profile/bootstrap/principal regressions and full guarded backend suite.

## Task 2: Native persistence and review

- [x] Add marked-loopback disposable PostgreSQL verification for exact profile projection, own update/field filtering, foreign denial, missing resource and actual statement/commit failure rollback. Preserve earlier evidence files.
- [x] Verify import boundaries and no service/repository → Flask/model/configured-engine imports.
- [x] One independent reviewer checks scope, error/status compatibility, actor ownership, pre-parse denial, legacy callers and bootstrap preservation. Fix important findings with failing regressions first.
- [x] Record evidence and scoped completion; remove task-owned database/container, keep changes uncommitted for review. No frontend rerun for backend-only extraction.

## Execution ledger

- Ruling: Extract ID read/update only — creation requires verified-subject bootstrap semantics distinct from an existing UserActor — creation/UUID SQL remain compatibility implementations; no fabricated principal or new bootstrap policy.
- Ruling: Reuse UserActor and explicit job methods, preserve ALLOWED_USER_FIELDS import and flat test fixtures — consistent with earlier pilots — no new generic CRUD base or framework.

- Fresh baseline 373/373 passes. Eight new direct-service/adapter tests initially failed on the absent service, then passed after extraction; existing profile/bootstrap/principal tests were not changed.
- ID model reads/updates now delegate to explicit trusted service entry points with built-in ValueError translation. HTTP actor calls move owner policy into service; PATCH uses the same service owner policy before parsing and before persistence to preserve foreign-target concealment/order.
- AST comparisons verify create_user and legacy get_user_by_uuid in UserModel, plus HTTP creation, remain unchanged. ALLOWED_USER_FIELDS remains an exported compatibility alias of the canonical fixed domain allowlist.
- Full guarded backend 381/381 passes, exit 0. Independent review found no Critical/Important/Minor findings and independently ran the eight new tests.
- Native PostgreSQL PASS: own projection/update, identity/contact field filtering, bound string parameters, foreign/invalid update denials, missing profile and trusted legacy facades. Synthetic BEFORE UPDATE and deferred constraint triggers prove rollback on real statement failure and commit failure.
- Approved sandbox escalation provided local Docker access. Used only a new task-owned cached-image loopback container; random test database removed by the harness and container otm-mod038-profile-20261029 stopped/removed. No configured/hosted database, existing-container change, dependency, deployment or listener startup.
- Service/repository dependency inspection and guarded tests pass; earlier transaction/roster source hashes remain unchanged. No frontend files changed or frontend checks rerun.
- Changes remain uncommitted with the earlier pilots in the requested current checkout; no push, merge or publication performed.
