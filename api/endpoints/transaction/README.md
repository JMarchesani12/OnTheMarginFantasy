# Transactions

TransactionService/TransactionRepository provide checked listing and trusted trade application. TransactionWorkflowService/TransactionWorkflowRepository own proposals, responses, cancellation/veto, free-agent changes, personalized reads and pending dispatch. Repositories receive connections and fixed role/scope predicates; HTTP resolves UserActor before calling a workflow. Request JSON cannot select trusted mode or SQL scope.

Trusted operations have explicit for_job names. Trade/free-agent application and pending dispatch accept a supplied conn; this path neither acquires nor commits a separate connection. Mutations take the shared ownership mutex before transaction row locks. WeeklyCompletionService determines pending eligibility/order and retry; application ports preserve their validation/replay/deadline checks. Direct HTTP trade application remains disabled, and the historical week-lock helper is not registered as a route.

Locked-current-week proposals target the next eligible unlocked week; accepting queues future application rather than rewriting the current roster. Conference membership uses the league season first; invalid exact-season mappings or unmapped/cross-sport teams reject before ownership mutation. Cap0 means no teams; missing/negative caps are configuration errors.

Shared ownership reads use explicit league/week/member context on the caller's connection. Draft DISTINCT-team counts and free-agent active-row counts differ intentionally. Checked apply_trade and the internal transfer helper have distinct contracts. See [domain rules](../../../docs/domain-rules.md) and [weekly operations](../../../docs/operations.md).
