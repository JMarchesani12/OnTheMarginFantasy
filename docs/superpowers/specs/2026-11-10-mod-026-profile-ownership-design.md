# MOD-026: one profile owner and coordinated identity transitions

## Intent and chosen approach

Start Priority8 with MOD-026, as selected by the user. Make CurrentUserProvider the sole browser owner of application-profile loading/provisioning through the existing authenticated backend API. AuthProvider owns the Supabase session, sign-in and sign-out only. Preserve MOD-029's rule that unresolved, failed or foreign identity cannot supply an actionable numeric user ID.

This is a provider-coordination project with narrow Home/Settings integration. Deliver session-source guards and profile orchestration as separately verified stages inside the same approved scope. Do not rewrite Home, change route access policy, redesign authentication screens, introduce global caching, or begin the performance/error-parser cards.

## Approaches

The user chose API-backed profile ownership before smaller UI fixes. Keeping the present split (AuthProvider API provisioning, CurrentUserProvider direct Supabase table read) leaves ownership and race handling duplicated. Consolidating both on direct Supabase table access would require additional confirmed RLS/provisioning policy and duplicate an already authorized backend contract. The existing self-profile API provides the selected boundary; no backend endpoint/schema change or new state framework is needed.

## Existing behavior and concrete defects

AuthProvider's initial/visibility getSession lookup can publish after a newer auth event and restore an old session. It also performs profile lookup/creation, uses a local created marker to skip work, and clears shared pending signup storage after asynchronous work. CurrentUserProvider independently reads the User table directly; MOD-029 guards that lookup's subject/request generation, but cannot prevent AuthProvider publishing a stale subject or synchronize completion of initial creation.

A mismatched pending signup email is removed from storage but its parsed displayName remains eligible for the other account's creation. A delayed old operation can also clear a newer pending signup record. Two-tab creation returns409 from the existing uniqueness-protected backend; the browser does not currently converge by rereading the canonical profile.

Settings awaits refreshUser after updating, but refresh failure currently resolves and can display success. Home's account-bound owned-league arrays and Settings form/completion state need narrow identity scoping; the provider alone cannot clear existing screen state before the next effect.

## Session ownership and ordering

Keep AuthContext's public session/user/loading/sign-in/sign-out interfaces and existing password/magic-link/reset navigation behavior. Publish a coherent session/user snapshot, deriving the user from that accepted session where practical rather than independently publishing mismatched fields.

Guard initial and visibility lookups with lifecycle disposal, newest-lookup ordering and an auth-event generation. A newer auth event wins over every lookup started before it; a later visibility lookup may publish only if no newer event or lookup superseded it. Late success, failure and loading completion cannot restore A after B/logout or update after unmount. Subscription/visibility listeners clean up normally, including StrictMode effect replay. No profile API/storage work remains in AuthProvider. Do not add network work inside the synchronous Supabase auth-event callback.

## Single profile resource

CurrentUserProvider uses getUserByUuid for the current session's subject, and createUser only after a confirmed matching self-profile404. It no longer queries supabase.from('User'). The API continues to derive identity/email from verified token claims; the browser sends only displayName for creation. Local storage, URL data and numeric IDs never establish identity.

Capture subject, the corresponding explicit session access token and identity generation for each bootstrap operation. Use that same captured credential throughout its read/create/conflict-reread sequence. Add optional AbortSignal and structured status information only to the touched user API helpers as necessary; preserve apiFetch's explicit-credential no-SDK-refresh/replay contract. Do not parse or verify JWTs in the browser or add a generic retry layer.

Validate returned profile UUID against the captured subject and numeric ID as a positive safe integer before publication. Profile email/displayName come from the self-profile response; an existing profile's email need not equal a newly changed authentication email. Reject a mismatched/invalid response, never infer membership/profile ownership from email.

Use identity and request generations to mask foreign/unresolved/failed fields synchronously, reject A→B→A stale completions, dispose obsolete reads, and guard storage side effects. Superseded work must not create after its awaited404, publish a result, clear a newer hint or refresh a different account. A create already dispatched may still complete server-side for its captured authenticated subject; abort is not rollback.

Coalesce duplicate work for the same current identity/attempt. A token-renewal event alone must not erase a ready same-subject profile or provision it again. Credential renewal may restart an obsolete in-flight/failed bootstrap with the new captured token, but must remain bounded rather than loop on repeated errors. Preserve public refreshUser(): Promise<void>; deliberate refresh/retry uses the current identity and newest request, and reports failure to awaiting callers. Provider-triggered effects consume their own rejected promises after recording the error, avoiding unhandled rejections. The builder may expose an opaque internal identity-generation key to consumers; it must contain no token/credentials.

## Provisioning and bounded outcomes

Per attempt: one self-profile lookup; on confirmed absence, at most one create. Successful creation supplies the canonical profile response. A create409 permits exactly one self-profile reread; a matching profile means convergence, while absent/denied/failed reread is a visible retryable failure. No second create in that attempt.401/403, malformed/failed reads, network errors and ambiguous create failures do not trigger automatic provisioning or replay. Explicit Retry starts by rereading the profile, so a previously committed but unacknowledged create is discovered before another create is considered.

Missing signed-in identity/credential waits or produces the appropriate signed-out/setup state; missing verified session email must not be replaced by a pending storage email as authority for creation. Empty/denied/failed setup is visible and manually retryable. No maximum league/member policy or backend provisioning changes are involved; existing MOD-006 uniqueness remains the concurrency authority across tabs/processes.

Builder call: ignore old otm:user-created:<subject> markers as authority or a reason to skip the fresh profile read. Remove this provider flow's marker writes; no broad local-storage cleanup/migration is necessary.

## Pending signup name handling

Preserve name precedence for a genuinely missing profile: a nonempty pending displayName whose normalized email matches the current verified session email, then a nonempty string session metadata username, then the existing verified-email-prefix fallback. Treat pending data as a display-name hint only. Never apply it over an existing profile or borrow another account's name/email.

Builder call: compare trimmed, case-normalized emails only to associate the hint; this is not account matching/merging or authorization. Ignore mismatched hints and leave them for their matching account. Clear a matching hint only after a current matching profile/creation result is confirmed and the stored raw record is still the exact record captured by that attempt. Malformed hints may be removed only while current and unchanged. Late work must not clear another tab's newer signup record. Do not change the signup form or storage key format unless an actual required race cannot be guarded with this contract.

## Narrow consumer integration

Expose profile loading/error/Retry feedback in Home and Settings without changing anonymous discovery, route access, layout or primary league-list request feedback policy. A small shared status component is acceptable. It must not hide or remount every screen on routine token renewal or a same-subject refresh. Home's two owned-league resources must mask/reset when the account identity generation changes and reject obsolete results; do not redesign stage/list retry states or implement MOD-027A here. Keep public search/overview behavior intact.

Scope Settings' form and asynchronous save/refresh completions to the current account generation and mounted view. Preserve typed input on failure; no stale success/error/finally update or refresh call after A→B/logout. The save's own same-subject refresh must not be mistaken for an account change. Announce success only after the matching refresh succeeds; failed refresh leaves a visible error/Retry outcome. No old-account response may overwrite the new account's form. Keep the existing update payload and validation.

Other league screens keep their existing useCurrentUser contract. MOD-029 context invalidation and draft epoch tests must remain green; no all-screen migration or mutation coordinator in this card.

## Verification and acceptance

First reproduce existing session-lookup A→B/logout races, pending create/read ordering, wrong-account pending displayName, and concurrent creation conflict. Tests must run actual providers/profile coordinator with controlled Supabase auth events/session promises and fake API/storage; no real credentials, provider calls or network. Preserve/extend the actual-provider MOD-029 tests rather than deleting their race assertions when transport changes.

Cover account A→B→A, logout/unmount, old visibility lookup after auth event, overlapping visibility/refresh ordering, same-subject token renewal, ready-profile stability, cancelled read before create, pending create completion after switch, malformed/mismatched/newer storage hints, returned UUID/ID mismatch, initial profile read success,404→create success,409→one reread, denied/empty/conflict-reread/network/ambiguous-write failure and explicit Retry bounds. Assert transport credentials/signals, no direct User-table reads, operation counts, fresh matching profile visibility and absence of obsolete storage changes.

Run Home/Settings integration tests for private-data reset before effects, retained form input on failure, successful same-account save+refresh, and stale save completion after account switch/logout. Provider errors/Retry must be visible; Home's separate league-fetch errors remain MOD-027A. Run full frontend tests, production build, import graph and diff checks; backend contracts unchanged, with existing create/self-read/uniqueness evidence referenced as historical rather than claimed freshly tested. Browser/Supabase runtime scheduling is not proven by a fake-hook harness; use an available real renderer/browser when practical and report exact coverage limits.

Obtain a fresh final review, fix material findings with reproducing RED→GREEN tests and a green full suite, and record source hashes/commands/limits. Work starts from clean audit commit6c8fcd4 (Priority7); leave this stage uncommitted/undeployed as requested. No schema/configured DB inspection, provider execution, Docker setup or hosting changes are needed.

## Completion and separate work

MOD-026 completes when one API-backed profile owner, coherent latest-session publication, bounded provisioning, subject-bound profile visibility, safe pending hints and the narrow consumer refresh/reset contract are verified. MOD-027A–G feedback/accessibility, MOD-028B safe error parsing, performance measurement and cleanup remain separate Priority8 tasks. Do not mark them complete merely because their dependency is improved.
