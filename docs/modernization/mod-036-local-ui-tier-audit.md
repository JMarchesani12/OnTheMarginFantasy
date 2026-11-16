# MOD036 local UI and tier-tool audit — 2026-11-16

Bounded audit only; no product UI/provider/cache/error-boundary/memoization/dependency/deployment change. All actual fixes/optimizations remain deferred. [Current manifest](evidence/mod-036-local-current-2026-11-16.json) references [successful raw evidence](evidence/mod-036-local-32a82bfdd925460f9148b3a7b4562874.json).

## Scope and isolation

Controlled Vite build of existing frontend with an empty envDir, custom envPrefix and explicit synthetic definitions for all four VITE endpoint/auth keys. Repository .env files are not loaded. Config guard confirms envDir and absence of automatic VITE env values. Build outputs stay in the ignored plan workspace; application source/configuration is unchanged. Node22.22.2, existing dependencies only.120 recorded source/dependency hashes, emitted-asset hashes and byte calculations verified.

Installed headless Chrome157.0.8103.51 uses a fresh task-owned profile, owned loopback CDP/static server, background-network restrictions and page request interception. Only the fixture's loopback origin appears in recorded page requests; no blocked/external page requests or uncaught browser exceptions. No configured user/session/provider/DB/HTTP app/job is started. Actual React/MemoryRouter, Home/LeagueCard/ProfileStatus, DraftOrderEditor, LeagueScoreboard and existing CSS run; Home auth/profile hooks and API results are synthetic aliases. Fixture input manifest excludes real Supabase/API client modules. This is a native component fixture, not the authenticated application or live draft transport.

## Controlled bundle footprints

The existing17 lazy route declarations produce17 dynamic entries. Initial static JavaScript closure:428,013bytes raw,126,475 gzip,108,630 Brotli. Shared static chunks are counted once; dynamic imports are excluded from the initial closure. Each route below adds its static dependency closure after subtracting initial JS:

| Route | Additional raw JS | Additional gzip | Cold JS including initial, gzip |
| --- | ---: | ---: | ---: |
|Home|13,942|4,574|131,049|
|League detail|41,065|13,009|139,484|
|Draft|71,362|22,929|149,404|
|Roster|34,258|10,191|136,666|
|Manage|26,444|8,156|134,631|
|Team schedule|10,162|3,805|130,280|

Raw evidence lists all route files, static imports, additional/cold JS, per-asset raw/gzip/Brotli bytes and hashes. CSS is inventoried separately as emitted assets and direct entry/route CSS references; these JS totals do not include CSS/images or a complete route-CSS closure. Compressed values sum independently compressed files using Node defaults; they are not observed wire transfers or server compression settings. No arbitrary bundle-size budget, network/TTI claim, package blame or new splitting framework is justified by these sizes alone. Existing lazy routing is preserved.

## Native component scaling

Each of nine cases (three components ×8/32/128items) requests one warmup render plus five measured renders:54 benchmark render requests/45 timing samples, followed by separate keyboard setup mounts. All expected row counts checked. Timer starts at root.render and ends after matching DOM rows plus two requestAnimationFrame callbacks. It includes scheduling/style/layout/frame waits; **not React CPU or full-page latency**. Browser performance metrics are retained as cumulative observations; heap/DOM counters without GC controls are not memory-leak proof.

| Actual component / fixture | 8 items: settle median ms / DOM elements | 32 items | 128 items |
| --- | ---: | ---: | ---: |
|Home with synthetic own leagues|32.2 /163|32.3 /547|31.8 /2,083|
|DraftOrderEditor|32.5 /103|32.3 /367|32.4 /1,423|
|LeagueScoreboard,13weeks|32.3 /368|32.4 /1,376|32.4 /5,408|

The roughly two-frame readings are dominated by the measurement boundary. They do not prove negligible render cost or identify a React CPU hotspot. No blanket memoization/virtualization/cache rewrite is supported. Full draft/roster/schedule page profiling with actual auth, sockets, network/backend latency, production hardware and realistic distributions remains separate.

## Keyboard findings

**Home tab pattern needs a bounded follow-up.** Actual native events show ArrowRight leaves focus/selection on Your Leagues; Tab moves focus to Search Leagues; Enter activates it. Both role=tab controls have tabIndex0 and no aria-controls linkage. The [W3C APG tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/) calls for arrow navigation within horizontal tabs and associated tabpanel relationships; ordinary Tab moves out of the tablist. This is a concrete pattern gap, not a complete WCAG conformance audit. Later fix should choose/complete the tab pattern or deliberately change the semantics, preserving current state/loading/error behavior. No fix made here.

**Draft ordering passed the isolated native keyboard check.** Space on Move Team2 up reorders Team2 before Team1. Focus moves to Move Team2 down because the upward move is then disabled; live status says Team2 moved to position1 of8. Actual component/state callback executes. Parent Manage League authorization/saving, drag/touch, screen reader announcements and full browser/AT acceptance are not established by this fixture.

App.tsx/main.tsx source inventory reports17 lazy declarations and no catch-all route or named error-boundary wrapper there. That is static context, not a demonstrated route-crash/chunk-load failure in this component audit, nor sufficient basis for adding a framework. Full unknown-route/error-recovery behavior remains untested.

## Separate TypeScript tier-tool reliability

Exercise actual loadSeasonScoreboards/warning collector with canned globalfetch and owned temp caches. Never import index.ts because it runs main at top level. No live provider request, user cache or generated tier outputs touched. This tool is distinct from Python ingestion; Python client behavior does not establish this tool's provider limits or performance.

| Probe | Observed existing behavior |
| --- | --- |
|Successful cold → warm cache|One fetch initially, zero on second call; same cached payload returned.|
|HTTP503, two explicit invocations|One attempt per invocation, two total; warning and empty events returned, no cache file. No automatic retry.|
|Network rejection|One fetch; Error propagates, no warning produced by this loader.|
|HTTP200 malformed JSON|Body is cached before parsing; SyntaxError. Second invocation throws SyntaxError from the same cache, zero refetches.|
|HTTP200 valid JSON without events|Cached/returned; invalid-response warning on both calls, no refetch on second.|

**Invalid cache handling is a demonstrated reliability follow-up.** Consider parsing/schema validation before publishing cache entries and a deliberate invalid-cache recovery policy, with regression tests. Preserve legitimate empty-day payloads and decide error/CLI behavior explicitly. No TTL/retry/backoff/timeout/provider-limit/cache policy implemented. No hanging request, real rate limit, live response shape or complete CLI-output recovery is tested. Existing nine tier analysis/output/conference/validation tests remain intact.

## Verification and cleanup

Frontend235/235 tests, existing tier9/9 tests, both TypeScript checks, frontend import graph75files/219edges pass. Seven new audit helper/probe tests pass (initial missing-module RED; fixture JSX resolution, native key text and quoted-selector regressions RED→GREEN). Controlled Vite/esbuild builds, nine native cases/45saved timing samples, keyboard snapshots/AX tab properties, provider/cache observations, all120 recorded hashes and emitted asset byte/hash calculations checked.

Two failed audit-driver attempts are preserved separately: [first](evidence/mod-036-local-30647a3a3fe84c7e83691fa9467eaade.json) omitted Enter text in CDP events; [second](evidence/mod-036-local-758b3f63d4504edea6ca8b6427aa907d.json) hit a quoted CSS-selector expression error after Home keys passed. These are driver errors, not product findings. Fixes use native key payloads per the [CDP Input protocol source](https://raw.githubusercontent.com/ChromeDevTools/devtools-protocol/master/pdl/domains/Input.pdl) and JSON-stringified selector expressions; final successful run verifies Enter/Space behavior. Each attempt verifies owned browser/server/profile cleanup. Failed artifacts retain historical hashes; only successful final provenance is asserted current.

Final owned Chrome PID40867 exited, server closed, profile removed; all provider temp caches removed. Build/fixture outputs remain ignored scratch artifacts for review; no ordinary browser profile used or Docker/database started. Work uncommitted/undeployed. [Closeout evidence](evidence/mod-036-local-summary-2026-11-16.json).

MOD036's local measurement pass is complete in this scope. Full authenticated screen/real socket/production rendering, assistive technology, mobile/drag/touch, complete route-error recovery and actual tier-operator/provider evidence remain explicit acceptance/follow-up limits. No live behavior or global accessibility completion is implied. All actual fixes/optimizations remain deferred.

Independent final review: Critical0/Important0/Minor1. Reviewer passed7audit tests and independently verified final raw digest,120source hashes,49asset hashes/byte/compression records,17route closure totals, native/provider/retained-failure/cleanup facts and scope limits.

Deferred minor: repeated samples check component kind/row count, which may initially match the prior render. Two RAF callbacks are not an explicit generation/commit marker. Cumulative metrics show remount activity, but54render requests are not proof of54individually verified commits. Treat timings as coarse fixture frame-settle observations; add a per-mount generation marker before future detailed profiling. Keyboard setup switches component kinds and is not dependent on same-kind repeated sample timing. No native rerun or product change required for this documented limitation.

Reviewer did not rerun Chrome/main audit/broad application checks; full authenticated pages/provider/production/AT/mobile/route recovery and prior MOD018 work remain outside its scope.
