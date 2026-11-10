# MOD-026 Profile Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** One API-backed browser profile owner with latest-session ordering and safe account-scoped consumers.
**Architecture:** AuthProvider publishes accepted Supabase session snapshots only. A bounded loadApplicationProfile helper performs subject/token-bound lookup/create/conflict reread and guarded signup-hint cleanup; CurrentUserProvider owns lifecycle/coalescing. Home masks private resources and Settings scopes form/async completions by opaque identity generation.
**Tech Stack:** Existing React19/TypeScript, apiFetch, isolated node:test VM hook harness; no new packages or backend changes.
**Spec:** docs/superpowers/specs/2026-11-10-mod-026-profile-ownership-design.md

## Global Constraints

- Preserve MOD029 identity masking/race assertions, apiFetch explicit-token no-refresh/no-replay, existing routes/auth screens and update payload.
- Per bootstrap: one GET; only404 permits one create;409 permits one reread; failed/ambiguous operations do not auto-replay.
- Pending storage is a display-name hint only, matching current session email; never identity authority. Clear only current captured raw hint.
- No caching framework, Home list feedback redesign, schema/backend/provider/Docker/deployment work or commit. Use clean audit baseline6c8fcd4 and preserve user work.

## Review Focus

- A→B→A and visibility callbacks must not revive an earlier session/profile/hint.
- Token renewal alone must preserve ready same-subject profile/form; failed/pending credential changes may start one new attempt per token.
- Create ambiguity and409 reread must remain bounded and subject/token-consistent.
- Settings' own refresh is not an account change; failed refresh cannot announce save success.
- Private Home lists must disappear in the render before effects while public discovery remains available.

### Task 1: Latest session source

Files: modify `front-end/src/context/AuthContext.tsx`; create `front-end/tests/authSessionOrdering.test.ts`.
Interfaces: existing useAuth fields/methods; user derived from accepted session. Final-review correction adds sessionIdentityKey/isSessionIdentityCurrent/isSessionCredentialCurrent as internal synchronous continuity capabilities. No profile/storage work in AuthProvider.
- [x] Write actual-provider deferred session/event/visibility tests; reproduce initial A after B/logout and overlapping lookups.
- [x] Guard active/event/request ordering, remove provisioning/storage, preserve auth methods and cleanup.
- [x] Run scoped tests, expect PASS including unmount and listener cleanup.

### Task 2: Profile coordinator and API owner

Files: new `front-end/src/lib/profileBootstrap.ts`; modify `context/currentUserContext.tsx`, `api/user.ts`; update `tests/currentUserIdentity.test.ts`; add `tests/profileBootstrap.test.ts`, `tests/profileBootstrapApi.test.ts` and focused provider tests.
Interfaces: `loadApplicationProfile({subject,accessToken,email,username,signal,isCurrent}): Promise<User>`; getUserByUuid/createUser gain optional third AbortSignal plus numeric error status; CurrentUserContext retains fields/refreshUser Promise<void>, adds identityKey/isCurrentIdentity for consumers.
- [x] Write RED helper/API tests: exact token/signal, validated UUID/id,404-create,409-one-reread, denied/network/ambiguous failure, hint precedence/cleanup/mismatch/newer hints/cancel-before-create.
- [x] Implement bounded helper and optional API signals/status without apiFetch changes.
- [x] Port existing actual-provider tests to API transport while retaining A→B→A/logout/refresh-order/failure assertions; add no-direct-table-read/coalescing/token renewal/ready stability and stale create cases, observe RED.
- [x] Implement provider lifecycle with render-time identity masking, captured operations, abort/current guards and rejection-aware refresh. Auto effects consume rejection; same-token pending work coalesces; explicit refresh supersedes.
- [x] Run scoped tests and build; expect PASS, no unhandled rejections.

### Task 3: Narrow consumer safeguards

Files: new `components/Profile/ProfileStatus.tsx`; modify `screens/Home/Home.tsx`, `screens/Settings/SettingsPage.tsx`; add `tests/profileConsumers.test.ts` and extend provider/consumer harness only as needed.
Interfaces: identityKey/isCurrentIdentity from Task2; existing useRequestScope; ProfileStatus shows setup/error/Retry with rejection consumption.
- [x] Write failing actual-page tests for account private-list masking/late results/public search, Settings input retention/save-refresh and stale completions, visible provider retry.
- [x] Tag/mask Home's two private lists by identity generation, abort obsolete reads; leave stage/list feedback/search algorithms unchanged.
- [x] Key Settings form by account generation, guard save/refresh completions, retain input on refresh failure and show success only after successful matching refresh. Same-subject refresh does not remount form.
- [x] Run scoped and full frontend suites, build/import graph/diff; expect PASS including MOD029/draft lifecycle tests.

### Task 4: Review and evidence

Files: MOD026 evidence JSON and backlog/verification entries.
- [x] Fresh whole-change reviewer checks approved scope, tests, plan and ledger rulings.
- [x] Fix Critical/Important issues once with RED→GREEN tests/full green suite; defer/document Minor issues and runtime scope limits.
- [x] Record test counts/hash/import boundaries, unchanged backend/apiFetch and preceding pilot source evidence, browser/provider limitations; no live validation claimed.
- [x] Mark MOD026 complete within approved scope, keep MOD027/028B separate, leave work uncommitted/undeployed.
