# MOD-039 Settings Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, then one fresh final review.

**Goal:** Remove Manage League's identical settings parser by importing its existing shared implementation.
**Architecture:** Pure shared helper unchanged; Manage League retains its own mapper/form/fetch behavior.
**Tech Stack:** Existing TypeScript/React/Node tests.
**Spec:** docs/superpowers/specs/2026-11-07-mod-039-settings-normalization-design.md

## Global Constraints

Preserve prior uncommitted backend pilot. No shared-helper/API/default/current-week/freshness/auth/storage/backend/SQL/dependency change. Leave uncommitted/undeployed; no configured runtime/provider/native DB.

## Review Focus

- Falsy inputs versus valid JSON falsy primitives keep different parsing results.
- Existing League branch keeps original malformed settings; SingleLeague branch uses defaults.
- Manage League clears current-week fields while shared mapper preserves them.
- Actual component binding imports shared helper without changing local mapper/effects/form initialization.
- No weakening of runtime semantics into a new schema validator.

### Task 1: Characterize actual functions
Files: front-end/tests/leagueSettingsNormalization.test.ts.
- [x] Load actual nested mapper declarations via TypeScript AST and existing shared module, without copying algorithms.
- [x] Verify helper inputs and mapper branch/fallback/current-week cases before extraction; expect PASS.

### Task 2: Reuse shared helper
Files: ManageLeaguePage.tsx and focused test.
- [x] Assert actual shared import/binding is used by the local mapper; run and observe RED with duplicate local function.
- [x] Import normalizeLeagueSettings and remove only its local duplicate.
- [x] Run focused/full frontend tests and production TypeScript/build; expect PASS.

### Task 3: Review/evidence
- [x] Fresh independent review of this frontend-only pilot; resolve material findings failure-first.
- [x] Record source hashes, exact checks and inventory/non-extractions; preserve backend pilot hash evidence.
- [x] Final diff check; leave uncommitted with bounded MOD039 status.
