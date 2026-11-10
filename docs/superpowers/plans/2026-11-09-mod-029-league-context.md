# MOD-029 League Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Fresh matching account/URL context before Detail and Roster actions.
**Architecture:** A shared resolver and hook own membership provenance. Ready-context children own existing screen state; subject-bound profile results and scoped async guards prevent obsolete operations crossing contexts.
**Tech Stack:** Existing React/TypeScript, node:test isolated transpiled component harness, Vite.
**Spec:** docs/superpowers/specs/2026-11-09-mod-029-league-context-design.md

## Global Constraints

- Convert Detail and Roster only; retain mapper/week/form/payload defaults and server authorization.
- No caching, provisioning, schema changes, mutation replay, commit, or deployment.
- Navigation seeds ignored until a fresh matching response; tab preference remains league scoped.
- Existing audit workspace and inline execution retained as authorized; preserve all earlier uncommitted work.

## Review Focus

- A→B→A with the same route must not revive a prior request or callback.
- Fallback payloads carrying member-like fields never grant membership.
- Failed profile refresh must withhold the former numeric identity.
- Destination tab preference must not be overwritten during remount.
- Obsolete nested trade action completions must not trigger new reads.

### Task 1: Identity binding prerequisite

Files: modify `front-end/src/context/currentUserContext.tsx`; create `front-end/tests/currentUserIdentity.test.ts` and shared `tests/helpers/leagueContextHarness.ts`.
Interfaces: existing useCurrentUser contract; userId/profile fields exposed only for the resolved current subject.
- [x] Write actual-provider tests for delayed A/B/logout, overlapping refresh, failure/empty lookup; run and observe stale identity failure.
- [x] Bind profile outcome to subject and request generation; mask synchronously during transitions and invalidate obsolete completion/unmount.
- [x] Run identity tests, expected pass; record narrow MOD-026 prerequisite only.

### Task 2: Shared resolution and context hook

Files: create `front-end/src/hooks/useLeagueContext.ts`, `front-end/src/utils/leagueContext.ts`, `front-end/tests/leagueContext.test.ts`.
Interfaces: `resolveLeagueContext(leagueId,userId,signal)` returns `{league,isMember}`; `useLeagueContext(routeId)` returns context plus loading/error, scope identity and `isCurrent()`.
- [x] Characterize old Detail list/fallback and seeded Roster skipped lookup counts in evidence; test resolver matching, fallback provenance, failure without fallback, payload mismatch.
- [x] Implement extracted list/find/fallback using existing mapper and optional read AbortSignal arguments in `api/leagues.ts`.
- [x] Write failing hook tests for invalid route, missing profile, route/account A→B→A, ignored navigation seed and stale response.
- [x] Implement render-time masking plus cancellation/generation guard; run tests, expected pass.

### Task 3: Screen integration and scoped resources

Files: modify Detail/Roster, TradeRequestsPanel/PendingTransactionsPanel; create `hooks/useRequestScope.ts` and `tests/leagueContextPages.test.ts`.
Interfaces: ready children receive fresh league, current user, membership provenance and `isCurrent`; scoped request hook guards current mounted screen and per-resource request ordering.
- [x] Write failing actual-page tests for seeded/cold resolution, scope removal/replacement, fresh-membership actions, old mutation completion, payload/week defaults and tab storage; test scoped resources/nested panels.
- [x] Replace duplicate context effects with shared hook and keyed ready children. Retain existing presentation/domain code and defaults.
- [x] Guard mutations at invocation and completion; gate nested panels; reject obsolete roster/member/partner/scores responses, clear selected partner teams immediately on partner change.
- [x] Run targeted and full frontend tests, production build and import graph; expected pass, no unresolved imports/cycles.

### Task 4: Review and evidence

Files: update backlog/verification and new MOD-029 JSON evidence.
- [x] Fresh final reviewer reads approved spec, plan, ledger, touched code/tests and prior-work boundaries.
- [x] Fix Critical/Important findings with reproducing failing tests, then full suite/build; ledger deferred minors/scope rulings.
- [x] Record actual request baseline/after, source hashes, tests, limitations, and completed paired-screen scope; run diff check.
- [x] Leave changes uncommitted; retain ledger because no commit history records this work.
