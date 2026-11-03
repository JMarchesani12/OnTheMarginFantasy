# MOD-038 Remaining Transaction Completion Plan

> Execute inline with superpowers:executing-plans, test first and one fresh final review.

**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md); user explicitly authorized migrating the rest after corrected transaction inventory. Current checkout, preserve prior work; uncommitted/no deploy.

## Task 1 — Workflow extraction

- [x] Baseline557; direct verified-actor/job/helper/failure tests RED→GREEN.
- [x] Move remaining model behavior into TransactionWorkflowService with stateless lazy workflow repository; existing TransactionService/Repository pilot stays unchanged. Keep exact facade constructor, constants/exception/helper dispatch and defaults. Move31 original queries, all role/reader SQL fragments and shared ownership query routing to repository. No generic execute/CRUD API.
- [x] Actor APIs before I/O for propose/respond/cancel/veto/free agency/open trades; explicit trusted counterparts and pending/free-agent dispatch/application/roster capabilities. Preserve pre/post ownership, scoped row locks, role predicates, JSON/arrays, original helper connections and failure semantics.

## Task 2 — Adapters/jobs

- [x] HTTP actions call actor workflow, listing retains pilot; disabled apply410 unchanged. Weekly cron uses explicit pending job operation. No configured app/job/provider startup.
- [x] Remove unregistered week-lock helper SQL from transport; preserve its absence from routes. Demonstrate original undefined self.db failure before minimal connection-owner correction; service preserves separate validation/write scopes and original DTO/errors.

## Task 3 — Verification/audit

- [x] Native all original/new query families: proposal/accept/reject/cancel/veto toggle/threshold, free-agent pending/locked-week/duplicate/caps/swap/deadline/dispatch/application/replay, open personalized JSON/LATERAL read scopes, roster violations/lock, real arrays/JSONB/executemany and rollback/revocation/concurrency. Rerun old pilot and affected scoring integration.
- [x] All guarded tests, fresh final review, original algorithm/query AST proof and no facade SQL across eight domains; source audit/complete native evidence/docs/hash/link/diff checks and owned-resource cleanup.

## Ledger / constraints

- Preserve free-agent apply's separate week lookup and missing cap/deadline revalidation, dispatcher preflight/re-lock behavior, reject-before-deadline distinction, actor postchecks/no stronger revocation guarantee, projection fields and status values. This is architecture completion, not new correctness/auth/rate-limit/schema/timeout policy.
- Fixed server-side roles become repository SQL scope predicates; service retains pure role validation and ownership policy. Reader scope is selected from server-built reader params, never a caller-controlled SQL fragment.
- Legacy exception is inherited by the facade so public TransactionModel.SwapLimitExceeded and workflow catches share identity. Legacy injected helper overrides remain dispatchable.

- Baseline557/557. New7 cases RED for missing workflow plus original legacy lock helper undefined self.db; GREEN7/7 and full564/564. Existing backend tests unchanged.
- Extracted31 query calls, SQL role/reader fragments and entitlement routing; exact SQL text ASTs/fixed role mapping retained. All33 original method ASTs match after named-query/entitlement/pure-role substitutions, constructor exact. Model/HTTP adapter SQL-free; canonical imports independent of model/HTTP/configured engine.
- Legacy exception is inherited consistently; exact identity checked. Actor APIs require UserActor (which already validates integer IDs/nonempty subject) before I/O; no duplicated actor validation policy.
- Unregistered lock helper correction is the only application bugfix: watched self.db AttributeError before moving original update to service-owned connection, with original validation/write scope and route absence retained.
- Native PASS33/33 workflow operations, actual arrays/JSONB/LATERAL/executemany, role/ownership/status/deadline/swap/cap/pending/roster/effective week, mutation/actual statement/deferred rollback, postwrite/query-time revocation and real observed cancellation lock/replay behavior. Original pilot concurrency/checked reads rerun PASS. Complete schedule/scoring integration reruns PASS; changed weekly-job source captures refreshed.
- Independent fresh review /root/transaction_complete_final_review: no Critical/Important/Minor findings; fresh full guarded suite and source AST comparison, no implementation delegation. No application edits after review.
- Final audit confirms8/8 model facades without SQL; previous partial transaction inventory retained as resolved history. Eight complete domain reports/source hashes plus audit/internal links/diff verified. Legacy facades retained, owned DB/container removed, current checkout uncommitted/no deployment or hosted/schema/dependency/startup work. Planned backend domain extraction complete; broader frontend/optional layout/correctness/startup remains separate.
