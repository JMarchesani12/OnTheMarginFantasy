# React frontend audit

2026-10-28. Documentation-only audit; no fixes implemented. Read with [architecture.md](architecture.md), [features.md](features.md), [behavior-checklist.md](behavior-checklist.md) and [progress.md](progress.md). Feature IDs below use the inventory. `FE` means `front-end/src`; evidence locations are repository-relative and line numbers refer to this checkout.

## Scope and confidence

Reviewed routing/bootstrap, both providers, HTTP client and representative API wrappers; traced loading effects, state persistence, requests and mutation refreshes in Home and league screens/components. Inspected targeted account/create/settings forms, draft socket/clock/dialog, schedule rendering and shared utilities/import relationships. Large screens were sampled around these responsibilities, not reviewed line by line. This is a bounded source audit, not a production behavior or security certification.

Classification:

1. **D — demonstrated defect:** a concrete source path establishes the limitation, mismatch or missing interaction. These are source demonstrations, not browser reproductions.
2. **P — measured performance problem:** requires measured latency, rendering, transfer or resource evidence. **None established in this run.** Static request counts, source lengths and dependency counts are measurements of code structure, not proof of slow UX.
3. **M — maintainability/organization:** concrete duplication, ownership or coupling with an identifiable maintenance cost.
4. **S — speculative improvement/investigation:** plausible risk or optimization requiring reproduction, product agreement or measurement before implementation.

No application processes, production requests, environment reads, dependency installation, builds or application tests were performed. Read-only shell/Python checks counted source lines and scanned literal relative TS/TSX imports. Proposed verification below is future work, not a claim of passing checks. Prior behavior-checklist bug exclusions remain exclusions; frontend gates do not establish REST authorization.

## Current patterns worth retaining

- Vite SPA with React Router's explicit routes and lazy imports for all 17 screens (`App.tsx:4–87`); no reason established to adopt file-based routing or a different framework.
- API functions grouped by domain with one bearer-aware transport (`api/client.ts`), shared types and useful pure utilities. Schedule pagination, tier display, date handling, ranking and daily-total utilities already have focused tests; preserve their semantics.
- Many request effects use mounted/cancelled guards. Home search debounces 400 ms; team lookup debounces 250 ms and ignores superseded responses. Roster own/available requests already run with `Promise.all`.
- Auth unsubscribes its SDK listener and removes the visibility listener; draft cleans up socket connections and intervals; rules uses a league-keyed content component with explicit retry. Native buttons, labels, roster selection `aria-pressed`, draft announcements and expandable history already exist.

## Request, freshness and state inventory

| Resource / ownership today | Fetch trigger and dependency chain | Cache/key/freshness and refresh today |
| --- | --- | --- |
| Session / AuthProvider | Initial `getSession`, auth events, visibility return | Supabase owns persisted session/refresh. Local `otm:user-created:<uuid>` is a provisioning marker, not cached profile data; pending-create metadata is global. |
| Application profile / CurrentUserProvider | Auth ready → direct Supabase `User` lookup by UUID | Provider memory; explicit `refreshUser` after settings save. AuthProvider separately looks up/creates through Flask. No coordination or request deduplication. |
| Own leagues / Home | Profile ID → stage list and separate all-membership list | Two local arrays, no shared request key/expiry; refetch on ID/stage/mount. No visible loading/error for primary list. |
| League context / six league screens | Navigation state can seed local league; missing context → byUser(all) → optional getLeague; Detail always revalidates | No shared cache or freshness timestamp. State can remain indefinitely on screens that skip fetch when league exists. Navigation state is a snapshot, not canonical membership authority. |
| Members, conferences, sports | Separate screen/component effects | Local state only; sports loaded separately by Home/Create/Discover. Members may refetch when entire league object changes. No app TTL or shared invalidation. HTTP/browser cache behavior is unverified. |
| Standings / Detail | League/effective week → pointsAwarded, sequential batches above week 10 | Local record keyed by week inside a screen; no ingestion/focus refresh. |
| Member/conference/team schedules | Context → member/week/conference/team request | Effect dependencies encode identity; local last response, no reusable cache. Member-week switch refetches; most guards prevent stale writes, not network work. |
| Draft | League/week → available teams; authenticated socket → snapshots; summaries via REST | Snapshot updates local state; selections persisted by league/member. One-second live UI clock. Ten-second team polling only when token absent, not a general reconnect fallback. |
| Roster/trades/pending | Context → own+available in parallel; members → counterpart roster; each panel fetches independently | Mount/prop/manual refresh and local mutation reloads. No shared transaction invalidation. Pending ownership is intentionally distinct from applied ownership. |

No query-cache dependency is declared in `front-end/package.json`; `apiFetch` adds auth/retry but has no result cache, in-flight registry or invalidation. This alone is not a defect. If caching is later added, first specify resource identity and freshness rather than introducing a library globally.

## Demonstrated defects

Each task below is an intentional behavior change unless explicitly stated otherwise; none is implemented here.

### D01 — Own-league request failures are invisible

**Evidence / features:** `screens/Home/Home.tsx:76–102,377–384`; F-005, with F-004 dependency. Primary list starts empty and only logs failures; render maps cards without loading, failure or successful-empty branches. A failed initial load looks like an empty list; a failed stage change retains the previous list.

**Impact:** Users cannot distinguish no leagues, loading or failure; old-stage cards may remain under a new selection.

**Bounded task:** Add explicit primary-list request states and retry, tied to user/stage identity; clear or clearly identify previous results during a switch.

**Verify:** Delayed success, empty success and rejected initial/stage requests produce distinct UI; retry recovers; failures never claim successful emptiness.

### D02 — Successful transactions leave sibling panels stale

**Evidence / features:** `screens/League/LeagueRosterPage.tsx:340–405,856–870`; `components/League/TradeRequestsPanel.tsx:40–115`; `PendingTransactionsPanel.tsx:52–71`; F-015/016. Proposal/add-drop success reloads roster only. Pending panel stays mounted with the same league ID; proposal does not signal the mounted trade panel. Accept reloads open trades and filters PENDING_APPLY out of incoming/outgoing, but does not refresh pending items.

**Impact:** A submitted or accepted transaction can be absent from the displayed lists until manual refresh/tab remount/navigation, undermining submission feedback.

**Bounded task:** Give the roster feature one mutation-refresh coordinator (callbacks or a narrowly scoped resource owner); refresh open and pending lists after relevant successful writes. Retain pending-versus-applied semantics.

**Verify:** Mock proposal, add/drop and acceptance; newly returned pending/open entries appear without remount/manual refresh. Failed writes retain selections and do not show success. Acceptance does not pretend ownership has already transferred.

### D03 — Shortening team search can leave “Searching” stuck

**Evidence / features:** `screens/League/TeamLookupPage.tsx:88–126`; F-012. Start a request (sets loading true), then reduce input below two characters: cleanup marks old request cancelled, short-query branch clears results/error but not loading, and cancelled `finally` cannot clear it.

**Impact:** Persistent searching feedback with no active eligible search.

**Bounded task:** Reset loading in the short-query/no-context branch; keep obsolete-response protection.

**Verify:** Hold a two-character query response, erase text, then resolve/reject it. Loading ends immediately, no old results appear, and subsequent valid search works.

### D04 — Discover cold URL cannot resolve its league

**Evidence / features:** `screens/League/DiscoverLeaguePage.tsx:19–24,108–123`; F-006; existing B3/Q8. It reads only `location.state.league`, never the route parameter, and explicitly asks users to open from search when state is absent.

**Impact:** Shared/new-tab direct URLs cannot display details. History-state-preserving reloads may work; not every refresh fails.

**Bounded task:** Subject to Q8, resolve the URL league ID with navigation data as optional seed; define missing/invalid/unauthorized outcomes and a deterministic back destination.

**Verify:** In-app entry, new-tab URL, no-state refresh, invalid/unknown ID and denied request. Correct league renders without navigation state and errors are actionable.

### D05 — Create form has unassociated visible labels

**Evidence / features:** `screens/CreateLeague/CreateLeague.tsx:229–332`; F-007. League Name, Sport, date fields, timeout action and grace labels are siblings of controls with neither wrapping association nor `htmlFor`/matching IDs. Creator team name is a useful correctly associated example.

**Impact:** Controls lack their visible labels as programmatic accessible names.

**Bounded task:** Associate these labels and controls; connect validation descriptions where present without changing validation policy.

**Verify:** Each field is discoverable by its visible label in an accessibility tree/control-by-label check; label click focuses the control; keyboard submission still works.

### D06 — Draft completion dialog lacks modal focus behavior

**Evidence / features:** `screens/League/LeagueDraftPage.tsx:1244–1296` declares `role="dialog"`, `aria-modal`, title and close button; no focus transfer/trap, background inertness, Escape handler or focus restoration appears in the component; F-013/020.

**Impact:** ARIA modal declaration does not prevent keyboard focus remaining behind or escaping the overlay.

**Bounded task:** Add a focused modal implementation with initial focus, contained tab order, dismissal and restored focus; handle automatically opened completion when the old trigger no longer exists.

**Verify:** Complete draft using keyboard; focus enters dialog, Tab/Shift-Tab stay within it, Escape/close dismiss it, and focus returns to an appropriate visible control. Confirm screen-reader title and background isolation.

### D07 — Draft order has pointer-only manual reordering

**Evidence / features:** `screens/League/ManageLeaguePage.tsx:859–905`; F-018. Rows use HTML drag events; row actions offer removal, no keyboard move action. Randomization is not equivalent to choosing an order.

**Impact:** Keyboard users cannot perform the same intentional ordering operation.

**Bounded task:** Add named move-up/down controls with boundary disabling and retained focus; reuse existing order state and save payload.

**Verify:** Keyboard-only reorder, first/last boundaries, saved and reloaded order, and unchanged membership/removal behavior.

### D08 — HTTP auth retry predicate does not match middleware error

**Evidence / features:** `api/client.ts:40–54` matches “invalid session”; `api/authMiddleware.py` returns “Invalid or expired token”; F-002/022; existing B6.

**Impact:** This middleware error cannot enter the transport's explicit refresh/retry branch. SDK automatic token refresh may mask it; universal session failure is not demonstrated.

**Bounded task:** Agree a machine-readable auth failure contract and align a single retry with it; do not blindly retry every 403 or non-idempotent mutation.

**Verify:** Expired token refresh succeeds once, refresh failure terminates, permission denial does not refresh, and a mutation is not duplicated after an ambiguous committed response.

## Maintainability and organization findings

### M01 — Repeated league-context resolution has divergent policies

**Evidence / features:** Detail `78–123`, Draft `62–105`, Roster `129–170`, Conference `114–155`, TeamLookup `44–86`, TeamSchedule `69–110` repeat byUser lookup/find/fallback and loading/error handling; F-008/011–013/015/016. Detail revalidates even when seeded; several others return early if any league exists. Manage `195–253` maintains another mapper despite `utils/leagueMapping.ts`.

**Impact:** Fixing context, mapping, account change or freshness requires multiple edits; a route ID can diverge from retained local context on same-component navigation. Exact visible race scenarios remain S01.

**Bounded task:** Extract one league-context hook using the existing mapper with explicit URL/user identity and seed policy; migrate Detail and one other screen first. Then compare behavior before wider adoption. Consolidate Manage's mapping only after documenting its form-specific defaults.

**Verify:** Both migrated screens agree for seeded/cold/member/nonmember/failed loads; league and account transitions cannot retain another identity's actionable context. Preserve commissioner/status gates and current effective-week semantics.

### M02 — Server state and unrelated UI responsibilities share large components

**Evidence / features:** Physical source-line counts: Draft 1,300; Manage 1,032; Detail 952; Roster 873; Conference 724; ScheduleTabs 702. Draft combines socket protocol, normalization, persistence, clock, filtering, commands and modal; Manage combines mapping, settings/draft forms, order, moderation and deletion. F-008/009/011/013/015–021/023. Length alone is not a performance defect.

**Impact:** High interaction surface makes cleanup and refresh changes difficult to review; D02 and S02 have ownership boundaries in these components.

**Bounded task:** First extract draft clock and socket lifecycle into focused hooks, leaving snapshot application and rendering contracts explicit; separately extract the Manage draft-order section. Avoid a simultaneous rewrite of all screens.

**Verify:** Recorded J3 behavior unchanged by internal extraction; one active socket/clock after settling, cleanup on exit, identical snapshot/pick command shapes; identical order/save payloads and permission/status gates. Track behavior fixes in separate tasks.

### M03 — Shared bonus editor is owned by a route folder

**Evidence / features:** Manage imports `../CreateLeague/BonusesEditor`; Create imports `./BonusesEditor`; F-007/017. `api/roster.ts:1` also says `src/api/schedule.ts`, and `api/user.ts:getUser` reports “Failed to get sports”. `currentUserContext.tsx` uses different filename casing from AuthContext.

**Impact:** Cross-screen dependency obscures ownership; copied names mislead debugging. Casing inconsistency is cosmetic, not demonstrated breakage.

**Bounded task:** Move shared editor with imports unchanged semantically; correct misleading comments/error wording separately. Leave context casing alone unless a repository naming policy is adopted.

**Verify:** Both editor consumers resolve to the same component/type; TypeScript/import resolution succeeds; no form payload or CSS changes. Error wording changes are separately reviewed user-visible text changes.

### M04 — API error contracts lose useful detail inconsistently

**Evidence / features:** `api/leagues.ts` create/update/join/approve/deny throw status-only errors; remove/delete/member-update parse message bodies; `api/user.ts` also uses status-only errors. F-004/006–008/017–019/021.

**Impact:** Forms cannot consistently explain server validation versus network/session failure; repeated parsing policy invites drift.

**Bounded task:** Add one bounded error parser that tolerates non-JSON responses and preserves status/message; migrate league create/join first. Avoid changing backend status contracts in this task.

**Verify:** JSON message, JSON error, plain text and empty bodies all produce safe actionable feedback; failures preserve form entries and re-enable submission. Do not expose raw sensitive server traces.

## Speculative improvements and reproduction tasks

### S01 — Profile provisioning and identity transitions need race verification

**Evidence / features:** `context/AuthContext.tsx:34–129` releases loading before unawaited API provisioning and may invoke provisioning from initial load/auth events/visibility; `currentUserContext.tsx:35–89` independently queries Supabase with no cancellation/generation guard and no provisioning completion dependency. Errors retain prior profile fields. F-002/004/005/022.

**Impact hypothesis:** First-signup profile lookup can finish before creation and stay missing; delayed account-A response can overwrite account-B state. Duplicate lookups/creates are possible without an in-flight guard, but counts and user-visible failures were not reproduced.

**Bounded task:** Use deferred mocked SDK/API responses to establish ordering. If reproduced, coordinate provisioning/profile readiness under one UUID-scoped owner and suppress obsolete results; preserve SDK subscription cleanup and server uniqueness.

**Verify:** First login with absent profile resolves after creation without reload; concurrent events do not create twice; sign-out/switch while old lookup is pending never exposes old actionable profile IDs. Measure actual request counts separately.

### S02 — Draft connection lifecycle and response ordering need controlled tests

**Evidence / features:** Draft `373–420` sets `hasJoinedDraft` inside an effect that depends on it, inducing a setup→cleanup→setup transition; `draft:join` is outside `connect` and gated by a ref reset only in cleanup. `applyDraftSnapshot` reads `league?.memberId` but omits that direct dependency. REST `loadTeams` has no obsolete-response guard and may write after newer socket availability. F-013/020/023; expands B4.

**Impact hypothesis:** Reconnect may lose room subscription; cold-loaded member context can remain stale in callback; old REST availability can undo a newer snapshot. No actual dropped event or invalid pick was observed.

**Bounded task:** Reproduce cold entry, dependency-triggered reconnect, transport loss, token refresh and delayed REST/socket ordering in a fake transport. Then make room join tied to each authenticated connection and define snapshot/REST precedence; fix closure dependencies explicitly.

**Verify:** One settled connection, exactly one effective room membership per connection, fresh snapshot after reconnect, latest member used, no availability regression from obsolete HTTP results, no events/timers after unmount. No authenticated socket failure should silently imply working polling fallback.

### S03 — Cancellation and keyed state reset are inconsistent

**Evidence / features:** Detail members `133–151`, roster loader `84–121`, draft team loader `160–198` and transaction panels lack latest-request guards; many neighboring effects have them. Most wrappers do not accept AbortSignal. F-008/013/015/016. LeagueScheduleTabs initializes member/week from props once (`68–74`); DraftHistory retains snapshot/error on league-ID change (`12–20`).

**Impact hypothesis:** Slow old results can replace current selections/data on reused components; guarding setters alone still spends network work. Not every unmount state update is a memory leak, and React StrictMode's development effect replay does not prove duplicate production traffic.

**Bounded task:** Test one league/member switch with inverted response order; define which selection resets on identity change. Add generation guards and optional transport cancellation only to confirmed paths.

**Verify:** Delayed old response/rejection cannot change current data/error/loading; cancellation is not shown as user failure; intended week/member choices survive ordinary rerenders, but never migrate accidentally to another league.

### S04 — Duplicate requests and waterfalls are optimization candidates, not measured slowdowns

**Evidence / features:** Home's stage/all effects share byUser when stage is `all` (exact same body on initial all selection, or a transition to all while its other request is in flight); ordinary active load requests overlapping subsets rather than identical bodies. Detail members depends on `[league]`, so navigation seed followed by fetched replacement triggers another members request. Cold league routes wait for profile → byUser → optional league → dependent resource. Detail `187–196` awaits each score batch sequentially: week 20 yields three batches (0–9, 10–19, 20). Sports refetches across three screens. F-004–009/011–013/015.

**Impact hypothesis:** Avoidable traffic and accumulated latency on slow networks; magnitude unknown. Some dependencies are legitimate: member ID/current period comes from league context.

**Bounded task:** Capture a mocked/staging network trace for Home all, seeded/cold Detail and week 20. First deduplicate identical Home reads and narrow members dependency to league ID. Benchmark bounded parallel score batches against existing sequential behavior before changing concurrency.

**Verify:** Report request count, critical-path duration, payload bytes and errors under the same fixture/network conditions. Confirm scores/order unchanged and no excessive concurrency. Do not remove membership lookup without preserving its member-specific fields.

### S05 — Freshness and persisted selections need an explicit policy

**Evidence / features:** Inventory above; roster key `rosterTab:<leagueId>` is read only in initial state, before league resolves on cold entry, then default is written once key exists (`LeagueRosterPage:51–82`). Conference key is league-scoped; draft key is league/member-scoped. Storage helper swallows unavailable-storage errors, not an actual reusable server cache. F-005/008/009/011/013/015/016; Q8.

**Impact hypothesis:** Cold roster navigation can overwrite a saved tab; seeded context/deadlines can grow stale while another browser changes them. Account-sharing semantics for league-scoped preferences are undecided.

**Bounded task:** Reproduce seeded versus cold tab restoration; agree Q8 and per-resource freshness before adding any cache. A small scoped hook/coordinator may suffice.

**Verify:** Seeded and cold restoration match the agreed policy; identity changes reset appropriately; unavailable storage is harmless; successful mutation and focus/revisit refresh rules are tested. No stale role/deadline is treated as authority.

Candidate resource identities, if a cache is justified: own leagues `(auth UUID, userId, stage)`; league context `(auth UUID, leagueId)`; roster/member schedule `(auth UUID, leagueId, memberId, weekNumber)`; conference games also `(seasonYear, conferenceId)`; team games `(leagueId, seasonYear, teamId)`; search `(leagueId/query or query/sportId, limit, offset)`; open trades `(auth UUID, leagueId, memberId)`; pending `(auth UUID, leagueId)`; sports may be public/global. Clear protected data on identity change. Define mutation invalidation explicitly: admission/removal → membership/list/context; settings/order → context/rules/draft; transaction → open/pending and affected roster/schedule when ownership actually applies. No TTL values or global polling policy are justified yet.

### S06 — Rendering, bundles and wider accessibility require measurement

**Evidence / features:** Draft live clock updates state every second in a 1,300-line screen; roster renders filtered team groups; ScheduleTabs builds game/date rows with existing memoization/pagination utilities. App uses lazy routes but one Suspense fallback and no error boundary/catch-all route. Home tab roles have selection but no arrow-key handling/panel linkage (`354–377`). F-001/005/007/009/011–016/018/020.

**Impact hypothesis:** Large-list commits, JS download, focus movement, unknown paths or chunk-load failures may harm UX; no profiler, web vitals, bundle sizes, contrast results or complete assistive-technology journey was measured.

**Bounded task:** Profile draft with realistic team/pick counts and schedule with a full scoring period; inspect production chunks and run keyboard/screen-reader checks. Decide unknown-route/recovery behavior explicitly. Test recovery-password success timeout (`UpdatePassword:64–68`), which is not cancelled on exit, before changing navigation/sign-out timing.

**Verify:** Record device/browser, fixture size, commit duration/count, transfer/gzip size, LCP/INP/CLS and network conditions. Optimize only a measured bottleneck; compare before/after. Check Home tab keys/panels, route focus/title, dialog behavior, errors/status announcements, zoom and contrast. Global button outline removal has a replacement focus box-shadow (`index.css:135–141`); do not label it invisible without checking rendered styles.

## Modest target organization and change separation

Keep `screens`, `components`, `api`, `context`, `types`, `utils` and colocated styles. There are no framework-enforced file routes here. Do not create a new global state layer, move all domain files or rename every page.

Only introduce these locations as their bounded tasks are undertaken:

```text
src/
  screens/League/                 # existing route components remain here
    hooks/
      useLeagueContext.ts        # M01: repeated resolution, explicit identity
      useDraftConnection.ts      # M02/S02: connection lifecycle
      useDraftClock.ts           # M02: timed rendering responsibility
  components/League/
    BonusesEditor.tsx            # M03: shared by Create and Manage
    DraftOrderEditor.tsx         # M02: focused extracted presentation/actions
  api/                           # existing domain functions and client stay
  context/                       # existing providers stay pending S01 evidence
  utils/                         # existing pure domain calculations stay
```

**Moves/renames only:** M03 move `screens/CreateLeague/BonusesEditor.tsx` → `components/League/BonusesEditor.tsx`, updating both consumers and any relative imports. No paired CSS file exists for that editor. No other move/rename is necessary now. This can be reviewed independently of refactoring.

**Internal refactoring:** M01 league hook/map consolidation; M02 draft hooks/order extraction; M04 shared error parsing mechanism. Keep requests/payloads/UI semantics stable during extraction; user-facing error text improvements are a distinct change. Hooks are internal to league routes until another consumer exists. Import direction stays screens → components/hooks → API/types/utils; shared components must not import screens.

**Intentional behavior changes:** D01–D08, confirmed S01–S05 fixes, keyboard reorder/dialog interaction, freshness/invalidation, retry decisions and URL recovery. Keep them in separate small tasks from pure moves/extractions, with the verification criteria above. Q8 navigation/persistence and transaction-application timing require explicit acceptance criteria; don't settle them through cleanup.

## Dependency and naming result

A read-only Python scan of 63 TS/TSX files resolved 175 literal relative module edges, including type-only edges and lazy imports, and found **zero cycles and zero unresolved relative TS/TSX imports**. It excluded CSS and package edges and does not analyze computed imports, package internals or CSS dependency cycles. There is no demonstrated circular dependency requiring reorganization. The concrete cross-screen import found was Manage → CreateLeague/BonusesEditor (M03). Existing shared utilities already avoid broad screen-to-screen coupling. PascalCase pages/components and domain-named API modules are useful patterns; minor casing/copy inconsistencies do not justify mass renames.

## Boundary, remaining coverage and order of work

This pass stops at source-backed frontend patterns and targeted interaction paths. It does not claim complete review of every branch in roughly 8,900 TSX lines, runtime feature correctness, passing lint/build/tests, live Supabase RLS, API identity binding or deployed behavior. No measured performance finding is being deferred as if it were established.

Remaining coverage:

- Browser reproduction of every D/S scenario, especially two-account transitions and socket/HTTP ordering; J1–J5 remain the journey baseline.
- Full large-screen render/form branch review, validation/date conversions, dirty form behavior, overlapping submissions and moderation error recovery. Existing busy flags are not proof against all duplicate commands; no idempotency conclusion made.
- Production build/chunk analysis, network traces, React profiling/web vitals and representative device data; no blanket memoization/virtualization recommendation.
- Complete keyboard/assistive-technology, contrast, responsive/zoom and reduced-motion checks, including auth and bonus-editor fields. Source sampling is not an accessibility conformance audit.
- Navigation back/forward, same-component league/team changes, invalid IDs, missing routes, auth-required redirects, chunk failures and preferences across account changes. These are test targets, not all demonstrated defects.
- Exhaustive runtime response schemas and server-side permission/actor binding remain a separate backend audit (B1/B2); do not “fix authorization” by hiding frontend controls.

Suggested bounded order: D01/D02/D03 and reproduce S01 identity races; D05–D07 accessibility; reproduce S02 draft lifecycle; M01 and M03 independently; then trace S04 before cache/concurrency work. D04/Q8 and D08 need their explicit navigation/auth contracts. Keep each move, extraction and behavior change reviewable on its own.
