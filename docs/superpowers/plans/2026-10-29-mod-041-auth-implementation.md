# MOD-041 Authentication Boundary Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. Implement the approved design with test-first changes; obtain one final independent review.

**Goal:** Ship the first MOD-041 slice: scoped browser credentials, bounded session recovery and structured pre-execution authentication errors.

**Architecture:** Extract a dependency-injected browser transport factory so real request behavior is testable without importing Supabase/environment configuration. Keep the production client facade and backend auth hook. Add a small HTTP response-boundary module for request IDs and explicit auth failures; no normalization of arbitrary legacy model errors in this slice.

**Tech Stack:** Existing TypeScript, fetch, Supabase Auth, Flask and unittest/Node tests; no new dependencies.

**Spec:** [Approved design](../specs/2026-10-29-mod-041-boundaries-design.md).

## Global constraints

- No rate limiter, paid services, deployment, database access or listener startup.
- Preserve existing API success payloads, principal resolution, resource denials and trusted jobs.
- Implement inline; keep pre-existing documentation changes.
- This is the auth slice, not completion of all MOD-019/024/028/034 or MOD-038.

## Review focus

- Explicit bootstrap credentials must not reenter Supabase session lookup.
- Request bodies/headers must survive caller Request inputs and caller cancellation.
- Concurrent authentication failures must not cause repeated refreshes after a fresh token is already available.
- Permission/legacy-text/operational failures and ambiguous mutation outcomes must never replay.
- Credentials must not escape through foreign URLs, path traversal or redirects.

## Task 1: Browser authentication transport

Files: create `front-end/src/api/authenticatedFetch.ts`, `front-end/tests/authenticatedFetch.test.ts`; modify `front-end/src/api/client.ts` and `front-end/tests/profileApi.test.ts`.

Interface: `createAuthenticatedFetch({apiBaseUrl, getAccessToken, refreshAccessToken, fetch, timeoutMs?})` returns `(input: RequestInfo | URL, init?: ApiFetchOptions) => Promise<Response>`. Token callbacks return `Promise<string | null>`. `refreshAccessToken(rejectedToken)` preserves the initiating subject; `canReplay(rejectedToken, refreshedToken): Promise<boolean>` checks SDK identity and token continuity before every replay. `ApiFetchOptions` extends RequestInit with skipAuth, retryOnAuthError and timeoutMs. Factory holds one refresh promise and detects stale-token failures against the latest refreshed token. Default total request budget: 30 seconds, overridable by a finite positive timeoutMs. This is a conservative browser budget for current interactive callers; long-running operations can explicitly override after measurement.

- [x] Write tests proving URL/path scoping, explicit-token isolation, Request/header/body preservation, one shared refresh, late stale responses, exact structured 401 matching, no ambiguous mutation replay, redirect refusal, replay-body constraints and abort/timeout behavior including refresh waits.
- [x] Run `node --test --experimental-strip-types tests/authenticatedFetch.test.ts` in front-end; observe missing-feature failures.
- [x] Implement the factory using Request snapshots, a total AbortController budget and replay only for null/string bodies supplied as init or bodyless Request inputs. Do not replay Request bodies or streams. Use redirect:error on authenticated calls. Preserve fetch response bodies for callers.
- [x] Keep client.ts as the SDK/environment composition facade. Update VM fixture dependency wiring to execute the real factory, preserving bootstrap contract tests. Allow configured-origin `/api/` paths only; skipAuth does not attach SDK credentials and cannot send explicit Authorization outside scope.
- [x] Run all frontend Node tests and `npm run build`.

## Task 2: Backend auth response boundary

Files: create `api/httpBoundary.py`, `api/tests/test_http_auth_boundary.py`; modify `api/authMiddleware.py` and `api/api.py`.

Interfaces: `install_http_boundary(app)` idempotently registers request-ID hooks. `authentication_error(code)` returns the approved JSON body and 401 using the current request ID. Auth installation installs the boundary before its denial hook, so minimal test apps and production wiring share the behavior.

- [x] Write tests for missing/invalid token codes and request IDs, pre-execution mutation denial, valid/public/OPTIONS/subject-only bootstrap preservation, no-store authenticated/error responses and missing/invalid client request-ID isolation. Use real synthetic JWT verification and Flask clients.
- [x] Run `python3 api/tests/run_isolated.py test_http_auth_boundary.py`; observe contract failures.
- [x] Implement only the designated missing/invalid-token failures in the auth hook; preserve principal and resource failures. Set X-Request-ID on Flask responses; expose through existing CORS configuration. No new JSON envelope for ordinary endpoint errors yet, so client parsing remains compatible without migrating every API consumer.
- [x] Run `python3 api/tests/run_isolated.py` and all frontend tests; no external network.

## Task 3: Review and record

- [x] Review changes against the approved spec and Review Focus; one independent final reviewer.
- [x] Fix important findings with failing regressions first, then rerun relevant suites.
- [x] Record actual test evidence and remaining MOD-041 work in progress/backlog. Do not mark broad pipeline or architecture migration implemented.

Ruling: Start with auth-only structured errors and retain legacy endpoint failure shapes — this permits bounded client/server rollout without incorrectly classifying all legacy ValueError/PermissionError paths. Full safe-error migration remains MOD-019.


## Execution ledger — 2026-10-29

- Baseline: backend 354/354 and frontend 45/45 passed using existing installed dependencies; no infrastructure started.
- Ruling: Work in the current checkout, per explicit user reply — preserve pre-existing documentation changes — no separate branch/worktree isolation.
- Browser transport tests initially failed because the new module was absent, then passed after implementation. Additional token-group and body-cancellation regressions failed against the first implementation and passed after per-token coordination and native signal composition.
- Backend contract tests failed against string auth errors/missing headers, then passed. Full suite initially exposed 19 legacy envelope assertions; updated those assertions for the intentionally approved auth contract while preserving principal/resource denial expectations.
- Ruling: Use a finite 30-second default total browser budget, overridable per call — current interactive callers have no explicit long-operation requirement — legitimate longer operations must opt into a reviewed override if this proves too short. AbortSignal.timeout/any require modern browser support; no older-browser compatibility has been established.
- Final review: independent reviewer identified one Important account-switch replay race; no Critical or Minor findings. Switching before refresh, during refresh and before late cached replay all failed in added facade regressions, then passed after session-continuity checks before refresh and every replay. Subject parsing is only a continuity check; the server remains the JWT verification authority.
- Final: fixed account-switch replay — three facade race regressions RED→GREEN; full frontend 62/62 and backend 359/359 pass. Existing bootstrap/model authorization tests remain active.
- Final: Ruling: Full rate limiting, provider policies, resource bounds, generic error normalization, deployment, database and lifecycle work remain outside this auth slice — retain the separately scoped ownership in the architecture decision — those broader guarantees are not delivered by these tests.
- Fresh verification: `python3 api/tests/run_isolated.py` exit 0 (359 tests); frontend `node --test --experimental-strip-types tests/*.test.ts` exit 0 (62 tests); `npm run build` exit 0; targeted ESLint on client.ts/authenticatedFetch.ts exit 0 (existing browser-mapping freshness notice). No application deployment, dependency installation or database connection.
- Changes remain uncommitted in the requested current checkout; no merge, push or publication performed.
