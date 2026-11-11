# MOD-028B Safe Create/Join Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans, established inline execution.

**Goal:** Safe actionable create/join errors without mutation replay or input loss.
**Architecture:** Shared trusted error parser/formatter; only two API failure branches and form catches migrate.
**Tech Stack:** TypeScript/React, existing Node controlled harness, native Response.
**Spec:** docs/superpowers/specs/2026-11-11-mod-028b-safe-create-join-design.md

## Global Constraints
No auth transport/retry/backend/schema/dependency changes; preserve user work; no commit/deploy.
## Review Focus
Raw errors must never become display authority; status/body mismatches must not suggest wrong action; uncertain outcomes must not encourage blind resubmission.
### Task 1
- [x] Parser/status/shape/hostile payload and actual form/API integration tests RED.
- [x] Implement shared helper, migrate create/join API failures and UI catches; GREEN/full frontend/build/import/diff.
- [x] Fresh read-only review; material fixes RED→GREEN, bounded pilot audit evidence. Remaining consumers stay open.
