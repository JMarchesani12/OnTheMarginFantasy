# MOD-029: fresh league context for Detail and Roster

## Intent and agreed policy

Consolidate league resolution in Detail and Roster while preventing an old URL, navigation seed, or account from supplying actionable membership. The user chose fresh matching context before actions: URL/account changes invalidate the old context, and navigation state is at most a display hint. This is a paired-screen project, delivered in separately verified extraction and freshness stages.

## Approaches

The confirmed approach is a local `useLeagueContext` shared by these two screens, with fresh account/route matching before actions. Keeping navigation state authoritative would preserve Roster's skipped lookup but violates the chosen policy. A global cache and all-screen migration would broaden ownership and require a separate invalidation contract; defer them. No performance reduction is promised.

## Existing behavior and boundaries

Detail always lists the current user's leagues and falls back to the single-league read only after a successful list has no match. Roster skips resolution when seeded. Both already use the shared league mapper. Their resource effects and mutation completions can outlive navigation. CurrentUserProvider can also publish a delayed profile lookup for the previous authenticated subject.

Keep the existing endpoints, authorization, mapper defaults, week calculations, transaction payloads, confirmations, and API transport refresh policy. Convert no other league screen. Do not add caching, provisioning, schema changes, automatic mutation replay, or deployment. The provider change is only the MOD-026 identity-transition prerequisite, not completion of MOD-026.

## Identity prerequisite

Bind the exposed numeric profile ID and associated profile fields to the authenticated subject that resolved them. During auth loading, subject changes, logout, unresolved lookups, and failed lookups, withhold an actionable profile ID. Guard asynchronous success, error, and loading completion against obsolete requests and unmount, including overlapping refreshes. Retain the existing Supabase UUID lookup and refresh interface. Never infer identity from navigation state, email, or request bodies. Test delayed A after B, logout, failed/empty lookup, and same-subject refresh ordering.

## Shared resolution and freshness

The route supplies the league ID; accept only a positive safe integer. Resolve only after auth and the subject-bound internal profile are ready. Key each resolution by route league ID, authenticated subject, numeric profile ID, and refresh generation. Return explicit loading/error/ready state and mapped league data; fresh membership provenance must remain distinguishable from read-only fallback data.

Use the existing list/find/fallback order. Failed list requests must not trigger fallback. A fallback response never creates membership merely because the mapper supplies memberId zero or a navigation seed supplies an ID. Validate the returned league ID before publishing. Keep server denial/error behavior; no client grant based on commissioner labels. Reject obsolete results and expose no previous actionable context even in the render before effect cleanup.

Builder call: ignore navigation seeds in this pilot rather than display unverified account-specific metadata. Both cold and seeded entries show the existing loading treatment until resolution. This is permitted by the user's optional-hint policy.

## Screen resources and commands

Keep screen-specific forms and domain logic local. A keyed ready-context child is an acceptable implementation boundary: route/account/generation changes must immediately remove the former actionable subtree and clear its teams, members, scores, errors, selections, and pending UI state. Keep loading/error rendering outside that boundary. Use read cancellation where supported and generation/disposal guards everywhere needed; cancellation alone is insufficient.

Roster team reads remain parallel, member and partner reads retain existing semantics, and scoreboard batching/week defaults remain unchanged. Within a ready context, obsolete partner/week/refresh reads cannot overwrite newer results or selections. Requests must use captured matching context, never mixtures of old member IDs and new league IDs.

Before team-name, leave, add/drop, trade, and nested transaction actions, require current ready context and valid fresh membership. Preserve existing role/status rules. Capture the operation scope; after awaiting, ignore success, failure, finally updates, navigation, and reload callbacks if that scope is obsolete. A submitted mutation may still commit on the server; do not claim abort rolls it back or retry it automatically. Audit TradeRequestsPanel and PendingTransactionsPanel callbacks so removing a ready subtree prevents their old completions from acting on the new screen.

Builder call: preserve the existing league-scoped active-tab preference (`rosterTab:<leagueId>`), because it conveys no membership or selected team. Reinitialize it for the destination league on remount without writing the previous league's tab into the destination. Do not persist actionable team/partner selections across context changes.

## Staging and evidence

1. Characterize current list/fallback request counts and mapper outcomes for the paired screens. Extract the common resolution boundary without claiming the freshness behavior is a mechanical refactor.
2. Implement and verify the narrow subject-binding prerequisite separately.
3. Apply the approved freshness policy through the shared hook and scoped screen resources/commands. Record these as intentional behavior changes, including the additional fresh lookup on seeded Roster entry.

Keep one MOD-029 pilot scope, with stage-specific evidence. Additional screen migrations, broad profile ownership, or shared caching require follow-up scope; do not silently expand this project.

## Verification and completion criteria

Use isolated tests exercising actual provider, hook, and page code with controlled auth, transport, deferred responses, and routing. Cover cold/seeded entry, member/read-only fallback, malformed route, mismatched response, denial/error, missing profile, rapid route/account/logout changes, delayed old resource results, overlapping partner/roster refresh, and mutations completing after scope replacement. Assert requests and disabled/absent actions, not just helper outputs. Verify unchanged payload/week/form defaults and tab restoration.

Measure before/after list, fallback, and dependent read counts; distinguish intentional freshness cost from accidental duplication. Run the frontend suite, production build, source import verifier, and diff checks. Obtain a fresh final review. Document any browser/real-session coverage limits rather than claiming simulated tests prove browser scheduling. Leave changes uncommitted and undeployed, consistent with the established audit workflow.
