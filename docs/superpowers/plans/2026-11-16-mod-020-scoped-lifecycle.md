# Authorized Scoped Lifecycle Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans, preserving the approved native inline workflow and one fresh final review. User owns commits; do not stage/commit/push/deploy.

**Goal:** Refresh only an authenticated reader's eligible leagues atomically with full-detail/own-list reads, eliminating global read-triggered lifecycle writes.

**Architecture:** Ordinary LeagueReadService reads lose callbacks and expose supplied-connection methods. A separate LeagueLifecycleQueryService owns candidate discovery, draft-compatible locks, authorization rechecks, scoped five-phase updates and the final read in one transaction. Keep explicit trusted global synchronization unchanged.

**Tech Stack:** Existing Python, SQLAlchemy, PostgreSQL17.6 and guarded isolated tests; no dependency installation or live providers.

**Spec:** [Approved design](../specs/2026-11-16-mod-020-scoped-lifecycle-design.md). User approved2026-11-16.

## Global Constraints

- No scheduler, indexes, schema/SQL rollout, new status policy or frontend behavior changes.
- Preserve five-phase order/predicates, timezone resolution and PostgreSQL transaction-time now(); scoped ended-season live-draft churn remains intentional.
- No configured DSN/app/provider. Native validation uses a marked disposable loopback server and owned UUID fixtures only; remove exact owned resources, retain Docker/cache.
- Preserve historical raw artifacts and user-owned changes/index. Retain global synchronize_for_job as an explicit trusted operation; never wire it into HTTP reads.
- Every returned composed result must survive transaction commit; phase/read/permission/lock/commit failure rolls back the whole request.
- One full transaction retry only for an initially absent DraftState appearing while waiting for League. Second occurrence → fixed safe409. No generic SQL/deadlock retry.

## Review Focus

- A member removed or commissioner changed while waiting cannot trigger unauthorized lifecycle writes; public previews remain read-only.
- Own-list stage filtering occurs after refresh of membership candidates, with no newly joined unrefreshed league appearing in the response.
- Existing-state draft start/finalization and absent-state first start preserve state→League lock order with bounded retry.
- Completed/live and null/missing-season rows keep existing final statuses and scoped timestamp/write behavior; unrelated rows remain untouched.
- Every callback consumer and old measurement assumption is explicitly migrated; no silently ignored callbacks or hidden global fallback.

## File responsibilities and interfaces

- `api/endpoints/league/lifecycle/repository.py`: current five SQL phases; new scoped predicates and candidate/locking/authorization queries. Each `mark_*(conn, league_ids=None, reader_user_id=None, members_only=False)` retains global behavior when no scope arguments are given. Scoped IDs require verified integer reader ID; an empty scope is a no-op. Bind expanding IDs with SQLAlchemy, never interpolate values. All five UPDATEs include exact IDs and fresh membership/commissioner predicate (membership-only for own list).
- `api/endpoints/league/lifecycle/query_service.py` (new): `LeagueLifecycleQueryService(engine, repository=None, read_service=None)`, `details(actor, league_id) -> dict|None`, `mine(actor, stage='all') -> list`. Private transaction runner retries only `DraftStateAppeared`; public `LifecycleRefreshConflict` signals exhausted retry. Verified UserActor required; no job flag/trusted path here.
- Repository queries: `candidate_ids(conn,user_id,league_id=None) -> list[int]` (detail full access; own list actual membership), `lock_state(conn,league_id) -> bool`, `lock_league(conn,league_id) -> bool`, `state_exists(conn,league_id) -> bool`, `authorized(conn,league_id,user_id,members_only=False) -> bool`. Each query has one responsibility. Candidate IDs sorted/deduplicated; locks use ascending IDs, state before League per candidate. Skip deleted/unauthorized candidates; detect newly appeared state after League lock and abort before phase updates.
- `api/endpoints/league/reads/service.py`: read-only `details(actor,id)`, `details_for_reader_id(id,user_id)`, `details_for_job(id)`, `mine(actor,stage='all')`, `mine_for_user_id(user_id,stage='all')`. Add `details_in_transaction(conn,league_id,reader_user_id=None)` and `mine_in_transaction(conn,user_id,stage='all',league_ids=None)`. Ordinary methods own read connections; supplied methods never open another transaction. Reuse current stage normalization/logging.
- `api/endpoints/league/reads/repository.py`: `own_leagues(conn,user_id,stage,league_ids=None)` retains existing projection/filter/order; optional ID set restricts final coordinator selection. Empty set returns empty, not unscoped results. Detail already reapplies reader scope.
- `api/endpoints/league/leagueEndpoints.py`: instantiate coordinator, route full details/self-list through it after existing gates; map only LifecycleRefreshConflict to409 `{'message':'League state changed. Please retry.'}`. Preview/rules/members/conferences/search unchanged. Keep lifecycle global service if any explicit trusted wiring needs it; remove unused adapter dependency if none remains.
- Tests: new `api/tests/test_league_lifecycle_queries.py`, existing lifecycle/timezone/read authorization/own-list tests. Measurement helpers and native verifiers migrate explicit entry-point choices, not frozen raw artifacts.

## Task 1 — Read-only reader boundary

**Interfaces:** Produces supplied-connection reader methods and callback-free signatures above, consumed by Tasks2–3.

- [x] Add failing tests `test_reader_details_and_mine_do_not_synchronize_or_update` and `test_supplied_connection_reads_reuse_connection_and_scope`: execute actual service through current test adapters; assert only SELECTs and no separate engine.begin/connect call in supplied methods. Check empty ID scope cannot become an unscoped own list.
- [x] Run `python3 api/tests/run_isolated.py test_league_lifecycle_queries.py`; expected RED from callback requirements/missing supplied methods, not import/setup failures.
- [x] Implement supplied methods, callback-free wrappers and optional own-list IDs. Preserve full field projections and stage semantics. Adjust SQLite adapters only to support bound parameters/expanding IDs honestly; they cannot establish PostgreSQL locking semantics.
- [x] Update direct-reader unit callers to the explicitly read-only API. Route integration can remain pending until Task3; do not add a temporary global fallback.
- [x] Run focused read suites: `python3 api/tests/run_isolated.py test_league_lifecycle_queries.py test_own_league_listing.py test_league_read_authorization.py`; expected relevant reader assertions PASS, with any route expectations migrated in Task3 before full-suite completion. Record exact command/output and integration dependency, not a falsely complete suite claim.

## Task 2 — Scoped phases and atomic coordinator

**Interfaces:** Consumes Task1 supplied methods. Produces coordinator details/mine and LifecycleRefreshConflict for Task3. Global lifecycle service remains callable with no new arguments.

- [x] Add RED tests `test_scoped_phases_preserve_policy_and_leave_other_ids_untouched`, `test_candidate_lock_authorize_phase_read_commit_sequence`, `test_membership_scope_is_independent_of_stage`, `test_empty_denied_and_missing_have_no_updates`, `test_failures_roll_back_without_returning_payload` and `test_first_state_appearance_restarts_once_then_conflicts`. Derive expected statuses from existing literal fixture, not new SQL. Assert phase order and fresh authorization; two simulated appearances mean2attempts/0commits, one appearance then success means2attempts/1commit. No retry on unrelated exceptions.
- [x] Run `python3 api/tests/run_isolated.py test_league_lifecycle_queries.py test_league_lifecycle_service.py test_league_status_timezone.py`; expected new behavioral tests RED, existing trusted policy matrix retained.
- [x] Add scoped phase arguments and SQL predicates without rewriting existing policy. Add candidate/state/league/auth queries and coordinator. Explicitly request READ COMMITTED using a connection execution option before begin; do not inherit an unspecified engine isolation override. Lock all eligible IDs before phase execution. Use fresh statements after locks; first-state appearance raises the internal retry exception. Commit before returning. Restrict final own-list to refreshed eligible IDs.
- [x] Exercise actor rejection, commissioner-only detail versus membership-only own list, stage transition active→completed, missing/null status and ended-season live draft. Fail after each phase, final SELECT and transaction exit; assert previous rows/updatedAt restored.
- [x] Rerun the Task2 command; expected all focused tests PASS. Existing timezone SQL tests still see3local-date transitions and unchanged draft/Completed guards. Global phase calls/None result unchanged.

## Task 3 — HTTP integration and explicit consumer migration

**Interfaces:** Consumes Task2 coordinator and conflict class; produces unchanged normal HTTP payloads with scoped freshness.

- [x] Add RED routed tests `test_full_detail_and_self_list_use_scoped_coordinator`, `test_previews_and_denials_do_not_refresh`, `test_refresh_conflict_returns_safe_409`, `test_commit_failure_never_returns_success`. Assert verified actor identity, route concealment, no global synchronizer calls, fixed409body and no arbitrary database text. Preserve profile/identity errors.
- [x] Run `python3 api/tests/run_isolated.py test_league_read_authorization.py test_own_league_listing.py`; expected integration assertions RED on existing callbacks/global service.
- [x] Wire coordinator only for full detail/self-list. Update test doubles to stub the coordinator boundary where needed; retain actual SQL/reader tests independently.
- [x] Inventory `rg -n 'sync_statuses|details_for_job|details_for_reader_id|mine_for_user_id|synchronize_for_job' api scripts --glob '*.py'`. Migrate `scripts/modernization/verify_league_details.py` to intentional read-only calls; `verify_league_lifecycle.py` to explicit global-policy tests plus appropriate fresh coordinator tests. Migrate any additional callback consumers found by the inventory. Document changed internal signatures; no public HTTP signature change.
- [x] Version `scripts/modernization/measure_mod020_lifecycle.py` and `scripts/modernization/tests/test_mod020_lifecycle.py` for actual coordinator capture and explicit statement sequence. Keep explicit global reference outside measured read flow; no fake callback count for current reads. Test that obsolete global-before-SELECT sequence fails the current contract, while old raw report remains immutable.
- [x] Run `python3 api/tests/run_isolated.py`; expected full backend PASS. Run `python3 -m unittest discover -s scripts/modernization/tests -p 'test_mod0*.py'`; expected all affected audit helpers PASS. Record actual counts; investigate every failure before claiming completion.

## Task 4 — Bounded native equivalence, locking and closeout

**Create:** `scripts/modernization/verify_mod020_scoped_lifecycle.py`, targeted helper tests, unique evidence and `docs/modernization/mod-020-scoped-lifecycle-implementation.md`.

- [x] Before product GREEN native claims, add/test independent assertions for exact sequence and untouched-ID detection. A reordered trace or unrelated touched row must fail. Reuse owned marked-server guards, UUID database cleanup and failure-aware artifact persistence. Persist RUNNING before provenance/setup; PASS only after exact cleanup verification. No arbitrary DSN argument.
- [x] Use100leagues/ten baseline groups (not all three large tiers); independent expected status/touched sets and full returned-field comparison. Compare dirty and converged detail/own-list flows to explicit global-policy reference on reset/separate fixtures. Cases: authorized detail, absent/denied/missing, commissioner detail without membership, own-list all/active/completed, empty reader and membership added after discovery. Every denied/empty flow has0UPDATEs; permitted phases affect only refreshed IDs; unrelated status/updatedAt unchanged. Assert full statement sequence, not counts alone. Include phase counts for scoped ended-season live churn without claiming it is fixed.
- [x] Add native timezone/date cases around season boundaries with complete/live/paused/missing draft states and null/missing season data. Pin transaction timestamp behavior under delayed locks; do not wait for a real midnight. Use controlled transaction-local time predicates/test fixture adaptation, recording the adaptation and separately verifying actual SQL uses PostgreSQL now(). Prove failed transition can be retried in a fresh transaction and yields expected status.
- [x] Orchestrate bounded two-connection interleavings with barriers, not sleeps: existing state start/pick/finalization while refresh waits, absent-state start commits while refresh waits for League, member removal while waiting, and join after candidate discovery. Use actual control/pick/member methods where fixture prerequisites permit; any narrower lock-protocol simulation must be explicit and not presented as full workflow coverage. Enforce timeouts. First-start race must exercise rollback/retry; no League→new-state lock acquisition. Add lock-timeout and restricted-role UPDATE failure cases; assert no committed partial transitions/read payload. Simulated role must belong only to disposable fixture and be dropped exactly; never change configured privileges.
- [x] Run native driver against the task-owned marked loopback PostgreSQL17.6 fixture only. Expected PASS for policy equivalence/full payloads/scoped touched IDs/sequence/rollback/retry/interleavings; zero owned databases/roles afterward. Record exact container labels/ID/loopback/mounts and remove exact owned container only. No production latency or scheduler claim.
- [x] Rerun full guarded backend and affected audit suites after any code fixes. Verify current hashes, historical artifacts unchanged and `git diff --check`. Write implementation report, callback signature inventory, explicit concurrency/set-boundary/remaining-churn limitations; update MOD020 status/roadmap without rewriting historical baseline.
- [x] One fresh final scoped review using executing-plans. Regrade by effect; material findings get one RED→GREEN fix pass/full impacted checks, no rereview. Record minors/declined areas and leave all changes uncommitted.

## Self-review and handoff

Spec coverage: Tasks1–3 own API/read separation and authorization; Task2 owns atomic scope/locks/retry/status preservation; Task4 owns native interleavings/sequence/touched IDs/evidence/release limits. Review Focus lines have explicit owning tests above. Supplied method/coordinator/conflict names match their consumers. No first-start conflict is conflated with a generic DB retry; no stage-filtered candidate bug; no unknown external-consumer promise. Only related subsystem changes are planned. No commits or scheduler rollout.

Execution method remains native inline with one final review. User reviewed and approved; implementation completed with evidence/rulings in the implementation report and owned ledger. Approved design remains the binding authority.
