# MOD-031A stage 1 — Draft clock hook extraction

## Intent and approach

User requested continuing through remaining Priority7 work, starting with MOD031A.
First extract the clock only; the connection wrapper is the second separately
reviewed stage. Existing MOD023 realtime controller behavior is retained. Preserve
all uncommitted MOD039/MOD030/MOD031B pilots.

Use a focused local useDraftClock hook in front-end/src/hooks/useDraftClock.ts.
A helper that extracts only arithmetic would leave timer/server-offset ownership
in the screen, so it does not meet this stage's purpose. A rewrite of countdown
or realtime ordering would change behavior and is excluded.

## Clock contract

Move existing nowMs initializer, clockOffsetMs state, live-only1000ms interval and
cleanup, remaining-seconds calculation and m:ss formatting into the hook.
Input: isLive:boolean and expiresAt:string|null. Output: remainingSeconds:number|null,
timeLeftLabel:string|null and a stable updateServerNow(serverNow?:string) callback.
The page retains its existing expiresAt/status interpretation and calls the offset
callback when applying authoritative snapshots.

Preserve exact behavior:
- Initial nowMs samples Date.now once for the mounted hook; offset starts0.
- Truthy valid serverNow sets offset=Date.parse(serverNow)-Date.now at snapshot
  application time. Missing/invalid serverNow leaves the prior offset unchanged.
- Offset updates do not eagerly resample nowMs or restart the interval.
- Only live drafts have one settled interval. Pause/complete/unmount cleans it up;
  restart/resume creates one interval. Changing expiry/offset alone does not.
- Null/empty/invalid expiry returns null label/count. Otherwise use
  max(0,floor((parsedExpiry-(nowMs+offset))/1000)); format minutes:two-digit-seconds.
- No new reset on league/token changes, server clock ordering/revision, deadline
  validity/range, immediate-tick, visibility, hidden-tab or timezone policy.

Replace only those page responsibilities with hook input/output wiring. Keep
snapshot/state/pick application, UI, selection persistence, status/modal handling,
request/command callbacks and MOD023 controller unchanged. Keep hook invocation
unconditional and before the screen's missing-league return. A stable offset
callback must not recreate the socket/controller effect.

## Verification and completion

Characterize actual existing page clock arithmetic, offset application and interval
behavior with controlled Date/timers before extraction. Cover live/pause/resume/
complete/unmount, one interval/no duplicate on snapshot or expiry change, offset
updates, invalid/missing values, zero clamp, m:ss boundaries and frozen non-live
clock samples. Tests execute actual production code with controlled React/timers,
not a copied arithmetic algorithm. After extraction exercise the real hook and
page wiring, including offset callbacks and realtime subscription stability.

Run full frontend tests, TypeScript/production build and import graph; preserve
current MOD023 tests. No browser timing/E2E, backend/native/configured runtime/
provider/deployment/commit/push. Fresh independent stage review and source-hashed
evidence. This stage alone does not complete MOD031A: next extract a useDraftConnection
wrapper around the current page wiring without replacing createDraftRealtime.
After MOD031A, reconcile MOD032's already completed schedule decomposition and
scope remaining MOD029/MOD033 using their recorded dependencies/policies.
