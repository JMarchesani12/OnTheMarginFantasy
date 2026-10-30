# MOD-038 Profile Creation/UUID Persistence Plan

> **For agentic workers:** Use superpowers:executing-plans inline with test-first changes and one independent final review.

**Goal:** Finish user-domain persistence extraction without changing bootstrap identity, conflict, failure or legacy model contracts.

**Architecture:** ProfileSubject(subject,email) is a transport-independent value composed only from verified JWT fields by HTTP. UserService.create_profile(subject_actor,display_name) validates input, checks at most two mapped IDs and inserts within one transaction. UserRepository executes queries on the supplied connection. Legacy creation/UUID lookup delegate to explicit trusted service methods; HTTP UUID lookup retains the existing unique principal resolver.

**Tech Stack:** Existing Flask, dataclasses, SQLAlchemy, unittest and disposable PostgreSQL. No new dependencies.

**Spec:** [Approved MOD-038 design](../specs/2026-10-29-mod-038-layering-design.md) and user's instruction to continue the next slice. Profile bootstrap identity is already required by approved MOD-041.

## Scope and constraints

- Retain existing read/update service and preserve current checkout changes.
- No app principal is required before creation; no UserActor fabricated from missing profile.
- ProfileSubject is a typed trust-boundary value, not proof of JWT verification; only middleware-derived claims populate it in HTTP composition.
- Preserve email/name trimming, creation fields, POST validation order, existing-profile 409, ambiguous mapping 403, safe constraint failure 400 and unexpected error 500.
- Preserve shared principal resolver and protected UUID endpoint behavior; legacy UUID lookup continues first-row behavior rather than acquiring new HTTP policy.
- Preserve legacy create_user(email, display_name=None, uuid=None) normalization, errors and direct-call semantics through named trusted service methods.
- No schema/index/uniqueness changes, new race guarantees, environment/production access, rate limiter, dependencies, listener or deployment.

## Review focus

- Client identity/email fields never populate ProfileSubject or override verified claims.
- Missing subject/email and malformed data still fail before writes.
- Existing/ambiguous mappings do not provision or overwrite a row.
- Integrity errors at statement or commit roll back and stay safe; unexpected errors are not misclassified.
- Legacy direct UUID lookup/creation preserve signatures and exception contracts independently of HTTP bootstrap policy.

## Task 1: Creation service and legacy UUID lookup

Files: extend user contracts/service/repository; replace remaining SQL in userModel with facade delegates; wire userEndpoints POST; create api/tests/test_user_creation_service.py.

Interfaces: frozen ProfileSubject(subject:str,email:str); ProfileAlreadyExists/ProfileIdentityAmbiguous/ProfileCreationRejected domain failures with internal codes, no HTTP status. `create_profile(subject_actor,display_name=None)`, `create_profile_for_job(email,display_name=None,uuid=None)` and `get_profile_by_uuid_for_job(uuid)`. Repository `profile_ids_for_subject(conn,subject)`, `get_by_uuid(conn,uuid)` and `insert(conn,email,display_name,uuid)`. Legacy facade translates only designated domain failures to ValueError.

- [x] Write direct-service tests for actor required before I/O, create/reload, normalization, one transaction, repeat/ambiguous denials, constraint/unexpected insert and commit rollback, legacy UUID lookup/missing outcomes and legacy create validation.
- [x] Run `python3 api/tests/run_isolated.py test_user_creation_service.py` red before implementation.
- [x] Extract SQL and normalization. Interactive creation owns the existing-profile decision and transaction; legacy direct creation intentionally retains no new existing-subject precheck.
- [x] HTTP keeps verified subject/email extraction, body/legacy identity matching and name-shape validation in their existing order; service owns existence/creation. Preserve exact error bodies/statuses and shared principal resolver.
- [x] Run new and existing profile/bootstrap suites and full guarded backend.

## Task 2: Native verification and review

- [x] Add separate marked-loopback runner/report; rerun prior native profile read/update checks before creation fixtures, then test real auth FK/email collisions, duplicate subject ambiguity, new creation, repeat denial, and statement/deferred-commit insertion rollback.
- [x] Use only task-owned cached-image container and random database; remove both after verification. No configured DSN/.env or hosted database.
- [x] Check no SQL remains in UserModel and no service/repository imports Flask/model/configured engine. Keep canonical shared principal module unchanged.
- [x] Independent final review; fix important findings with failing regressions first.
- [x] Record actual tests, historical report supersession and limits; leave current checkout uncommitted.

## Execution ledger

- Ruling: Introduce a domain-local ProfileSubject rather than reuse UserActor — bootstrap precedes a mapped application user — same verified-claims boundary, no auth bypass.
- Ruling: Merge interactive creation's at-most-two mapping check and insertion into one service transaction — service owns policy/persistence orchestration — no claim of serialized creation or unique UUID enforcement; MOD-006 remains separate.

- Fresh baseline 381/381 passes. Eight new service tests initially failed on the missing ProfileSubject contract, then passed after implementation. Existing bootstrap/profile/principal suites were not changed.
- UserModel now delegates all four methods and contains no SQL; creation/UUID builtin ValueError translation preserved. All HTTP user operations call service; removed the now-unused endpoint model construction/import after checking callers. Shared principal resolver remains unchanged.
- Interactive creation now owns its at-most-two check plus insert transaction. Verified claim/email/body mismatch/name validation order remains in the adapter, while existence/ambiguity policy is in the service. UserActor is never fabricated before provisioning.
- Full guarded backend 389/389 passes, exit 0. Independent final reviewer found no Critical/Important/Minor issues and separately ran eight new tests.
- Native PostgreSQL PASS: prior profile read/update checks rerun; new normalized creation/projection/reload/repeat conflict; duplicate UUID ambiguity; actual unique-email and auth-user FK failures; statement and deferred-commit insert failures roll back; legacy UUID/creation behavior remains compatible.
- Current profile-creation evidence supersedes earlier profile-source hashes. Historical reports were retained, not rewritten. This work does not serialize concurrent bootstrap or add UUID uniqueness; MOD-006 is unchanged.
- Approved sandbox escalation used only local Docker and a task-owned cached-image loopback container. Harness removed its random database and container otm-mod038-creation-20261029 was stopped/removed. No hosted DB, existing container mutation, dependency, listener or deployment.
- Changes remain uncommitted in current checkout. No frontend files or checks changed; prior transaction/roster source snapshots remain unchanged.
