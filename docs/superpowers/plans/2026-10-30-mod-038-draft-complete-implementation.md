# MOD-038 Remaining Draft Implementation Plan

> Use superpowers:executing-plans inline, test-first and one independent final review.

**Goal:** Finish draft content migration: live/trusted manual picks, timeout skip/auto-pick, shared cap/random policy and remaining lookups/composition.
**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md); user requested finishing draft.
**Architecture:** DraftPickService retains existing orchestration/helper dispatch and explicit actor/job entry points. Named pick repository queries own remaining SQL with supplied connection; existing result accessors retained for compatibility. DraftModel inherits service as SQL-free facade, preserving method/helper overrides and db-only construction. Worker calls trusted timeout service, listener uses snapshot service, socket uses membership+snapshot services.

## Constraints

- Current checkout and prior work preserved; uncommitted. No deployed/schema/dependency/frontend changes or process startup.
- Preserve live ownership precheck/INSERT predicate, turn/expiry/grace/cap policy, lock/atomic allocation/state advancement/finalization/error mapping and default weeks.
- Preserve disabled manual HTTP410, trusted manual allocation, conference buckets/random choice/caps/season membership/availability and current pg_notify placement. No realtime/publication redesign (MOD-023 separate).
- Preserve timeout no-ops, grace/expiry, skip rotation/unpicked holes/last-turn clock, auto-pick selection/finalization, retries/errors and current worker schedule/sleep. Native SQL defects fixed only after demonstrated RED regression.
- Move SQL byte-for-byte except necessary fixes; service keeps existing SQLAlchemy result access protocol/IntegrityError mapping. No generic execute API: repository methods are operation-specific.
- Legacy public/helper names and inherited dispatch remain; no new service imports of transport/model/configured engine. Root model imports service only. Canonical actor live call and named trusted paths, no HTTP bypass flags.

## Task 1: Remaining behavior extraction

- [x] RED direct-service tests actor/ownership/live allocation/rollback, trusted manual/notification, timeout no-ops and inherited helper compatibility.
- [x] Move model behavior into pick service and SQL into named repository methods; SQL-free inherited model facade; actor HTTP pick/round lookup and adapter mock wiring.
- [x] Full guarded backend and AST equivalence of query/algorithm dispatch with explicit transformation accounting.

## Task 2: Native completion

- [x] Native live/manual allocations/caps/expiry/final pick/actual unique failures/rollback and transactional notifications; timeout no-op/skip/holes/last-turn/auto-pick/availability/caps/rotation.
- [x] Observe competing picks/timeout serialization and post-query revocation; statement/deferred commit failures. Fix only demonstrated provider defects test-first.

## Task 3: Composition/review/evidence

- [x] Worker explicit timeout service and repository deadline query; listener/socket membership/snapshot service composition, existing startup/configuration untouched.
- [x] One independent final review, full native draft rerun, final backend/docs/hash/link/diff/import checks and owned-resource cleanup.

## Ledger

- Ruling: Preserve implementation/helper dispatch through inheritance rather than duplicating wrappers across all pick/auto helpers, matching completed scoring compatibility strategy.
- Ruling: Current notifications, manual HTTP deprecation, restart and post-check semantics remain; finishing architecture does not close correctness/realtime/startup backlog.

- Ruling: Keep ten existing SQL-free control/snapshot compatibility methods on DraftModel rather than making them pick-service responsibilities; inherit pick helpers and retain private shared-control bridges needed by allocation. Caller behavior and helper dispatch match original AST.
- RED/GREEN: baseline512/512; new direct-service cases failed6/6 for missing pick_service, then passed6/6. Final full guarded run518/518; reviewer independently518/518.
- Native RED/GREEN: expired timeout raised NoSuchColumnError for unquoted isExpired (PostgreSQL folds alias). Quote exposed original SyntaxError at :leagueId::bigint; use CAST(:leagueId AS bigint), CAST(:cur AS bigint), CAST(:last AS bigint). Same probe GREEN with expected member rotation; no policy change.
- Ruling: Native alias/bind corrections are necessary execution fixes, demonstrated before changes; all other38 query text ASTs unchanged. Source-preserving policy comparison:34 legacy method ASTs unchanged after intentional query/notification substitutions. Constructor/repository injection and four explicit interactive/job APIs are additions.
- Native PASS: all40 repository operations required/exercised; live/manual/timeout/caps/buckets/finalization/revocation/statement/deferred-commit rollback, native pg_notify barrier/commit-only behavior, real competing pick/timeout lock wait and actual deadline helper. Previous snapshot/finalization/controls/order rerun. No configured DB/process imports, hosted connection, worker/listener startup or application schema change.
- Ruling: Notification listener verification uses an owned psycopg2 LISTEN connection plus SELECT barrier to drain committed notifications; no production listener is started. Synthetic fixture corrected NOT NULL identity setup and non-row write-result handling during harness development, with no application change.
- Independent final review: /root/draft_complete_review; no Critical/Important/Minor findings; fresh518/518 guarded suite, compatibility/policy/query/transaction/composition review. No implementation delegation.
- Final: current evidence supersedes prior draft hashes; all six completed-domain hash reports checked; docs/internal links/diff/import boundaries verified. Owned temporary DB removed by harness and named container stopped. Current checkout remains uncommitted, no push/merge/deploy. Broader MOD-040 and MOD-023/025/034 remain open.
- Final formatting check removed one extra EOF blank line from the facade. AST identity verified; native evidence retains pre-normalization hash and normalized source hash explicitly. No executable change after final native run.
