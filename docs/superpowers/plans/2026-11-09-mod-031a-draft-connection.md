# MOD-031A Connection Hook Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline and one fresh stage review.

**Goal:** Move page connection wiring into useDraftConnection while retaining the actual controller identity and behavior.
**Architecture:** Hook owns Socket.IO/controller effect and member refresh; parent supplies snapshot loader/apply/clear/state callbacks. createDraftRealtime unchanged.
**Tech Stack:** React/TypeScript, existing Node controlled tests.
**Spec:** docs/superpowers/specs/2026-11-07-mod-031a-draft-connection-design.md

## Global Constraints

Preserve clock/prior pilots; unchanged controller/API/auth/epoch/command guards. Hook unconditional before page return. No backend/native/configured runtime/provider/schema/dependency/deploy/commit/push.

## Review Focus

- Actual controller ref changes across epochs; old command identity guards remain meaningful.
- Callback/member changes refresh/use latest handlers without socket churn.
- Every reconnect joins; all reads remain serialized with abort/denial/disposal safeguards.
- Missing token/league clears view without subscription; cleanup disposes once.
- Parent read capability preserves order, signal/error propagation and merged payload.

### Task 1: Failure-first hook integration
- [x] Capture page/clock/controller baseline.
- [x] Add real-hook + real-controller/fake-socket tests for callbacks, member refresh, epochs, denial/reconnect/late responses/ref identity and missing inputs. Observe RED missing hook.

### Task 2: Extract and wire
- [x] Implement typed generic useDraftConnection using existing controller and latest callback refs.
- [x] Parent supplies stable explicit (leagueId,signal) loader; replace only connection refs/effects/imports with hook call.
- [x] Update test-only page harness to load actual hook; existing lifecycle/clock tests remain unchanged.
- [x] Full frontend/build/import graph, baseline controller/clock equality and parent boundary check: expect PASS.

### Task 3: Review/record
- [x] Fresh independent scoped review; fix material findings failure-first.
- [x] Record evidence and full MOD031A completion; preserve earlier work.
- [x] Leave uncommitted and continue remaining Priority7 dependency audit separately.
