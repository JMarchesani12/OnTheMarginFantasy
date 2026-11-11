# MOD-028B Transaction Errors Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans, established inline execution.

**Goal:** Extend shared safe parsing to roster/trade mutation feedback.
**Architecture:** Five API failure branches and five existing mutation catches; reuse parser and refresh scopes.
**Tech Stack:** React/TypeScript, existing Node harness/native Response.
**Spec:** docs/superpowers/specs/2026-11-11-mod-028b-transaction-errors-design.md
## Global Constraints
No read/auth/backend/schema/timing changes, automatic retries, payload changes or deployment/commits.
## Review Focus
Failure must retain form state and not invalidate success resources; uncertain outcomes must not imply ownership changed.
### Task 1
- [x] Actual API/page/panel regressions RED.
- [x] Shared message mappings and five mutation paths GREEN; existing scope/refresh tests/full suite/build/import/diff.
- [x] Fresh review/fix material findings and record bounded batch status/evidence.
