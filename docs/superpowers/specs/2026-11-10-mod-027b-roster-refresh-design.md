# MOD-027B: coordinated roster and transaction refresh

## Intent and chosen scope

Make successful roster mutations visible in related resources without leaving the page or remounting forms. The user selected a roster-page-owned refresh signal covering successful add/drop, proposal, accept/reject, cancellation and veto/unveto. Preserve backend timing: a successful request or acceptance does not itself establish applied ownership.

## Approaches

Chosen: a page-owned monotonic refresh revision and guarded success callback, consumed by existing resource loaders/panels. This fits the existing request scopes and lets each resource report its own failure. Remounting children would reset panel tabs/forms. A shared query/cache library adds infrastructure beyond this card. The builder may choose a small local hook if it makes the coordinator clearer; no generic cache or event bus.

## Existing boundaries

LeagueRosterPage owns member roster, availability, selected partner roster and forms; TradeRequestsPanel owns open trades/actions; PendingTransactionsPanel owns pending items. Currently parent submissions reload roster only, while trade-panel mutations reload that panel only. Reuse existing authenticated APIs and MOD-029 league/account/week guards. Preserve current effective-week/cutoff calculation and payloads, PENDING_APPLY filtering, deadlines and backend authorization. No backend/schema/API transport changes.

## Refresh contract

After a confirmed successful mutation in the current context, issue one coordinator invalidation. Reload own roster and availability, selected partner roster if present, open trades if mounted, and pending transactions. Do not reload unrelated league metadata/member lists. A conditional panel that is not mounted fetches current data when opened; invalidation must not force it open or remount it. Preserve active tabs, partner choice, search/conference filters and unrelated form drafts.

Use one refresh path for all named successful actions. Child actions notify the parent instead of doing a duplicate self-reload plus parent-triggered self-reload. Manual resource Refresh remains supported. An explicit page refresh/retry may reuse coordinator invalidation. A mounted resource gets one refresh per revision; later revisions supersede/abort obsolete reads using existing channels. No polling, automatic write retry or mutation replay.

Resource state and completion checks must bind to league/account context, effective week where relevant, selected partner, and the latest refresh attempt. Invalidate old actionable roster/partner readiness when a mutation triggers refresh, including before fresh effects deliver data. Keep mutation actions disabled while their required resource is unresolved or failed; stale ownership must not authorize another command. Resource feedback can retain display hints only if clearly nonactionable; builder default is to show loading instead of old actionable teams. A failed refresh leaves that resource unready, shows a visible error and offers a read-only retry. Partial successes remain usable where their dependencies are ready; one failed panel must not discard another panel's successful response.

League/account/navigation/unmount or cutoff changes invalidate old reads and success callbacks. An old mutation completion must not refresh a new account/league/week. For selected-partner changes within the same context, a confirmed command can refresh the current resources, but must not clear a newer partner's selections or replace its roster with the old partner's result. Preserve current MOD-029 protections; test source-to-render cutoff checks rather than relying solely on an effect cleanup.

## Write outcomes and form behavior

Only successful mutation responses trigger invalidation. Failed writes retain the submitted selection and existing form error behavior, with no success invalidation. On success, clear only the still-matching submitted selection; preserve a newer draft or new partner selection. Reconcile retained selections against fresh applicable roster data. Do not optimistically move teams, consume a mutation response's projected memberRosterTeamIds as current ownership, or infer application from a pending status. Fresh week-based owned/available/partner reads remain authoritative. Pending items and open proposals update from their corresponding reads.

A write success followed by a read failure is still a successful write. Show a bounded status such as “Request submitted. Refreshing related data…” and resource-specific refresh failure/Retry as appropriate; never report it as a failed write or encourage resubmission. Keep read failures out of the mutation's write-error branch. Retry refreshes reads only. Successful accept/reject/cancel/veto can use action-appropriate success wording without implying teams moved. The builder owns precise concise copy and minimal existing-style presentation, including status/alert semantics.

## Verification

Tests must execute actual page and child panels with controlled transport, exercising their integration rather than only asserting callback props. Verify proposal becomes visible in outgoing trades without a remount; pending add/drop and pending acceptance appear in pending transactions; PENDING_APPLY acceptance does not transfer displayed ownership; authoritative changed reads can update ownership when actually applied. All successful response/cancel/veto paths invalidate sibling resources; failed writes preserve selection and do not invalidate.

Cover read failure after confirmed write, visible read-only retry without a second mutation, independently successful resources, retained tabs/partner/filter state, obsolete initial reads versus refresh reads, overlapping refresh revisions, partner changes during mutations, context/account changes, unmount and week-cutoff changes. Keep prior MOD-029 scope/cutoff and MOD-026/027A tests intact. Use existing controlled hook/module harness; real React/browser scheduling remains explicitly unverified unless practical installed tooling is available. No dependency installation or live service/database execution is required.

Run the complete frontend tests, production build, import graph and diff checks. Obtain one fresh final code review, reproduce/fix material findings with RED→GREEN and a green full suite, and record exact evidence, hashes, rulings and runtime limits. Leave previous MOD-027A work intact and all changes uncommitted/undeployed. Mark only MOD-027B complete in the audit once its verified scope is satisfied. Remaining feedback/accessibility/performance/cleanup cards retain separate scope.
