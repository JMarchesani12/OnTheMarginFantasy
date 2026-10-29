# Regression verification baseline

Latest result: **MOD-003B complete** in bounded HTTP/application authorization scope. Final guarded backend **256/256 pass**, exit0, including prior profile/state/live/control/transport assertions. Diff check passes. No frontend changes/checks rerun; prior results are historical. PostgreSQL/RLS/concurrency/notification/browser/live-socket limits remain; no production used.

2026-10-28. Read with [behavior checklist](behavior-checklist.md), [backlog](backlog.md), [database audit](database-audit.md), and [progress](progress.md). Baseline is checkout `162f89a` plus the pre-existing modification to `api/startSeasonJobs/configs/ncaa-mens-basketball-2026.json` and untracked modernization docs. This is not a clean-HEAD or deployed-production result.

**Original baseline result (historical):** original suites passed (66 backend + 34 frontend utility + 9 tier-tool tests). Added 12 backend tests: 10 pass and **two fail on known profile-isolation defects**. Final backend suite is **76 passing / 78 total, exit 1**. Frontend build and tier type check pass; frontend lint has **63 pre-existing errors and 11 warnings, exit 1**. There is no all-green regression gate yet. No failure was fixed, skipped, marked expected-failure, or converted into a compatibility requirement.

## Tools, prerequisites and isolation

Used installed Python 3.14.1 and Node v22.22.2, the existing `unittest`/Node test runners, TypeScript/Vite/ESLint, and existing dependencies. No dependency installation, new browser framework, production process, network request, deployed database connection, migration, scoring job or rebuild command was run.

Installed backend versions checked: Flask 3.1.2, SQLAlchemy 2.0.44, PyJWT 2.10.1, Flask-SocketIO 5.6.0, python-dotenv 1.2.1, psycopg2-binary 2.9.11 and requests 2.32.5. Vite build reports 7.2.6. These describe this machine; the repo still lacks a documented/pinned complete runtime setup (MOD-034). Frontend `node_modules` was already present. Node must support `--experimental-strip-types`; backend prerequisites are in `api/requirements.txt`.

New `api/tests/run_isolated.py` is the canonical safe backend entry point for this baseline. It clears inherited environment values and supplies only a synthetic project ID/JWT secret, disables dotenv loading before test discovery, blocks SQLAlchemy engine creation and psycopg2.connect, and blocks common socket connection/DNS/datagram paths. It never imports the production app factory. It is a guard for these unit suites, **not an OS/network sandbox**: future tests using other native clients/subprocesses must be reviewed separately. Do not replace this command with web/CLI startup or assume arbitrary future tests are safe.

Profile tests use per-test `sqlite3.connect(':memory:')` data with `.test` emails and fixed synthetic UUIDs, real JWT signing/verification, middleware, registered user routes, endpoints and UserModel SQL. The small result adapter executes the actual compatible SQL subset; it does not simulate authorization. SQLite does **not** validate PostgreSQL types, role privileges, RLS, migrations, auth.users constraints, locking or transaction concurrency. Its minimal User fixture is test data, not a new schema baseline. Connections close after each test.

Draft contract tests use real registered handlers, serializer and room broadcast function with a substituted persistence/state model and an intercepted socket emitter. They do not open sockets or prove model transitions/room authorization. Tiebreak tests use the real resolver with hand-derived game inputs, replacing stored-game retrieval only. Existing bootstrap tests substitute providers/DB and use temporary checkpoints; their simulated ERROR output is intentional fault-path output, not an additional suite failure.

## Commands and actual results

Commands are from repository root unless the directory column says otherwise. Initial backend run was after adding the safety runner but before any new test cases; existing test files were not modified. Final runs used the same runner with all new tests discovered.

| Directory | Command / actual invocation | Actual result |
| --- | --- | --- |
| Root | `python3 --version`; `node --version` | Python 3.14.1; Node v22.22.2; exit 0. |
| Root | `python3 api/tests/run_isolated.py` — original suite | 66 tests, 66 pass; exit 0. |
| `front-end` | `node --test --experimental-strip-types tests/*.test.ts` — initial and final | 34 tests, 34 pass; exit 0 both runs. |
| `front-end` | `npm run basketball:tiers:test` — initial and final | 9 tests, 9 pass; exit 0 both runs. |
| `front-end` | `npm run basketball:tiers:typecheck` | TypeScript check passes, exit 0. |
| `front-end` | `npm run lint` | 74 findings: 63 errors / 11 warnings; exit 1. Pre-existing, no frontend files modified. |
| Temporary sanitized frontend copy | `npm run build` (`tsc -b && vite build`) | Exit 0; 220 modules transformed; build completed. Artifact discarded with temp copy; no preview/deploy/runtime test. |
| Root | `python3 api/tests/run_isolated.py 'test_profile_regression.py'` | 7 tests: 5 pass, 2 fail on known MOD-002 defects; exit 1. |
| Root | `python3 api/tests/run_isolated.py` — final | 78 tests: 76 pass, 2 failures, no errors/skips/expected failures; exit 1. Original 66 still pass. |

Targeted reproduction commands for later work (final full run already includes these files):

```sh
python3 api/tests/run_isolated.py 'test_profile_regression.py'
python3 api/tests/run_isolated.py 'test_draft_contracts.py'
python3 api/tests/run_isolated.py 'test_weekly_tiebreak_baseline.py'
```

The build was run by copying `front-end` to a Python TemporaryDirectory, excluding `.env`, `.env.*`, `node_modules`, `dist` and `.git`; symlinking the existing node_modules; removing inherited VITE_/SUPABASE_/DATABASE_ variables; setting synthetic VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY and VITE_API_BASE_URL; and invoking `subprocess.run(['npm', 'run', 'build'], cwd=copy, env=sanitized_environment)`. This avoids reading build env files/embedding live configuration. TypeScript may update ignored `node_modules/.tmp` build metadata via that symlink. The copy and bundle were discarded. A direct `npm run build` in the source checkout would load its local env and is not the exact invocation used here.

Detailed stdout/stderr was inspected during the run and kept in temporary `/tmp/modernization-*.log` files; those are ephemeral, not portable repository artifacts. The counts/failure inventory below are the durable record. Commands are reproducible; no production credentials are needed for the unit tests.

## Pre-existing failures, reproduced rather than preserved

### Profile isolation — MOD-002 / backend D01

Both new negative tests run ordinary assertions and remain in default discovery. They expose an existing defect, not a regression introduced by the tests. They expect denial (403 or 404) and no private-data exposure/write; exact denial contract remains an implementation decision.

| Test | Actual result / evidence | Limit |
| --- | --- | --- |
| `ProfileRegressionTests.test_mod_002_foreign_profile_read_is_denied` | Alice's locally signed valid token GET `/api/user/2` returns **200**, not 403/404, exposing Bob's synthetic profile. | Real middleware/route/model SQL on synthetic in-memory rows; not a production exploit or RLS test. |
| `ProfileRegressionTests.test_mod_002_foreign_profile_update_is_denied_without_changing_data` | Alice PATCHes `/api/user/2` with displayName Tampered and body userId=1; Bob's persisted synthetic displayName becomes **Tampered**, not Bob. | Demonstrates actual unintended write in fixture, not only response status. No real account changed. |

Root cause evidence: middleware validates JWT into g.user, but registered user endpoints pass URL user ID to UserModel without consuming/binding the subject. The fixture DB executes that SQL and intentionally supplies no nonexistent row-isolation layer. This matches the source audits. Deployed roles/RLS are unknown. At this baseline stage only isolation/regression evidence existed. MOD-001 resolver completion is recorded below; MOD-002 authorization remains unimplemented.

### Frontend lint — existing findings

No frontend source was changed. The lint rule totals are:

| Rule | Errors | Warnings |
| --- | --- | --- |
| `@typescript-eslint/no-explicit-any` | 47 | 0 |
| `react-hooks/rules-of-hooks` | 12 | 0 |
| `react-refresh/only-export-components` | 3 | 0 |
| `no-unsafe-finally` | 1 | 0 |
| `react-hooks/exhaustive-deps` | 0 | 11 |

The 12 conditional-hook errors are in `src/screens/League/LeagueDraftPage.tsx` at 673, 686, 709, 727, 738, 750, 782, 790, 800, 807, 823 and 839. They warrant focused reproduction/regression protection before draft structural extraction (MOD-031A); a successful TypeScript/build does not clear hook-order risk. `ManageLeaguePage.tsx:305` has no-unsafe-finally. Fast-refresh export findings are `AuthContext.tsx:148`, `currentUserContext.tsx:94` and `BonusesEditor.tsx:38`.

Complete per-file location ledger below: A = no-explicit-any, H = rules-of-hooks, R = only-export-components, F = no-unsafe-finally, W = exhaustive-deps. Lines refer to this checkout.

| Frontend file | Findings by rule / line |
| --- | --- |
| `src/components/League/LeagueScheduleTabs.tsx` | W: 295 |
| `src/components/League/PendingTransactionsPanel.tsx` | A: 58 |
| `src/components/League/TradeRequestsPanel.tsx` | A: 46, 86, 99, 112 |
| `src/context/AuthContext.tsx` | R: 148 |
| `src/context/currentUserContext.tsx` | R: 94 |
| `src/screens/Auth/ResetPassword.tsx` | A: 31 |
| `src/screens/Auth/SignIn.tsx` | A: 85, 116 |
| `src/screens/Auth/UpdatePassword.tsx` | A: 69 |
| `src/screens/CreateLeague/BonusesEditor.tsx` | R: 38 |
| `src/screens/CreateLeague/CreateLeague.tsx` | A: 101 |
| `src/screens/League/ConferenceSchedulePage.tsx` | A: 139, 193, 260 |
| `src/screens/League/DiscoverLeaguePage.tsx` | A: 53, 84, 146 |
| `src/screens/League/LeagueDetailPage.tsx` | A: 107, 143, 202, 270, 288 |
| `src/screens/League/LeagueDraftPage.tsx` | A: 87, 172, 566, 636, 902; W: 245, 370, 500, 571; H: 673, 686, 709, 727, 738, 750, 782, 790, 800, 807, 823, 839 |
| `src/screens/League/LeagueRosterPage.tsx` | A: 112, 154, 191, 235, 370, 399; W: 294, 298, 302 |
| `src/screens/League/ManageLeaguePage.tsx` | A: 269, 298, 412, 458, 488, 507, 517, 545, 565, 612; W: 285, 321, 500; F: 305 |
| `src/screens/League/TeamLookupPage.tsx` | A: 70, 105 |
| `src/screens/League/TeamSchedulePage.tsx` | A: 94, 128 |
| `src/screens/Settings/SettingsPage.tsx` | A: 40 |

## Small additions and regression intent

12 added tests in three files; no existing test was rewritten and no app file was changed.

| Test file / count | Checklist/features | Observable behavior protected / plausible break caught |
| --- | --- | --- |
| `api/tests/test_profile_regression.py` — 7 | J1 partial, K0/K1; F-002/004/022 | Anonymous/malformed/empty bearers cannot read/write; real expiry/signature/issuer/audience validation; preflight cannot update; own save/reload and JSON identity fields preserved; non-whitelisted fields cannot alter identity/email; missing/empty-update status/message contracts; two-account denial tests expose current failures. Does not automate login/signup/browser context or league list. |
| `api/tests/test_draft_contracts.py` — 3 | J3 transport slice, K6; F-013/023 | Successful pick is 201 JSON with serialized date and matching league-scoped event; rejected/expired/conflicting/constraint-failed pick returns client/conflict error with no success event; missing inputs cannot execute a pick or emit success. Model is substituted, so no assertion of real pick/concurrency/room authorization. |
| `api/tests/test_weekly_tiebreak_baseline.py` — 2 | J4 calculation slice, K7; F-009/025/032 | Head-to-head winner beats larger single-game margin; without H2H result use largest absolute margin including losses; lower untied member and differential values stay intact. Fixture expectations are literal, not computed with production helpers. |

Retained existing regression value: J2 trimmed/nonblank create/join names and rule-version pinning; J4 tier adjustment (home/away/both-owned), tournament clamp/multiplier/order, week0/opening/final-period/timezone boundaries, daily totals, schedule pagination and ranks; locked roster forwarding; bootstrap failure/checkpoint/resume; tier-analysis symmetry/conference overrides/CSV output. These are bounded model/helper tests, not full journeys. Unresolved final ties are deliberately not frozen into a new ranking policy; behavior/product review is still needed before formula changes.

Test sensitivity was checked in **temporary API copies only**, each running the guarded runner with its targeted file:

- Replacing JWT verification with unconditional claims caused `test_expiry_signature_issuer_and_audience_are_verified_before_profile_access` to fail.
- Changing draft turn/expiry conflict from 409 to 200 caused `test_rejected_or_conflicting_pick_never_emits_success` to fail.
- Removing H2H resolution before single-margin fallback caused `test_head_to_head_winner_precedes_single_margin_without_reordering_non_tied_members` to fail.

All three mutation probes exited 1 with the intended assertion failure. Repository application sources were not mutated; temporary copies were discarded. This checks three representative failure modes, not exhaustive mutation coverage.

## Unverified areas and deferred feature-specific gaps

| Area | Gap / missing prerequisite | Follow-up |
| --- | --- | --- |
| J1 account/profile/leagues; F-002–005/022 | No browser login/signup/confirmation/recovery, provider race/account-switch, current-user direct Supabase policy or Home feedback tests. Need disposable Auth/Supabase project or SDK/browser fixtures and browser harness. | MOD-001/002/004/006/026/027A/028A; F-003 recovery manual only. |
| J2 create/discover/approve; F-006–008/017–019/021/029 | No full admission, capacity/concurrent approval, delete/cascade or cold-link journey. Name/rules unit checks do not execute malformed denial SQL or real FK/status constraints. Need disposable PostgreSQL/Supabase baseline and role policy Q1/Q4; never prod deletion. | MOD-003A/005/008/011/012/027D. |
| J3 draft; F-013/014/018/020/023/024/030 | Contract tests omit real pick/state/order/timeout/locking, multi-client sockets/reconnect and membership revocation. Conditional hooks need isolated browser reproduction before component moves. Need fake timer/transport or isolated socket server and synthetic leagues. | MOD-003B/023–025/031A; address hook finding separately before extraction. |
| J4 schedule/scoring; F-009–012/025–028/031/032/035/036 | No real SQL query/constraint/index plans, score replacement rollback/concurrent jobs, season-finalization CLI lifecycle, historical rebuild ownership remap or provider correction integration. Existing “integration” test names largely use mocks. Need executable schema/disposable DB, historical fixtures and provider fakes. | MOD-005/007/008/013–017/021/022. |
| J5 transactions; F-015/016/025/033 | No end-to-end propose/respond/veto/apply, caller isolation, replay, duplicate reservation, concurrency, pending-panel refresh or job timing checks. Need Q3/Q4 policy and transaction fixtures/isolated Postgres. | MOD-003C/009/010/013/027B. |
| Database access paths | Deployed RLS/grants/owners/functions/triggers/scheduler/drift not available. SQLite profile tests cannot prove direct Supabase or privileged-backend isolation. | MOD-004/005. |
| UI/navigation/accessibility; F-001/005–021 | No browser/React render harness installed or screen-reader/keyboard/reflow tests. Known labels/modal/reorder and search-loading gaps remain. No DOM library added merely to increase coverage this run. | MOD-027A–G/029/031/036. |
| Operational health/CLIs; F-023–028/034/036 | Production scheduler, credentials, supervision, notifications/delivery/readiness and checkpoint durability unknown. Do not start app factory/jobs as a smoke test. | MOD-014/016/024/034. |
| Tier analysis / legacy; F-037–041 | Existing 9 tier tests pass; no provider/CLI/cache integration or external-usage evidence. No basis to remove dormant/deprecated alternatives. | MOD-035/036. |

No coverage percentage or all-feature contract/security guarantee is claimed. No lint/type/build check establishes runtime authorization. Existing lint and the two isolation failures remain blockers for an all-green gate; preserve their visibility, not the defective behavior.

## Concise manual smoke checklist — not executed

Prerequisite: confirmed disposable/local environment with synthetic accounts A/B, a synthetic league/season, explicit isolated URLs, known role policy and operator-controlled job/provider fixtures. Do not use production signup/email, deletes, trades, scoring or rebuilds for this checklist. Until prerequisites exist, mark **not run**, not passed.

- [ ] **J1:** Sign in as A, save display name, refresh and inspect own leagues; sign out and sign in as B in the same browser. No stale A profile/league data. Check rejected login, slow/missing profile and expired session; attempt cross-user profile read/PATCH only in isolation (known failure).
- [ ] **J2:** A creates league/team; B discovers, opens a fresh direct URL, submits join request; A approves; both refresh membership. Try blank name, wrong actor/league/request and repeated submit; use synthetic records for removal only.
- [ ] **J3:** Configure order, start, pick, pause/resume and trigger a controlled timeout in two clients; rejected picks show no success; reconnect/refresh converge; nonmember cannot receive another league's room data; finish and inspect history. Watch console for hook-order/runtime errors.
- [ ] **J4:** With fixed games/ownership, compare roster → member/team/conference schedule → standings for current and historical week, both-owned/tier-adjusted game and final period. Include empty/error/refresh-after-fixture-ingestion. Use fixture operator only for scoring.
- [ ] **J5:** Propose/accept/cancel/veto/add-drop on synthetic rosters, verify open/pending lists refresh and pending acceptance does not imply applied ownership. Controlled application once, replay/conflict rejection, refresh both clients. No production jobs.
- [ ] **Shared:** Keyboard labels/forms/order/dialog focus; direct URL/back/refresh; empty versus failed load; failed submit retains input; expired-token recovery does not duplicate mutation. Record expected failures with backlog ID rather than marking journey passed.

## Handoff boundary

Changed only test files/runner plus this verification document and progress log. No principal implementation, authorization fix, schema/application refactor, dependency/config change, migration, deployment or production test. MOD-001 remains incomplete beyond regression isolation; next implementation still starts with principal binding and MOD-002. Stop here per request.


## MOD-001 resolver verification — 2026-10-28

This section supersedes the earlier baseline handoff for MOD-001 only. Added `api/authenticatedPrincipal.py` and `api/tests/test_authenticated_principal.py`; reused the unchanged guarded runner and synthetic profile fixture. No existing profile denial test or endpoint was changed.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_authenticated_principal.py'` before implementation | Exit 1: import error for absent `authenticatedPrincipal` module; confirms the new boundary did not exist. |
| `python3 api/tests/run_isolated.py 'test_authenticated_principal.py'` after implementation | 9 tests, 9 pass; exit 0. |
| `python3 api/tests/run_isolated.py 'test_profile_regression.py'` | 7 tests, 5 pass, 2 ordinary MOD-002 failures; exit 1. |
| `python3 api/tests/run_isolated.py` | 87 tests, 85 pass, 2 ordinary failures; no errors/skips/expected failures; exit 1. |

New tests cover verified A/B subject mapping despite conflicting URL/body/query/header actor IDs, missing/expired JWTs, absent/empty/blank subject, absent/duplicate application identity, unverified request context, no-request/job/app contexts, immutable identity, and database-error propagation. Real middleware/JWT verification runs on the test-only HTTP route; resolver SQL runs against synthetic in-memory SQLite. Duplicate UUIDs are created only by loosening the disposable fixture, with no schema change. Results contain only subject/application ID; profile data is not fetched. Errors expose stable codes (401 missing request/subject, 403 missing/ambiguous mapping), to be serialized by future adopting adapters. No endpoint currently gains authorization from this addition.

The preserved failures remain exactly `test_mod_002_foreign_profile_read_is_denied` (Alice GET of Bob returns 200) and `test_mod_002_foreign_profile_update_is_denied_without_changing_data` (Bob's stored name becomes Tampered). The full suite remains red; this is expected deferred MOD-002 work, not a passing authorization gate.

Limits: no PostgreSQL/RLS/live-schema/browser verification; the resolver trusts the middleware-owned `g.user` after authentication and must be called after middleware. Trusted jobs do not receive a fallback principal or HTTP bypass. No frontend recheck, production connection/modification, listener/app startup, schema change or job execution. MOD-001 complete; next is MOD-002 adoption/public-data repair, not performed here.


## MOD-002 stage 1 verification — 2026-10-28

Selected stage: authenticated numeric-ID profile GET/PATCH only. Actual dependency inspection confirmed MOD-001 exists and uses middleware-owned `g.user.sub`; no assumption of endpoint adoption was made. `UserEndpoints.get_user/update_user` now consume it, deny URL/principal mismatches with 404 and a generic message, and serialize resolver errors (401 missing subject, 403 absent/ambiguous application mapping). Success payloads and display-name-only update behavior remain unchanged. No schema or frontend changes required for this stage.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_profile_regression.py'` before source changes | 12 tests, 14 failing assertions/subtests, exit 1. Original cross-user read/write failures reproduced; new mapping/substitution tests also fail. Expired PATCH already denied by middleware. |
| Same targeted command after implementation | 12/12 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 92/92 pass, exit 0; no errors/skips/expected failures. Includes all nine principal tests. Bootstrap fixture's simulated ERROR output is intentional. |
| `git diff --check` | Exit 0. |

Five added profile tests exercise both users' own reads and foreign GET/PATCH denial despite URL/body/query/header actor substitution, missing/ambiguous identity denial on both methods, empty subject and expired PATCH. Denial tests inspect persisted names and safe JSON; the original two MOD-002 denial assertions remain unchanged and now pass. Existing own-profile save/reload confirms identity/email cannot be rewritten via PATCH, and success payload/validation/preflight contracts continue to pass. The only fixture adapter addition is real SQLite cursor `fetchmany`, needed by the production resolver's duplicate detection query.

Boundary: this green suite verifies the numeric-ID HTTP slice in isolation, not all account access paths. `/api/user/byUuid/` remains public in the production configuration, POST provisioning still trusts supplied UUID/email, and public commissionerEmail/profile logging remain for later MOD-002 stages. No claim that full MOD-002 is complete. Q1 public projection remains unresolved. Direct browser Supabase/RLS, PostgreSQL constraints/locking and identity-remapping concurrency remain unverified. No app factory/listener, job, production access/mutation, schema/migration, dependency upgrade or frontend check was run. Next: remaining MOD-002 lookup/provisioning plus consumer coordination, then public projection/log minimization; no other task started.


## MOD-002 stage 2 verification — 2026-10-28

Bounded scope: authenticated own-subject UUID lookup and claims-bound profile provisioning, including frontend bootstrap coordination and removal of creation's raw profile log. No public search projection decision was made. The bootstrap subject helper is shared with MOD-001's principal validator; missing application identity is accepted only for this subject-bound provisioning flow. No trusted-job HTTP fallback was added.

| Command from root (frontend commands from `front-end`) | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_profile_bootstrap.py'` before implementation | Nine tests, 15 failing assertions/subtests; exit 1. Demonstrated public UUID exposure, foreign lookup and provisioning binding gaps. |
| Same targeted command after implementation and constraint-error test addition | 10/10 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 102/102 pass, exit 0; no skips/expected failures. Includes unchanged original numeric cross-user denial assertions. |
| `node --test --experimental-strip-types tests/profileApi.test.ts` initially | Five request tests: two pass, three fail, exit 1 (skipAuth, body identity fields, SDK lookup despite explicit token). |
| Same targeted command after implementation and hook tests | 8/8 pass, exit 0. |
| `node --test --experimental-strip-types tests/*.test.ts` | 42/42 pass, exit 0. |
| `./node_modules/.bin/tsc -p tsconfig.app.json --noEmit` | Exit 0. |
| `./node_modules/.bin/eslint src/api/user.ts src/api/client.ts src/context/AuthContext.tsx tests/profileApi.test.ts` | Exit 1: one existing `react-refresh/only-export-components` error at AuthContext.tsx:149; no other lint findings. Tool also emits a baseline-browser-mapping age notice; no package update made. |
| `git diff --check` | Exit 0. |

Backend tests use real JWT/middleware/routes/model SQL against synthetic SQLite, reusing the existing fixture with added insert-result `_mapping` support. They parse only the real factory's auth allowlist AST, never import/run the factory. Coverage: anonymous/invalid/expired and own/foreign UUID lookup; missing-profile → create → reload; legacy matching fields versus forged UUID/email; existing/ambiguous identity; missing subject/email; object/name validation; no creation-profile debug payload. One constraint-error test injects SQLAlchemy IntegrityError at INSERT to verify generic 400 and unchanged rows. This is error-path injection, not PostgreSQL validation. Bootstrap logs' simulated ERROR lines in the full suite remain intentional fixtures.

Frontend tests transpile actual user API/client/AuthContext modules using installed TypeScript into a VM with isolated SDK/transport/React-hook/storage/document substitutes. They verify authenticated lookup and explicit token, displayName-only creation, 404-only null behavior, SDK session fallback/explicit-token avoidance, and existing/missing/denied bootstrap decisions/storage markers. They do not render React, contact Supabase or exercise browser scheduling/account switching. Type-check covers application sources; tests run via Node TypeScript stripping/transpilation.

Deliberate contracts: UUID lookup is now authenticated/private; own missing/foreign UUID gives 404, ambiguity 403. POST trusts verified sub/email, not body identity: matching legacy fields remain accepted, conflicts 403, missing email claim 403, invalid object/name 400, existing profile 409, ambiguity 403, successful creation 201. Success profile fields remain unchanged. Backend constraint details no longer reach responses and created profile is no longer debug-logged. JWT email freshness/provider state is not checked remotely; no email-change feature added.

Limits/next: full MOD-002 still needs Q1 public league-search field decision and commissionerEmail minimization/consumer verification. UUID snapshot uniqueness/concurrent provisioning, legacy remediation and provider consolidation belong to existing MOD-006/005/026; sequential checks here do not prove race safety. Deployed DB/RLS/direct SDK access, real signup/confirmation, browser lifecycle and historical logs remain unverified. No schema/migration, job, app/listener startup, environment values, network or production mutation used. Stop after this stage.


## MOD-002 final public-search privacy verification — 2026-10-28

User decision: keep commissioner email private. Removed only `commissionerEmail` from `LeagueModel.search_leagues` SQL projection and frontend `LeagueSearchResult`; Home search cards consume commissioner display name, not email. Public discovery retains ID, name, sport, capacity, status, draft date, discoverability, commissioner ID and display name. Response shape deliberately loses email; filters/pagination/public access are unchanged. The broader Q1 role matrix remains outside MOD-002.

| Command (root unless specified) | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_public_league_search.py'` before implementation | Initial fixture setup: four errors from missing synthetic ESPN URL; supplied test-only URL without changing application code. Corrected baseline: four tests, one ordinary failure (commissioner email exposed), three pass; exit 1. |
| Same targeted command after implementation | 4/4 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 106/106 pass, exit 0, no skips/expected failures. Prior cross-user profile denial assertions remain intact and pass. |
| `front-end`: `node --test --experimental-strip-types tests/*.test.ts` | 42/42 pass, exit 0. |
| `front-end`: `./node_modules/.bin/tsc -p tsconfig.app.json --noEmit` | Exit 0; verifies consumers against the reduced search type. |
| `front-end`: `./node_modules/.bin/eslint src/types/league.ts` | Exit 0; dependency-age notice only. Full lint not rerun; previously documented errors remain. |
| `git diff --check` | Exit 0. |

Four new tests execute real registered search handlers/middleware/model SQL using SQLite synthetic discoverable/hidden leagues with a commissioner contact value that must not appear in JSON. They assert exact retained fields, no email, anonymous access, hidden-league exclusion, sport filtering, page offset/limit, short/no-match query results and invalid-parameter JSON status. Actual auth allowlist is parsed without running/importing the factory. SQLite adapts ILIKE to LIKE and substitutes constant similarity; these tests do not prove PostgreSQL trigram ranking, collation, deployed privileges or query performance. A synthetic provider URL is set only during route construction; no provider/network call occurs.

MOD-002 is complete within its documented application/API boundary across stages 1–3. No production connection/mutation, schema/migration, dependency upgrade, app/listener startup, job or deployment occurred. Real browser lifecycle, direct Supabase/deployed RLS, historical logs and PostgreSQL concurrency remain unverified. MOD-006 owns concurrent unique provisioning after MOD-005 evidence; no race-safety claim is made here. Recommended next implementation: MOD-003A with its remaining role-policy decisions, not additional MOD-002 work. Stopped after this task.


## MOD-003A stage 1 verification — 2026-10-28

Scope: existing self-service member PATCH only. Principal dependency checked in actual code; frontend caller is an own-team rename. Implemented owner-constrained teamName-only UPDATE, explicit principal errors, generic 404 for missing/foreign targets and 400 for unknown fields/non-object/nonblank-string violations. Response fields and valid rename behavior retained. Trusted general model update unchanged. Commissioner role does not bypass owner checks on this route; remaining administrative policies were not inferred.

| Command (root unless specified) | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_member_profile_authorization.py'` before implementation | Seven tests; 14 assertion/subtest failures, exit 1. Real synthetic unauthorized renames and score/order mutations reproduced; missing target returned old 400. |
| Same targeted command after implementation | 7/7 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 113/113 pass, exit 0; no errors/skips/expected failures, original MOD-002 denial assertions unchanged. Intentional bootstrap ERROR fixture output remains. |
| `front-end`: `node --test --experimental-strip-types tests/profileApi.test.ts` before frontend narrowing | 8/9 pass, one failure on score/order payload, exit 1. |
| `front-end`: `node --test --experimental-strip-types tests/*.test.ts` after narrowing | 43/43 pass, exit 0, including new rename request test. |
| `front-end`: `./node_modules/.bin/tsc -p tsconfig.app.json --noEmit` | Exit 0. |
| `front-end`: `./node_modules/.bin/eslint src/api/leagues.ts src/types/leagueMember.ts tests/profileApi.test.ts` | Exit 0; dependency-age notice only. Full lint not rerun; prior findings remain. |
| `git diff --check` | Exit 0. |

Seven new backend tests reuse the existing synthetic in-memory profile SQL result adapter and actual principal JWT/middleware/league route/model paths. Added synthetic League/LeagueMember rows for commissioner A, member B and nonmember C, with B also owning a member in another league. Own renames preserve all response/DB fields except teamName. Foreign targets, including commissioner's attempt to rename B and nonmember/cross-league substitution, fail without mutation. Extra score/order/identity/league fields cannot cause partial writes. Missing/expired auth, absent/ambiguous profile, invalid payload and missing member have explicit outcomes. Ownership is part of the UPDATE predicate; no separate check-then-write lookup. No parent league ID exists in this route; own membership defines its resource scope. The SQL fixture is not a deployed schema or PostgreSQL/RLS/concurrency test.

Frontend test executes actual API module with substituted transport and confirms even stale JavaScript extra arguments cannot serialize score/order fields. Type-check confirms the only UI caller matches the narrowed signature. No browser rendering or account-switch verification claimed.

Remaining: MOD-003A is partial; own-league listing/creation, commissioner administration, moderation/admission, week generation and scoped reads are unchanged. Next bounded recommendation: principal-bound `/api/league/byUser`; Q1 nonmember read and Q4 operational policy still need resolution for later slices. No new schema/migration, dependency, production/network/private-row access, environment values, job/app factory/listener or deployment. Stop after selected stage, not another backlog task.


## MOD-003A stage 2 verification — 2026-10-28

Scope: `/api/league/byUser` only. Actual resolver, current handler/model SQL and frontend caller checked before implementation. Body userId remains required for compatibility but must match the resolved principal; only the principal's ID reaches the listing model. Foreign ID is 403 `user_identity_mismatch`; missing/ambiguous profile or subject uses explicit resolver errors; malformed JSON objects/ID/stage types get safe 400 messages. Own successful payload and stage semantics remain unchanged. No public visibility/admin role decisions made.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_own_league_listing.py'` before implementation | Nine tests, nine assertion/subtest failures and one error; exit 1. Foreign listing and identity failures returned 200; invalid userId string raised uncaught ValueError. |
| Same targeted command after implementation | 9/9 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 122/122 pass, exit 0; no errors/skips/expected failures. Prior profile/member denial tests preserved and passing. Intentional bootstrap ERROR fixture output remains. |
| `git diff --check` | Exit 0. |

Nine added tests use actual JWT verification/middleware/registered routes/principal and model listing query with synthetic SQLite profiles, leagues, sport and memberships. They verify exact retained own fields (member-specific name/order/points, nullable current week and other league metadata), both users' isolation, commissioner/member/nonmember identity cases, empty own membership, stage active/completed/all/case/default/null/unknown-string behavior, matching numeric-string ID, forged body/header/query identities, missing/invalid/expired JWT, absent/ambiguous app identity/empty subject and invalid request shapes/IDs/stage. Denials are checked before substituted model lifecycle sync is reached.

Tests substitute `sync_due_league_statuses` to avoid unrelated lifecycle transitions; production status-sync code remains unchanged. SQL current-week interval expression is adapted to SQLite datetime with fixed now and no Week rows, and settings fixture is SQLite TEXT. These checks validate identity/query binding and compatible SQL fields, not PostgreSQL interval/JSON types, current-week boundaries, lifecycle transitions, deployed RLS/locking/concurrency or query performance. No frontend tests/type/lint rerun because frontend code is unchanged; prior results stay historical.

Remaining MOD-003A: league creation, commissioner administration/moderation/admission, operational week generation and other league-scoped reads. Recommended next: bind creation's commissioner/initial membership to the authenticated principal; Q1 nonmember read and Q4 operational decisions remain for their slices. No schema/migration/dependency/production/network/environment-value access, app factory/listener startup, job or deployment; no other backlog task started. Stopped after stage 2.


## MOD-003A stage 3 verification — 2026-10-28

Scope: principal-bound league creation and its initial membership only. Actual resolver/model/caller inspected. Commissioner remains a required compatibility field but must match principal; only resolved principal.user_id reaches the create model. Foreign commissioner returns 403 `commissioner_identity_mismatch`, invalid ID/object/missing fields JSON 400, auth/subject/profile absence/ambiguity explicit 401/403. Matching integer and numeric-string commissioner inputs remain supported. Success remains 201 with existing league/sportInfo/creatorMemberId shape; model retains team-name trimming, settings/rule/timezone handling and week initializer call. Frontend caller already conforms and is unchanged.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_league_creation_authorization.py'` before implementation | Eight tests, six assertion/subtest failures, two SQLite constraint errors on invalid commissioner values; exit 1. Foreign/missing/empty/ambiguous identities incorrectly permitted creation. |
| Same targeted command after implementation | 8/8 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 130/130 pass, exit 0; no errors/skips/expected failures. Existing denial assertions remain intact. Intentional bootstrap ERROR fixture output remains. |
| `git diff --check` | Exit 0. |

Eight tests reuse the guarded runner/profile fixture with synthetic League/LeagueMember/Sport rows, real JWT/middleware/routes/model and SQLite foreign keys. Creation fixture extracts the model's INSERT/RETURNING body from PostgreSQL CTE, replaces JSONB cast with a SQLite parameter and supplies synthetic equivalent sportInfo/settings projection. It executes real membership INSERT SQL. Tests check persisted commissioner and member user IDs for both A/B, response fields, initial points/order/name, forged body/query/header identities, required and invalid object/ID values, matching numeric-string commissioner, model name validation, and no persisted league/member or week initialization on rejection. Week initializer is substituted; this is not PostgreSQL CTE/JSON compatibility, actual scheduling, RLS, concurrency or browser verification.

No frontend checks rerun because frontend unchanged; previous frontend/lint/type results stay historical. The model's pre-existing league/member commit followed by week initialization is unchanged; initializer failure can occur after creation commits, and rollback/retry semantics for that boundary were not tested or repaired here. No schema/migration/dependency, production/network/private-row/environment values, app factory/listener, real week/job or deployment used.

MOD-003A remains partial: next recommended slice is principal-bound commissioner-only league settings PATCH, then other administration/moderation/admission/scoped-read operations. Q1 nonmember visibility and Q4 operational/week-generation policy remain open. Stop after stage 3; no other task started.


## MOD-003A stage 4 verification — 2026-10-28

Scope: commissioner-only league settings PATCH. Actual principal dependency, original update model/commissioner helper, frontend caller and existing rules tests checked. Handler now resolves principal, validates object shape and uses explicit checked `update_league_as_commissioner` model entry point. Shared update implementation verifies current commissioner before rules/settings validation and includes commissioner in final UPDATE predicate. Original trusted `update_league` remains separate from HTTP identity. Existing success fields, field allowlist (including name/capacity/status/settings/deadlines), rules-version/timezone behavior and missing-league 400 retained. No new role/lifecycle policy inferred.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_league_settings_authorization.py'` before implementation | Eight tests, six assertion/subtest failures; exit 1. Unauthorized member/nonmember/foreign commissioner and missing identity/empty-subject writes, plus stale-owner write reproduced. |
| Same command after implementation and operational-failure case addition | 9/9 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 139/139 pass, exit 0; no errors/skips/expected failures. Trusted-model rules tests and prior denial assertions unchanged and passing. Intentional bootstrap ERROR fixture output remains. |
| `git diff --check` | Exit 0. |

Nine tests use real JWT/middleware/registered route/model logic and synthetic profiles/leagues/member rows. SQL fixture extracts PostgreSQL UPDATE CTE's UPDATE/RETURNING body, adapts JSONB cast to SQLite storage and supplies equivalent synthetic sportInfo/decoded settings projection. It also executes actual league reads and parameterized owner predicate. Assertions cover valid A/B commissioner saves/response fields/persisted deadlines/name/capacity and pinned rules version; ordinary member, nonmember and another league commissioner denial; forged body/header/query actor and ownership-transfer attempts; missing/invalid/expired JWT, empty subject and missing/ambiguous application identity; existing empty-patch/settings/version/timezone/missing-target validation; non-object input; safe generic 500 on injected operational DB read error with unchanged row.

A deterministic fixture hook changes commissioner between initial read and UPDATE; former owner is denied and requested name/updatedAt do not change. This checks that final write enforces commissionership, not PostgreSQL transaction interleaving/locking or isolation levels. Shared read/write remains two transactions; no general concurrency/whole-operation atomicity guarantee. SQLite does not verify PostgreSQL CTE/JSON/types/RLS or browser behavior. Frontend unchanged; checks not rerun and historical results not claimed fresh.

Remaining MOD-003A: bind admission actors starting with join-request creation, then moderation/member removal/deletion and other scoped reads/week generation. Q1 nonmember visibility/Q4 operational policy remain open; no broader REST authorization completion claimed. No schema/migration/dependency/production/network/private-row/environment-value access, app/listener, job or deployment. Stop after stage 4; no other task started.


## MOD-003A stage 5 verification — 2026-10-28

Scope: join-request creation identity only. Actual model/caller/previous dependencies checked; legacy body userId remains required but must match verified principal. Only principal.user_id and URL league_id reach unchanged create_join_request model. Foreign userId is 403 `user_identity_mismatch`, missing/invalid ID/object JSON 400, principal absence/ambiguity/auth errors explicit 401/403. Success remains 201 with existing JSON fields; trimmed name, message, existing-member rejection and sequential own pending-repeat behavior retained.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_join_request_authorization.py'` before implementation | Nine tests, nine assertion/subtest failures; exit 1. Foreign creation/pending lookup and empty/missing identity bypasses reproduced; invalid boolean/fractional IDs also created requests. Some later subtest no-write assertions observe the preceding unauthorized fixture insert. |
| Same command after implementation | 9/9 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 148/148 pass, exit 0; no errors/skips/expected failures. Previous denial assertions remain unchanged. Intentional bootstrap ERROR fixture output remains. |
| `git diff --check` | Exit 0. |

Nine tests reuse the guarded runner and actual profile SQLite result fixture, with synthetic League/LeagueMember/LeagueJoinRequest tables, real JWT verification/middleware/registered route/model SQL. No SQL dialect adaptation needed for this query subset. Tests inspect persisted owner/league/name fields for A/B, deny forged userId before insert, prevent another user's pending response leakage through creation, ensure header/query/body actor and league fields cannot override verified owner/URL, retain own repeat response/no-overwrite, existing-member/name contracts, numeric-string ID compatibility and auth/identity/shape/type errors. Synthetic duplicate app mappings are created only in the disposable fixture. No existing assertions weakened or skipped.

No frontend changes/checks rerun; Discover already sends matching current user ID and team name. SQLite does not establish deployed PostgreSQL FK/role/RLS/concurrency behavior or browser journeys. Sequential pending reuse is not a concurrent uniqueness guarantee. Discoverability, private-league visibility, capacity/status admission policy, approval/denial/cancellation and moderator permissions are unchanged and outside this stage; broader Q1/Q4 decisions remain open. No production/network/environment/private-row access, app/listener/job, schema/migration/dependency/deployment or unrelated cleanup.

MOD-003A remains partial. Recommended next: commissioner-only join-request listing bound to principal, then remaining moderation and scoped operations. Stop after stage 5; no other task started.


## MOD-003A stage 6 verification — 2026-10-28

Scope: commissioner-only join-request listing. Actual principal/helper/model/caller and moderator rendering inspected. Required actingUserId remains compatibility assertion, must match principal (403 actor_identity_mismatch), and never grants authority. Checked model entry point verifies commissioner for URL league and final request SELECT includes commissioner EXISTS predicate; trusted original listing shares query implementation separately. Missing/ambiguous app identity/auth explicit 401/403; invalid object/actor/status types JSON 400. Existing authorized response/contact fields, status filter/descending order/empty results and missing-league 400 are preserved. No approval/denial/cancellation changes.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_join_request_listing_authorization.py'` before implementation | Nine tests, nine assertion/subtest failures, exit 1. Forged commissioner actor and stale check exposed applicant data; absent identity/empty subject also bypassed checks. Invalid status list logged DB binding error and returned 500 instead of 400. |
| Same command after implementation | 9/9 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 157/157 pass, exit 0; no errors/skips/expected failures. Existing profile/member/admission denial assertions unchanged. Intentional bootstrap ERROR fixture output remains. |
| `git diff --check` | Exit 0. |

Nine tests reuse guarded runner/profile SQLite fixture (extended result interface) with synthetic commissioners/members/nonmember and multiple leagues/request rows. Real JWT/middleware/registered routes/model/helper/parameterized SQL execute without dialect adaptation. Exact own-league response including authorized userEmail/userDisplayName, descending order, status filter/unknown/empty/null behavior, empty league, numeric-string actor, foreign roles, forged body/header/query scope, auth/identity and input errors are asserted. Synthetic role-change hook modifies commissioner immediately before final SELECT and verifies 200 empty list/no applicant data; this is intentional fail-closed data behavior after initial check passes, not a 403 race outcome or PostgreSQL concurrency/locking proof. Duplicate identity setup is disposable only.

Frontend unchanged and checks not rerun; historical results not claimed fresh. No live DB/RLS/direct Supabase/browser verification, post-query revocation guarantee, production/network/environment/private-row access, app/listener/job, schema/migration/dependency/deployment or unrelated cleanup. Q1 nonmember visibility/discoverability and Q4 operational permissions remain open.

MOD-003A remains partial. Next recommended slice: commissioner join-request approval bound to verified principal, followed by remaining moderation and scoped operations. Stop after stage 6; no other task started.


## MOD-003A stage 7 verification — 2026-10-28

Scope: principal-bound commissioner approval only. Actual model/caller inspected. Required body actingUserId remains compatibility assertion matching principal; mismatch 403 actor_identity_mismatch; malformed object/ID 400; auth/identity explicit 401/403. Checked model locks and verifies URL league commissioner inside approval transaction before mutations; request read and resolution UPDATE bind both URL league/request, and resolvedByUserId uses principal ID. Existing 200 request/member shape and pending/nonpending/replay/missing-resource contracts preserved. Trusted model remains direct-call/HTTP-independent, sharing approval transaction body and league-first lock order.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_join_request_approval_authorization.py'` before implementation | Nine tests, nine assertion/subtest failures, exit 1. Forged commissioner actor/missing identity/empty subject could approve; invalid actor types also caused mutation. Some subsequent subtest no-change assertions observed prior unauthorized fixture mutation. |
| Same command final (after trusted-call regression added and lock-order alignment) | 10/10 pass, exit 0. |
| `python3 api/tests/run_isolated.py` final | 167/167 pass, exit 0; no errors/skips/expected failures. Prior denial assertions unchanged. Approval rollback case intentionally logs synthetic exception; bootstrap ERROR output remains intentional fault fixtures. |
| `git diff --check` | Exit 0. |

Ten tests reuse guarded runner/profile fixture with synthetic applicants, commissioner/member/nonmember accounts, leagues/members/requests/sport configuration. Real JWT/middleware/registered routes/model transaction executes against SQLite; FOR UPDATE removed only in fixture, PostgreSQL UPDATE alias/RETURNING/JSONB syntax adapted, and synthetic JSON/GREATEST functions support the existing league update branch. Tests inspect both commissioners' persisted resolution actor/member owner/name/order and response shape; deny forged actor, wrong role/foreign league/request, missing/nonpending/replay, invalid actor/shape and auth/identity failures without state changes. Body/header/query cannot replace URL resource or principal. Injected failure after member INSERT proves synthetic membership/league/request state rolls back together. Trusted direct call without Flask request context remains functional and accepts audit actor metadata as before; HTTP cannot select that path.

Code review aligned trusted and checked approval entry points to league-before-request locking, avoiding opposite approval lock orders introduced by the new checked path. This is code-level ordering, not a PostgreSQL deadlock/concurrency proof. SQLite rollback is not deployed RLS/constraint/isolation/locking validation; counter/rounds/capacity policy and broader admission races remain unchanged/unverified. No frontend checks rerun (caller unchanged), production/network/environment/private-row access, app/listener/job, schema/migration/dependency/deployment or unrelated cleanup.

MOD-003A remains partial. Next: commissioner denial bound to principal, reviewing known malformed denial SQL finding before valid-flow assertions; other moderation and scoped operations/Q1/Q4 remain. Stop after stage 7; no other task started.


## MOD-003A stage 8 verification — 2026-10-28

Scope: commissioner denial authorization and its necessary canonical-status/SQL repair. Handler resolves principal, requires legacy matching actingUserId, passes only principal actor and URL scope to checked model. Checked transaction locks/verifies league commissioner before scoped request lock/update. Both checked/trusted entry points use league-first order and shared denial body, with trusted path independent of HTTP identity. Fixed lowercase pending comparison and malformed trailing-comma SQL; final UPDATE guards request ID, URL league and PENDING. Intended 200 DENIED response with principal resolver restored; wrong role/actor 403, auth/identity 401/403, malformed body/ID and missing/foreign/resolved request 400. Frontend unchanged and already conforms.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_join_request_denial_authorization.py'` before implementation | Nine tests, ten assertion/subtest failures and one error from direct model rejecting canonical PENDING; exit 1. Intended denial failed, identity/forged-actor checks were absent, and rollback path was unreachable. |
| Same command after implementation | 9/9 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 176/176 pass, exit 0; no errors/skips/expected failures. Existing assertion set preserved. Approval rollback's logged synthetic exception and bootstrap ERROR fixture output remain intentional. Denial rollback logs are captured/asserted by its test. |
| `git diff --check` | Exit 0. |

Nine tests reuse guarded runner/profile SQLite fixture with synthetic commissioners/members/nonmember, two leagues and pending/approved/denied/cancelled request rows. Fixture CHECK admits uppercase canonical statuses; only FOR UPDATE is removed from model SQL. Actual denial UPDATE/RETURNING executes, including fixed comma and scope/status predicates. Assertions verify both commissioners' successful request fields/persisted resolver and no league/member mutation; deny forged actor, wrong role/league/request, all resolved states/replay; ensure body/header/query cannot replace URL or resolver; explicit auth/missing/ambiguous identity and malformed-input errors; synthetic fault after actual UPDATE rolls back resolution; trusted direct model remains callable without HTTP request.

SQLite CHECK is synthetic, not deployed PostgreSQL verification. Row locks, concurrency/deadlocks, deployed SQL/types/RLS/status constraints and real browser flow remain unverified; no disposable PostgreSQL command run. No frontend checks rerun because caller unchanged; historical results stay historical. No schema/migration/dependency/production/network/environment/private-row access, app/listener/job or deployment.

MOD-003A remains partial. Necessary denial repair overlaps MOD-011; its backlog note now records completed denial code/synthetic checks, with cancellation and required disposable PostgreSQL validation still open. Next MOD-003A slice: authenticated own-request cancellation, reviewing its known lowercase status bug, followed by remaining moderation/scoped operations and Q1/Q4 decisions. Stop after stage 8; no broader task started.


## MOD-003A stage 9 verification — 2026-10-28

Scope: authenticated own-request cancellation and necessary canonical-status repair. Handler resolves principal, requires matching legacy userId (403 mismatch), passes verified owner/URL scope only. Model's locked owner check retained, no commissioner override; fixed PENDING comparison and guarded final UPDATE by request ID/league/user/PENDING. Intended 200 CANCELLED response/timestamp restored with resolvedByUserId unchanged (normally null). Auth/identity errors explicit 401/403, malformed object/ID 400, foreign owner 403, missing/foreign/resolved request 400. Trusted direct model remains HTTP-independent and retains request-owner enforcement.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_join_request_cancellation_authorization.py'` before implementation | Ten tests, twelve assertion/subtest failures and one direct-model error rejecting canonical PENDING; exit 1. Intended cancellation was broken and HTTP identity/actor gaps reproduced as wrong error outcomes. |
| Same command after implementation | 10/10 pass, exit 0. |
| `python3 api/tests/run_isolated.py > /tmp/mod003a-stage9-tests.log 2>&1` | 186/186 pass, exit 0; no errors/skips/expected failures. Summary inspected; existing assertions preserved. Approval rollback exception/other bootstrap ERROR fixture output remains intentional. |
| `git diff --check` | Exit 0. |

Ten tests reuse guarded runner/profile SQLite result adapter with synthetic League/LeagueMember/request rows and uppercase-status CHECK; only FOR UPDATE is removed. Actual cancellation UPDATE/RETURNING executes. Assertions inspect A/B own cancellations/exact fields/persisted status/timestamp and unchanged resolver; reject forged IDs, foreign owners including target league commissioner, foreign URL request IDs, all resolved statuses/replay, auth/missing/ambiguous identity/invalid shape/types with unchanged state. Body/header/query resource/resolver substitutions ignored. Fault injected after actual UPDATE rolls back to prior request state; logs captured. Direct model rejects nonowner and succeeds for owner without HTTP context. No existing assertions weakened/skipped.

SQLite CHECK/transaction results are not deployed PostgreSQL SQL/types/status-CHECK/RLS/row-lock/concurrency verification. No frontend checks rerun (wrapper unchanged, no screen caller found); historical frontend/type/lint results stay historical. No production/network/private-row/environment access, app/listener/job, schema/migration/dependency/deployment or unrelated cleanup.

MOD-003A remains partial: next principal-bound commissioner member removal, then deletion/remaining scoped reads/week generation with relevant Q1/Q4 decisions. MOD-011 now has denial/cancellation code repairs and synthetic regression evidence recorded; it remains open for its required disposable PostgreSQL validation. Stop after stage 9; no broader task started.


## MOD-003A stage 10 verification — 2026-10-28

Scope: authenticated commissioner member removal. Actual existing locked model and frontend caller inspected. Handler now resolves principal, treats required actingUserId as matching integer/numeric-string assertion (403 mismatch), validates JSON object/actor/boolean shift flag (400), and supplies principal ID plus URL resources to model. Existing model already locks/checks league commissioner and scoped member; wrong commissioner now PermissionError/403 instead of ValueError/400. Valid 200 response/default true/explicit false shifting, missing/foreign target/commissioner-removal 400 and replay/count/order behavior retained. Trusted direct model remains HTTP-independent with authority enforcement; frontend unchanged.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_member_removal_authorization.py'` before implementation | Twelve tests, fourteen assertion/subtest failures and one direct-model error-class mismatch; exit 1. Forged actor/missing identity could remove, invalid actor/shift inputs coerced, wrong role mapped to 400. Later subtest state assertions also observed preceding unauthorized synthetic removals. |
| Same command after implementation | 12/12 pass, exit 0. |
| `python3 api/tests/run_isolated.py > /tmp/mod003a-stage10-tests.log 2>&1` | 198/198 pass, exit 0; no errors/skips/expected failures. Previous assertions unchanged. Intentional approval rollback exception/bootstrap ERROR fixture output remains. |
| `git diff --check` | Exit 0. |

Twelve tests reuse guarded runner/profile SQLite fixture with synthetic commissioner/member/nonmember profiles, two leagues and distinct member IDs/orders. Actual JWT/middleware/routes/model SQL execute with FOR UPDATE removed and synthetic now/GREATEST functions. Tests inspect successful A/B scoped removals, exact member-list payload and retained points, default shifting and explicit no-shift, unchanged other-league data; deny forged actors/other roles/foreign member IDs, missing targets and commissioner removal; reject auth/missing/ambiguous identity/shape/actor/nonboolean flag; verify actual DELETE fault rollback and replay without extra changes; direct model outside request context still enforces commissioner.

Fixture has no dependent roster/history rows: cascading deletes/FK enforcement, historical integrity, deployed PostgreSQL roles/RLS/row locks/concurrency, browser behavior and nullable-order cases are not verified. Existing league-status policy/count algorithm not redesigned. No frontend checks rerun, schema/migration/dependency, production/network/private-row/environment-value access, app/listener/job or deployment.

MOD-003A remains partial. Next recommended slice: commissioner league deletion bound to principal, then remaining scoped reads/week generation with Q1 nonmember visibility/Q4 operator decisions. Stop after stage 10; no other task started.


## MOD-003A stage 11 verification — 2026-10-28

Scope: authenticated commissioner league deletion only. Actual locked model and frontend caller checked. Handler requires principal and matching legacy actingUserId assertion (403 mismatch), validates object/ID (400), and passes principal ID/URL league only. Existing model commissioner check now returns PermissionError/403 and final DELETE includes commissioner predicate. Valid 200 fields and missing/replay 400 retained. Trusted model remains callable without HTTP context and still enforces commissioner. No profile deletion or new retention/status policy.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_league_deletion_authorization.py'` before implementation | Nine tests, twelve assertion/subtest failures and one direct-model error-class mismatch, exit 1. Forged actor/missing identity/invalid types could delete synthetic leagues; wrong commissioner mapped to 400. Subsequent no-change assertions also observed preceding unintended fixture deletions. |
| Same command after implementation | 9/9 pass, exit 0. |
| `python3 api/tests/run_isolated.py > /tmp/mod003a-stage11-tests.log 2>&1` | 207/207 pass, exit 0; no errors/skips/expected failures. Existing assertions preserved. Intentional approval rollback exception/bootstrap ERROR fixture output remains. |
| `git diff --check` | Exit 0. |

Nine tests reuse guarded runner and removal/profile SQL result adapter, synthetic accounts/two leagues and representative SQLite ON DELETE CASCADE member/request rows. Actual JWT/middleware/registered routes/model SQL run with FOR UPDATE removed only. Assert both commissioners' own deletion and exact response, matching numeric-string identity, other-league and child preservation, forged actor/member/nonmember/foreign commissioner denial, URL versus body/header/query scope, auth/missing/ambiguous identity/shape/type errors, missing/replay contracts, actual DELETE fault rollback restoring league/children and direct-model commissioner enforcement without HTTP context. No assertions weakened/skipped.

SQLite cascade fixture is a deliberately small test schema, not a deployed schema/migration or historical-retention guarantee. Actual PostgreSQL roles/RLS/locks/concurrency/deadlocks, complete dependent FK cascades/history and browser confirmation flow unverified. No frontend checks rerun (caller unchanged); historical results remain historical. No production/network/private-row/environment-value access, app/listener/job, schema/migration/dependency/deployment or unrelated cleanup.

MOD-003A remains partial. Next requires Q1 nonmember read/preview policy for remaining league details/rules/member/conference reads and Q4 standalone HTTP week-generation authority before adopting those routes. No new global admin/operator inferred. Separate deployed-policy/schema/PostgreSQL evidence tasks remain open. Stop after stage 11; no other task started.


## MOD-003A remaining-scope policy review — 2026-10-28

Read actual league/schedule registrations and relevant read/preview/week caller paths; five routes remain grouped into two implementation stages (four league reads, then standalone week generation), plus final verification/handoff. No tests executed or application/test changes in this review; latest actual suite remains stage 11's 207/207, not a new verification run. User choices requested for open Q1 nonmember visibility and Q4 standalone generation authority; proposed limited discoverable previews/member-only full reads and commissioner-only HTTP generation await response. Automatic creation/internal week initialization is separate. No new policy or broader security guarantee claimed, and no production/network/environment-value access, app/listener/job/schema/migration/deployment occurred.


## MOD-003A final read policy and internal-only generation — 2026-10-28

Accepted policy: limited discoverable previews for authenticated nonmembers; full details/rules/member data/conferences only for members and commissioner; private leagues restricted. Standalone HTTP generation disabled, with trusted internal/automatic model calls unchanged. These user answers supersede the preceding pending Q1/Q4 proposal.

| Command / check | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_league_read_authorization.py'` before implementation | Initial 7 tests: 24 failures and 1 error, exit 1; unauthorized/private data and missing app-identity checks exposed. |
| `python3 api/tests/run_isolated.py 'test_http_week_generation_disabled.py'` before implementation | 2 tests, 12 failing subtests, exit 1; HTTP still invoked generation. |
| Frontend `node --test --experimental-strip-types tests/profileApi.test.ts` before preview helper | 9 pass / 10 total, exit 1; preview helper missing. |
| Added explicit full-projection contract, before implementing | Backend 10-test read suite: 2 failures, exit 1; nonmembers still received partial 200 responses to `view=full`. Frontend 10 pass / 11 total, exit 1; full API helpers omitted the projection parameter. Both fixed without reducing assertions. |
| First full backend run after endpoint implementation | 216 tests, 2 failures and 1 error, exit 1; three existing rules-format tests lacked newly required authenticated identity setup. Added real middleware/synthetic valid JWT/profile and full-access model fixture; original assertions unchanged. Two earlier preview failures were a new SQLite result adapter missing `.all()`, corrected in fixture only. |
| Independent review regression, before projection correction | Explicit member/commissioner details `view=preview` returned full data and invoked lifecycle sync. New 11-test read suite failed 5 assertions/subtests, exit 1. Corrected details projection condition; reduction now applies regardless of full entitlement. Static review found no further material issue. |
| Final `python3 api/tests/run_isolated.py > /tmp/mod003a-final-backend.log 2>&1` | **220/220 pass**, exit 0; no skips or expected failures. Existing profile-isolation denials pass unchanged. Intentional rollback/bootstrap fault-test messages are not suite failures. |
| Frontend `node --test --experimental-strip-types tests/*.test.ts` | **45/45 pass**, exit 0. |
| Frontend `./node_modules/.bin/tsc -p tsconfig.app.json --noEmit` | Exit 0. |
| Frontend `./node_modules/.bin/eslint src/api/leagues.ts src/types/leagueMember.ts src/screens/League/DiscoverLeaguePage.tsx tests/profileApi.test.ts` | Exit 1: three existing `no-explicit-any` errors at Discover lines 53/84/146, confirmed unchanged in HEAD. No suppression/cleanup. Tool also reports its stale browser-baseline-data notice; no dependencies updated. |
| Same focused ESLint excluding Discover | Exit 0 for API/types/tests. |
| `git diff --check` | Exit 0. |

Eleven read integration tests reuse the existing guarded harness/profile database with synthetic users, discoverable/private leagues, memberships, rules/conferences and empty week/score fixtures. They execute verified JWT middleware, actual registered endpoints and model SQL. They assert exact reduced projections, member/commissioner-without-membership full reads, private/foreign/missing restrictions, missing/expired/missing-subject and missing/ambiguous application identities, forged actor/query/header values, inability to elevate with projection parameters, explicit member/commissioner details-preview reduction without lifecycle sync, and membership/discoverability revocation immediately before scoped data queries. Preview/denial paths do not invoke global status synchronization. Two schedule tests assert no call to generation for authenticated roles/missing profiles/forged trusted flags/invalid bodies and middleware 401 for anonymous requests. Two frontend actual-module transport regressions verify authenticated reduced and explicit-full projections.

The credential-free runner disables dotenv/network/real engine construction and does not import the app factory. Tests adapt PostgreSQL interval syntax for SQLite and substitute global lifecycle synchronization; they do not establish real PostgreSQL locks/RLS/transactions/cascades/concurrency or browser rendering. No frontend production build or real browser was run in this final stage. Existing full-detail global status synchronization remains unchanged (MOD-020). Previous PostgreSQL evidence tasks, including MOD-011, stay open. No production/network/credential/environment-value access, application listener/job, migration/schema/dependency/deployment or other task implementation. MOD-003A is complete; recommended next is MOD-003B, separately scoped after dependency/policy review.


## MOD-003B stage 1 — authenticated member-only draft snapshots — 2026-10-28

Scope: only registered GET `/api/draft/state/<league_id>`. Verified principal is resolved first; initial League SELECT includes requested-league membership before draft reads and completed-state repair. Existing socket member-only policy is preserved, including denial for commissioner without membership and discoverable nonmembers. Valid snapshot and trusted default/connection model-call contracts remain. Commands, sport-round metadata and sockets are unchanged; no broader authorization-completion claim.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_draft_state_authorization.py'` before implementation | 10 tests: 12 assertion/subtest failures and 1 error for new missing reader argument, exit 1. Old handler accepted missing/ambiguous app identities, nonmembers and forged identities, returned missing league 400 and printed raw operational failures. Existing valid snapshot/repair fixtures passed. |
| Same command after implementation | **10/10 pass**, exit 0. |
| `python3 api/tests/run_isolated.py > /tmp/mod003b-stage1-backend.log 2>&1` | **230/230 pass**, exit 0; no skips or expected failures. Existing profile-denial and draft transport assertions unchanged and passing. Intentional rollback/bootstrap fault-fixture output remains. |
| `git diff --check` | Exit 0. |
| Independent focused read-only code review | No material findings; reviewer did not independently rerun tests. |

Ten tests reuse the existing synthetic profile/read SQL adapters and credential-free harness; actual verified JWT middleware, registered draft routes and snapshot model SQL execute. Fixture includes unique app identities, two member leagues, a commissioner without membership, an outsider, live/paused/stale-complete state, actual picks/conference metadata and future turns. Assertions cover exact full response fields and nested member/pick/next-turn contracts, member/league substitutions, discoverable/private/missing denial, forged body/query/header/job identities, expired/invalid/empty subject and missing/ambiguous app identities, permission removal immediately before the first scoped query, no denied DraftState reads/repair, persisted authorized repair, preflight, generic operational errors without raw stdout logging and default/supplied-connection calls outside HTTP context. Existing socket membership SQL is compared directly for uniquely mapped users; its PostgreSQL UUID cast is adapted only in the fixture. No live Socket.IO integration test or socket ambiguity repair is claimed.

The existing runner clears environment, disables dotenv/network/deployed engine creation and avoids the app factory. SQLite does not prove PostgreSQL/RLS/locking/concurrent revocation or deployed schema behavior. The initial SQL gate is not serialization against a removal during later snapshot queries. No frontend changes/build/type/lint/browser checks rerun; previous results stay historical. No production/network/private rows/credentials/environment-value access, listener/worker/job, schema/migration/dependency/deployment or unrelated cleanup. MOD-003B remains partial; next is principal-bound owned-member live picks, then commissioner controls/order and explicit manual/operator policy. Stop after this bounded stage; no other task started.


## MOD-003B stage 2 — principal-bound owned-member live picks — 2026-10-28

Scope: only POST `/api/draft/pick`, principal resolution then owned-member/requested-league check inside existing model transaction, repeated in final INSERT SELECT. No control/manual/socket/schema/algorithm adoption. Safe object/ID parsing; successful pick/slot/state/event, 409 conflicts, HTTP week default 0/model default 1 and explicit weeks preserved.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_live_pick_authorization.py'` before implementation | Initial 9 tests: 19 failures and 2 errors, exit 1. Unauthorized picks and missing app identity accepted, bool/float coercion and uncaught malformed-ID conversion observed. Also exposed fixture timestamp/COUNT-cast gaps and cascading fixture mutations after unauthorized successes. |
| Fixture correction / intermediate run | Adapted UTC timestamps and COUNT cast. Initial broad `::int` removal also damaged `::interval`; narrowed to exact COUNT-cast text. No assertions changed. Before correction, first post-implementation target had 2 failures/1 error due interval adapter; after correction 9/9 passed. |
| First full backend run after implementation | 239 tests, 6 failures, exit 1, all existing mock-domain transport tests bypassing newly required auth. Added real middleware/profile/synthetic JWT setup; all existing assertions retained. |
| `python3 api/tests/run_isolated.py 'test_draft_contracts.py'` after authenticated setup | 3/3 pass, exit 0, including exact response and matching room-event assertions. |
| `python3 api/tests/run_isolated.py > /tmp/mod003b-stage2-backend.log 2>&1` after adding commissioner-own-turn/explicit-week case | **240/240 pass**, exit 0; 10 new live authorization tests, no skips/expected failures. Existing state/profile denial and draft contract assertions pass. Intentional bootstrap/rollback fixture output remains. |
| `git diff --check` | Exit 0. |
| Independent focused read-only review | No material findings; reviewer did not independently rerun tests. |

Live tests execute actual JWT/middleware/registered routes/model transaction/ownership checks/INSERT/slot/state/snapshot and cap queries on synthetic data. Only the socket emitter is substituted. Reuses prior state/profile/read adapters with a fixture database factory hook; SQLite adapts FOR UPDATE, interval calculation, exact COUNT cast, UTC timestamp values and SQLAlchemy-style integrity exceptions. Covers successful two-user/two-league picks and commissioner own turn, default/explicit/numeric-string input contracts, foreign/missing/cross-league membership and spoofed body/header/query/job identities, expired/empty/missing/ambiguous identity, malformed object/ID errors, 409 turn/expiry/unique conflicts, same-connection ownership mutation before guarded INSERT, persisted-data rollback after slot failure, no denied success emission and trusted model calls outside HTTP context.

The late-mutation test establishes the final predicate and rollback in the synthetic transaction, not a PostgreSQL concurrent-removal guarantee; no new row locks or lock order introduced. Existing post-commit snapshot/broadcast failure boundary remains non-atomic and unchanged. Completion/finalization branches, database/RLS/locking/deadlock/concurrent role changes, browser and live Socket.IO behavior are not established by this fixture. No frontend changes/checks rerun. No production/network/private rows/credentials/environment-value access, factory/listener/worker/job, schema/migration/dependency/deployment or unrelated cleanup. MOD-003B remains partial; next is commissioner controls/order authorization, with explicit manual/operator policy before that later stage. Stop after this stage; no other task started.


## MOD-003B stage 3 — commissioner controls and order — 2026-10-28

Scope: start/pause/resume/finalize/order only. Verified principal supplies actor; body actor fields assert matching identity only, finalize retaining its required field. Existing UI/finalize commissioner role is checked before domain work and again pre-commit in the same model transaction, including force-finalize authorization/mutation. No lock hierarchy or algorithm changes. Safe JSON input errors and existing valid200/payload/event/trusted contracts preserved.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_draft_control_authorization.py'` before implementation | 10 tests, 60 assertion/subtest failures, exit 1. Noncommissioners could mutate via controls/order or forged actor; no final authority check. Legitimate success/trusted fixture cases passed. |
| First target/full runs after implementation | 10-test target and 250-test full suite each failed 3 subtests (pause/resume/finalize) because preceding start rollback left no state for the next scenario. Fixed fixture preparation to upsert valid per-case DraftState; assertions unchanged. |
| Target command after fixture correction | **10/10 pass**, exit 0. |
| `python3 api/tests/run_isolated.py > /tmp/mod003b-stage3-backend.log 2>&1` | **250/250 pass**, exit 0; no skips/expected failures. Existing profile/state/live/draft transport assertions retained. Intentional bootstrap/rollback fixture messages remain. |
| `git diff --check` | Exit 0. |
| Independent focused read-only review | No material findings; reviewer did not independently rerun tests. |

Real JWT/middleware/registered routes and domain SQL execute on the reused synthetic fixture, including actual seed turns, order changes, finalization, snapshots and rollback; only emitter substituted. Tests exercise both commissioners across all five controls and role/league/actor forgery, personal-membership-independent commissioner control, auth and missing/ambiguous identity, object/array/ID/actor validation, URL-bound order and existing foreign-member rejection, exact success envelope/event type/room (no order event), late commissioner change before the final check, finalization fault after state write, and trusted defaults/required checked finalization actor (None cannot bypass).

Adapters translate PostgreSQL generate_series, ANY/array reordering, interval/date/count casts, aliases, timestamps, locking and executemany for SQLite. This is not deployed PostgreSQL/RLS/lock/competing-transaction evidence. The role-change test mutates the same connection before the final check, then confirms rollback; it does not guarantee serialization or prevent a competing change after that check. Existing post-commit event/snapshot boundary is unchanged. Known MOD-025 subset-order/start-replay defects are not repaired or protected by valid-behavior tests. No frontend changes/checks rerun, browser or live socket verification. No production/network/private rows/credentials/environment-value access, factory/listener/worker/job, schema/migration/dependency/deployment or unrelated cleanup. MOD-003B remains partial: manual-pick operational access policy and principal adoption remain. Stop after this stage; no other task started.


## MOD-003B final manual-policy stage and completion — 2026-10-28

User explicitly chose disabled HTTP manual allocation, trusted internal model calls only. POST `/api/draft/pick-manual` returns410 `http_manual_pick_disabled` for any authenticated body/actor/job flags; no parsing or persistence. Middleware still401 for anonymous/invalid/expired JWT. Trusted model implementation/default week1/explicit week/notification SQL unchanged. No global operator role introduced.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py > /tmp/mod003b-manual-baseline.log 2>&1` | Fresh pre-stage baseline250/250 pass, exit0. |
| `python3 api/tests/run_isolated.py 'test_http_manual_pick_disabled.py'` before handler change | 3 tests,25 failures, exit1; old handler called model/parsed invalid bodies instead of rejecting all HTTP allocation. |
| `python3 api/tests/run_isolated.py 'test_manual_pick_trusted_contract.py'` before handler change | 3/3 pass, exit0; trusted default/explicit-week persistence/notification and rollback contracts already valid. |
| Target HTTP command after change | 3/3 pass, exit0. |
| `python3 api/tests/run_isolated.py > /tmp/mod003b-final-backend.log 2>&1` | **256/256 pass**, exit0; no skips/expected failures. Earlier profile/state/live/control/draft transport assertions preserved. Intentional bootstrap/rollback fault-test messages remain. |
| `git diff --check` | Exit0. |
| Final independent focused read-only review | No material findings across registered draft HTTP scope; static review only, no independent test rerun. |

HTTP tests use actual JWT/middleware/registered route with assertions that database begin, manual model allocation and socket emitter are never called. Covers synthetic roles/unknown profiles, forged actor/job/header/query claims, valid/invalid/nonobject/malformed JSON, middleware denial and preflight. Trusted tests reuse prior live/profile fixtures, execute actual model/insert/slot/cap/notification SQL outside HTTP context, assert default week1/explicit week4 and output allocation fields, and confirm rollback/no notification after slot failure. The local SQLite pg_notify function records invocation; it does not simulate PostgreSQL transactional delivery. No model source changed in this final stage.

Final registered route audit: member-only state and own-member live pick derive verified principal, commissioner controls/order derive principal and check actual role in model transaction, manual HTTP is disabled. Sport-round metadata remains JWT-protected global configuration (not actor/league data); socket subject/membership gates remain unchanged. No new administrative/operator role or job-flag bypass. Earlier stage limitations persist: no deployed PostgreSQL/RLS/locking/concurrent revocation/notification/cascade, browser or live socket proof; existing socket ambiguity behavior, post-commit event/snapshot boundary and MOD-025 order/replay defects unchanged. No frontend changes/checks rerun. No production/network/private rows/credentials/environment-value access, factory/listener/worker/job, schema/migration/dependency/deployment or unrelated cleanup. MOD-003B is complete in bounded HTTP/application scope; next recommended MOD-003C, separately scoped after dependency/role review. Stop after MOD-003B.


## MOD-003C final scoring/operational slice — 2026-10-29

- User selected disabled HTTP weekly scoring and explicit trade application; retain trusted model/job access. Both routes return 410 without model/persistence calls. Scoring reads require verified full league-read access; existing scoring/tiebreak/transaction rules unchanged.
- `python3 api/tests/run_isolated.py test_scoring_authorization.py`: 9/9 pass.
- `python3 api/tests/run_isolated.py test_operational_trusted_contract.py`: 2/2 pass. Includes real pending trade application SQL and isolated finalizer-function execution against synthetic SQLite without job module startup imports.
- `python3 api/tests/run_isolated.py`: 345/345 pass, exit 0. `git diff --check`: pass. No frontend changes/checks, production/configured jobs/schema/deployment access. Existing synthetic failure-path log messages do not represent test failures.
- MOD-003C complete only in bounded application/HTTP scope. PostgreSQL/RLS/locking/concurrent revocation/scheduler/browser guarantees remain unverified. See [current checklist](mod-003c-checklist.md). No other MOD started.


## MOD-009 — locked trade application guards — 2026-10-29

- Before implementation: `python3 api/tests/run_isolated.py test_trade_application_guards.py` ran 5 tests with 9 failures, reproducing invalid state/type application, replay and stale ownership/conference acceptance.
- Final focused run: 6/6 pass. Full `python3 api/tests/run_isolated.py` run: **351/351 pass**, exit 0, no skips/expected failures. `git diff --check` passes.
- Checks real model SQL on the existing synthetic SQLite adapter: all nonpending states and wrong type reject without ownership writes; direct/dispatcher replay rejects; dispatcher pre-read cannot override later application state; valid trade preserves half-open week2 ownership history and None success; stale ownership and conference caps reject; faults before first/second ownership insertion and completion roll back all writes. Existing trusted week1 application and J4 baseline tests pass in the full suite.
- The dispatcher stale-read fixture initially failed because FOR UPDATE is removed before the query hook; corrected the hook to target the actual locked-read SELECT shape. This models state observed by the application, not a competing PostgreSQL transaction.
- No schema, HTTP, frontend, scheduler, production or network changes/access. Existing deadline policy retained. SQLite cannot verify row locks or two concurrent applies; that MOD-009 acceptance remains outstanding on disposable PostgreSQL. Ownership concurrency across distinct commands remains MOD-010.


## MOD-007 — atomic weekly score replacement — 2026-10-29

- MOD-009 infrastructure check: `psql` and Docker clients are present; `postgres`/`initdb` are absent from PATH. Read-only Docker daemon/image inspection reports daemon unavailable. No database connection, container, installation or infrastructure startup performed; concurrent-apply evidence remains outstanding.
- `python3 api/tests/run_isolated.py test_weekly_score_atomicity.py` before implementation: 3 tests, **2 failures**, proving both failure points lose old scores. Each fault has an independent fixture so the second case cannot pass against an already emptied table. After implementation: **3/3 pass**.
- `python3 api/tests/run_isolated.py`: **354/354 pass**, exit 0. `git diff --check`: pass. Existing weekly ranking/tiebreak/week0/final-period tests included.
- Production deletion helper now requires the caller's connection; compute_weekly_scores deletes and inserts inside the same transaction. Removed the week0 fixture's deletion override so it exercises the real deletion helper. New tests run actual deletion/insertion SQL against synthetic SQLite, inject faults before first and second inserts, assert the complete old set survives, and verify exact successful rows, other league/week isolation and sequential repeat convergence.
- No scoring-rule, response, schema, frontend or job orchestration changes. Concurrent replacements/uniqueness remain MOD-008; this does not establish PostgreSQL isolation, deployed schema/RLS or concurrent job behavior. No production/network/configured database access.
