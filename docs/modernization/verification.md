# Regression verification baseline

Latest result: MOD-002 is complete for its bounded application/API scope. Final stage below records **106/106 isolated backend tests and 42/42 frontend tests passing**, plus passing app TypeScript and changed-type lint. Earlier partial/red results are historical; broader existing lint failures and deployed/concurrency limits remain.

2026-10-28. Read with [behavior checklist](behavior-checklist.md), [backlog](backlog.md), [database audit](database-audit.md), and [progress](progress.md). Baseline is checkout `162f89a` plus the pre-existing modification to `api/startSeasonJobs/configs/ncaa-mens-basketball-2026.json` and untracked modernization docs. This is not a clean-HEAD or deployed-production result.

**Result:** original suites passed (66 backend + 34 frontend utility + 9 tier-tool tests). Added 12 backend tests: 10 pass and **two fail on known profile-isolation defects**. Final backend suite is **76 passing / 78 total, exit 1**. Frontend build and tier type check pass; frontend lint has **63 pre-existing errors and 11 warnings, exit 1**. There is no all-green regression gate yet. No failure was fixed, skipped, marked expected-failure, or converted into a compatibility requirement.

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
