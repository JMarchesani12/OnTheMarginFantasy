# MOD-027A Own-League Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Give Home distinct current-selection loading, empty, error and retry outcomes.

**Architecture:** Local keyed primary request state, preserving separate discovery membership reads and existing profile identity guards.

**Tech Stack:** React/TypeScript, existing Node test harness, Vite.

**Spec:** docs/superpowers/specs/2026-11-10-mod-027a-own-league-feedback-design.md

## Global Constraints

- No dependencies, API/schema changes, caching or Home rewrite.
- Hide old account/stage data synchronously; abort and guard obsolete attempts.
- Preserve ProfileStatus and public discovery; leave work uncommitted/undeployed.

## Review Focus

- Stage round trips must not revive superseded work.
- Retry followed by navigation must not target an old selection.
- Missing profile must not display successful-empty feedback.
- Invalid response containers must not imply no leagues.
- Same-identity profile refresh/disposal must not revive old requests.

### Task 1: Primary list feedback and request safety

**Files:** Modify front-end/src/screens/Home/Home.tsx; create front-end/tests/homeLeagueFeedback.test.ts.

**Interfaces:** Consumes getLeaguesForUser(userId, stage, signal), useCurrentUser identityKey/isCurrentIdentity; produces local feedback only, no exported interface.

- [x] Write tests using actual Home and the existing controlled hook harness: initial and stage pending, three empty messages, cards/filtering, safe failure/retry, malformed container, cancellation and late results, account/profile transitions, stage round trips and unmount. Preserve existing response shapes.
- [x] Run `cd front-end && node --experimental-strip-types --test tests/homeLeagueFeedback.test.ts`; expect missing-feedback/stale-stage assertion failures before production changes.
- [x] Implement keyed discriminated primary state, current-selection render masking, request disposal, immediate retry pending and safe status/alert feedback. Keep membership normalization unchanged; reject invalid primary containers.
- [x] Run targeted tests and existing profile consumers; expect all pass.
- [x] Run `cd front-end && node --experimental-strip-types --test tests/*.test.ts`, `npm run build --prefix front-end`, `node scripts/modernization/verify_frontend_imports.cjs`, `git diff --check`; expect exit0.

### Task 2: Review and audit evidence

**Files:** Update backlog.md, verification.md, priorities-2026-10-29.md under docs/modernization; create evidence/mod-027a-own-league-feedback-2026-11-10.json.

**Interfaces:** Consumes Task1 verified Home behavior; produces audit evidence/status limited to MOD-027A.

- [x] Request one fresh final review against approved design, plan, changed files and tests; fix material findings with reproducing RED→GREEN and full suite if needed.
- [x] Record exact test/build/import results, source hashes, decisions and controlled-harness limitation; mark only MOD-027A complete.
- [x] Verify diff/status and leave uncommitted; keep ignored ledger until history records this work.

Completion note: lifecycle regression coverage covers disposal/account/stage paths but the review records the specific unmount/retry-navigation permutations as a deferred Minor, not independently exercised cases.
