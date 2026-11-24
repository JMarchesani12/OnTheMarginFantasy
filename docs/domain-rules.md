# API and league behavior

## Identity and requests

HTTP adapters resolve verified principals into explicit actors; caller-supplied user/member IDs do not establish authority. Services own authorization and transaction policy; repositories use supplied connections and named SQL. Trusted job operations are explicit for_job ports, never a request-controlled mode. Disabled manual-pick, week-generation and trade-application HTTP writes remain disabled.

Application profiles are read/provisioned through the authenticated API. CurrentUserProvider owns that work; AuthProvider manages sessions. A linked Supabase UUID identifies at most one application User; legacy null UUIDs remain allowed. Foreign-profile reads/updates are denied, and profile setup verifies returned identity. Account/credential changes invalidate old actionable state and stale responses.

Responses use safe error messages and request IDs. Browser API helpers suppress arbitrary server/network text and preserve cancellation/outcome semantics. Request validation bounds supported integer/list inputs and rejects malformed shapes before domain mutation. Do not use raw exception/SQL/provider text as user-facing messages.

## League membership and initialization

numPlayers is the current member count, not a maximum capacity. Admission approves membership atomically under the league/admission locks. There is no hard league-size limit. Pre-draft rounds use actual membership and season-specific conference capacity: `min(sport.maxDraftRounds, floor(sum(min(conference team count, owner count * conference cap)) / owner count))`. Creation and pre-draft membership changes recalculate capacity; live/completed drafts are never resized. Starting requires at least one full round.

League creation and initial weeks/rules/draft state use one transaction. Existing initialized week plans return canonical rows rather than rewriting history. Week numbers are unique within a league; member scores are unique per league/week/member and reference members/weeks in that same league.

## Ownership, conferences and caps

LeagueTeamSlot uses half-open week intervals: acquiredWeek is included, droppedWeek is excluded. Adjacent and permitted empty intervals are valid; overlapping ownership for a league/team is excluded. Ownership points to a member of the same league. Mutating workflows use the shared ownership mutex and their domain row locks; supplied-connection paths must not acquire/commit a detached transaction.

Conference membership resolves the league's season first, falling back to the default only when that team has no seasonal row. Invalid seasonal mappings must not silently fall back. Draft/transaction teams need a valid same-sport conference mapping; there is no uncapped Independent bucket. Conference cap 0 allows no teams, positive values impose that limit, and missing/negative values are configuration errors.

Shared ownership reads use the caller's connection and explicit league/week context. Services retain authorization, cap policy, locking and write timing; draft DISTINCT-team and free-agent active-row counts have distinct semantics.

## Drafts and transactions

Draft controls, ordering, picks and snapshot reads have separate services/repositories. Draft order validates membership/permutation; start/control transitions serialize on league/draft state. Allocation, ownership and state transitions share a transaction. Conferences are optional within their per-owner caps; legal picks are not reserved to protect future roster completion. Owners with no legal picks lose remaining turns and may finish with smaller rosters. Exhaustion skips do not create fake picks or ownership records. The timeout worker also detects stuck live turns without waiting for an expired clock, validates caps before advancing, and polls at a 30-second bound. Socket connect/join/delivery recheck session/current membership; removed members or expired credentials must not receive private snapshots. See [draft boundaries](../api/endpoints/draft/README.md).

A trade proposed while the current week is locked targets the next eligible unlocked week. Proposal/acceptance do not rewrite the locked current-week roster; pending accepted changes are applied by the weekly workflow at their eligible boundary. Deadlines, caps, ownership and future-period availability can still reject a trade. See [transaction boundaries](../api/endpoints/transaction/README.md).

## Weekly completion and finalization

Weekly completion closes eligible weeks and retries eligible pending work even when no new week needs scoring. Pending changes apply once their assigned week's preceding week has successfully closed. Failed work remains retryable rather than being silently marked complete. Stored weekly score replacement locks its scoped Week and writes the replacement atomically.

Each sport-season finalizes atomically only after all league weeks are closed, pending changes resolved, memberships present and standings valid. Numeric totals must be finite and member coverage exact. A failed/blocked season remains retryable while other seasons proceed. Finalization marks league/season completion; it does not rewrite score/ownership history. Its command considers all eligible ended seasons, not a caller-supplied single season. See [operations](operations.md).

## Calendars and game references

Season metadata changes do not automatically rewrite existing league calendars. Calendar repair previews changes by default and only applies to eligible unused Pre-Draft leagues. Draft, ownership, transaction, stored-score, locked-period or finalized-season history blocks mutation. Kept week IDs are retained; referenced periods are not silently removed. Historical remapping requires separate policy.

Season/game/conference references must agree on sport and phase/season scope. Unknown external game participants and optional phase may remain null; existing parent delete behavior is preserved. Scoring retains pinned league rules, season-specific conferences and tournament phase classification. [Season setup](../api/startSeasonJobs/README.md) documents bootstrap, period generation and postseason configuration.
