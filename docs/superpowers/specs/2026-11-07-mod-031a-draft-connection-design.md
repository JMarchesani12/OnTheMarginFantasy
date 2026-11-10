# MOD-031A stage 2 — Draft connection hook extraction

## Intent and approach

Continue the user-requested remaining Priority7 work after the separately reviewed
clock stage. Extract current page socket/controller wiring into a local
front-end/src/hooks/useDraftConnection.ts, reusing createDraftRealtime unchanged.
Do not build another controller, event protocol, cache or auth policy. This stage
completes MOD031A's remaining connection ownership boundary when verified.

## Boundary

The hook owns the current socket creation, latest snapshot callback ref, controller
ref, effect setup/cleanup and member-metadata refresh effect. Page inputs explicitly
supply leagueId, token, endpoint, account/route scope key, memberId, authoritative
snapshot loader and snapshot/clear/readiness/error/loading callbacks. The page
keeps its current league resolution, member identity, state application, settings,
UI/commands, storage/available-team handling and clock hook.

Return the actual mutable controller ref (DraftRealtime|null). Commands keep
capturing its current controller identity before awaiting work and comparing it
afterward; do not replace it with an always-stable controller facade that defeats
old-generation guards. Manual join/refresh forwards to the same controller.

Keep one settled subscription for league/token/endpoint/scope generation. Register
before connect via unchanged controller logic, rejoin on every connect, serialize
HTTP refreshes and ignore pushed snapshots as signals. Latest snapshot callbacks
must not recreate subscriptions. Preserve clear-before-start/invalid-scope behavior
and cleanup's dispose plus identity-checked ref clearing. Preserve memberId-triggered
refresh without recreating the socket, including initial metadata arrival. No
new reset, replay, join/read retry, readiness or delivery guarantee.

Keep snapshot reads in an explicit parent loader: getDraftState then getAvailableTeams
with the same AbortSignal, returning their existing merged shape and propagating
errors/status. The hook invokes that capability for its captured league. It must
not silently swallow errors, introduce request dedup/caching, mutate auth refresh
or request origins, or reapply command/pushed payloads to state. Stable callback
or latest-ref wiring may be chosen to prevent callback identity churn; epoch inputs
remain the authority for scope disposal. Hook invocation stays unconditional and
before the missing-league return.

## Verification and delivery

Use the existing real-controller controlled-I/O tests and current actual-page
lifecycle/clock tests; add real-hook integration for stable callback updates,
member-only refresh, token/league/account/endpoint change cleanup, missing token,
one-controller ownership and captured old-command identity. Verify original event/
request shapes, composed read failure propagation, denied/private-view clearing,
reconnect/abort/late response invariants and timer independence remain covered.
Tests execute the production hook and controller with controlled dependencies,
not a copied subscription algorithm. No browser DOM/E2E claim unless run.

Full frontend tests, TypeScript/build and source import graph must pass; retain
clock-stage evidence and compare current page against a captured stage2 baseline.
No backend/native/configured runtime/provider, schema/dependency/deploy/commit/push.
Fresh independent stage review, source-hashed evidence and MOD031A completion status.
Then audit MOD032's already completed schedule decomposition and scope MOD029/MOD033
against their existing dependencies; do not infer all Priority7 complete from this
single hook extraction.
