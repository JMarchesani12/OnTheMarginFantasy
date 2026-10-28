# Modernization backlog

2026-10-28. Proposed work only; no fixes implemented. Synthesizes [architecture](architecture.md), [all 41 features](features.md), [behavior checklist](behavior-checklist.md), [frontend audit](frontend-audit.md), [backend audit](backend-audit.md) and [database audit](database-audit.md). FE/BE D/M/S references point to those audit sections; DB references point to the database audit. Feature ranges are inclusive stable inventory IDs, not file paths.

## Priorities, assumptions and sizing

P0: identity/exposure and reproducible evidence; P1: integrity, focused regressions and demonstrated user failures; P2: measured performance investigations and bounded responsibility consolidation; P3: low-impact mechanical/text cleanup and investigations with weaker evidence. Priority is impact plus dependency, not task-number order. No runtime-measured performance problem has been established by any audit. Performance work starts with measurement and may end with “no change justified.”

S ≈ up to 1–2 engineering days; M ≈ 3–5 days, excluding access/product decisions and rollout. Ranges express uncertainty, not commitments. Risk describes implementation/rollout impact, not verified exploit likelihood. Dependencies on Q1–Q8 refer to product questions in the behavior checklist. Resolve a task's decisions before changing that behavior, but continue independent source/test work meanwhile. Never codify known security/SQL/state defects as compatibility requirements. Existing tests have been mapped, not executed by this audit; the acceptance checks below are future work.

Schema tasks require safe preflight, reviewed remediation, disposable-database validation and deployment/recovery planning. Metadata unavailability blocks live conclusions and migrations requiring that evidence, not independent app-level fixes. Use synthetic users/rows; do not use production mutation, jobs or private-row exports as verification. Every schema/policy deployment and external publication remains outside this audit.

## Recommended first implementation

**MOD-001**, followed immediately by MOD-002 and MOD-003A–C. Add a small credential-free principal/test boundary, then demonstrate own-profile success and cross-user denial while adopting it in profile endpoints. This addresses the shared cause of the highest-impact source-demonstrated security defects and makes later authorization changes verifiable. Do not report broad authorization fixed when only the helper/profile slice is complete. Run MOD-004/005 evidence/provenance work in parallel only if an implementation session authorizes that workflow; it need not delay these app fixes.

Security sequence: MOD-001 → MOD-002 and separately MOD-003A/B/C; MOD-004 validates the direct Supabase and backend privilege boundary. Integrity sequence: MOD-005 → key/constraint work; MOD-007 → MOD-008 → MOD-013, MOD-009 → MOD-010 → MOD-013; MOD-011 → MOD-012; MOD-025 protects draft invariants. Small UI/accessibility fixes can ship independently as dependencies allow. No repository-wide reorganization is proposed.

## Incremental organization conventions

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

- **Priority / size / risk:** P0 / M / High.
- **Features:** F-005–012, F-017–019, F-021, F-029, F-031.
- **Problem / evidence:** BE D01; DB access-path matrix; commissioner checks trust supplied actor and member PATCH permits draftOrder/seasonPoints.
- **Expected benefit:** Prevent foreign league/member administration.
- **Scope / exclusions:** Adopt principal across league/create/byUser/member/moderation/delete/week-generation and league-scoped reads; bind URL league to all resources and restrict writable fields by operation. Exclude draft/trades (next tasks).
- **Dependencies:** MOD-001; role/public-read matrix Q1/Q4.
- **Acceptance / verification:** Independent member, nonmember and commissioner fixtures exercise every migrated route, arbitrary actor IDs and mismatched league/member/request/week IDs; allowed J1/J2 journeys still work; ordinary team-name edit cannot alter scores/order.
- **Contract impact:** Behavior: yes; API: permission/error contract changes, preserve valid payloads where possible; schema: no.

### MOD-003B — Authorize draft read and command paths

- **Priority / size / risk:** P0 / M / High.
- **Features:** F-013, F-014, F-018, F-020, F-022–024, F-030.
- **Problem / evidence:** BE D01; socket subject binding already exists, REST start/pause/resume/order/manual differ.
- **Expected benefit:** Protect draft control and member ownership consistently.
- **Scope / exclusions:** Principal binding for live/manual picks, state, order, start/pause/resume/finalize; decide API-only operator role. Preserve socket room checks; no cursor/order algorithm refactor.
- **Dependencies:** MOD-001; Q1/Q4 role matrix.
- **Acceptance / verification:** Cross-user/member/league ID substitutions fail across registered draft operations; intended commissioner/member/operator commands pass; sockets and REST agree on scope.
- **Contract impact:** Behavior: yes; API: authorization/status changes; schema: no.

### MOD-003C — Bind roster, scoring and transaction authorization to resource scope

- **Priority / size / risk:** P0 / M / High.
- **Features:** F-009, F-015, F-016, F-025, F-032, F-033.
- **Problem / evidence:** BE D01/D02; trade routes discard URL league; DB-02/05.
- **Expected benefit:** Prevent cross-league transaction actions and unauthorized scoring.
- **Scope / exclusions:** Principal binding for roster/add-drop/propose/respond/cancel/veto/list/pending/apply/score triggers; resolve transaction by URL league and member ownership; distinguish internal job access. Exclude trade state-machine repair.
- **Dependencies:** MOD-001; Q1/Q4 operational/read permissions.
- **Acceptance / verification:** Foreign member IDs and valid transaction under wrong URL league fail; legitimate parties/voters and internal jobs pass; nonoperator cannot invoke operational score/apply functions. Exercise read exposure too.
- **Contract impact:** Behavior: yes; API: auth/scope errors; schema: no.

### MOD-004 — Verify and version Supabase access policies and role boundaries

- **Priority / size / risk:** P0 / M / High.
- **Features:** F-002, F-004, F-022–028, F-034, F-036.
- **Problem / evidence:** DB-02 access matrix: direct browser User SELECT and backend/listener DSNs; no versioned RLS/grants.
- **Expected benefit:** Make isolation testable across direct and server access.
- **Scope / exclusions:** Collect sanitized deployed metadata read-only if access becomes available; define table/role matrix, then author policy/grant migrations only for verified gaps in a later implementation. Inspect views/RPC/definer/default grants/publications, job roles and DSN alignment. Exclude production policy application and private-row exports.
- **Dependencies:** Metadata access required for deployed conclusions; coordinate MOD-002/005.
- **Acceptance / verification:** Document flags/owners/roles/grants for all exposed tables and routines; isolated anon/A/B/service-role tests prove required access and deny cross-user access; no assumption backend gets auth.uid; migration rollback/recovery plan reviewed. If metadata unavailable, record blocked evidence and do not invent policies.
- **Contract impact:** Behavior/API: conditional access changes; schema: policies/grants conditional.

### MOD-005 — Reconcile migration history and produce a reproducible schema baseline

- **Priority / size / risk:** P0 / M / Medium.
- **Features:** F-007, F-022, F-028, F-031, F-035, F-036.
- **Problem / evidence:** DB-01: duplicate DraftPick, FK ordering/extension prerequisites, two migrations, missing referenced tournament migration; BonusPointEvent discrepancy.
- **Expected benefit:** Prevent irreproducible setup and unsafe schema changes.
- **Scope / exclusions:** Recover provenance/history, define migration runner/order/ledger and Supabase prerequisites, distinguish descriptive snapshot from executable baseline; reconcile missing migration and README claims. No production application, inferred missing DDL or unrelated schema rename.
- **Dependencies:** None for repository reconciliation; metadata access for live comparison; MOD-004 coordination.
- **Acceptance / verification:** Disposable supported Supabase-compatible database initializes from documented baseline and upgrades from supported prior state; normalized definitions match intended source; absent migration reference resolved with provenance; current drift explicitly verified or unknown.
- **Contract impact:** Behavior: no intended; API: no; schema: reproducibility artifacts, actual changes separately reviewed.

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

- **Priority / size / risk:** P1 / S–M / High.
- **Features:** F-009, F-025, F-032, F-036.
- **Problem / evidence:** BE D06 / DB-04: delete commits before replacement.
- **Expected benefit:** Keep old scores intact on failure.
- **Scope / exclusions:** Use one transaction for weekly replacement; preserve ranking/tier/tie rules. Exclude job completion orchestration and uniqueness migration.
- **Dependencies:** MOD-001 safe harness; model-only work need not wait for all auth tasks.
- **Acceptance / verification:** Inject failure after delete and during insert: old complete score set remains; success produces expected exact set; isolated ranking fixtures unchanged.
- **Contract impact:** Behavior: failure atomicity yes; API: no intended; schema: no.

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

- **Priority / size / risk:** P1 / S–M / High.
- **Features:** F-016, F-025, F-033.
- **Problem / evidence:** BE D07 / DB-05: apply_trade lacks locked type/PENDING_APPLY checks.
- **Expected benefit:** Prevent invalid or replayed ownership writes.
- **Scope / exclusions:** Check type/status and preconditions in locked application transaction; define idempotent replay/rejection outcome across direct and pending dispatcher. Exclude ownership helper extraction.
- **Dependencies:** MOD-003C for HTTP protection; isolated model fix can proceed independently.
- **Acceptance / verification:** Rejected/cancelled/wrong-type/already-applied commands do not mutate ownership; two concurrent applies transfer once; valid pending trade remains atomic and J4 stays correct.
- **Contract impact:** Behavior: yes; API: define replay/error outcome and current null success compatibility; schema: no.

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
- **Scope / exclusions:** Construct/call ScoringModel directly from both scoring jobs, validate completion before flags, update misleading standings/bonus comments. Keep HTTP adapter response behavior and formulas; do not add BonusPointEvent without a persistence requirement.
- **Dependencies:** MOD-001 isolation; MOD-007 for scores; Q5 completion policy.
- **Acceptance / verification:** Run CLI logic with fake model/DB outside Flask; injected failure leaves completion flags unset; successful/all-league outcomes mark only agreed scope; HTTP season response unchanged.
- **Contract impact:** Behavior: job failure/success yes; API: no intended; schema: no.

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
