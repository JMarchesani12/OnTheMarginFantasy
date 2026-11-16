# MOD020 — authorized scoped lifecycle refresh

## Intent and chosen approach

Preserve fresh full-detail and own-league page results while preventing those requests from updating unrelated leagues. The user chose authorized target/set refresh before reading, deferring a scheduled global job. Keep Python/SQLAlchemy/PostgreSQL and existing HTTP/auth contracts.

Approaches considered: (1) explicit authorized request orchestration with scoped transitions, selected because it preserves existing page freshness without scheduler rollout; (2) pure reads backed by a global scheduled refresh, deferred because it needs a cadence, failure ownership and tolerable staleness decision. Retaining the hidden global callback fails the scope goal.

This is a bounded application change, not a new lifecycle/status policy or scoring/index redesign. User owns commits/integration. No SQL rollout or scheduler registration.

## Current call graph and observed policy

- `LeagueEndpoints._league_read_response`: authenticated principal → access metadata → preview/full gate. Full details invokes `LeagueReadService.details(actor,id,synchronize_for_job)`.
- Own listing validates authenticated self-ID → `LeagueReadService.mine(actor,synchronize_for_job,stage)`.
- Both reader methods invoke a callback outside their read transaction; callback commits five global UPDATEs in one independent transaction, then the reader performs its scoped SELECT.
- Rules/conferences/members, public search, and discovery previews do not call lifecycle synchronization. They must not acquire a new lifecycle side effect.
- `details_for_reader_id`, `details_for_job`, `mine_for_user_id` are internal entry points; repository search finds production callers only through these adapters. Audit drivers, native verification helpers and unit tests also pass callbacks. All must be inventoried/updated explicitly; do not silently accept and ignore a formerly required callback.
- `synchronize_for_job` is a trusted global service method, not an actual registered cron entry. Existing scripts call it. Retain it as an explicit trusted operation; HTTP cannot select it via request flags.
- Draft start/order locks existing DraftState before League. If state is absent, it locks League and checks whether state appeared while waiting; it never acquires a new state lock while holding League. Picks/finalization also use state before League. Member removal/admission lock League before dependent member/request records; lifecycle must not lock those child records in reverse order.
- Current phases: Pre-Draft, Drafting, Post-Draft, In-Season, Completed, in that order. League-local timezone settings control calendar dates; season lookup uses sport/year. Completed wins last after season end. Existing Completed exclusions differ per phase and must remain unchanged.

## Proposed boundary and cadence

Introduce an explicit application/query coordinator (builder may choose a clear local name) that composes lifecycle refresh and repository reads on one supplied transaction. The ordinary `LeagueReadService` detail/list entry points become read-only with no lifecycle callbacks; reusable `*_in_transaction` read methods permit the coordinator to reuse its connection. Neither route handlers nor low-level readers run the trusted global operation.

Full-detail route uses coordinator with verified UserActor and target ID, after existing preview gates. Own listing uses coordinator with verified actor and normalized stage. Every such request refreshes eligible scope synchronously before its SELECT; there is no timer, TTL or background activity. If a request fails, its transitions roll back. Other endpoints retain their current behavior; this does not promise background freshness or refresh for public previews/search.

Detail scope: exactly the target league, only if commissioner or current member. Missing, private-denied and public-preview-only actors cause zero lifecycle writes. The service must enforce this internally, not rely on the route's earlier entitlement check.

Own-list scope: all leagues with an actual LeagueMember row for the actor, independent of requested active/completed filter. Refresh before stage filtering so newly completed leagues move between lists correctly. Commissioner-only leagues without membership remain absent, matching current listing semantics. Do not expand membership via commissioner access or join requests.

## Transaction and concurrency contract

Builder call: use a single READ COMMITTED transaction per composed refresh/read. Determine candidate IDs using actor scope, sort/deduplicate them, and process each ID in ascending order. For each candidate, lock existing DraftState first, then League. Once League is locked, recheck draft-state presence and actor entitlement using fresh statements. If an initially absent state appeared while waiting, roll back the whole transaction and restart once from candidate discovery; do not lock that new state while holding League. A second occurrence produces a safe HTTP409 conflict and no committed transitions, not an unbounded retry or partial result. This retry is only for this identified first-start race; SQL/deadlock/permission failures propagate and roll back without generic retries.

After League locks, use fresh membership/commissioner predicates before any UPDATE and reapply actor predicates in scoped UPDATEs and final SELECT. Normal member removal/admission/delete/commissioner settings operations serialize on League. Do not lock LeagueMember rows: preserve existing mutation lock order. Authorization is enforced at refresh/write and final-read boundaries; no guarantee against arbitrary external writers bypassing application lock discipline or revocation after the final read.

Candidate sets are bounded by membership at transaction discovery. A membership added after discovery can appear on a later request; final listing must be restricted to the discovered/refreshed eligible IDs so a new unrefreshed league cannot leak into this response. Existing eligible rows removed while waiting are skipped. Return ordering, fields, null current-week handling and stage filters remain unchanged for the resulting set. Document this concurrency-only set boundary explicitly; do not change static listing completeness.

Keep PostgreSQL `now()` transaction-time evaluation, matching existing SQL: a transaction delayed across midnight still evaluates its start-time calendar; a restarted transaction gets a new timestamp. Do not silently switch to wall-clock timing.

Hold locks through all phase updates and SELECT, commit before returning payload. Any phase, SELECT, permission, lock or commit failure rolls back all refreshed leagues in that request. No result escapes a failed commit. Sort locking deterministically across multiple leagues; test against draft start/final pick and member removal, not just isolated methods.

## Status behavior and scope of first implementation

Keep the existing five phase predicates and ordering, adding exact authorized scope only. Do not replace them with a newly derived CASE or blanket Completed exclusion. The first batch removes unrelated writes; it does not promise zero writes for every already-converged league. Specifically ended-season Completed + live draft may still transition Drafting→Completed inside the authorized scope, with updatedAt touched. This preserves current final statuses and timestamp behavior for refreshed resources. A separate later policy-preserving no-op optimization may remove that churn after independent equivalence design.

Retain UTC fallback/local date boundary behavior, unfinished-draft guards, missing-season and null-status behavior. Unrelated leagues must retain status and updatedAt even when dirty. The trusted explicit global method retains existing behavior for deliberate job/script callers; new scoped HTTP flow must never delegate to it.

## Error and compatibility contract

Keep routes, preview concealment, actor resolution, self-list identity checks, payloads and normal successful statuses unchanged. Missing/denied detail produces existing not-found behavior; valid empty own list stays empty with zero updates. The only deliberate new response is safe409 for exhausted first-start race, with fixed text and no database detail. Existing database error policy remains otherwise unchanged; no fallback stale success.

Retire read callback parameters at repo-local call sites and update verification scripts/tests to choose either explicit coordinator freshness or read-only behavior. External consumers of these Python methods are not known; list signature changes for integration review rather than implying an external compatibility guarantee. Public HTTP/API signatures do not change.

## Verification required in bounded implementation plan

1. Unit/route RED→GREEN: reader calls execute only SELECTs; coordinator sequence candidate→state/league locks→fresh authorization→five scoped phases→scoped SELECT→commit. Invalid actor/denied/missing/empty cases have zero UPDATEs. Preview gates stay read-only.
2. Preserve existing lifecycle policy matrix, timezone boundaries, rollback after every phase/SELECT/deferred commit and full detail/list fields. Include Completed/live ended and active-season cases, unknown/missing seasons and null statuses; distinguish final status convergence from repeat write counts.
3. Owned marked-local PostgreSQL: reproduce ten baseline groups at a bounded size, compare refreshed targets with existing global-policy reference on equivalent separate fixtures. Verify exact full returned projections, statement sequence, UPDATE row counts, touched IDs and untouched unrelated statuses/timestamps. Preserve historical raw artifacts; new unique RUNNING/PASS/FAILED evidence/source hashes/cleanup.
4. Native interleavings: existing-state start/pick/finalization, absent-state first start, membership removal while waiting, lock/permission failure, delayed refresh across day/season boundary and retry after failed transitions. No external configured DSN or live provider.
5. Full guarded backend suite and affected measurement helpers. No frontend/browser/scoring/ingestion rerun unless actual code changes require it. No production speedup/scheduler/role/RLS claim.

## Builder discretion and release limits

Builder chooses local coordinator/repository method names, bounded synthetic fixture size, and test placement. Do not redesign admission, draft start/finalization, status policy, score aggregation or introduce indexes. If locking cannot satisfy the stated boundary without changing another subsystem, report the concrete conflict before broadening implementation. Production workload/lock timing and any future scheduler need their own rollout decision.

Design status: fresh builder check returned “nothing important left.” User approved2026-11-16. Product code has not changed in this design/planning batch.
