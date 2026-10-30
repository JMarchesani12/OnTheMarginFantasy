# Modernization backlog

Originally audited 2026-10-28; reprioritized 2026-10-29 after MOD-001–003 completion. Implementation status appears on the relevant cards. Synthesizes [architecture](architecture.md), [all 41 features](features.md), [behavior checklist](behavior-checklist.md), [frontend audit](frontend-audit.md), [backend audit](backend-audit.md) and [database audit](database-audit.md). FE/BE D/M/S references point to those audit sections; DB references point to the database audit. Feature ranges are inclusive stable inventory IDs, not file paths.

## Priorities, assumptions and sizing

P0: identity/exposure, demonstrated data-integrity hazards and reproducible evidence; P1: integrity, focused regressions and demonstrated user failures; P2: measured performance investigations and bounded responsibility consolidation; P3: low-impact mechanical/text cleanup and investigations with weaker evidence. Priority is impact plus dependency, not task-number order. No runtime-measured performance problem has been established by any audit. Performance work starts with measurement and may end with “no change justified.”

S ≈ up to 1–2 engineering days; M ≈ 3–5 days, excluding access/product decisions and rollout. Ranges express uncertainty, not commitments. Risk describes implementation/rollout impact, not verified exploit likelihood. Dependencies on Q1–Q8 refer to product questions in the behavior checklist. Resolve a task's decisions before changing that behavior, but continue independent source/test work meanwhile. Never codify known security/SQL/state defects as compatibility requirements. Original audit acceptance checks were prospective; later card status and verification.md record actual implementation/test evidence.

Schema tasks require safe preflight, reviewed remediation, disposable-database validation and deployment/recovery planning. Metadata unavailability blocks live conclusions and migrations requiring that evidence, not independent app-level fixes. Use synthetic users/rows; do not use production mutation, jobs or private-row exports as verification. Every schema/policy deployment and external publication remains outside this audit.

## Current recommended implementation order — 2026-10-29

MOD-001, MOD-002/002A and MOD-003A/B/C are complete in their recorded application scopes. Their completion does not establish deployed RLS, schema constraints, concurrency or job recovery. Current ordering and architecture discussion agenda: [reprioritized roadmap](priorities-2026-10-29.md).

1. **Next actionable fix: MOD-009**, then MOD-007; MOD-025 is the next draft integrity priority. Trusted jobs still expose replay/partial-write risks after HTTP authorization.
2. Prepare MOD-005 source provenance and MOD-004 access evidence early; do not block independent model fixes on unavailable metadata. PostgreSQL-dependent acceptance remains explicit.
3. **Discuss MOD-038 API layering and MOD-041 request/response/outbound interceptors early**, before broad structural implementation. These are decisions, not approval of a migration or new rate-limit infrastructure.
4. MOD-034 startup isolation and MOD-019 safe errors/resource limits with MOD-028A browser refresh alignment; respect lifecycle/gateway policy dependencies.
5. Follow MOD-006/008/010/011/012 prerequisites, then MOD-013/014 recovery and MOD-015/016 historical consistency; address MOD-023/024 reliability as applicable. MOD-011 needs verification rather than duplicate code repairs; MOD-014 is partially overlapped, not complete.
6. MOD-039 shared-function extraction and MOD-040 structural pilots, plus existing MOD-029–033 decomposition, follow the architecture/correctness prerequisites. Small identical-helper extractions may accompany touched code earlier. User-facing defects can proceed independently; performance remains measurement-first.

This queue supersedes the original MOD-001-first recommendation. IDs remain stable; task priority is not a promise to bypass dependencies. No other MOD implementation, production access or deployment is started by this planning update.

## Incremental organization conventions

These conventions remain the baseline. Approved MOD-038/041 decisions and their recorded pilots refine touched domains; they do not authorize an automatic repository-wide folder or middleware migration.

- Keep frontend `screens`, `components`, domain `api`, `context`, `types`, `utils` and colocated styles. Screens orchestrate route/user identity and rendering; shared components do not import screens. PascalCase components/hooks named useX; domain API modules own wire calls, not UI state. Keep existing casing outside touched files. Route-local hooks begin in `screens/League/hooks`; promote only with demonstrated reuse.
- Shared BonusesEditor belongs in `components/League`; draft clock/connection hooks and DraftOrderEditor have focused inputs/outputs. One resource owner should coordinate refresh for each feature; identity keys include user/league/week/filter as appropriate. A cancellation guard is not a cache. Do not install a global state/cache library as a prerequisite.
- Keep backend routes → transport adapters → model/domain logic → DB/provider boundaries. Adapters parse/authenticate/authorize/serialize; jobs call transport-independent logic. Transactions and locks belong to explicit orchestration boundaries, with connection passed to participating helpers. Inject engine/provider/listener where needed; avoid new import-time network/env requirements and wildcard imports.
- Retain existing Python module/table/route naming for compatibility. New extracted files should follow their local domain convention; rename only when resolving demonstrated ambiguity. SQL identifier/API renames require explicit migration/consumer work, not style cleanup. Version schema changes in ordered migrations, documenting prerequisites/provenance; distinguish snapshot from executable migration.
- Separate import-only moves, internal extraction, intentional behavior/API/schema changes, and performance optimization into reviewable changes. Characterize valid behavior before extraction; add regression tests for actual defects/races rather than mirrored implementation tests. No mass folder move, dependency replacement or dormant-feature deletion.

## Proposed tasks

### MOD-001 — Isolate authorization tests and resolve the authenticated principal

- **Priority / size / risk:** P0 / S–M / Medium.
- **Features:** F-004, F-022.
- **Problem / evidence:** BE D01; behavior B1/J1; middleware sets g.user but REST handlers do not consume it. db.py creates an engine at import.
- **Expected benefit:** Establish regression protection and a trusted identity primitive.
- **Scope / exclusions:** Add an injectable principal resolver mapping verified sub to application identity and a fail-closed test harness with fake DB/JWT inputs. First cover profile PATCH allowed/foreign/missing identities; do not migrate every endpoint or change schema.
- **Dependencies:** None.
- **Acceptance / verification:** Tests execute without credentials/network/app listener; forged body UUID/userId cannot alter resolved principal; expired/missing token and missing/ambiguous app identity have explicit outcomes. This foundation is incomplete protection until MOD-002/003A–C migrate callers.
- **Contract impact:** Behavior: internal resolver only; API: none until adopted; schema: no.
- **Status — 2026-10-28:** MOD-001 complete within the internal-boundary scope. Reused the existing isolated harness/regressions; added `api/authenticatedPrincipal.py` and nine focused tests. `resolve_authenticated_principal(db)` reads only middleware-verified `g.user.sub`, returns immutable `AuthenticatedPrincipal(subject, user_id)`, and queries at most two application IDs to reject absent/duplicate mappings. `PrincipalResolutionError` supplies stable codes: `interactive_request_required`/`missing_authenticated_subject` (401), `application_identity_not_found`/`application_identity_ambiguous` (403). Adopting adapters must catch/serialize these exceptions; database errors propagate. No configured engine import, endpoint adoption, job bypass, schema change or production access.
- **Actual verification:** New focused suite 9/9 passes (exit 0); profile suite 5/7 passes (exit 1); full isolated backend suite 85/87 passes (exit 1), with only the unchanged MOD-002 foreign-profile GET and persisted PATCH denial failures. Initial focused run failed on the absent resolver module before implementation. See [verification.md](verification.md#mod-001-resolver-verification--2026-10-28).
- **Limit / next:** This primitive does not secure existing endpoints. Trusted jobs retain transport-independent model/domain access and cannot obtain an interactive principal without an authenticated HTTP request. SQLite tests do not validate PostgreSQL/RLS or deployed UUID uniqueness. Next: MOD-002 profile adoption/public-data repair; stop here before endpoint work.


### MOD-002 — Bind profile operations and remove unnecessary public contact fields

**Current status: complete — 2026-10-28**, for the bounded application/API scope; deployed security and MOD-006 concurrency are not claimed.

- **Priority / size / risk:** P0 / M / High.
- **Features:** F-002, F-004, F-006, F-022.
- **Problem / evidence:** BE D01/D03; public UUID profile, commissionerEmail search projection and profile logging; DB-02/03.
- **Expected benefit:** Close account impersonation/exposure paths.
- **Scope / exclusions:** Authorize profile GET/create/PATCH from subject, prevent arbitrary UUID/email provisioning, decide minimal public league projection and remove raw profile logs. Explicitly document compatibility changes; no new account-delete/email-change feature.
- **Dependencies:** MOD-001; resolve Q1 public fields.
- **Acceptance / verification:** Two synthetic users cannot read private/edit/provision each other through ID/UUID/body substitution; intended public search still works; own profile lifecycle passes; logs contain no contact/profile payload. Record changed public shapes/statuses and update consumers.
- **Contract impact:** Behavior: yes; API: deliberate auth/projection changes; schema: no.
- **Stage 1 status (historical) — 2026-10-28: partial; stage 1 complete (numeric-ID profile GET/PATCH authorization).** Verified the actual MOD-001 resolver and middleware; both numeric-ID handlers now call `resolve_authenticated_principal(db)` before profile access. A foreign/nonexistent URL ID returns 404 `{"message":"User not found"}` without reading/updating that profile. Missing/blank subject returns the resolver's 401 JSON error; absent/ambiguous application mapping returns its 403 JSON error. Reads/writes use the resolved application ID. Own-profile fields, display-name-only update whitelist, valid responses and empty-update 400 remain unchanged; no frontend change needed for this stage.
- **Actual verification:** Reused the guarded runner and SQLite profile fixture (added result `fetchmany` support). Five new tests cover bidirectional URL/body/query/header substitutions, missing/ambiguous identities, empty subject and expired PATCH. Before implementation the 12-test profile suite exited 1 with 14 assertion/subtest failures, including both original denial failures. After: profile 12/12 and full isolated backend 92/92 pass, exit 0; original denial assertions unchanged. No schema/migration/dependency/job/production work.
- **Stage 1 handoff (historical):** Continue MOD-002 with subject-bound UUID lookup and profile creation, coordinating the current frontend `skipAuth` lookup and missing-profile bootstrap. Current creation still trusts body UUID/email; UUID lookup remains public under the production allowlist. Then resolve Q1 minimal league search fields, remove raw profile logging and test consumers/log privacy. These were deliberately excluded from the smallest useful stage; the full card is not complete. Direct Supabase/RLS and concurrent identity-remapping guarantees remain unverified. Stop before other backlog tasks.
- **Stage 2 — 2026-10-28: subject-bound UUID lookup/provisioning complete.** Removed UUID lookup from `api.py` public prefixes. Extracted `verified_request_subject()` from the existing principal validator for authenticated bootstrap before an application profile exists. UUID GET is own-subject only: 401 invalid/missing JWT or subject, 404 foreign UUID or own missing profile, 403 ambiguous mapping; successful private payload is unchanged. POST derives UUID/email solely from verified JWT claims; body identity fields are optional legacy inputs, accepted only when matching (403 on conflict). Missing claim email is 403; malformed object/name 400; existing profile 409; ambiguity 403; successful create remains 201. SQLAlchemy constraint failures have generic 400 responses without SQL/contact details. Removed raw created-profile debug logging.
- **Consumer / verification:** Frontend UUID lookup now authenticates; creation sends only displayName. AuthProvider supplies the current session token to both calls and stops after lookup errors; apiFetch avoids SDK getSession when Authorization is supplied. Ten new guarded backend tests cover own/foreign/anonymous UUID access using the actual factory auth allowlist parsed without importing the factory, claims-bound creation/reload, forged UUID/email, repeated/ambiguous provisioning, validation and safe logs/errors. Eight frontend tests execute actual modules with SDK/transport/hook substitutes. Results: bootstrap 10/10; full isolated backend 102/102; frontend 42/42; application TypeScript check passes. Focused lint fails only on pre-existing AuthContext fast-refresh export rule at line 149; no suppression or unrelated fix.
- **Stage 2 handoff (historical):** MOD-002 was still partial: resolve Q1 minimal public league-search projection, remove commissionerEmail exposure and verify search consumer/response contracts. Raw profile creation logging is now removed. No browser/deployed PostgreSQL/RLS verification; sequential duplicate checks are not concurrency-safe on the nonunique UUID snapshot. Conflict-safe/unique provisioning remains existing MOD-006 (after MOD-005 provenance/preflight), not implemented here. No schema/migration, production access or other backlog work; stop after this stage.
- **Stage 3 / final — 2026-10-28:** User resolved the MOD-002 public-field decision: commissioner email stays private. Removed `commissionerEmail` from search SQL and frontend `LeagueSearchResult`. Retained the other discovery fields, including commissioner display name; source inspection confirms Home displays that name and does not consume email. Anonymous search remains public; filters, pagination, valid status/payload fields and error contracts preserved except the intentional removal of email. Added four guarded real-route/model-SQL regressions using synthetic SQLite. Privacy assertion failed before implementation (email present), then all four passed. Full isolated backend 106/106, frontend 42/42, app TypeScript and changed-type ESLint pass (exit 0); existing broader lint issues remain.
- **Completion / next:** MOD-002's numeric and UUID profile authorization, claims-bound provisioning, consumer coordination, contact-field minimization and raw profile creation-log removal are implemented. Q1 is resolved only for profile/search contact privacy; other league/resource role decisions remain with MOD-003A–C. Recommended next implementation is MOD-003A, with its role decisions checked before adoption. MOD-004/005 deployed-policy/schema evidence and MOD-006 conflict-safe unique provisioning remain separate existing work. No schema/migration, production connection/mutation, job, deployment or other backlog implementation. Historical logs and deployed PostgreSQL/RLS/browser behavior unverified; SQLite does not prove trigram ranking or concurrency.

### MOD-003A — Authorize league administration and scoped reads

- **Current status — 2026-10-28: complete in the bounded application/API scope.** All 13 grouped stages are implemented and verified below. Final accepted Q1 policy: authenticated nonmembers get limited discoverable previews, with no contact/actor/score/order fields; full reads require membership or commissioner ownership, and private leagues stay restricted. Final accepted Q4 policy: disable standalone HTTP week generation; trusted internal model calls and automatic league-creation initialization remain unchanged. No MOD-003A implementation parts remain. Historical stage handoffs below are superseded by the final completion entry.

- **Priority / size / risk:** P0 / M / High.
- **Features:** F-005–012, F-017–019, F-021, F-029, F-031.
- **Problem / evidence:** BE D01; DB access-path matrix; commissioner checks trust supplied actor and member PATCH permits draftOrder/seasonPoints.
- **Expected benefit:** Prevent foreign league/member administration.
- **Scope / exclusions:** Adopt principal across league/create/byUser/member/moderation/delete/week-generation and league-scoped reads; bind URL league to all resources and restrict writable fields by operation. Exclude draft/trades (next tasks).
- **Dependencies:** MOD-001; role/public-read matrix Q1/Q4.
- **Acceptance / verification:** Independent member, nonmember and commissioner fixtures exercise every migrated route, arbitrary actor IDs and mismatched league/member/request/week IDs; allowed J1/J2 journeys still work; ordinary team-name edit cannot alter scores/order.
- **Contract impact:** Behavior: yes; API: permission/error contract changes, preserve valid payloads where possible; schema: no.
- **Historical stage 1 status — 2026-10-28: partial; stage 1 complete (self-service member team-name PATCH).** Confirmed actual MOD-001 resolver and MOD-002 adoption/tests; remaining Q1/Q4 decisions are not treated as resolved. Selected the smallest useful stage, `/api/league/leagueMember/<member_id>` PATCH. Frontend's only caller edits the current user's team name. Handler now resolves verified principal, accepts a JSON object containing only nonblank string teamName, and calls new `update_owned_league_member(member_id, user_id, team_name)`. SQL updates only teamName with ownership in the same WHERE predicate. No row/foreign owner yields generic 404; missing/ambiguous app identity yields resolver 403, missing/invalid/expired authentication 401. Extra score/order/identity/league fields yield 400 with no partial write. Success remains 200 with existing member fields. No commissioner override on this self-service route; existing general model update stays unchanged for trusted callers.
- **Consumer / verification:** Narrowed frontend rename function/payload type to required teamName; sole UI caller already conforms. Seven new guarded JWT/route/SQLite-SQL tests cover own commissioner/member renames (including a second league), foreign member/nonmember/cross-league denial, actor substitution, score/order smuggling, missing/expired auth, missing/ambiguous app identity and invalid/missing target/input. Initial seven-test run had 14 assertion/subtest failures; final 7/7 and full isolated backend 113/113 pass. Frontend request regression failed on old score/order payload then passed; full frontend 43/43, app TypeScript and touched frontend lint pass (exit 0). Existing MOD-002 cross-user denial assertions remain intact.
- **Stage 1 handoff (historical):** Continue MOD-003A with own-league listing (`/api/league/byUser`) bound to principal, then creation/commissioner administration/admission and remaining league-scoped reads with explicit role decisions. Q1 nonmember visibility and Q4 operational/week-generation access remain unresolved; no new global administrator role inferred. Other endpoints are unchanged and not secured by this stage. SQLite does not validate deployed PostgreSQL/RLS/concurrent identity mapping. No schema/migration, production/network access, job, deployment, unrelated cleanup or other task. Stop after this stage.
- **Stage 2 — 2026-10-28: own-league listing complete.** `/api/league/byUser` now resolves the verified principal before listing/model side effects. Required body userId remains a compatibility assertion; matching integer/numeric-string IDs work, foreign IDs return 403 `user_identity_mismatch`, missing ID retains 400, malformed objects/IDs/stages return JSON 400. Listing always uses the principal ID; supplied body/query/header actor/UUID/subject fields cannot change identity. Missing/ambiguous identity produces explicit resolver 401/403. Successful 200 response fields and stage filters/defaults/unknown-string fallback are unchanged; nonmembers get an empty own list. Frontend caller already conforms; no frontend change.
- **Stage 2 verification:** Nine new tests reuse guarded runner/profile fixture and execute real JWT/middleware/routes/listing SQL against synthetic memberships. Initial run: nine assertion/subtest failures and one error from the old uncaught invalid-ID conversion; final targeted 9/9 and full isolated backend 122/122 pass (exit 0), including existing member/profile denial tests. Global status sync is substituted in tests; denied requests are checked not to reach it. SQLite current-week interval syntax is adapted with an empty Week fixture; no PostgreSQL lifecycle/date/RLS/concurrency guarantee. `git diff --check` passes. Frontend checks not rerun for this backend-only stage; previous results remain historical.
- **Stage 2 handoff (historical):** MOD-003A remains partial. Next bounded slice: bind league creation's commissioner/initial membership to principal, then commissioner administration/admission/resource-scoped reads. Remaining Q1 nonmember visibility and Q4 operational/week-generation decisions are still open. Existing model status-sync side effects are unchanged (separate MOD-020); no other endpoint adoption, schema/migration, production/network access, job, dependency or deployment. Stop after stage 2.
- **Stage 3 — 2026-10-28: principal-bound league creation complete.** Verified current create adapter/model/frontend; creation's commissioner drives both League and initial LeagueMember. Handler now resolves principal first, requires object/original fields, validates legacy commissioner ID as a matching integer/numeric-string assertion and always passes principal user ID to the model. Mismatch 403 `commissioner_identity_mismatch`; invalid/missing field 400; auth/identity failure explicit 401/403. Valid 201 payload, initial membership, team-name trimming, rule/timezone settings and model's week initialization call remain unchanged. Existing frontend already sends its current app ID; no consumer edit required.
- **Stage 3 verification:** Eight new guarded real-JWT/route/model tests persist synthetic league/member rows using adapted PostgreSQL CTE/JSON insertion on SQLite; week initialization is substituted. Assert own identities for A/B, spoofed commissioner/actor/header/query, no creation on auth/missing/ambiguous identity failures, numeric-string compatibility, required/object/ID validation and existing team-name behavior. Initial result: six assertion/subtest failures and two SQLite constraint errors on invalid supplied commissioners; final targeted 8/8 and full isolated backend 130/130 pass (exit 0), existing denial tests intact. `git diff --check` passes. No frontend changes/checks rerun.
- **Stage 3 handoff (historical):** MOD-003A is partial. Next bounded slice: commissioner-only league settings PATCH bound to principal, then other administration/moderation/admission and scoped reads with resource ownership checks. Q1 nonmember visibility and Q4 operational/week-generation decisions remain open. This stage does not make creation/week initialization atomic: model commits league/member before its existing week call; failure/retry behavior and real PostgreSQL CTE/JSON/types/scheduling are unverified and unchanged. No schema/migration, production/network access, job, dependency/deployment or other task; stop after stage 3.
- **Stage 4 — 2026-10-28: commissioner-only league settings PATCH complete.** HTTP handler resolves principal and calls `update_league_as_commissioner(league_id, user_id, patch)`; no supplied actor/commissioner field grants authority. Shared model logic checks current league commissioner before settings validation and includes commissioner in UPDATE predicate. Foreign member/nonmember/other-league commissioner and a commissioner change before write yield 403 without changing requested fields. Valid 200 shape, existing writable-field allowlist, rules-version protection, timezone/deadline settings and missing-league 400 are preserved. Original `update_league` remains explicit trusted entry point using shared implementation; HTTP cannot select it. Non-object JSON is 400, auth/identity failures explicit 401/403, operational failures safe generic JSON 500.
- **Stage 4 verification:** Nine new guarded real-JWT/route/model tests on synthetic SQLite with adapted PostgreSQL UPDATE CTE/JSON projection. Initial eight-test run had six assertion/subtest failures; final targeted 9/9 (including operational fault injection) and full isolated backend 139/139 pass, exit 0. Existing trusted-model rule and prior denial assertions unchanged. Deterministic commissioner change validates final owner predicate; not a PostgreSQL concurrent-transaction/locking proof. Frontend payload already conforms; no frontend changes/checks rerun. `git diff --check` passes.
- **Stage 4 handoff (historical):** MOD-003A remains partial. Next bounded slice: bind admission actors, starting with join-request creation to authenticated principal; then moderation/member removal/league deletion and remaining scoped reads/week generation. Q1 nonmember visibility and Q4 operational policy are unresolved for those later slices. Settings lifecycle restrictions/allowlist beyond existing behavior were not redesigned. No schema/migration, production/network access, app/listener/job, dependency/deployment, unrelated cleanup or other task; stop after stage 4.
- **Stage 5 — 2026-10-28: principal-bound join-request creation complete.** HTTP join_request resolves principal, requires object/legacy userId matching resolved app identity, and passes only principal.user_id plus URL league_id to the unchanged model. Foreign userId returns 403 `user_identity_mismatch`; missing/invalid ID/object 400; auth/identity failures explicit 401/403. Other body/query/header actors/league IDs do not override resource or identity. Valid 201 JSON, trimmed team name, message, existing-member 400 and returning the same own pending request are preserved. A forged actor can no longer obtain another user's existing pending request through the create route. Discover caller already conforms; no frontend edit required.
- **Stage 5 verification:** Nine new real-JWT/middleware/routes/model SQL tests reuse isolated runner/profile SQLite fixture. Initial result nine assertion/subtest failures; final targeted 9/9 and full isolated backend 148/148 pass (exit 0), prior denial assertions intact. Checks cover A/B persisted ownership, foreign IDs, URL versus body league/actor substitutions, foreign pending isolation, own repeat/no overwrite, member rejection, numeric-string compatibility, auth/identity and invalid payload cases. SQLite does not prove deployed PostgreSQL/RLS or concurrent duplicate prevention. `git diff --check` passes; frontend checks not rerun because unchanged.
- **Stage 5 handoff (historical):** MOD-003A remains partial. Next bounded slice: bind commissioner-only join-request listing to principal, then approval/denial/cancellation, member removal/league deletion and remaining scoped reads/week generation. Q1 nonmember visibility/discoverability and Q4 operational policy remain unresolved; this identity-only stage does not add discoverability/capacity/status admission rules or concurrency guarantees. Model and trusted callers unchanged. No schema/migration, production/network/environment-value access, app/listener/job, dependency/deployment, unrelated cleanup or other task; stop after stage 5.
- **Stage 6 — 2026-10-28: commissioner-only join-request listing complete.** Handler resolves principal and treats required actingUserId as a matching integer/numeric-string assertion (403 `actor_identity_mismatch` on conflict); malformed object/actor/status types return JSON 400; principal errors explicit 401/403. New `list_join_requests_as_commissioner` checks URL-league commissioner using principal ID and constrains final request SELECT with commissioner EXISTS predicate. Members/nonmembers/foreign-league commissioners cannot use forged actor IDs to expose messages/contact fields. Prior trusted listing remains separate, sharing query implementation. Valid 200 fields (including applicant contact used by moderator UI), descending creation order, status filter/empty results and missing-league 400 remain unchanged. If commissioner changes between check and read, final query returns 200 empty list with no applicant data. Frontend request already conforms; no edit.
- **Stage 6 verification:** Nine new actual-JWT/middleware/registered-route/model SQL tests on synthetic SQLite. Initial nine-test result: nine assertion/subtest failures, including forged actor exposure and stale commissioner read; malformed status produced logged 500. Final targeted 9/9 and full isolated backend 157/157 pass (exit 0), prior denial assertions unchanged. Tests cover both commissioners, member/nonmember/foreign league, forged actors, scope/filter/order/empty/type/auth/identity outcomes and deterministic role change before SELECT. No SQL dialect adaptation required; not PostgreSQL/RLS/locking proof. `git diff --check` passes; frontend checks not rerun because unchanged.
- **Stage 6 handoff (historical):** MOD-003A remains partial. Next bounded slice: principal-bound commissioner approval of join requests, then denial/cancellation, member removal/league deletion and remaining scoped reads/week generation. Q1 nonmember visibility/discoverability and Q4 operational policy remain open; no general concurrency/revocation-after-query guarantee. No schema/migration, production/network/environment-value access, app/listener/job, dependency/deployment, unrelated cleanup or other task; stop after stage 6.
- **Stage 7 — 2026-10-28: principal-bound commissioner approval complete.** Approval handler resolves principal, validates legacy required actingUserId as matching integer/numeric-string assertion (403 actor_identity_mismatch), and invokes new checked model entry point. Checked approval locks URL league and verifies commissioner inside the same transaction before request/membership/league mutations. Request read and final resolution UPDATE both bind URL league/request; resolvedByUserId comes from principal. Existing 200 request/member shape, pending/replay and missing-target 400 behavior remain. Trusted model entry point stays HTTP-independent and shares transaction body; both paths lock league before request to avoid introducing opposite approval lock orders. Existing membership/count/settings logic retained, not redesigned.
- **Stage 7 verification:** Ten guarded actual-JWT/routes/model-SQL tests with synthetic SQLite profiles/leagues/requests/members/sport. Initial nine-test result: nine assertion/subtest failures on impersonation/identity/type gaps; final targeted 10/10 and full isolated backend 167/167 pass, exit 0, prior denial assertions intact. Tests check A/B valid resolution/member payload/persistence, foreign actors/roles/URL requests, replay/nonpending/no mutations, auth/identity/type input, SQL failure after member insertion with rollback, and trusted direct model call without request context. Rollback test intentionally logs synthetic exception; no test failure. SQLite strips FOR UPDATE and adapts PostgreSQL JSON/counter SQL, so concurrency/locking/deployed schema are not verified. `git diff --check` passes; no frontend changes/checks rerun.
- **Stage 7 handoff (historical):** MOD-003A remains partial. Next bounded slice: principal-bound commissioner denial (review known malformed denial SQL evidence rather than treating it as valid behavior), then cancellation/member removal/deletion and remaining scoped reads/week generation. Q1 nonmember visibility/discoverability and Q4 operational policy remain open. Approval capacity/rounds lifecycle policy, deployed PostgreSQL locks/RLS/concurrency/deadlock/retry guarantees remain unverified beyond code lock-order review and SQLite rollback. No schema/migration, production/network/environment-value access, app/listener/job, dependency/deployment, unrelated cleanup or other task; stop after stage 7.
- **Stage 8 — 2026-10-28: principal-bound commissioner denial complete.** Handler resolves principal, requires matching integer/numeric-string actingUserId assertion (403 mismatch), and uses checked model entry point. Checked transaction locks/checks URL-league commissioner before request lock/update; trusted direct model remains separate with the same league-first lock order. Denial now uses canonical PENDING and valid UPDATE syntax (removed comma before WHERE), restoring the intended DENIED transition. Final UPDATE binds request/league/PENDING, resolver is principal, and 200 request response fields remain. Foreign/missing/resolved request rejected 400; auth/identity failures 401/403; invalid body/actor 400. No membership/league mutation on valid denial. Frontend already conforms.
- **Stage 8 verification:** Nine guarded real-JWT/routes/model SQL tests with synthetic SQLite uppercase-status CHECK. Initial nine-test run: ten assertion/subtest failures and one trusted-model status error; final targeted 9/9 and full isolated backend 176/176 pass, exit 0, prior assertions intact. Tests cover A/B valid transition/resolver/shape, foreign actors/roles/request IDs, all resolved statuses/replay, body/query/header substitution, auth/identity/input, rollback after actual UPDATE fault, and trusted call without HTTP context. Fixture removes only FOR UPDATE; actual denial UPDATE executes in SQLite. `git diff --check` passes; no frontend edits/checks rerun. No PostgreSQL lock/type/schema guarantee.
- **Stage 8 handoff (historical):** MOD-003A remains partial. Next: principal-bound own-request cancellation, reviewing its known lowercase status defect, then member removal/deletion and remaining scoped reads/week generation. Denial repair overlaps the denial portion of MOD-011 only; cancellation and required disposable PostgreSQL verification remain open there. Q1/Q4 decisions for later slices remain open. No schema/migration, production/network/environment-value access, app/listener/job, dependency/deployment, unrelated cleanup or other task implementation; stop after stage 8.
- **Stage 9 — 2026-10-28: authenticated own-request cancellation complete.** Handler resolves principal and requires matching legacy userId integer/numeric-string assertion (403 mismatch); malformed object/ID 400, auth/identity explicit 401/403. Model retains locked request-owner check with no commissioner override, now checks canonical PENDING and constrains UPDATE by request/URL league/user/PENDING. Valid 200 CANCELLED request fields/timestamp restored; resolvedByUserId remains unchanged (normally null) as before. Trusted direct model remains HTTP-independent and still checks supplied owner. No league/member mutations; frontend wrapper already conforms (no screen caller found).
- **Stage 9 verification:** Ten guarded actual-JWT/routes/model SQL tests with synthetic SQLite uppercase-status CHECK. Initial result twelve assertion/subtest failures and one direct-model pending-status error; final targeted 10/10 and full isolated backend 186/186 pass, exit 0, prior assertions intact. Tests check A/B successful shape/persistence, forged actors, foreign owners including league commissioner, foreign URL requests, all resolved statuses/replay, auth/missing/ambiguous identity/input, post-UPDATE rollback and direct model ownership. Fixture removes only FOR UPDATE; no PostgreSQL locking/RLS/schema guarantee. `git diff --check` passes; no frontend changes/checks rerun.
- **Stage 9 handoff (historical):** MOD-003A remains partial. Next: principal-bound commissioner member removal, then league deletion and remaining scoped reads/week generation. Q1/Q4 decisions remain open for their relevant slices. MOD-011 denial/cancellation code repairs now covered by stages 8–9, but its required disposable PostgreSQL verification remains outstanding, so that card stays open. No schema/migration, production/network/environment-value access, app/listener/job, dependency/deployment, unrelated cleanup or other task implementation; stop after stage 9.
- **Stage 10 — 2026-10-28: principal-bound commissioner member removal complete.** Handler resolves principal and validates required matching integer/numeric-string actingUserId assertion (403 mismatch), object/actor/boolean shift flag (400); only principal ID/URL league/member and actual boolean reach existing locked model transaction. Existing in-transaction commissioner/league/member scoping remains; noncommissioner now raises PermissionError/HTTP 403 instead of validation 400. Valid 200 fields, default true/explicit false shift modes, missing/foreign target and commissioner-removal prohibition 400, replay and count/order behavior retained. Existing frontend sends valid identity/boolean, no edit. Direct model remains HTTP-independent with commissioner enforcement.
- **Stage 10 verification:** Twelve guarded real-JWT/routes/model SQL tests on synthetic profiles/leagues/members, stripping FOR UPDATE and substituting SQLite GREATEST/now. Initial result fourteen assertion/subtest failures and one direct-model error-class mismatch; final targeted 12/12 and full isolated backend 198/198 pass, exit 0, previous assertions intact. Covers A/B valid scoped removals/response/order modes/other-league preservation, forged actors/roles/foreign IDs, commissioner prohibition, identity/input failures, rollback after DELETE, replay and direct model. `git diff --check` passes; no frontend checks rerun. No deployed PostgreSQL/RLS/locking or dependent historical FK/cascade validation.
- **Stage 10 handoff (historical):** MOD-003A remains partial. Next: principal-bound commissioner league deletion, then remaining scoped reads/week generation and relevant Q1/Q4 decisions. No new league-status removal policy, nullable-order repair or historical-retention/schema changes; existing model behavior outside identity/error semantics preserved. No schema/migration, production/network/environment-value access, app/listener/job, dependency/deployment, unrelated cleanup or other task implementation; stop after stage 10.
- **Stage 11 — 2026-10-28: principal-bound commissioner league deletion complete.** Handler resolves principal, validates required matching integer/numeric-string actingUserId assertion (403 mismatch), object/actor (400), and passes only principal actor plus URL league to existing locked model transaction. Model wrong-commissioner error is now PermissionError/403; final DELETE also checks commissioner. Valid 200 deletedLeagueId/deletedLeagueName, missing/replay 400 and direct-model commissioner enforcement remain; frontend caller unchanged. No user-profile deletion or new status/retention policy.
- **Stage 11 verification:** Nine guarded actual-JWT/routes/model SQL tests reuse synthetic removal/profile fixture with two leagues and representative SQLite member/request ON DELETE CASCADE rows. Initial result twelve assertion/subtest failures and one direct-model error-class mismatch; final targeted 9/9 and full isolated backend 207/207 pass, exit 0, prior assertions intact. Covers A/B own scoped deletion/response/numeric-string compatibility, other-league preservation, forged actor/roles/resources, auth/missing/ambiguous identity/input, missing/replay, post-DELETE parent/child rollback and direct model without HTTP context. `git diff --check` passes; no frontend checks rerun. SQLite strips FOR UPDATE; synthetic cascades do not establish deployed PostgreSQL/history FK behavior.
- **Stage 11 handoff (historical):** MOD-003A remains partial. Resolve remaining Q1 nonmember read/preview visibility and Q4 standalone HTTP week-generation permissions before adopting remaining league details/rules/members/conferences reads and week generation. No global administrator/operator role inferred. MOD-004/005/011 deployed-policy/schema/PostgreSQL evidence remains separate. No schema/migration, production/network/environment-value access, app/listener/job, dependency/deployment, unrelated cleanup or other task implementation; stop after stage 11.
- **Remaining-scope review (historical) — 2026-10-28:** Five routes remain, grouped into two implementation stages: (1) league GET details/rules/members/conferences and any required preview consumer coordination; (2) standalone POST `/api/schedule/createWeeks`. Then final verification/handoff. User was asked to resolve Q1 discoverable nonmember preview versus full/member-only reads and Q4 commissioner versus internal-only standalone week generation. Recommended limited discoverable previews/member-only full reads and commissioner-only HTTP generation; these are proposals, not approved policy. Automatic creation/internal model week initialization is separate and unchanged. No new implementation or tests run during this policy review; stage-11 207/207 result remains historical evidence until final changes are verified.


- **Stage 12 — scoped reads complete:** Details/rules/members/conferences now resolve the verified JWT principal and check actual commissioner/membership rows. Full-data model queries repeat the reader scope; trusted calls retain the explicit optional-reader separation. Signed-in discoverable nonmembers receive only league ID/name/sport/commissioner display name or member resource ID/team name/display name. No commissioner email, app user IDs/UUIDs, settings, scores, draft order or rules/conferences are exposed in those previews. Private/missing/foreign reads return generic 404; discoverable nonmember rules/conferences or explicit `view=full` return 403. Members/commissioners retain full valid response contracts, including commissioners without membership rows. `view=preview` only reduces access. Discover uses a narrow preview API/type and removes draft metadata; typed full-data API functions request `view=full` so previews cannot masquerade as full objects. Public search is unchanged.
- **Stage 13 — standalone generation disabled:** Authenticated POST `/api/schedule/createWeeks` always returns 410 `http_week_generation_disabled`, ignoring actor IDs, fake trusted-job flags and body shape; anonymous calls remain middleware 401. The endpoint never invokes generation. No schedule model or automatic initialization behavior changed, and no HTTP job bypass was introduced.
- **Final verification:** Added 11 actual-JWT/registered-route/model-SQL read tests and 2 disabled-generation tests, plus 2 frontend transport tests. Read tests cover full member/commissioner access, restricted/private/cross-user/auth/ambiguous-identity cases, exact safe preview projections and permission/discoverability changes before the final SQL read. Full suite **220/220 backend tests, exit 0**, preserving existing cross-user profile denials; frontend **45/45, exit 0**; app TypeScript exit 0; `git diff --check` exit 0. Focused frontend lint reports three pre-existing Discover `any` errors (confirmed in HEAD), exit 1; other touched frontend files lint clean. The three existing rules-format tests now supply authenticated identities; no assertions were weakened. See verification.md for initial failing runs and fixture corrections.
- Independent read-only review identified a details-preview projection gap for authorized members/commissioners. A new regression failed before correction (five assertions/subtests); explicit details previews now reduce payload and avoid lifecycle sync for these callers too. No further material issue found.
- **Completion / limitations / next:** MOD-003A is complete; no other backlog task started. Recommended next is MOD-003B after confirming its actual dependencies and draft-role decisions. MOD-004/005/011 PostgreSQL/RLS/schema/concurrency/cascade evidence stays open; MOD-020 global status-sync-on-read behavior is unchanged. SQLite adapters substitute lifecycle synchronization and PostgreSQL-only syntax/locking, so do not prove deployed database behavior or browser rendering. No production/network/credential/environment-value access, app/listener/job, schema/migration/dependency/deployment or unrelated cleanup. Stop after MOD-003A.

### MOD-003B — Authorize draft read and command paths

- **Current status — 2026-10-28: complete in bounded HTTP/application authorization scope.** All four stages are implemented. Final accepted Q4 manual policy: HTTP manual picks disabled, trusted internal model allocation retained. State/live/control routes bind verified principal to membership/owned member/commissioner respectively; existing socket membership checks remain unchanged. Global sport-round reference metadata remains JWT-protected and unchanged, with no actor/league identity to bind. Historical partial stage handoffs below are superseded by the final completion entry.

- **Priority / size / risk:** P0 / M / High.
- **Features:** F-013, F-014, F-018, F-020, F-022–024, F-030.
- **Problem / evidence:** BE D01; socket subject binding already exists, REST start/pause/resume/order/manual differ.
- **Expected benefit:** Protect draft control and member ownership consistently.
- **Scope / exclusions:** Principal binding for live/manual picks, state, order, start/pause/resume/finalize; decide API-only operator role. Preserve socket room checks; no cursor/order algorithm refactor.
- **Dependencies:** MOD-001; Q1/Q4 role matrix.
- **Acceptance / verification:** Cross-user/member/league ID substitutions fail across registered draft operations; intended commissioner/member/operator commands pass; sockets and REST agree on scope.
- **Contract impact:** Behavior: yes; API: authorization/status changes; schema: no.
- **Stage 1 plan — 2026-10-28:** Authorize only GET `/api/draft/state/<league_id>`, matching existing socket membership policy. Confirmed actual MOD-001 resolver and completed MOD-003A code; draft REST state still lacks identity binding. Resolve the verified subject to one application identity, then pass its ID into a scoped initial snapshot query before any completed-state repair. Preserve the default trusted snapshot path and valid member response; deny nonmembers/missing leagues with generic 404 and resolver failures explicitly. No commissioner-without-membership exception is inferred for draft snapshots: existing socket requires membership. Files: draftEndpoints.py, draftModel.py, new isolated state authorization tests, progress.md and verification.md. RED/GREEN route/model SQL tests cover ownership/league substitution, safe failures, repair ordering and trusted calls; then full isolated backend and focused review. Commands/round metadata/socket behavior/algorithms/schema/migrations are excluded. Further read-policy exceptions and manual/API-only operator permissions remain decisions for later stages.

- **Stage 1 status (historical) — 2026-10-28: partial; stage 1 complete (authenticated member-only draft snapshots).** `DraftEndpoints.state` now resolves the verified JWT subject via MOD-001, never supplied actor/member/job fields, and passes only the resulting application ID as `reader_user_id`. The snapshot's initial League query includes membership in the requested league before any draft reads or completed-state repair. Denied/missing targets return identical 404 `League not found`; missing/ambiguous app identity is explicit resolver 403, missing/invalid/expired/empty-subject auth is 401. Existing generic operational 500 remains, without printing raw exception details. A valid member retains all snapshot fields, picks/conference labels/order/next turns, server time and existing authorized completed-state repair. Default trusted model calls and existing `conn` callers remain independent of HTTP identity.
- **Policy boundary:** Matches the actual socket membership predicate for uniquely mapped users: league discoverability is not draft-preview access; commissioner status alone does not bypass membership. No new global/API-only operator role, commissioner read exception or manual allocation policy inferred. Socket handlers and sport-round metadata route are unchanged. This stage does not claim to resolve socket missing/ambiguous-identity handling or broader Q1/Q4 command policies.
- **Stage 1 verification:** Ten new tests reuse the credential-free harness and existing synthetic profile/read adapters, executing actual JWT/middleware/registered route/snapshot SQL. Initial RED: 10 tests, 12 failures and 1 error from the not-yet-supported reader argument, exit 1. GREEN: 10/10 and full backend **230/230, exit 0**, no skips/expected failures or assertion weakening. Existing cross-user profile denials and draft transport assertions pass. Covers two users/two member leagues, private/discoverable/foreign/missing targets, commissioner without membership, forged actors/member/league/job/query/header values, auth and missing/ambiguous identity, revocation before initial scoped read, denial before repair, legitimate completed-state repair, complete picks/next-turn payload, OPTIONS, safe errors and trusted direct/conn calls. Direct existing socket membership SQL agrees for unique-identity fixtures; no live socket integration claimed. Independent read-only review found no material issue; `git diff --check` passes. No frontend changes/checks rerun; prior frontend/type/lint results are historical.
- **Limitations / next:** MOD-003B remains partial. Next useful stage is principal-bound live picks with owned-member and requested-league checks; then commissioner control/order commands and manual allocation only with explicit operational-role decisions. Existing command handlers remain outside this stage and are not secured by its read gate. SQLite adapts only the UUID cast for socket-predicate comparison; it does not prove PostgreSQL/RLS/locking/concurrent revocation, browser or live-socket behavior. Membership is checked in the initial snapshot statement, not serialized against subsequent concurrent removal. No schema/migration, production/network/credentials/environment values, app/listener/job, dependency/deployment or unrelated cleanup. Stop after this bounded stage; no other backlog task started.

- **Stage 2 plan — 2026-10-28:** Bind only live POST `/api/draft/pick` to verified principal plus owned member in requested league. Check ownership before domain reads and repeat it in the actual pick INSERT within the existing transaction; no new lock hierarchy. Preserve optional trusted calls, acquired-week defaults, turn/expiry/cap/conflict and broadcast contracts. Validate this adapter's object/ID inputs safely. Reuse isolated state/profile fixtures, add real JWT/route/live-model SQL authorization, late-revocation and rollback tests; keep existing transport assertions with authenticated setup. Then full isolated backend/review/docs. Exclude other commands/manual policy, algorithm changes, socket changes, schema/dependencies/production.

- **Stage 2 status (historical) — 2026-10-28: partial; stages 1–2 complete.** Live POST `/api/draft/pick` now resolves verified principal before parsing/domain access. Only the resulting application ID becomes `acting_user_id`; supplied actor/member/header/query/job claims cannot establish identity. Model verifies member ID belongs to principal and requested league before settings/state reads, then repeats the condition in the actual INSERT SELECT within the existing transaction. Denied/missing/foreign member returns generic 404 `League member not found`; resolver failures remain explicit 401/403. Late zero-row inserts raise before slot/state writes and roll back. No added lock hierarchy or real concurrent-removal guarantee.
- **Stage 2 contracts / verification:** Object/type errors return JSON 400; integers/numeric strings retained, boolean/float/container IDs rejected. Valid 201 pick/slot/state advancement and matching room event preserved, including commissioner acting only for their own member/turn. Existing wrong-turn/expiry/unique-conflict 409s and cap validation remain. HTTP acquired-week default 0 and trusted model default 1 stay distinct; explicit week preserved. Ten new real JWT/registered route/model-SQL tests pass; full isolated **240/240, exit 0**, unchanged profile denials and draft response/event assertions pass, no skips/expected failures. Original transport tests gained real authenticated setup without weakening assertions; state fixture gained a database factory hook for reuse. Independent read-only review found no material issue; diff check passes. No frontend changes/checks rerun.
- **Stage 2 limitations / next:** SQLite adapts PostgreSQL locking/interval/count/timestamp/error behavior; final-predicate revocation is a synthetic same-connection mutation/rollback, not real PostgreSQL concurrent ownership-change proof. Existing post-commit snapshot/broadcast failure boundary is unchanged, not atomic with persistence. Commands/start/pause/resume/finalize/order, manual allocation and sockets remain outside stage 2; this does not secure those handlers. Next same-card work: commissioner controls/order authorization with actual caller/model policy confirmed; manual/API-only allocation requires explicit operator-role decision. No production/network/credentials/environment values, factory/listener/worker/job, schema/migration/dependency/deployment or unrelated cleanup. Stop after this bounded stage; MOD-003B remains partial, no other task started.

- **Stage 3 plan — 2026-10-28:** Bind start/pause/resume/finalize/order to verified commissioner, matching actual Manage UI/finalize policy. Keep finalize actingUserId as required matching assertion; optional supplied actor assertions on other controls cannot grant authority. Shared model transaction boundary checks actual commissioner before work and before commit, rolling back on late authority changes; force-finalize check and mutation move into the same transaction. No new lock order/concurrency guarantee. Preserve valid payload/event/trusted call behavior, exclude MOD-025 subset/replay repairs and manual/operator role. Files: draft endpoints/model, isolated control SQL tests and reusable fixture hook, task/progress/verification. Test actual JWT/routes/domain SQL, allowed/denied/cross-league actors, input/identity failures, rollback and trusted paths; full isolated suite and focused review before handoff.

- **Stage 3 status (historical) — 2026-10-28: partial; stages 1–3 complete.** Start/pause/resume/finalize/order now resolve verified principal and pass only its application ID into commissioner-checked model operations. Actual League commissioner is checked before work and again before commit within the same transaction. Force-finalize authorization and finalization now share the connection/transaction; no unchecked mutation after a separate authorization transaction. Required finalize actingUserId remains a matching legacy assertion; supplied optional actor assertions on other controls must also match principal. Forged headers/query/job/body identities cannot grant authority. Role failures 403, resolver failures explicit 401/403, malformed object/IDs/arrays/actor assertions JSON 400; valid 200 payloads/events retained, order still emits no event.
- **Stage 3 verification:** Ten new real JWT/route/model-SQL tests cover both commissioners, member/nonmember/foreign commissioner denial across all five actions, personal-membership-independent commissioner control, identity/auth/input errors, actor forgery, URL-bound order and existing foreign-member rejection, late authority-change rollback, finalization fault rollback, exact snapshot/finalize/order/event contracts and trusted direct calls. Initial RED 10 tests/60 failures, exit 1. Intermediate 3 failures from missing DraftState after preceding test rollback were fixed by per-case fixture preparation; assertions unchanged. Final targeted 10/10 and full **250/250 backend tests pass, exit 0**, no skips/expected failures or weakened earlier assertions; diff check passes, independent focused review found no material issue. No frontend changes/checks rerun.
- **Stage 3 limits / next:** SQLite adapts PostgreSQL generate_series/arrays/interval/date/locking/executemany and does not prove deployed PostgreSQL/RLS/locks/competing transactions or browser/live sockets. Authority checks occur at entry and pre-commit; they do not serialize a competing commissioner change after the final check. Synthetic role change is on the same connection and rolled back, not a competing transaction. Existing post-commit event/snapshot boundary stays unchanged. MOD-025 subset/start-replay defects remain separate and are not asserted as valid compatibility behavior. Trusted defaults remain independent of HTTP; explicit force-finalize still requires a checked actor, including rejecting None. Remaining MOD-003B work is manual-pick access/identity binding after resolving Q4 commissioner versus trusted-internal/API-only operator policy. No global operator role inferred; the manual HTTP handler remains outside these stages and is not secured by them. Socket checks and sport-round metadata unchanged. No production/network/credentials/environment values, app/factory/listener/worker/job, schema/migration/dependency/deployment or unrelated cleanup. Stop after stage 3; no other task started.

- **Stage 4 plan — 2026-10-28:** User explicitly selected disabled manual HTTP access with trusted internal model calls only, resolving this card's Q4 manual-pick decision. POST `/api/draft/pick-manual` will return 410 without parsing, resolving client actors or calling persistence; normal middleware still rejects anonymous/invalid/expired JWTs. Preserve model create_draft_pick/default week1/notification and other stage behavior. Reuse isolated harness/profile/live fixture for HTTP no-call tests plus actual trusted persistence/notification SQL and rollback contracts, then full backend/review/task records. No schema, frontend, job or unrelated change. Stop after MOD-003B final handoff.

- **Stage 4 — manual HTTP allocation disabled:** Per explicit user choice, authenticated POST `/api/draft/pick-manual` returns 410 `http_manual_pick_disabled` for every body/role, including forged actors/job flags and malformed JSON, without body parsing, profile/database access, model invocation or broadcast. Anonymous/invalid/expired JWT remains middleware 401; preflight does not execute allocation. No HTTP operator bypass created. Trusted create_draft_pick model code is unchanged, including default week1, explicit weeks, persisted pick/slot and notification SQL.
- **Final verification:** Added 3 HTTP no-execution tests plus 3 actual trusted-model persistence/notification/rollback tests using existing guarded harness/profile/live fixtures. HTTP RED: 3 tests/25 failing subtests, exit1; trusted3/3 passed before handler change. Final targeted HTTP3/3 and full isolated **256/256 backend tests pass, exit0**, no skips/expected failures, earlier denial/transport assertions retained. Diff whitespace check passes. No frontend files/checks rerun; prior results historical. Final focused review and limitations are recorded in verification.md.
- **Completion / limitations / next:** No MOD-003B implementation stages remain. Next recommended task is MOD-003C after reading its card and confirming actual resource/role dependencies; no work on it started. SQLite/synthetic transactions do not establish deployed PostgreSQL/RLS/locking/concurrent revocation/cascades/browser/live-socket or transactional notification delivery. The fixture records pg_notify SQL invocation only. Existing socket missing/ambiguous-profile handling, post-commit event/snapshot boundary and MOD-025 subset/replay behavior remain unchanged; broad security/deployment completion is not claimed. Existing socket predicate agreement is checked only for unique identities, not live integration. No production/network/private rows/credentials/environment values, app/factory/listener/worker/job, schema/migration/dependency/deployment or unrelated cleanup. Stop after MOD-003B.

### MOD-003C — Bind roster, scoring and transaction authorization to resource scope

- **Current status — 2026-10-29: complete in bounded application/HTTP authorization scope.** Roster/scoring/transaction reads and interactive transaction actions are principal/resource-bound. User-approved internal-only weekly scoring/trade application HTTP routes are disabled; trusted models retained and finalizer dependency uses its model directly. Final isolated backend 345/345 pass. No implementation slices remain; checks/limitations/stop instruction: [concise checklist](mod-003c-checklist.md). MOD-003B remains closed; deployed PostgreSQL/RLS/concurrency/security-wide completion is not claimed.

- **Priority / size / risk:** P0 / M / High.
- **Features:** F-009, F-015, F-016, F-025, F-032, F-033.
- **Problem / evidence:** BE D01/D02; trade routes discard URL league; DB-02/05.
- **Expected benefit:** Prevent cross-league transaction actions and unauthorized scoring.
- **Scope / exclusions:** Principal binding for roster/add-drop/propose/respond/cancel/veto/list/pending/apply/score triggers; resolve transaction by URL league and member ownership; distinguish internal job access. Exclude trade state-machine repair.
- **Dependencies:** MOD-001; Q1/Q4 operational/read permissions.
- **Acceptance / verification:** Foreign member IDs and valid transaction under wrong URL league fail; legitimate parties/voters and internal jobs pass; nonoperator cannot invoke operational score/apply functions. Exercise read exposure too.
- **Contract impact:** Behavior: yes; API: auth/scope errors; schema: no.

### MOD-004 — Verify and version Supabase access policies and role boundaries

- **Current status — 2026-10-29: partial; remaining runtime/rollout boundary explicit.** Real provider Auth/PostgREST and grant-recovery checks now pass. Normal postgres cannot change platform-owned default grants in the real local provider; full proposal needs an authorized platform path or separately reviewed narrower scope. Maintainer reports Render hosting with listener service intentionally suspended; no restart authorized. [Runtime handoff](mod-004-runtime-handoff.md) covers remaining Render service/command/environment and consumer mapping. Render integration is not connected; no hosted changes.

- **Priority / size / risk:** P0 / M / High.
- **Features:** F-002, F-004, F-022–028, F-034, F-036.
- **Problem / evidence:** DB-02 access matrix: direct browser User SELECT and backend/listener DSNs; no versioned RLS/grants.
- **Expected benefit:** Make isolation testable across direct and server access.
- **Scope / exclusions:** Collect sanitized deployed metadata read-only if access becomes available; define table/role matrix, then author policy/grant migrations only for verified gaps in a later implementation. Inspect views/RPC/definer/default grants/publications, job roles and DSN alignment. Exclude production policy application and private-row exports.
- **Dependencies:** Metadata access required for deployed conclusions; coordinate MOD-002/005.
- **Acceptance / verification:** Document flags/owners/roles/grants for all exposed tables and routines; isolated anon/A/B/service-role tests prove required access and deny cross-user access; no assumption backend gets auth.uid; migration rollback/recovery plan reviewed. If metadata unavailable, record blocked evidence and do not invent policies.
- **Contract impact:** Behavior/API: conditional access changes; schema: policies/grants conditional.

- **Evidence stage — 2026-10-29:** Configured Supabase catalogs inspected read-only; [access review](mod-004-access-review.md) and [dated metadata](evidence/supabase-catalog-2026-10-29.json) now available. All 23 public tables enable RLS, one own-User SELECT policy exists, broad browser-role grants and backend postgres BYPASSRLS are observed. No policy/grant changes; role tests, reviewed intended privilege matrix and versioned access baseline remain open.

- **Versioned artifact stage — 2026-10-29:** Observed access baseline and separately unapplied browser-privilege proposal/recovery now available as working-tree artifacts. Full local table/sequence privilege matrix, own-profile/service access, creator defaults and recovery tests pass. Frozen reference matches configured Supabase catalogs read-only. [Runbooks](../../db/proposals/README.md). MOD-004 remains open: external consumers, deployed runtime roles and authorized/versioned least-privilege rollout not established. No deployed permissions changed.

### MOD-005 — Reconcile migration history and produce a reproducible schema baseline

- **Current status — 2026-10-29: complete in documented repository baseline/supported-provider scope.** The frozen baseline initializes on a fresh real Supabase Auth/PostgREST stack, two explicit historical source states upgrade/adopt/replay with data preserved, and role/proposal/recovery HTTP checks pass. [Provider evidence](evidence/supabase-provider-verification-2026-10-29.json) and [runbook](../../scripts/modernization/SUPABASE_PROVIDER.md). Supersedes earlier open provider-acceptance notes below. No hosted baseline/ledger/adoption/DDL or grant changes; arbitrary prior states and production disaster restore are not claimed. Missing original SQL is reconciled as unavailable history plus maintainer recollection, not reconstructed content.

- **Priority / size / risk:** P0 / M / Medium.
- **Features:** F-007, F-022, F-028, F-031, F-035, F-036.
- **Problem / evidence:** DB-01: duplicate DraftPick, FK ordering/extension prerequisites, two migrations, missing referenced tournament migration; BonusPointEvent discrepancy.
- **Expected benefit:** Prevent irreproducible setup and unsafe schema changes.
- **Scope / exclusions:** Recover provenance/history, define migration runner/order/ledger and Supabase prerequisites, distinguish descriptive snapshot from executable baseline; reconcile missing migration and README claims. No production application, inferred missing DDL or unrelated schema rename.
- **Dependencies:** None for repository reconciliation; metadata access for live comparison; MOD-004 coordination.
- **Acceptance / verification:** Disposable supported Supabase-compatible database initializes from documented baseline and upgrades from supported prior state; normalized definitions match intended source; absent migration reference resolved with provenance; current drift explicitly verified or unknown.
- **Contract impact:** Behavior: no intended; API: no; schema: reproducibility artifacts, actual changes separately reviewed.

- **Evidence stage — 2026-10-29:** [Provenance review](mod-005-schema-provenance.md) records migration commits/checksums and missing migration history; configured database matches all 23 table/180 column names, not yet normalized DDL. SeasonPhase.rules exists; missing migration is not recovered. Corrected README instructions to stop directing users to a nonexistent file. No executable baseline/runner or upgrade validation yet; MOD-005 remains open.

- **Baseline implementation stage — 2026-10-29:** [Versioned package/runner](../../db/baselines/20261029/README.md) now defines ordered SQL, checksums, supported local initialize/adopt states, private ledger and recovery boundaries. 16/16 local integration tests and 354/354 backend tests pass, including concurrency/rollback/drift rejection. Expanded frozen metadata verified against configured Supabase read-only. MOD-005 remains open for full provider-compatible setup/upgrade/recovery acceptance and operational prerequisites; minimal Auth fixtures are not a complete Supabase environment. No deployed adoption/migrations.

### MOD-006 — Establish one application profile per auth subject

- **Priority / size / risk:** P1 / M / High.
- **Features:** F-002, F-004, F-022.
- **Problem / evidence:** DB-03: nullable nonunique User.uuid with maybeSingle/API lookups; FE S01.
- **Expected benefit:** Prevent ambiguous identity/provisioning.
- **Scope / exclusions:** Confirm identity/null policy, aggregate-only duplicate/null preflight, conflict-safe provisioning and justified unique constraint. Separate browser provider consolidation (MOD-026); no automatic merge/deletion of accounts.
- **Dependencies:** MOD-002/005; deployed preflight before migration.
- **Acceptance / verification:** Concurrent first-login fixtures yield one profile; duplicate/null legacy cases get a reviewed remediation path; existing email policy preserved explicitly; isolated uniqueness/error-mapping checks pass.
- **Contract impact:** Behavior: yes for duplicate provisioning; API: error outcomes may change; schema: unique/null policy only when justified.

### MOD-007 — Replace weekly scores atomically

- **Priority / size / risk:** P0 / S–M / High.
- **Features:** F-009, F-025, F-032, F-036.
- **Problem / evidence:** BE D06 / DB-04: delete commits before replacement.
- **Expected benefit:** Keep old scores intact on failure.
- **Scope / exclusions:** Use one transaction for weekly replacement; preserve ranking/tier/tie rules. Exclude job completion orchestration and uniqueness migration.
- **Dependencies:** MOD-001 safe harness; model-only work need not wait for all auth tasks.
- **Acceptance / verification:** Inject failure after delete and during insert: old complete score set remains; success produces expected exact set; isolated ranking fixtures unchanged.
- **Contract impact:** Behavior: failure atomicity yes; API: no intended; schema: no.

- **Implementation status — 2026-10-29: Complete in bounded model scope.** Weekly score deletion and all replacement inserts share one `db.begin()` connection. Three new isolated tests verify rollback after deletion/before first insert and during second insert, exact successful replacement with other league/week rows preserved, and sequential repeat convergence. Full backend 354/354 passes, including existing ranking/tiebreak/week0/final-period fixtures. No scoring rule, response, schema or job orchestration changes. Concurrent job uniqueness remains MOD-008.

### MOD-008 — Enforce week/weekly-score identity under concurrent work

- **Priority / size / risk:** P1 / M / High.
- **Features:** F-007, F-009, F-025, F-028, F-031, F-032, F-036.
- **Problem / evidence:** DB-04/07: no league/weekNumber or league/week/member uniqueness; ensure-weeks check/insert.
- **Expected benefit:** Avoid duplicate periods/scores and ambiguous LIMIT 1 reads.
- **Scope / exclusions:** Define canonical natural keys, aggregate duplicate preflight, serialize/idempotently create weeks and score replacement; review independent composite FKs for same-league week/member. Do not silently deduplicate historical data.
- **Dependencies:** MOD-005/007; reviewed remediation and metadata.
- **Acceptance / verification:** Two concurrent ensure/score runs converge to one valid set; cross-league references rejected where adopted; migration dry-run reports counts only; historical week0/postseason fixtures pass.
- **Contract impact:** Behavior: concurrency yes; API: stable valid responses; schema: uniqueness/consistency migration.

### MOD-009 — Guard trade application inside its lock

- **Priority / size / risk:** P0 / S–M / High.
- **Features:** F-016, F-025, F-033.
- **Problem / evidence:** BE D07 / DB-05: apply_trade lacks locked type/PENDING_APPLY checks.
- **Expected benefit:** Prevent invalid or replayed ownership writes.
- **Scope / exclusions:** Check type/status and preconditions in locked application transaction; define idempotent replay/rejection outcome across direct and pending dispatcher. Exclude ownership helper extraction.
- **Dependencies:** MOD-003C for HTTP protection; isolated model fix can proceed independently.
- **Acceptance / verification:** Rejected/cancelled/wrong-type/already-applied commands do not mutate ownership; two concurrent applies transfer once; valid pending trade remains atomic and J4 stays correct.
- **Contract impact:** Behavior: yes; API: define replay/error outcome and current null success compatibility; schema: no.

- **Implementation status — 2026-10-29:** Locked `apply_trade` now rejects wrong types and every non-PENDING_APPLY state before domain reads/writes; direct and dispatcher replays raise `ValueError("Transaction is not pending apply")`. Valid success retains `None`. Week scope lookup and existing ownership/conference validation execute on the application connection before mutation. Isolated state, stale-dispatcher-read, replay, historical interval and rollback tests pass; full backend 351/351. **Open acceptance:** two concurrent applies on disposable PostgreSQL (SQLite strips FOR UPDATE); cross-command ownership concurrency remains MOD-010. No schema/HTTP/frontend/job scheduling changes or production access.

- **Completion — 2026-10-29: MOD-009 complete in bounded application scope.** PostgreSQL 17.6 direct/direct and dispatcher/dispatcher concurrent application checks now pass: first application holds the real row lock, second is observed waiting in pg_stat_activity, first commits once, second raises the defined nonpending ValueError; exact half-open ownership intervals and COMPLETED state verified. Earlier isolated invalid-state/precondition/rollback tests retained; fresh backend 354/354 passes. [Harness](../../scripts/modernization/README.md) and [results](evidence/postgres-assessment-2026-10-29.json). Supersedes prior open concurrent-apply acceptance above. Cross-command ownership concurrency remains MOD-010; no deployed changes.

### MOD-010 — Verify ownership reservation concurrency and add justified guards

- **Priority / size / risk:** P1 / M / High.
- **Features:** F-013, F-015, F-016, F-024, F-025, F-030, F-033.
- **Problem / evidence:** DB-05; BE S02/S03; no interval overlap/same-league guards; checks on separate connections.
- **Expected benefit:** Prevent double ownership/cap violations across commands.
- **Scope / exclusions:** Synthetic competing draft/add/drop/trade/manual runs, common lock/connection boundary and aggregate preflight; add interval CHECK/exclusion/composite keys only after validating business timing and existing data. No new generic idempotency platform or JSON-to-join-table redesign.
- **Dependencies:** MOD-005/009; Q3 timing; metadata before constraints.
- **Acceptance / verification:** Parallel conflicting commands yield one valid owner with correct half-open intervals; replay and rollback preserve history/conference caps; intended future ownership intervals remain valid; constraint deployment has remediation/rollback plan.
- **Contract impact:** Behavior: concurrency yes; API: conflict outcomes possible; schema: conditional validated guards.

### MOD-011 — Repair join denial and cancellation

- **Priority / size / risk:** P1 / S / Low–Medium.
- **Features:** F-006, F-019, F-029.
- **Problem / evidence:** BE D04 / DB-06: lowercase pending and malformed denial SQL.
- **Expected benefit:** Restore intended request transitions.
- **Scope / exclusions:** Use canonical statuses and valid parameterized SQL; preserve role/scope protections; exclude admission algorithm changes.
- **Dependencies:** MOD-003A for trusted actor; can add isolated regression cases first.
- **Acceptance / verification:** PENDING deny/cancel succeeds once; approved/foreign request rejected; denial executed against disposable Postgres to validate SQL syntax/status CHECK; response contract explicit.
- **Contract impact:** Behavior: yes; API: intended transition restored; schema: no.
- **Stage 8 overlap note (historical) — 2026-10-28:** MOD-003A stage 8 repaired denial's canonical PENDING comparison and trailing-comma SQL while adopting verified commissioner identity. Synthetic denial transition/role/scope/replay/rollback tests pass; see verification.md stage 8. This card remains **open**: cancellation still checks lowercase pending, and its required disposable PostgreSQL SQL/status-CHECK validation has not run. Do not repeat denial repair or claim MOD-011 complete from SQLite results.
- **Current verification status — 2026-10-28:** MOD-003A stage 9 also repaired cancellation's canonical PENDING check and bound HTTP identity/final UPDATE owner/league/status predicates. Both denial and cancellation code repairs have synthetic transition/role/scope/replay/rollback coverage (backend 186/186 passes). Do not repeat these code fixes. MOD-011 remains **open for disposable PostgreSQL validation** of actual SQL/status constraints/locking; no PostgreSQL check or production access occurred, and concurrency/deployed schema are not claimed verified.

### MOD-012 — Serialize admission capacity and draft-order allocation

- **Priority / size / risk:** P1 / M / High.
- **Features:** F-006, F-007, F-018, F-019, F-029.
- **Problem / evidence:** BE S02/S03, DB-06/07: MAX(order)+1 before league lock; creator commits before weeks.
- **Expected benefit:** Avoid capacity/order collisions and partially initialized leagues.
- **Scope / exclusions:** First cover concurrent approval/request reuse and league creation failure, then lock allocation and define initialization retry/transaction boundary. No broad league-model split.
- **Dependencies:** MOD-005/008/011; MOD-003A role policy.
- **Acceptance / verification:** Last-slot approvals cannot exceed capacity or collide; pending request race returns deliberate outcome; create failure cannot present an unusable completed league and retry repairs/converges without duplicate weeks.
- **Contract impact:** Behavior: concurrency/recovery yes; API: deliberate conflict/retry outcomes; schema: reuse existing and MOD-008 keys.

### MOD-013 — Define retry-safe weekly job completion and pending application

- **Priority / size / risk:** P1 / M / High.
- **Features:** F-015, F-016, F-025, F-032.
- **Problem / evidence:** DB-07 / BE S02: score/mark/lock/apply separated; early return skips pending, failed leagues still selected.
- **Expected benefit:** Prevent partial completion and unrelated pending applications.
- **Scope / exclusions:** Confirm Q3 timing, scope pending work to eligible league/week, serialize overlapping runs and isolate failures with explicit completion/retry state. No scheduler rollout or scoring formula changes.
- **Dependencies:** MOD-007/008/009/010; Q3/Q5.
- **Acceptance / verification:** Fault injection at each stage and concurrent runners converge; failed leagues do not advance/application-skip incorrectly; no-week case follows agreed timing; one failed transaction does not silently lose remaining work; J5 synthetic replay passes.
- **Contract impact:** Behavior: job timing/recovery yes; API: no intended; schema: only if explicit durable state proves needed.

### MOD-014 — Decouple scoring jobs from Flask and repair season finalization

- **Priority / size / risk:** P1 / S–M / High.
- **Features:** F-025, F-026, F-032, F-036.
- **Problem / evidence:** BE D08/M01; DB-07: final CLI calls jsonify adapter without context and ignores result.
- **Expected benefit:** Make job outcomes reliable and transport-independent.
- **Scope / exclusions:** Construct/call the transport-independent scoring service directly from both jobs (legacy ScoringModel facade retained), validate completion before flags, update misleading standings/bonus comments. Keep HTTP adapter response behavior and formulas; do not add BonusPointEvent without a persistence requirement.
- **Dependencies:** MOD-001 isolation; MOD-007 for scores; Q5 completion policy.
- **Acceptance / verification:** Run CLI logic with fake model/DB outside Flask; injected failure leaves completion flags unset; successful/all-league outcomes mark only agreed scope; HTTP season response unchanged.
- **Contract impact:** Behavior: job failure/success yes; API: no intended; schema: no.

- **Overlap status — 2026-10-29: construction decoupling complete, broader card partial.** MOD-003C first repaired finalizer invocation. MOD-038 now makes both job builders construct ScoringService and use explicit trusted service methods; isolated builder tests and finalizer fixture verify the new composition outside HTTP. No endpoint object is constructed. Completion/failure policy, broader startup decoupling and failure-path/recovery acceptance remain open; MOD-014 is not complete and existing completion/locking SQL was not redesigned.

### MOD-015 — Make seasonal conference precedence and sport consistency explicit

- **Priority / size / risk:** P1 / M / High.
- **Features:** F-007, F-009–016, F-024, F-025, F-027, F-028, F-030, F-033, F-035.
- **Problem / evidence:** DB-08: current OR season membership join can duplicate candidate rows; independent sport/phase FKs.
- **Expected benefit:** Avoid duplicate teams and inconsistent conference/scoring decisions.
- **Scope / exclusions:** Fixture current-only/season-only/both/independent cases; choose fallback precedence, apply first to team search and roster, then independently to remaining consumers. Audit cross-sport/season relationships and propose guarded constraints after preflight; no global table rename.
- **Dependencies:** Q6 historical policy; MOD-005 for any migration.
- **Acceptance / verification:** Each consumer returns one appropriate membership per team/season; matching seasonal row overrides fallback only under agreed rules; independent handling preserved; inconsistent sports/seasons rejected at selected boundary. Record deliberate historical behavior differences.
- **Contract impact:** Behavior: potentially yes; API: row cardinality correction; schema: conditional consistency constraints.

### MOD-016 — Protect historical integrity in week rebuild/rescore

- **Priority / size / risk:** P1 / M / High.
- **Features:** F-009, F-025, F-026, F-028, F-031, F-035, F-036.
- **Problem / evidence:** DB-09 / behavior Q6; maintenance does not remap interval/transaction meanings.
- **Expected benefit:** Prevent maintenance from changing historical ownership/scoring silently.
- **Scope / exclusions:** Agree retention/tier/rule policy; add dry-run impact summary and active-league guards; separately implement bounded period remapping/recovery if justified. No automatic production rebuild or universal tier snapshot requirement.
- **Dependencies:** MOD-005/007/008; Q6 required before remapping.
- **Acceptance / verification:** Synthetic historical ownership/transactions/postseason fixture produces explicit before/after mapping and equivalent intended totals; failure/retry restores or converges; no production execution in verification. Split approved remapping into a follow-up task if scope exceeds M.
- **Contract impact:** Behavior: maintenance safeguards yes; API: CLI additions; schema: conditional history model, separately approved.

### MOD-017 — Measure query plans and propose only supported indexes

- **Priority / size / risk:** P2 / M / Low for investigation; index rollout later Medium.
- **Features:** F-004–006, F-008, F-009, F-011–016, F-024–028, F-032.
- **Problem / evidence:** DB index matrix / DB-10; no runtime evidence available.
- **Expected benefit:** Choose useful indexes without excess write cost.
- **Scope / exclusions:** Capture sanitized plan/count/latency/bytes baselines for highest-volume confirmed queries; evaluate matrix candidates and structurally duplicate indexes. Each justified index migration becomes a separate small implementation with before/after evidence. No blanket index addition/drop.
- **Dependencies:** MOD-004/005 metadata; representative isolated data or safe read-only plans.
- **Acceptance / verification:** Deliver parameterized plans, fixture/cardinality context, row/buffer/runtime comparisons where available and write/storage tradeoffs; record unavailable evidence; query outputs equivalent; no redundant index dropped solely on its name.
- **Contract impact:** Behavior/API: no; schema: none in measurement task.

### MOD-018 — Measure retrieval and stabilize/paginate proven large lists

- **Priority / size / risk:** P2 / M / Medium.
- **Features:** F-005, F-006, F-012–016.
- **Problem / evidence:** DB-10; BE S01: Python team ranking, deep offset and unbounded collections.
- **Expected benefit:** Bound work while preserving completeness/ranking.
- **Scope / exclusions:** First measure rows/bytes and deterministic league-search tie order; preserve team abbreviation ranking before any pushdown. Propose cursor/paging only for collections with demonstrated need, one endpoint/client pair at a time; never silently page complete draft/roster snapshots.
- **Dependencies:** MOD-015/017; consumer contract agreement.
- **Acceptance / verification:** Equal-name league fixtures have stable page ordering; candidate limit/pushdown retains expected ranking; if paging justified, walk all pages without missing/duplicate items and record query/payload improvement. Stop at no-change conclusion when measurements do not justify changes.
- **Contract impact:** Behavior/API: conditional paging/order changes; schema: only separate measured index task.

### MOD-019 — Bound request resources and standardize safe backend errors

- **Priority / size / risk:** P1 / M / Medium.
- **Features:** F-004, F-006–009, F-013, F-015–022, F-027, F-028, F-030, F-032–034.
- **Problem / evidence:** BE D05/S06: conversions outside try, exception serialization, sqlite IntegrityError, raw details, unbounded arrays/no source quotas.
- **Expected benefit:** Prevent avoidable 500s, disclosure and excessive work.
- **Scope / exclusions:** First fix conversion/JSON/SQLAlchemy exception mapping and safe JSON envelopes in user/league/draft/roster; next independently cap weeks/team arrays/body/query resources using documented domain limits. Confirm gateway quotas before adding rate infrastructure; no API path renaming.
- **Dependencies:** MOD-001–003C error alignment; Q5 gateway policy.
- **Acceptance / verification:** Malformed JSON/IDs, duplicate/FK violations and oversized input have deliberate 4xx, no traces/SQL/private values; normal requests and conflict codes stay documented; machine auth code aligns with MOD-028A. Split error mapping and limit enforcement into separate reviews.
- **Contract impact:** Behavior: yes; API: documented errors/limits change; schema: no.

### MOD-020 — Remove global lifecycle writes from ordinary league reads after measurement

- **Priority / size / risk:** P2 / M / Medium–High.
- **Features:** F-005, F-008, F-013, F-018, F-020, F-025.
- **Problem / evidence:** BE S01 / DB-10: five global status UPDATEs during league read methods.
- **Expected benefit:** Reduce cross-league side effects and potential contention.
- **Scope / exclusions:** Instrument read-trigger counts and establish lifecycle transitions, then use a scoped/idempotent transition boundary or supervised job with agreed timing. No unmeasured claim of latency improvement.
- **Dependencies:** MOD-017; Q5 timing; MOD-025 lifecycle fixtures.
- **Acceptance / verification:** Read path issues no global UPDATE; boundary/date fixtures show same agreed visible lifecycle; delayed/retried transition recovery passes; before/after query counts and timing recorded.
- **Contract impact:** Behavior: lifecycle timing may change explicitly; API: no intended shape change; schema: no unless justified later.

### MOD-021 — Batch member/week scoring reads where measurements justify it

- **Priority / size / risk:** P2 / M / High.
- **Features:** F-008, F-009, F-011, F-025, F-026, F-032, F-035.
- **Problem / evidence:** BE S01 / DB-10: per-member games/rules/tie queries.
- **Expected benefit:** Reduce repeated work without changing results.
- **Scope / exclusions:** Count queries for league members/weekly standings, share immutable per-run context and batch one hot query path at a time. Keep tier/tournament/tie semantics; no scoring rewrite.
- **Dependencies:** MOD-007/015/017.
- **Acceptance / verification:** Historical synthetic fixtures produce identical scores/ranks/owner labels including ties/dual ownership/postseason; request/job query count improves against baseline; no stale cross-league context.
- **Contract impact:** Behavior/API: no intended; schema: no.

### MOD-022 — Deduplicate ingestion by sport season and bound provider retries

- **Priority / size / risk:** P2 / M / Medium–High.
- **Features:** F-027, F-028, F-035.
- **Problem / evidence:** BE S04 / DB-10: per-league provider fetch/global upsert; repeated team/phase lookups.
- **Expected benefit:** Reduce repeated provider/DB work and improve recoverability.
- **Scope / exclusions:** Measure calls, route active leagues through season/date/group dedup, reuse scoped lookup context; add bounded retry/backoff/timeouts with Retry-After where appropriate. Separate orchestration consolidation from retry policy review; no provider/schema replacement.
- **Dependencies:** MOD-015/017; bootstrap/checkpoint fixtures.
- **Acceptance / verification:** Two leagues same season cause one logical fetch per unique key; duplicate group events upsert once; correction/phase overrides and checkpoints remain correct; retry is bounded and simulated outages resume without premature completion.
- **Contract impact:** Behavior: retry/delivery yes; API: no public change; schema: no.

### MOD-023 — Publish every committed draft transition and verify reconnect convergence

- **Priority / size / risk:** P1 / M / Medium–High.
- **Features:** F-013, F-020, F-023, F-024.
- **Problem / evidence:** BE D09/S05; FE S02; DB notification section: AUTO-SKIP/finalize missing notify, joins not reissued on connect.
- **Expected benefit:** Keep draft clients consistent after timeout/reconnect.
- **Scope / exclusions:** First add missing model notifications with rollback tests; separately reproduce browser room rejoin/out-of-order snapshots and repair confirmed lifecycle faults. Preserve payloads, no durable event platform by default.
- **Dependencies:** MOD-003B/025; connection extraction MOD-031 optional.
- **Acceptance / verification:** AUTO-PICK/SKIP/finalize notify only on commit; reconnect joins authorized league and receives current snapshot; duplicate/delayed events cannot regress state; one settled subscription and cleanup verified; membership revocation policy explicit.
- **Contract impact:** Behavior: realtime recovery yes; API: no intended event-shape change; schema: no.

### MOD-024 — Verify operational supervision, listener recovery and sanitized observability

- **Priority / size / risk:** P1 / M / Medium.
- **Features:** F-022–028, F-034, F-036.
- **Problem / evidence:** BE S05/S06; DB functions/jobs section: LISTEN failures, mismatched DSN names, static health, unknown scheduler.
- **Expected benefit:** Make job/listener failures detectable and recoverable.
- **Scope / exclusions:** Document actual invocation/cadence/roles if available, bounded reconnect and shutdown, redacted structured operation/error logs and health liveness/readiness semantics. Separate deployment decisions from code changes; no external messages or production job runs.
- **Dependencies:** MOD-004; Q5 supervision/health policy; MOD-023 notification contract.
- **Acceptance / verification:** Fake disconnect/poll/snapshot failures recover or report health; two DB config sources are validated without revealing DSNs; overlapping runner policy documented/tested; logs correlate synthetic operations without contact/SQL secrets; static health compatibility retained or versioned.
- **Contract impact:** Behavior: operations yes; API: readiness optional explicit contract; schema: no.

### MOD-025 — Validate draft order and guard draft-start replay

- **Priority / size / risk:** P1 / M / High.
- **Features:** F-013, F-018, F-020, F-024, F-030.
- **Problem / evidence:** BE D10/D11: incomplete member permutation accepted, start resets cursor without clearing picks.
- **Expected benefit:** Prevent corrupted turn order/cursor regression.
- **Scope / exclusions:** Two independent reviews: exact order permutation validation; lifecycle-aware/idempotent start and concurrent command protection. No change to live/manual acquisition-week defaults without Q4.
- **Dependencies:** MOD-003B for route authorization; isolated lifecycle harness.
- **Acceptance / verification:** Missing/duplicate/foreign/order IDs cannot update; complete order persists; repeated/concurrent start in pre/live/paused/complete cannot reset committed picks; explicit supported resume path passes J3.
- **Contract impact:** Behavior: yes; API: deliberate lifecycle/conflict errors; schema: no.

### MOD-026 — Coordinate profile ownership and identity transitions

- **Priority / size / risk:** P1 / M / Medium.
- **Features:** F-002, F-004, F-005, F-022.
- **Problem / evidence:** FE S01/S03; DB-03: two providers provision/read via different paths.
- **Expected benefit:** Avoid stale account data and provisioning races.
- **Scope / exclusions:** First reproduce account A→B/logout/pending-create races, then select one application-profile resource owner using authorized API or confirmed RLS path. Reset identity-keyed state/cancel obsolete work; no global caching framework.
- **Dependencies:** MOD-002/004/006.
- **Acceptance / verification:** Delayed A response cannot populate B; concurrent provisioning converges; settings refresh updates consumers; denied/empty/retry outcomes visible; no credentials/network in isolated tests.
- **Contract impact:** Behavior: confirmed race fixes yes; API: reuse existing or explicitly agreed profile path; schema: MOD-006 only.

### MOD-027A — Show own-league loading, empty and failure states

- **Priority / size / risk:** P1 / S / Low.
- **Features:** F-005.
- **Problem / evidence:** FE D01: Home only logs primary-list errors.
- **Expected benefit:** Distinguish failure from no leagues.
- **Scope / exclusions:** Key primary list state/retry to account/stage; exclude caching or Home rewrite.
- **Dependencies:** MOD-026 identity contract.
- **Acceptance / verification:** Delayed/empty/failed initial and stage requests render distinct outcomes; retry works; previous stage cannot masquerade as current.
- **Contract impact:** Behavior: yes; API/schema: no.

### MOD-027B — Refresh sibling trade/pending panels after successful mutations

- **Priority / size / risk:** P1 / S–M / Medium.
- **Features:** F-015, F-016.
- **Problem / evidence:** FE D02: successful add/drop/proposal/accept refresh incomplete lists.
- **Expected benefit:** Make submission outcomes visible.
- **Scope / exclusions:** One roster mutation refresh coordinator for open/pending/roster resources; preserve pending versus applied ownership, no cache library.
- **Dependencies:** MOD-003C/009 API outcomes.
- **Acceptance / verification:** Proposal/add-drop/accept appear in appropriate lists without remount; failed write retains selection; pending acceptance does not transfer displayed ownership prematurely.
- **Contract impact:** Behavior: yes; API/schema: no.

### MOD-027C — Clear team-search loading when query becomes ineligible

- **Priority / size / risk:** P1 / S / Low.
- **Features:** F-012.
- **Problem / evidence:** FE D03: cancelled finally cannot clear loading after shortened query.
- **Expected benefit:** End stuck search feedback.
- **Scope / exclusions:** Reset in short-query/no-context branch and preserve stale-response guard; no ranking rewrite.
- **Dependencies:** None.
- **Acceptance / verification:** Held valid response followed by erased query, resolve/reject, then valid search shows correct loading/results.
- **Contract impact:** Behavior: yes; API/schema: no.

### MOD-027D — Resolve Discover from URL without navigation state

- **Priority / size / risk:** P1 / S–M / Low–Medium.
- **Features:** F-006.
- **Problem / evidence:** FE D04 / B3/Q8: screen uses only location.state league.
- **Expected benefit:** Make shared/new-tab URLs useful.
- **Scope / exclusions:** Use URL league identity with optional seed, explicit missing/invalid/denied and deterministic back action; exclude route scheme changes.
- **Dependencies:** MOD-002/003A public-read policy; Q8 cold-link intent.
- **Acceptance / verification:** Cold new-tab, in-app seed, no-state load, unknown/invalid ID and denied fetch have deliberate outcomes; no stale league on URL change.
- **Contract impact:** Behavior: yes; API/schema: no.

### MOD-027E — Associate create-form labels with controls

- **Priority / size / risk:** P1 / S / Low.
- **Features:** F-007.
- **Problem / evidence:** FE D05: labels lack matching ids/htmlFor.
- **Expected benefit:** Provide accessible names and focus targets.
- **Scope / exclusions:** Label/control and validation-description associations only; no validation/form redesign.
- **Dependencies:** None.
- **Acceptance / verification:** Every visible field label resolves correct control; label click focuses; keyboard submit unchanged.
- **Contract impact:** Behavior: accessibility yes; API/schema: no.

### MOD-027F — Implement draft modal focus behavior

- **Priority / size / risk:** P1 / S–M / Low–Medium.
- **Features:** F-013, F-020.
- **Problem / evidence:** FE D06: aria-modal without focus containment/restoration.
- **Expected benefit:** Make draft completion keyboard accessible.
- **Scope / exclusions:** Initial focus, trap/background isolation, Escape/close and safe restoration after automatic completion; no draft layout rewrite.
- **Dependencies:** MOD-025 completion contract.
- **Acceptance / verification:** Keyboard completion enters modal; Tab/Shift-Tab contained; Escape/close dismisses; visible appropriate focus restored; title announced.
- **Contract impact:** Behavior: accessibility yes; API/schema: no.

### MOD-027G — Add keyboard draft-order controls

- **Priority / size / risk:** P1 / S / Low.
- **Features:** F-018.
- **Problem / evidence:** FE D07: pointer-only drag ordering.
- **Expected benefit:** Allow intentional order without pointer.
- **Scope / exclusions:** Move-up/down with boundary disabling/focus retention using existing order/save state; separate from extraction.
- **Dependencies:** MOD-025 order contract; MOD-031B optional.
- **Acceptance / verification:** Keyboard reorder first/middle/last, save/reload, removal and randomization remain valid; accessible action names.
- **Contract impact:** Behavior: accessibility yes; API/schema: no.

### MOD-028A — Align bounded auth refresh with server error code

- **Status — 2026-10-29: complete in bounded application scope.** MOD-041 auth slice adds structured pre-execution missing/invalid-token 401 codes and one browser refresh/replay only for `auth_token_invalid`. Origin/path scoping, redirect refusal, per-rejected-token refresh coordination, account continuity, cancellation and a configurable 30-second budget are implemented. Explicit bootstrap credentials never invoke SDK lookup/refresh. Permission/legacy errors, network failures and consumed/streaming bodies do not replay. Fresh backend 359/359, frontend 62/62, frontend build and changed-production-file ESLint pass; SDK/provider network and hosted/browser verification were not performed. [Implementation evidence](verification.md#mod-041-authentication-slice--2026-10-29).
- **Priority / size / risk:** P1 / S–M / Medium.
- **Features:** F-002, F-022.
- **Problem / evidence:** FE D08 / B6: invalid session predicate misses Invalid or expired token.
- **Expected benefit:** Recover expired sessions predictably.
- **Scope / exclusions:** Machine-readable auth failure, one safe refresh retry; no generic retry of all 403 or possibly committed mutations.
- **Dependencies:** MOD-019 auth envelope agreement.
- **Acceptance / verification:** Expiry refresh succeeds once; failure terminates; permission denial never refreshes; no duplicated mutation when outcome ambiguous.
- **Contract impact:** Behavior: yes; API: add/agree auth error code; schema: no.

### MOD-028B — Consolidate frontend safe error parsing

- **Priority / size / risk:** P2 / S–M / Low.
- **Features:** F-004, F-006–008, F-017–019, F-021.
- **Problem / evidence:** FE M04: repeated status-only versus message/error parsing.
- **Expected benefit:** Provide useful consistent form errors.
- **Scope / exclusions:** Shared status/message parser, first migrate create/join then small consumer batches; tolerate non-JSON; exclude backend status redesign and raw details.
- **Dependencies:** MOD-019 envelope agreement.
- **Acceptance / verification:** JSON message/error/plaintext/empty failures retain form input/re-enable submission and show safe actionable feedback; no raw trace leaks.
- **Contract impact:** Behavior: feedback yes; API/schema: no.

### MOD-029 — Consolidate league context, mapping and request identity incrementally

- **Priority / size / risk:** P2 / M / Medium.
- **Features:** F-005, F-008, F-009, F-011–019, F-021.
- **Problem / evidence:** FE M01/S03–S05: six resolution copies, divergent seeds, Manage mapper, duplicate/waterfall resources.
- **Expected benefit:** Reduce repeated policy edits and stale route/account context.
- **Scope / exclusions:** Extract local useLeagueContext and reuse mapper in Detail plus one screen first; define seed/user/URL keys. Separate internal extraction from cancellation/freshness/persisted-selection fixes; measure requests before shared cache/dedup. No global state framework or all-screen conversion in one review.
- **Dependencies:** MOD-003A/026; Q8 freshness/persistence policy.
- **Acceptance / verification:** Paired screens agree for seeded/cold/member/nonmember/error; rapid route/account changes cannot retain foreign actionable state; form-specific defaults preserved; document request baseline and only measured reduction claims.
- **Contract impact:** Behavior: extraction no; later confirmed freshness fixes yes; API/schema: no.

### MOD-030 — Move shared BonusesEditor to component ownership

- **Priority / size / risk:** P3 / S / Low.
- **Features:** F-007, F-017.
- **Problem / evidence:** FE M03: Manage imports CreateLeague route-owned editor.
- **Expected benefit:** Remove concrete cross-screen ownership coupling.
- **Scope / exclusions:** Move screens/CreateLeague/BonusesEditor.tsx to components/League/BonusesEditor.tsx and update both imports/relative imports. Mechanical move only; no casing campaign, payload/style/refactor changes.
- **Dependencies:** None.
- **Acceptance / verification:** Import/type check and frontend build resolve both consumers; diff is move/import-only; manual create/manage editor comparison if needed. No new mirrored unit test required.
- **Contract impact:** Behavior/API/schema: no.

### MOD-031A — Extract draft clock and connection responsibilities

- **Priority / size / risk:** P2 / M / Medium.
- **Features:** F-013, F-020, F-023.
- **Problem / evidence:** FE M02: draft combines socket lifecycle, clock and rendering.
- **Expected benefit:** Make realtime changes independently reviewable.
- **Scope / exclusions:** Separate focused useDraftClock then useDraftConnection internal hooks, explicit snapshot/command inputs; no simultaneous lifecycle fix or UI rewrite.
- **Dependencies:** Characterize J3; coordinate MOD-023; no need to block bug fix on extraction.
- **Acceptance / verification:** Same event/pick shapes and displayed clock behavior; one settled timer/socket, cleanup verified; J3 fixtures unchanged. Review clock and connection as separate commits.
- **Contract impact:** Behavior/API/schema: no intended.

### MOD-031B — Extract Manage draft-order editor

- **Priority / size / risk:** P2 / S–M / Low–Medium.
- **Features:** F-018, F-019.
- **Problem / evidence:** FE M02: Manage combines order/moderation/settings/deletion.
- **Expected benefit:** Give order UI a clear responsibility.
- **Scope / exclusions:** Extract DraftOrderEditor presentation/actions using existing parent state/save payload; no moderation/settings move or keyboard behavior change in same review.
- **Dependencies:** J2/J3 characterization; coordinate MOD-025/027G.
- **Acceptance / verification:** Order/save/removal/randomize payloads and role/status gates identical before/after; TypeScript/build pass.
- **Contract impact:** Behavior/API/schema: no.

### MOD-032 — Separate schedule ingestion from read/calendar responsibilities

- **Priority / size / risk:** P2 / M / Medium.
- **Features:** F-007, F-009, F-011, F-012, F-025, F-027, F-028, F-031, F-035, F-036.
- **Problem / evidence:** BE M02: ScheduleModel owns calendar/read/provider/bootstrap work.
- **Expected benefit:** Reduce unrelated changes in one model.
- **Scope / exclusions:** First extract provider ingestion with explicit DB/provider/context dependencies and retain facade; later separate calendar only if remaining coupling warrants it. Preserve HTTP/model interfaces, keep path moves separate from logic extraction.
- **Dependencies:** MOD-015/022 ingestion contract fixtures; MOD-016 calendar policy.
- **Acceptance / verification:** Same games/upsert classification/checkpoint outputs and read payloads with fixture provider; import graph remains acyclic; no network during tests.
- **Contract impact:** Behavior/API/schema: no intended.

### MOD-033 — Consolidate ownership and conference-cap logic after correctness work

- **Priority / size / risk:** P2 / M / High.
- **Features:** F-013, F-015, F-016, F-024, F-025, F-030, F-033, F-035.
- **Problem / evidence:** BE M03: draft/manual/auto/transaction count/ownership logic overlaps, alternate _apply_trade/apply_trade.
- **Expected benefit:** Reduce rule divergence across write paths.
- **Scope / exclusions:** One connection-aware ownership/cap primitive, migrate live draft plus one transaction consumer first; preserve intentional acquisition timing. No broad scoring/transaction model rewrite or deletion of alternate helper without caller check.
- **Dependencies:** MOD-009/010/015/025; Q4 defaults.
- **Acceptance / verification:** Shared fixture matrix matches before/after for independent/conference/full-cap/history cases; transactions remain in caller lock boundary; no hidden connection opens; both migrated paths preserve valid outputs.
- **Contract impact:** Behavior/API/schema: no intended after separately reviewed fixes.

### MOD-034 — Make startup/test dependencies explicit

- **Priority / size / risk:** P1 / M / Medium.
- **Features:** F-022–028, F-034, F-036, F-039, F-041.
- **Problem / evidence:** BE M04: import-time engine/env, listener in create_app, wildcard bootstrap/path assumptions, venv logger import; architecture lacks CI/runtime pins.
- **Expected benefit:** Enable isolated verification and predictable entry points.
- **Scope / exclusions:** Inject engine/listener startup, replace wildcard imports locally, fix incorrect bootstrap naming/comments without broad module renames; document supported Python/Node and safe test/build entry points. Add minimal automated isolated checks only once proven credential-free.
- **Dependencies:** MOD-001 harness; MOD-024 lifecycle expectations.
- **Acceptance / verification:** Import/test discovery without secrets opens no DB/network/listener; documented web/job/CLI launch smoke checks with fakes work; runtime versions support TS stripping; agreed unit/build checks execute in isolated CI. No prod startup during verification.
- **Contract impact:** Behavior: startup lifecycle intentional; API/schema: no intended.

### MOD-035 — Resolve legacy/documentation ownership before retirement

- **Priority / size / risk:** P3 / S–M / Low for investigation.
- **Features:** F-026, F-028, F-032, F-038–041.
- **Problem / evidence:** Inventory uncertain/obsolete labels; DB BonusPointEvent discrepancy; BE M01/M04, unregistered lock_week self.db mismatch.
- **Expected benefit:** Avoid preserving misleading contracts or deleting live operational paths.
- **Scope / exclusions:** Record owner/external caller/deployment evidence for deprecated wrappers, magic link, NCAA/socket alternatives, lock helper and bonus comments; correct proven documentation inconsistencies. Removal/repair only as a separately justified task after usage/compatibility decision; do not register dormant routes.
- **Dependencies:** MOD-005; Q2/Q4/Q7; external usage evidence may remain unavailable.
- **Acceptance / verification:** Each candidate has source/caller search plus owner/runtime evidence or explicit unknown; documented decision keep/deprecate/no change; no deletion based only on no imports/navigation.
- **Contract impact:** Behavior/API/schema: no in investigation; retirement requires follow-up.

### MOD-036 — Measure wider rendering/accessibility and tier-tool reliability

- **Priority / size / risk:** P3 / M / Low.
- **Features:** F-001, F-005, F-007, F-009, F-011–016, F-018, F-020, F-037.
- **Problem / evidence:** FE S06; BE S04 distinguishes separate TS provider; existing lazy routes/utilities.
- **Expected benefit:** Target actual bottlenecks and unmet interactions.
- **Scope / exclusions:** Profile representative draft/roster/schedules and keyboard navigation/Home tabs; inspect error-boundary/catch-all needs. For tier tool, retain existing tests and check bounded provider/cache/error needs if operator evidence warrants. No new caching/memoization/framework without evidence.
- **Dependencies:** MOD-017 where backend dominates; representative fixtures; known accessibility defects handled MOD-027E–G.
- **Acceptance / verification:** Record reproducible render/bundle/interaction or provider-failure evidence; propose narrow follow-up only for demonstrated issue; no measured problem claimed from line counts.
- **Contract impact:** Behavior/API/schema: no in measurement task.

### MOD-037 — Correct misleading local names and comments in separate small changes

- **Priority / size / risk:** P3 / S / Low.
- **Features:** F-004, F-015, F-022, F-025, F-026, F-032.
- **Problem / evidence:** FE M03 roster.ts says schedule.ts, getUser says sports; BE M01/M04 wrong route/path/bootstrap comments.
- **Expected benefit:** Make maintenance/debugging less error-prone.
- **Scope / exclusions:** Correct demonstrated comments and user error wording in separate text-only review; use organization conventions for touched files. No wholesale casing/route/table rename; mechanical editor move stays MOD-030.
- **Dependencies:** Coordinate MOD-014/028B/034 to avoid conflicting edits.
- **Acceptance / verification:** Source references/messages describe actual module/action; user-visible wording reviewed; import checks only if imports touched; no payload/SQL changes.
- **Contract impact:** Behavior: error text only if changed; API/schema: no.

## Added architecture and refactoring work — 2026-10-29

These cards reflect the user's explicit new scope. They cross-cut existing features without adding product capabilities. Individual statuses record approved decisions and bounded implementations; do not infer authorization for a repository-wide rewrite.

### MOD-038 — Decide API layering and dependency ownership

- **Status — 2026-10-29: architecture approved and decision scope complete.** User approved the [incremental-hybrid design](../superpowers/specs/2026-10-29-mod-038-layering-design.md) and requested implementation. First transaction read/trusted-apply pilot is implemented: canonical UserActor, explicit user/job service calls, connection-scoped repository, model compatibility facades and shared full-read policy. Independent review reports no findings. Fresh backend 366/366 and disposable PostgreSQL direct/dispatcher lock/replay plus read/projection/revocation checks pass. [Plan/ledger](../superpowers/plans/2026-10-29-mod-038-pilot-implementation.md), [evidence](evidence/mod-038-pilot-postgres-2026-10-29.json). This is not a whole-backend migration; MOD-040 retains broader follow-ups.
- **Priority / size / risk:** P1 / S for discussion/design; migration sized separately / Medium.
- **Features:** Cross-cutting existing backend features.
- **Problem / evidence:** Routes/endpoints/models exist, but model classes mix orchestration and SQL; job builders construct HTTP adapters. New shared auth/validation functions expose opportunities to clarify responsibilities.
- **Expected benefit:** Agree where validation, resource authorization, use cases, transaction ownership and persistence belong before moving code.
- **Scope / exclusions:** Compare retained layers, domain routes/schemas/services/repositories and incremental hybrid using one real read/command. Decide domain versus layer folders, schemas/library needs, connection passing, actor contracts, job entry points and compatibility facades. Exclude implementation, mandatory framework replacement and generic CRUD scaffolding.
- **Dependencies:** MOD-001–003 evidence; coordinate MOD-034/041 and existing MOD-032/033. No dependency on completing every correctness card for this discussion.
- **Acceptance / verification:** User-approved architecture decision with alternatives/tradeoffs, responsibility map, representative call graph, dependency rules and bounded pilot criteria. Do not mark implementation complete from a diagram.
- **Contract impact:** Behavior/API/schema: none in decision task; migration requires its own approved design and validation.

### MOD-039 — Inventory and extract demonstrated common functions

- **Priority / size / risk:** P1 / S–M per pilot / Medium.
- **Features:** Cross-cutting backend/frontend boundary helpers.
- **Problem / evidence:** Repeated parsing, error translation, principal/ownership predicates and serialization; existing requestValidation/authorization/apiFetch should be reused before introducing alternatives.
- **Expected benefit:** Reduce duplication while preserving meaningful role and transaction distinctions.
- **Scope / exclusions:** Inventory callers and semantic differences; extract one pure/boundary helper with two real consumers first. Separate frontend and backend batches. Keep domain rules with their owners; MOD-033 owns ownership/conference rule consolidation. No universal base controller/repository or global utilities rewrite.
- **Dependencies:** MOD-038/041 for structural/pipeline decisions when applicable; pure identical helper extraction need not wait. Coordinate MOD-019/028B/029 to avoid duplicate work.
- **Acceptance / verification:** Consumer-level valid/error/identity behavior preserved, no hidden I/O/commit/auth bypass, focused regressions and relevant broader checks pass. Record deliberate non-extractions where semantics differ.
- **Contract impact:** Behavior/API/schema: no intended; real defects receive separate behavior-change scope.

### MOD-040 — Pilot file-content and folder refactoring without changing behavior

- **Continuation — 2026-10-30: draft snapshot pilot complete.** Started next cohesive domain with actor/trusted snapshots and completed repair in DraftSnapshotService/Repository, preserving private connection helpers, SQL/envelope and supplied transactions. Backend 495/495, independent review with no findings and [native draft snapshot checks](evidence/mod-038-draft-snapshot-postgres-2026-10-30.json) pass. Commands/control/order/timeout/broadcast remain separate. League aliases retained for existing tests/tools; retire only after caller import migration and verification. [Plan/ledger](../superpowers/plans/2026-10-30-mod-038-draft-snapshot-implementation.md).
- **Continuation — 2026-10-30: league folder pass complete.** Grouped canonical implementation into admission/members/administration/reads/lifecycle; root modules alias canonical objects for legacy import/exception/patch compatibility. Non-import definitions unchanged. Backend 489/489, independent review with no findings and [complete native league rerun](evidence/mod-040-league-folders-postgres-2026-10-30.json) pass; manifest captures canonical and legacy files. [Layout](../../api/endpoints/league/README.md), [plan/ledger](../superpowers/plans/2026-10-30-mod-040-league-folders-implementation.md). No pending league extraction/folder slices; broader MOD-040 remains partial for other domains/frontend and correctness work.
- **Continuation — 2026-10-30: planned league content extraction complete.** Lifecycle now uses service/repository with original five ordered global updates/transaction; LeagueModel contains no SQL or connection acquisition. Backend 486/486, independent review with no findings and [complete native league evidence](evidence/mod-038-league-complete-postgres-2026-10-30.json) pass, including transition boundaries/precedence/rollback/real read callback and every prior league suite. No planned league extraction slices remain. Import-only admission/members/administration/reads/lifecycle folders, wider domains/frontend pilot and MOD-020/correctness remain separate; broader MOD-040 is still partial. [Plan/ledger](../superpowers/plans/2026-10-30-mod-038-league-lifecycle-implementation.md).
- **Continuation — 2026-10-30: member list/daily summaries extracted.** Actor/trusted read now uses service/repository with unchanged SQL/date/score/callback semantics and explicit schedule capabilities. Backend 482/482, independent review with no findings and [native summary evidence](evidence/mod-038-member-summary-postgres-2026-10-30.json) pass; prior suites rerun. Lifecycle sync remains the last league extraction slice. Recommend subsequent import-only admission/members/administration/reads/lifecycle folders retaining compatibility imports and route composition. [Plan/ledger](../superpowers/plans/2026-10-30-mod-038-member-summary-implementation.md).
- **Continuation — 2026-10-30: details/my leagues extracted.** Read service/repository now own scoped details and membership-only listings with original stage/score/week projection and explicit pre-read lifecycle callback. Backend 476/476, independent review with no findings and [native interval/listing/sync-boundary evidence](evidence/mod-038-league-details-postgres-2026-10-30.json) pass; all preceding native suites rerun. Two league slices remain: member lists/daily summaries and lifecycle synchronization. [Plan/ledger](../superpowers/plans/2026-10-30-mod-038-league-details-implementation.md).
- **Continuation — 2026-10-30: league discovery extracted.** Access metadata, scoped names-only previews and anonymous discoverable search now use LeagueReadService/LeagueReadRepository. Existing HTTP gates/rechecks, projections, bound SQL/pg_trgm ranking and pagination contracts preserved. Backend 471/471, independent review with no findings and [native discovery/search/revocation evidence](evidence/mod-038-league-discovery-postgres-2026-10-30.json) pass; preceding native suites rerun. Three planned league slices remain: details/my leagues, member lists/daily summaries and lifecycle synchronization. [Plan/ledger](../superpowers/plans/2026-10-30-mod-038-league-discovery-implementation.md).
- **Continuation — 2026-10-30: league conferences extracted.** Actor/trusted conference read now uses LeagueReadService/LeagueReadRepository with original one transaction, scoped league/season checks, count/order/zero fields and HTTP/model behavior. Backend 465/465, independent review with no findings and [native aggregate/revocation evidence](evidence/mod-038-league-conferences-postgres-2026-10-30.json) pass; prior slices rerun. Four planned league slices remain: discovery/access/previews/search, details/my leagues, member lists/daily summaries and lifecycle synchronization. [Plan/ledger](../superpowers/plans/2026-10-30-mod-038-league-conferences-implementation.md).
- **Continuation — 2026-10-30: league rules read extracted.** Actor/trusted rules read now uses LeagueReadService/LeagueReadRepository with original scoped query, tier fallback, rule/deadline output, single connection and model compatibility. HTTP discovery gates unchanged. Backend 460/460, independent review with no findings and [native tier/deadline/scope/revocation evidence](evidence/mod-038-league-rules-read-postgres-2026-10-30.json) pass; prior slices rerun. Details/member/conference reads, discovery and lifecycle remain separate. [Plan/ledger](../superpowers/plans/2026-10-30-mod-038-league-rules-read-implementation.md).
- **Continuation — 2026-10-30: league creation extracted.** Actor/trusted creation now uses LeagueAdminService/LeagueAdminRepository, with server-owned commissioner, version/default timezone/trimmed team policy, atomic league/member inserts and explicit post-commit initialization capability. Model/HTTP contracts preserved. Backend 455/455, independent review with no findings and [native insert/rollback/initializer-boundary evidence](evidence/mod-038-league-creation-postgres-2026-10-30.json) pass; prior slices rerun. Existing schedule generation unchanged and initializer failure still preserves creation; no retry/atomic-scheduling guarantee. Reads/lifecycle remain separate. [Plan/ledger](../superpowers/plans/2026-10-30-mod-038-league-creation-implementation.md).
- **Continuation — 2026-10-30: league settings updates extracted.** Actor/legacy/trusted updates now use LeagueAdminService/LeagueAdminRepository with original two scopes, validation order/version/allowlist, timezone sharing and guarded write. Backend 449/449, independent review with no findings and [native CTE/JSON/rollback/revocation evidence](evidence/mod-038-league-settings-postgres-2026-10-30.json) pass; prior league deletion/member/admission checks rerun. Original SQL alias and no-result post-commit semantics retained; no lost-update redesign. Creation/reads/lifecycle remain separate. [Plan/ledger](../superpowers/plans/2026-10-30-mod-038-league-settings-implementation.md).
- **Continuation — 2026-10-30: league deletion extracted.** Actor-bound and legacy commissioner-checked deletion now use LeagueAdminService/LeagueAdminRepository; locked authority, scoped DELETE, transaction/cascade and error/response contracts preserved. Backend 442/442, independent review with no findings and [native cascade/rollback/replay/revocation evidence](evidence/mod-038-league-delete-postgres-2026-10-30.json) pass; preceding admission/member checks rerun. Settings, creation, reads and lifecycle remain separate. [Plan/ledger](../superpowers/plans/2026-10-30-mod-038-league-delete-implementation.md).
- **Continuation — 2026-10-30: member removal extracted.** Commissioner removal, protection, optional draft-order shifting and player-count decrement now use MemberService/MemberRepository with league→member locking and actor-bound HTTP. Existing legacy inputs, errors, projection and settings behavior retained. Backend 437/437, independent review with no findings and [native rollback/concurrency evidence](evidence/mod-038-member-removal-postgres-2026-10-30.json) pass; preceding member/admission checks rerun. Broader league reads/administration and policy redesign remain separate. [Plan/ledger](../superpowers/plans/2026-10-30-mod-038-member-removal-implementation.md).
- **Continuation — 2026-10-30: member profile updates extracted.** Actor-bound rename and trusted allowlisted update now use MemberService/MemberRepository; atomic ownership predicate, concealed 404, raw names and legacy model/constant contracts preserved. Backend 431/431, independent review with no findings and [native profile plus admission rerun](evidence/mod-038-member-profile-postgres-2026-10-30.json) pass. PostgreSQL verifies rollback and ownership revocation during observed row-lock waits. Member removal/draft-order shifting and broader league reads/administration remain separate. [Plan/ledger](../superpowers/plans/2026-10-30-mod-038-member-profile-implementation.md).
- **Continuation — 2026-10-29: admission migration complete with approval.** Approval joins listing/creation/denial/cancellation in AdmissionService/AdmissionRepository; actor-bound HTTP, explicit trusted approval and legacy/private helper signatures retained. Existing membership/draft-order/count/round/JSON semantics preserved. Backend 426/426, independent review with no findings and [full native admission evidence](evidence/mod-038-admission-complete-postgres-2026-10-29.json) pass, including real failure rollback and observed competing same/distinct approval lock waits through service/facade; all previous admission native checks rerun. This completes the bounded admission extraction, not wider league administration or MOD-012 policy/schema work. [Plan/ledger](../superpowers/plans/2026-10-29-mod-038-admission-approval-implementation.md).
- **Continuation — 2026-10-29: admission creation/denial complete.** Extended AdmissionService/AdmissionRepository with membership-first normalized creation, existing-pending replay and commissioner denial under league→request locks. Actor-bound HTTP, explicit trusted denial, legacy signatures/private connection helper and original failure contracts preserved. Backend 419/419 and [native creation/denial plus prior listing/cancellation checks](evidence/mod-038-admission-create-deny-postgres-2026-10-29.json) pass; independent review has no findings. Approval, capacity and concurrent-creation uniqueness remain separate; no schema change. [Plan/ledger](../superpowers/plans/2026-10-29-mod-038-admission-create-deny-implementation.md).
- **Continuation — 2026-10-29: admission listing/cancellation complete.** Added league-local AdmissionService/AdmissionRepository with commissioner-only private listing and owner-only locked cancellation, explicit actors and legacy/trusted bridges. HTTP/model/private-helper projections, status/error behavior, ordering, replay and resolution fields preserved; LeagueModel.__new__ callers remain supported. Backend 412/412 and [native PostgreSQL listing/revocation/lock/rollback checks](evidence/mod-038-admission-postgres-2026-10-29.json) pass; independent review has no findings. Creation, approval, denial and admission serialization policy remain separate. [Plan/ledger](../superpowers/plans/2026-10-29-mod-038-admission-read-cancel-implementation.md).
- **Continuation — 2026-10-29: remaining scoring domain extracted.** ScoringService owns weekly calculation/atomic replacement, season standings and tiebreak orchestration; ScoringRepository owns all scoring SQL and pure rules own bonus awards. Legacy facade inheritance preserves actual helper overrides; both scoring jobs now construct services directly. Backend 406/406 and [native full-scoring evidence](evidence/mod-038-scoring-complete-postgres-2026-10-29.json) pass. One separately recorded correctness repair replaces invalid SQLAlchemy Row string indexing in depth/latest-week paths, protected by three regressions. Independent review has no findings. Recovery/timing/startup policies remain MOD-013/014/034, not implicitly complete.
- **Continuation — 2026-10-29: scoring weekly-points read complete.** Extracted actor-requiring ScoringReadService and supplied-connection ScoringRepository for this one read, preserving model/trusted interfaces, week normalization, projections/order, original HTTP envelope and pre/post league checks. Empty-list reads still authorize; late revocation retains concealed 404. Backend 396/396 and [native PostgreSQL binds/projection/revocation checks](evidence/mod-038-scoring-read-postgres-2026-10-29.json) pass; independent review has no findings. Calculation, standings, job recovery and disabled HTTP writes are untouched. [Plan/ledger](../superpowers/plans/2026-10-29-mod-038-scoring-read-implementation.md).
- **Continuation — 2026-10-29: user-domain persistence extraction complete.** Creation/legacy UUID lookup now join ID read/update in UserService/UserRepository; UserModel retains all method signatures and built-in failure compatibility as a SQL-free facade. Bootstrap uses verified ProfileSubject without requiring an existing app user. HTTP existing-profile 409, ambiguous identity 403, safe constraint failure 400 and unexpected failure 500 remain unchanged. Guarded backend 389/389 and [native creation/read/update checks](evidence/mod-038-profile-creation-postgres-2026-10-29.json) pass, including real statement/deferred-commit insertion rollback. Independent review has no findings. No schema/UUID uniqueness fix or repository-wide migration implied. [Plan/ledger](../superpowers/plans/2026-10-29-mod-038-profile-creation-implementation.md).
- **Continuation — 2026-10-29: profile read/update slice complete.** User requested the next domain; own-profile reads and display-name updates now use actor-requiring UserService and supplied-connection UserRepository. Existing model signatures, update allowlist, error/status contracts, bootstrap resolution and foreign-target denial before JSON parsing are preserved. Creation/legacy UUID persistence intentionally remain on their existing paths. Backend 381/381 and [native PostgreSQL statement/commit rollback checks](evidence/mod-038-profile-postgres-2026-10-29.json) pass; independent review has no findings. [Plan/ledger](../superpowers/plans/2026-10-29-mod-038-profile-implementation.md). Other domains and the remainder of profile persistence are future increments.
- **Continuation — 2026-10-29: roster domain content extraction complete.** User requested another domain; both roster reads now use actor-requiring services and connection-scoped repositories. Existing model/helper signatures, HTTP projections/statuses, locked-week selection, pending moves and query-time access predicates remain compatible. Fresh guarded backend 373/373 and [native PostgreSQL roster checks](evidence/mod-038-roster-postgres-2026-10-29.json) pass. Independent review has no blocking findings; minor endpoint construction cleanup deferred. No folder move, frontend extraction or hosted change. [Plan/ledger](../superpowers/plans/2026-10-29-mod-038-roster-implementation.md).
- **Status — 2026-10-29: API content pilot complete; broader card partial.** Approved MOD-038 extraction covers transaction listing and trusted trade application within the existing domain directory. Actual routes, legacy model/helper signatures, dispatcher behavior, authorization, ownership intervals and replay/rollback contracts are preserved. No folder move performed or needed for this pilot. Full isolated backend 366/366 and real disposable PostgreSQL concurrency/read checks pass; independent review has no findings. Remaining domains, optional import-only folder moves and frontend pilot are separate work; app/listener startup remains MOD-034.
- **Priority / size / risk:** P2 / S–M per domain pilot / Medium.
- **Features:** Cross-cutting API and frontend organization.
- **Problem / evidence:** User requested file-content and structure refactoring; large model/screen responsibilities and existing MOD-029–033 identify concrete candidates.
- **Expected benefit:** Make domain ownership and navigation clearer with reviewable migrations.
- **Scope / exclusions:** After the architecture decision, choose one API domain and later one frontend feature. Split content extraction from import-only moves; retain facades where callers need stability. Define test placement and naming/import conventions. Reuse existing decomposition cards rather than repeating their implementations. No mass rename, schema/API-path rename or simultaneous behavior redesign.
- **Dependencies:** MOD-038 approved target; MOD-034 import/startup boundaries; relevant domain correctness and MOD-029–033 prerequisites.
- **Acceptance / verification:** Before/after call/import map, acyclic dependencies, stable public/model/job contracts, isolated import/tests and relevant frontend type/build checks. Verify Flask endpoint registration, mocks, CLIs and jobs after moves.
- **Contract impact:** Behavior/API/schema: no intended; file/import paths may change with documented compatibility.

### MOD-041 — Decide incoming, response and outbound interceptor architecture

- **Implementation follow-up — 2026-10-29:** User requested implementation; the [first auth slice](../superpowers/plans/2026-10-29-mod-041-auth-implementation.md) is implemented and independently reviewed in the current checkout. MOD-028A's bounded recovery contract and basic request IDs/no-store response handling are covered. This does not complete MOD-019/024/034, provider policy work or MOD-038/040 structural migration. Rate limiting remains deferred; no deployment or infrastructure changes.
- **Status — 2026-10-29: complete in architecture-decision scope.** User approved the [architecture decision](../superpowers/specs/2026-10-29-mod-041-boundaries-design.md): Flask application hooks with explicit hosting and separate outbound-client ownership (option 3), existing Render hosting and rate limiting deferred. No required new paid infrastructure. Implementation remains in the mapped cards; deployment facts and concrete bounds/timeouts remain evidence tasks. MOD-038 incremental hybrid is now approved and its first transaction-domain pilot is implemented. [Follow-through sequence](../superpowers/plans/2026-10-29-mod-041-follow-through.md).
- **Priority / size / risk:** P1 / S–M for decision / Medium.
- **Features:** F-002, F-004, F-022–028, F-034; cross-cutting transport concerns.
- **Problem / evidence:** authMiddleware.before_request, app CORS, endpoint principal/error handling, separate socket auth and frontend apiFetch form several boundaries without a documented common pipeline; rate/gateway policy remains unresolved.
- **Expected benefit:** Place authentication, authorization, limits, errors, credentials and telemetry at explicit, testable boundaries.
- **Scope / exclusions:** Discuss Flask hooks versus WSGI middleware, registration/order and short circuits; public/bootstrap/OPTIONS/socket paths; principal resolution; coarse and per-identity limits; safe response envelopes/headers; frontend refresh and outbound provider credentials/timeouts/retries. Decide proxy trust, multiworker limiter storage, quota/failure policy and ownership. No new limiter/library/storage install, retry-all behavior, service authorization replacement or production gateway change.
- **Dependencies:** MOD-038 for layer ownership; Q5 runtime/gateway evidence. Independent discussion can start now.
- **Acceptance / verification:** User-approved incoming/response/outbound sequence with explicit responsibility/implementation mapping to MOD-019/028A/024/034, exemption matrix and synthetic test plan covering early denial/errors/retries/worker consistency. Unknown deployment facts remain unknown.
- **Contract impact:** None in decision task; selected auth/error/rate policies may intentionally change APIs in their implementation cards.

## Complete feature disposition

Every inventory feature is included below. Cross-cutting tasks apply only where their cards explicitly include that feature; a mapping does not claim every subfeature needs rewriting. Investigation tasks can conclude no change. F-001/003/010/014/017/021/034/037–041 especially do not justify new product capabilities from absence of tests alone.

| Feature | Proposed tasks / disposition |
| --- | --- |
| F-001 Introduction | MOD-036 measurement only; no content/layout change currently justified. |
| F-002 Authentication | MOD-002/004/006/026/028A: profile lifecycle, access boundary and bounded refresh. |
| F-003 Password recovery | No change currently justified to recovery flow; retain checklist checks and verify deployment redirects separately if evidence warrants. |
| F-004 Profile/settings | MOD-001/002/004/006/019/026/028B/037. |
| F-005 Own leagues | MOD-003A/017/018/020/026/027A/029/036. |
| F-006 Discover/admission | MOD-002/003A/011/012/017/018/019/027D/028B. |
| F-007 League creation | MOD-003A/005/008/012/015/019/027E/030/032/036. |
| F-008 League detail/member actions | MOD-003A/017/019/020/021/028B/029. |
| F-009 Standings/member schedules | MOD-003A/003C/007/008/015–017/019/021/029/032/036. |
| F-010 Rules view | MOD-003A read authorization and MOD-015 season consistency; no rules UI/formula rewrite currently justified. |
| F-011 Conference schedules | MOD-003A/015/017/021/029/032/036. |
| F-012 Team search/schedule | MOD-003A/015/017/018/027C/029/032/036. |
| F-013 Live draft | MOD-003B/010/015/017–020/023/025/027F/031A/033/036. |
| F-014 Draft history | MOD-003B read scope, MOD-015/018/036 investigation; no independent history rewrite justified. |
| F-015 Free agency/rosters | MOD-003C/010/013/015/017–019/027B/029/033/036/037. |
| F-016 Trades/veto/pending | MOD-003C/009/010/013/015/017–019/027B/029/033/036. |
| F-017 League settings | MOD-003A/019/028B/029/030; no scoring-setting semantics change by refactoring. |
| F-018 Draft setup/order | MOD-003A/003B/012/019/020/025/027G/028B/029/031B/036. |
| F-019 Moderation/member removal | MOD-003A/011/012/019/028B/029/031B. |
| F-020 Draft control/finalize | MOD-003B/019/020/023/025/027F/031A/036. |
| F-021 League deletion | MOD-003A/019/028B/029; retain explicit deletion/retention decisions, no new deletion capability. |
| F-022 Auth middleware / integration | MOD-001–004/006/019/024/026/028A/034/037. |
| F-023 Draft realtime | MOD-003B/004/023/024/031A/034. |
| F-024 Timeout worker | MOD-003B/004/010/015/017/023–025/033/034. |
| F-025 Weekly scoring/apply | MOD-003C/004/007–010/013–017/020/021/024/033/034/037. |
| F-026 Season finalization | MOD-004/014/016/021/024/034/035/037. |
| F-027 Scoreboard ingestion | MOD-004/015/017/019/022/024/032/034. |
| F-028 Season bootstrap | MOD-004/005/008/015–017/019/022/024/032/034/035. |
| F-029 Join cancellation API | MOD-003A/011/012; preserve API-only status pending external usage evidence. |
| F-030 Manual allocation API | MOD-003B/010/015/019/025/033; resolve acquisition-week/operator policy explicitly. |
| F-031 Create weeks API | MOD-003A/005/008/016/032. |
| F-032 Scoring trigger APIs | MOD-003C/007/008/014/017/019/021/035/037. |
| F-033 Explicit trade-apply API | MOD-003C/009/010/015/033. |
| F-034 Health | MOD-004/019/024/034; no unagreed readiness contract change. |
| F-035 Tournament rules | MOD-005/015/016/021/022/032/033; preserve versioned margin/tie rules, investigate historical integrity. |
| F-036 Rebuild/rescore | MOD-004/005/007/008/014/016/024/032/034; no production rebuild authorized. |
| F-037 Tier analysis | MOD-036 investigation only; no DB tier-update automation or tool rewrite currently justified. |
| F-038 Magic link alternative | MOD-035 usage decision; no behavior change/removal currently justified. |
| F-039 Deprecated wrappers | MOD-034 startup compatibility / MOD-035 usage decision; no removal currently justified. |
| F-040 Unregistered week lock | MOD-035 reachability/owner decision; no registration/repair/removal currently justified without caller evidence. |
| F-041 Alternative adapters/auth | MOD-034 import isolation / MOD-035 usage decision; no replacement/removal currently justified. |

## Delivery and evidence checkpoints

Each implementation task should update progress and link its changed files, exact isolated checks/results, remaining unknowns, contract decisions and any follow-up task. Run verification appropriate to the change: import/type/build checks for moves, journey/model fixtures for refactors, adversarial identity/concurrency/fault cases for integrity/security, disposable Postgres for SQL/migration behavior, browser keyboard/reconnect checks for interactions, and representative plans/traces for performance claims. Existing test suites are regression inputs, not proof of auth/concurrency coverage.

Task cards with staged scope intentionally require separate reviews: MOD-015 consumers, MOD-019 errors versus bounds, MOD-022 dedup versus retries, MOD-023 notifications versus browser lifecycle, MOD-025 order versus start, MOD-029 extraction versus freshness, MOD-031A clock versus socket, and MOD-032 ingestion versus calendar. If a stage exceeds M, assign a stable suffixed follow-up card with its own evidence and acceptance criteria before expanding implementation. Keep existing IDs stable when reprioritizing. Unknown external usage, live schema, roles, schedules and runtime metrics remain evidence gaps, not implicit permission to remove structures or deploy changes.
