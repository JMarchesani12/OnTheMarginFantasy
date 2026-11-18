# MOD-004 Owner Hardening Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline; one fresh scoped final review.

**Goal:** Prepare and test an unapplied owner-scoped public privilege transition and exact recovery.

**Architecture:** Versioned SQL review package with exact catalog guards, expected-state JSON and checksummed manifest. Disposable PostgreSQL acceptance uses a nonsuperuser owner and synthetic objects only.

**Tech Stack:** PostgreSQL 17.6, Python, psycopg2, Docker.

**Spec:** `docs/superpowers/specs/2026-11-18-mod004-owner-hardening-design.md`

## Global Constraints

No production grants, app rows, role elevation, provider-default changes or Git integration. Preserve the current user-owned checkout. Use fresh ACL evidence; do not rewrite frozen baseline or old proposal. Production execution requires separate approval after review.

## Review Focus

Drift must refuse before mutation; failed postconditions must roll back. Effective inherited/PUBLIC/column privileges must not survive. Recovery must refuse new objects or unrelated grants. Service and provider defaults must remain intact. Tests must use the exact shipped SQL as a nonsuperuser.

### Task 1: Versioned proposal and native acceptance

**Files:** Create `db/proposals/mod004-owner-v1/{apply.sql,recovery.sql,state-query.sql,before.json,after.json,manifest.json,README.md}`, `scripts/modernization/verify_mod004_owner.py` and a dated acceptance receipt. Update closeout notes.

**Interfaces:** SQL accepts no arguments and owns BEGIN/COMMIT; expected-state JSON is the exact result of state-query.sql. The verifier accepts no remote configuration or credentials.

- [x] Write and run acceptance against missing proposal; observe explicit missing-package failure.
- [x] Implement guarded SQL, preserved-boundary checks and exact recovery.
- [x] Run isolated native acceptance for clean apply, replay refusal, drift, rollback, future defaults and recovery.
- [x] Verify checksums and review once; no material findings; one minor input-provenance self-check deferred with independently verified current hash.
- [x] Record evidence and remaining acceptance gates. Production approval is deliberately not requested until the pending acceptance/configuration checks are answered.

No commits or branch changes: integration remains maintainer-owned.
