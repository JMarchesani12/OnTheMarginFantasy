# MOD-039 Integer Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline and one fresh final review.

**Goal:** Reuse the existing scalar integer validator in two draft HTTP consumer paths without changing behavior.
**Architecture:** Expose integer_value in requestValidation; field/list wrappers and draft pick/control parsing share that pure implementation.
**Tech Stack:** Existing Python/Flask/unittest.
**Spec:** docs/superpowers/specs/2026-11-07-mod-039-integer-parser-design.md

## Global Constraints

No behavior/API/SQL/auth/default/list-ceiling change. No configured runtime/DB/provider/dependency/deploy/commit. Existing audit checkout; leave uncommitted. Native reruns unnecessary for pure parsing changes.

## Review Focus

- Missing and malformed input precedence stays distinct.
- Optional weekNumber0 default differs from explicit null.
- Actor assertion remains verified-principal-bound; order validation remains domain-owned.
- Python integer-string forms and unbounded scalar ranges remain compatible.
- Existing field/list wrappers and their ceilings still use the same parser without I/O.

### Task 1: Characterize consumers
Files: api/tests/test_draft_integer_parsing.py.
- [x] Exercise actual JWT/HTTP/domain fixtures for valid signed/whitespace/digit strings, malformed scalar/order inputs, default/null week, missing fields and actor mismatch.
- [x] Run tests before extraction; expect PASS, establishing behavior preservation.

### Task 2: Shared parser
Files: api/utils/requestValidation.py, api/endpoints/draft/draftEndpoints.py, api/tests/test_integer_value.py.
Interface: integer_value(value, field) → int or existing ValueError message. Existing integer_field/list signatures unchanged.
- [x] Add focused public-scalar/wrapper and consumer-wiring regressions; run and observe missing public API failure.
- [x] Promote existing parser and import it in both consumers; remove local duplicates. Preserve all surrounding field/default/error/authority control flow.
- [x] Run new and existing draft/validation tests, then full isolated backend; expect PASS.

### Task 3: Verify and record pilot
- [x] Fresh independent review of full uncommitted change; fix material findings failure-first if any.
- [x] Record exact tests and inventory/non-extractions in modernization docs; mark only bounded first MOD039 pilot complete.
- [x] Diff/source check, leave uncommitted. No frontend/native rerun claims.
