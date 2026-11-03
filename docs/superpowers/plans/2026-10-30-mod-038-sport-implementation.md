# MOD-038 Sport Implementation Plan

> Use superpowers:executing-plans inline; test first, one fresh final review.

**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md). User approved sport next in current checkout; no repeated architecture/worktree approval needed.

**Scope:** Sport has exactly one catalog query and one GET endpoint. Add `api/endpoints/sport/service.py` (public catalog use case, owns original begin transaction) and `repository.py` (original SQL and plain mapping projection). Change `sportModel.py` into SQL-free facade preserving constructor/get_sports/db-only construction; wire `sportEndpoints.py` to service. Routes/auth public allowlist stay unchanged. No actors needed for this intentionally public catalog. No schema/dependencies/deploy/hosted access or process startup. Leave uncommitted.

## Tasks

- [x] Baseline guarded suite; real SQLite tests of public catalog exact projection/nulls, empty result, HTTP public success/error, service failure unwind and legacy db-only compatibility; watch new service cases fail first.
- [x] Extract unchanged SELECT into SportRepository.list_sports(conn), own transaction in SportService.list_sports(), retain facade and HTTP 200/500 messages.
- [x] Full guarded suite; exact original SQL AST/projection comparison and dependency checks. One fresh read-only final review, docs/evidence/diff checks.

## Verification scope

This is an unchanged provider-neutral SELECT, without parameter/type/alias/concurrency changes. Real in-memory SQLite executes the original query via the same SQLAlchemy text/result protocol; full guarded suite covers wider regressions. No Docker/native PostgreSQL run needed for this bounded catalog extraction; do not claim new PostgreSQL verification. Preserve lack of ORDER BY (no guaranteed new ordering), nulls/keys/types, one begin scope, public GET and generic error message. Avoid tests that merely assert delegation.

## Ledger

- Ruling: Canonical catalog service intentionally actor-free because /api/sports is explicitly public in current application middleware; no profile lookup, fabricated actor, or new authorization gate.
- Ruling: Composition facade resolves self.db per call, preserving legacy db-only __new__ callers and changes to db; no inherited-state machinery needed for one operation.

- Baseline518/518. RED3 missing-service errors plus3 passing original HTTP/legacy cases; GREEN6/6. Full guarded suite524/524.
- SQL text-call AST identical to original; canonical imports/SQL-free facade checked. Public allowlist/routes unchanged; no ordering guarantee or profile-resolution I/O introduced.
- Independent review /root/sport_final_review: no findings, fresh focused6/6. No implementation delegation.
- Evidence/source hashes: docs/modernization/evidence/mod-038-sport-catalog-2026-10-30.json; native not run or claimed, per verification scope. Docs/links/diff checks pass. No deploy/commit/hosted/schema/dependencies/process startup; schedule remains next backend domain.
