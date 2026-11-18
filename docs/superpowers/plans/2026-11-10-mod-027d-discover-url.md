# MOD-027D Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans. Combined design/implementation authorized.

**Goal:** Open Discover directly from its URL with fresh scoped public-preview data.
**Architecture:** Keyed route/account resolver using restricted preview helper; existing form child guarded by useRequestScope.
**Tech Stack:** React/TypeScript, existing Node harness.
**Spec:** docs/superpowers/specs/2026-11-10-mod-027d-discover-url-design.md

## Global Constraints
No backend/schema/dependencies/route changes, preserve previous working changes, no commit/deploy.

## Review Focus
Cold/seeded entries require same fresh preview; obsolete route/account work must not display or submit.

### Task 1
- [x] Add component/API regressions, observe RED.
- [x] Implement preview helper, keyed resolver and form guards; tests GREEN.
- [x] Full frontend/build/import/diff, fresh review/fix material findings, evidence/status; leave uncommitted.
