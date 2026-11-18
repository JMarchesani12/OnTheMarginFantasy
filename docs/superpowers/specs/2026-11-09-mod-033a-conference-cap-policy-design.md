# MOD-033A: resolve conference-cap policy before ownership extraction

## Intent and decision

The user chose to resolve cap defaults before the MOD-033 ownership/count extraction. Their confirmed policy for draft, auto-pick, free agency and trades is:

- `0` allows no teams from that conference.
- Positive values set the maximum teams per owner.
- Negative or missing values are configuration errors.

This is a bounded correctness prerequisite, MOD-033A. The subsequent shared ownership/count read pilot remains MOD-033 and is not implemented in this stage. Cap changes must be explicit behavior fixes rather than hidden inside a mechanical extraction.

## Approaches

Preserving workflow-specific semantics during the read pilot was proposed; the user instead selected resolving defaults first. For the policy itself, zero-as-unlimited was considered; the user chose zero-as-no-teams, matching current transaction tests. Implement one small shared cap validator and apply it at existing decision boundaries. A broad universal ownership validator or a schema migration is unnecessary for this correction.

## Current implementation

`DraftPickService._assert_member_can_add_team_conference_cap` returns early for caps <=0, allowing live/manual acquisitions. Auto-pick compares owned>=cap, so zero blocks a bucket and negative values also silently block it. Free-agent submission/application and trade validation compare post-change counts to caps and already block zero; conversion/comparison failures for missing values are inconsistent. `TransactionService.validate_trade_in_transaction` also uses an implicit missing-limit default of 999.

Roster violation reporting filters in SQL with `HAVING count > cap`; NULL caps or missing joined configuration can disappear instead of being reported as configuration errors. The schema baseline makes the field NOT NULL but supplies neither a default nor a nonnegative CHECK. No configured database contents have been inspected or changed for this task.

## Goals, boundaries and non-goals

Make cap interpretation consistent wherever an acquisition or roster-cap report uses it. Preserve positive-cap eligibility, season-first conference membership with current-row fallback only when appropriate, and fail-closed mapping behavior. All teams require a valid drafting conference; do not reintroduce an independent/uncapped team bucket.

Keep actor authorization, ownership mutex and row-lock order, caller-owned connections/transactions, deadlines, veto policy, pending-work retry behavior, acquisition weeks, half-open ownership history, and success payloads unchanged. Do not automatically remove existing teams, repair cap data, introduce an unlimited sentinel, or change conference selection randomness. Do not consolidate ownership SQL or remove alternate trade helpers in this stage. No schema/provider/job/deployment execution against configured services.

## Shared policy boundary

Add a focused pure cap-validation function in an appropriate existing domain utility or a small new `api/utils/conference_caps.py` module. It receives a stored cap and useful conference context, returns a nonnegative integer, and raises a clear `ValueError` for missing/negative/invalid configuration. Do not truncate fractional values or accept booleans as limits. The database column is integer; supporting arbitrary textual input formats is not a new API requirement. The builder may settle the exact name and message without changing existing ordinary cap-exceeded messages.

There is no default cap: remove the transaction fallback of 999 when an involved conference lacks a limit. Validate only conference configuration relevant to the operation or represented active roster, not unrelated sports/conferences globally. Keep ordinary cap rejection distinct from invalid configuration.

## Consumer behavior

### Draft and timeout auto-pick

Live/manual allocation must reject an acquisition at zero before inserting picks/slots or advancing state; the nonpositive-unlimited branch goes away. Positive-cap checks retain their present count semantics and error text. Missing mapping remains a configuration error.

Auto-pick skips a valid zero-cap bucket, just as it skips a full positive-cap bucket, and may choose a legal team elsewhere. If every valid bucket is zero/full/unavailable, retain the established no-eligible-team timeout behavior. An encountered invalid negative/missing cap is a configuration error, not an ordinary empty bucket and not permission to auto-skip/advance. A failure rolls back the owned transaction. Do not proactively inspect unrelated buckets merely to validate global configuration.

### Free agency and trades

Validate caps before comparisons in submission/proposal and queued application. Preserve simulation of drops before additions and application-time revalidation against actual ownership. Positive limits remain inclusive: a final count equal to the cap is allowed; greater is rejected. Zero blocks additions into that conference in every path.

Existing teams are not evicted when a cap becomes zero or lower than an existing roster. Drop-only work and transfers out can continue to reduce an otherwise over-cap roster under existing rules when configuration is valid; do not require retroactive roster compliance just to reduce it. Negative/missing configuration encountered by the operation fails explicitly; do not reinterpret it as a remediation exception. Submitted/queued work rejected by this validation must not be marked complete or partially rewrite history.

Retain existing public/legacy exception translation for ordinary cap violations. Invalid configuration should fail closed through existing domain/HTTP/job error boundaries with a useful configuration message. Do not add response fields, statuses, or a new transport error framework.

### Roster-cap reporting

A valid zero cap with active owned teams is an ordinary over-cap violation; an empty roster is not. Validate relevant configured caps before filtering counts. Negative/missing caps must yield a configuration failure rather than an ordinary negative-limit overage or a silently omitted row. Missing effective membership/configuration for an active roster team must not vanish through an inner join. The builder may use existing mapping checks or a bounded repository query adjustment; retain the public violation-list shape and valid positive-cap results.

## Verification and evidence

Characterize existing positive-cap/full-cap/history behavior before edits. Test the shared policy matrix (zero, positive, negative, missing and invalid typed values), then actual service paths with controlled repositories or the existing synthetic SQL fixture adapters. Cover live/manual zero rejection with unchanged state; auto zero bucket fallback and all-zero exhaustion; invalid auto configuration rollback; free-agent proposal and queued application; trade proposal/acceptance/application; reporting zero/invalid/missing mapping. Include equal-to-cap acceptance, over-cap rejection, drop-before-add, drop-only reduction and end-exclusive history. Assert supplied connections are reused and lock ordering/rollback behavior stays intact.

Use the full credential-free backend suite and source/import checks; run relevant synthetic PostgreSQL checks if SQL/reporting changes need native evidence and a marked local harness is available. Do not substitute live database inspection for tests or claim native coverage from SQLite. Record what was run, test counts, source hashes and any unavailable native/browser/provider evidence. Obtain a fresh final review, fix material findings with reproducing tests, and leave changes uncommitted/undeployed in the established audit workspace.

## Completion and follow-up

MOD-033A completes when the policy matrix agrees across these consumers and normal positive-cap contracts remain green. Update the backlog/evidence to distinguish this correctness prerequisite from the pending MOD-033 read extraction. No new database constraint is required for application-level consistency; any future schema guard needs its own data preflight and rollout decision.
