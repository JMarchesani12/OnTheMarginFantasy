# Transaction boundaries

`TransactionService` / `TransactionRepository` retain the original checked listing and trusted trade-apply pilot. `TransactionWorkflowService` / `TransactionWorkflowRepository` own remaining trade actions, free-agent planning/application/dispatch, personalized open reads, roster validation and the historical week-lock helper. Workflows compose the pilot; neither service imports a legacy model, Flask or configured engine. Named repository operations use supplied connections and own fixed role/reader SQL predicates plus shared entitlement-query routing.

HTTP constructs UserActor from the resolved principal and calls propose/respond/cancel/veto/free_agency/open_trades; listing uses the original actor service. Caller JSON cannot select trusted mode or SQL scope. Job operations have explicit for_job names; weekly cron calls apply_pending_for_job. HTTP trade application stays410. Week locking remains unregistered; its historical helper now uses a service-owned connection instead of the original undefined self.db. Validation and update keep their original separate scopes; no new lock/atomicity policy.

The former TransactionModel facade is retired. Tests and tools use TransactionWorkflowService directly, including its constants, SwapLimitExceeded exception and helper override hooks. The initial TransactionService listing/trusted-apply capability remains separately composed.

Preserve original role/status/deadline checks, pre/post ownership checks, row locks and query-time read predicates. Free-agent apply still uses a separate week lookup and original apply-time validation behavior; dispatcher preflight then application/re-lock remains. Caps/membership joins/swap counting, JSON/array/executemany semantics, reject-before-deadline distinction and revocation boundaries are unchanged. This extraction does not add stronger replay/revocation/atomic snapshot or correctness guarantees.

[Complete native evidence](../../../docs/modernization/evidence/mod-038-transaction-complete-postgres-2026-11-02.json) covers all33 workflow operations and reruns original trade/read pilots, including native arrays/JSONB/LATERAL/executemany, rollback, late revocation and observed row-lock contention. [Ledger](../../../docs/superpowers/plans/2026-10-30-mod-038-transaction-complete-implementation.md). Original pilot report is historical; complete report supersedes its source capture.

## MOD-013 current weekly integration — 2026-11-05

The extraction behavior above is historical. Trade/free-agent application and
pending dispatch now accept an optional supplied `conn`; that path never acquires
or commits a separate connection. Trade actions acquire the existing v1 ownership
mutex before their transaction row lock. Weekly eligibility/order and completion
are owned by `WeeklyCompletionService`; the trusted per-command application ports
retain their existing validation/replay/deadline contracts. They are not a substitute
for weekly eligibility checks. See [operations](../../README.md#weekly-completion-and-retry-mod-013).
