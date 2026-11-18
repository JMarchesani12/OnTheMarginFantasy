# MOD-031A Clock Extraction Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline and one fresh stage review.

**Goal:** Extract existing countdown/server offset/timer into useDraftClock without behavior changes.
**Architecture:** Hook(isLive, expiresAt) → remainingSeconds/timeLeftLabel/stable updateServerNow; page retains snapshot/status/realtime behavior.
**Tech Stack:** Existing React/TypeScript/Node tests.
**Spec:** docs/superpowers/specs/2026-11-07-mod-031a-draft-clock-design.md

## Global Constraints

Preserve all prior pilots. No immediate-tick/reset/clock policy/socket/controller/API/CSS change. Hook unconditional before page return. No backend/native/configured runtime/provider/deploy/commit/push. Stage1 only; connection follows separately.

## Review Focus

- Valid serverNow offset update ignores missing/invalid values and doesn't eagerly sample nowMs.
- One live interval; pause/complete/unmount cleanup, no restart for expiry/offset alone.
- Math/null/zero/m:ss behavior unchanged, including non-live frozen sample.
- Stable callback must not recreate realtime subscription.
- Snapshot/page wiring and prior lifecycle tests remain intact.

### Task 1: Characterization
- [x] Capture original page, extract existing test-only page harness for reuse and add controlled Date/timers/disposal.
- [x] Run actual page clock tests before extraction for timer lifecycle, offset, labels and controller stability; expect PASS.

### Task 2: Hook
- [x] Add actual hook tests, observe RED missing module.
- [x] Implement hooks/useDraftClock.ts by moving existing state/interval/arithmetic/formatting; wire page offset callback, remove duplicates.
- [x] Run clock/page/prior lifecycle suites and full frontend/build/import graph; expect PASS.

### Task 3: Review/handoff
- [x] Fresh independent scoped review; resolve material findings failure-first.
- [x] Record current evidence/status; preserve prior work; mark only clock stage complete.
- [x] Final checks and leave uncommitted.
