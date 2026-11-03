# MOD-041: HTTP and outbound-client boundaries

Date: 2026-10-29. Status: approved by the user on 2026-10-29. The user selected option 3 below, confirmed Render hosting, prioritized low recurring cost and agreed to defer rate limiting. The detailed contracts below are approved architecture requirements for separately scoped implementation. No deployment or application changes are authorized by this document.

## Intent and constraints

Give authentication, response handling and outbound calls explicit owners before MOD-038's incremental hybrid pilot. Retain Flask, Supabase authentication and the existing Render service. Require no new paid service, gateway, Redis, monitoring subscription or larger instance. Small processing overhead is expected; unchanged billing cannot be guaranteed without workload evidence.

Goals: stable authentication errors, bounded client recovery, preserved resource authorization, predictable early responses and transport-independent service entry points. Non-goals: rate enforcement, framework replacement, mass endpoint migration, schema changes, new retry infrastructure and production configuration changes. Avoid a universal decorator stack and avoid coupling domain services to Flask globals or HTTP status codes.

## Approaches

1. Extend current hooks and helpers locally: smallest immediate change; ownership/order can remain inconsistent.
2. Broad WSGI middleware stack: useful for infrastructure concerns but adds machinery around application identity and error handling.
3. **Selected direction:** Flask hooks/error handlers own application HTTP concerns; Render retains hosting responsibilities; narrowly scoped WSGI configuration is used only where verified deployment facts require it; browser and provider clients have separate policies. Services retain resource authorization and transaction ownership. Initial code may resemble option 1; explicit boundaries distinguish the approach. No additional middleware framework or infrastructure is required.

## Current evidence

- `api/authMiddleware.py` skips OPTIONS and configured public paths/prefixes, verifies JWTs into `g.user`, and returns text-valued authentication errors.
- `api/api.py` configures CORS, public health/sports/league-search routes and the Socket.IO prefix; constructs routes and starts a listener during app creation.
- `api/authenticatedPrincipal.py` distinguishes a verified subject from a unique application-user mapping. Endpoints resolve principals; model operations enforce resource access.
- `front-end/src/api/client.ts` attaches tokens without an API-origin restriction and refreshes on 400/401/403 only when body text contains "invalid session". Middleware returns a different message.
- ESPN clients use explicit timeouts, with a hardcoded scoreboard timeout in the inspected implementation; no explicit retry policy was found there.
- Draft sockets authenticate connection tokens separately and check league membership on room operations. HTTP handshake exemption does not grant room access.
- `api/start.sh` specifies one Gunicorn worker. This does not establish deployed worker count, proxy topology or installed gateway protections. Existing operational records say the listener is intentionally suspended; this work must not restart it.

## Incoming request ownership and order

1. **Render/server boundary:** retain existing hosting and TLS behavior. Verify forwarded-header behavior before configuring proxy trust; do not assume a hop count or trust arbitrary client forwarding headers. Rate limiting and new gateway configuration are deferred.
2. **Flask request context:** assign a server-generated request ID and start timing before authentication, so early denials are correlated. Do not trust a supplied request ID as the authoritative ID.
3. **Transport bounds:** configure finite request-body bounds; route schemas enforce collection/string limits before costly work. Values and affected routes require an inventory of legitimate payloads in MOD-019. Never consume an unbounded body in an earlier hook. These bounds are validation, not quotas.
4. **Route policy and JWT:** explicitly classify routes; protected requests require verified claims. Preserve current missing/invalid-token denial behavior, including authentication before normal protected-route processing. OPTIONS follows CORS/preflight handling without application-principal lookup.
5. **Adapter identity and schema:** profile bootstrap/own-profile lookup require a verified subject but must not require an existing profile. Other protected application operations resolve exactly one application principal. Keep this opt-in at adapters, reusing the resolver; optional request-local reuse may avoid duplicate lookups, with no cross-request identity cache. Parse and validate route/query/body data without deriving identity from body actor fields.
6. **Service boundary:** pass explicit verified actor and validated inputs. Services enforce resource/role/state authorization and own transactions. Repositories use the supplied connection and do not commit. Jobs call explicit trusted entry points; no HTTP flag can select trusted authority. MOD-038 defines concrete actor types and compatibility facades.

Do not force every existing endpoint through a new service immediately. Preserve existing authorization checks and transaction/lock boundaries during adoption.

## Route and transport policy

| Class | Identity | Resource policy / response |
| --- | --- | --- |
| Health | Public | Preserve `{ok:true}` liveness; no new database readiness probe |
| Sports and league search | Public as currently registered | Preserve public projections; enforce applicable input bounds |
| OPTIONS | No application identity | CORS/preflight rules; no domain operation |
| Profile creation and own UUID lookup | Verified JWT subject | Bind to subject; allow missing profile during bootstrap |
| Ordinary application routes | Verified JWT plus application principal | Service/model resource checks; preserve intentional concealed 404 denials |
| Disabled operational HTTP commands | Preserve existing authentication boundary | Remain disabled; never gain a trusted-job bypass |
| Socket.IO handshake and events | Separate socket token verification | Preserve membership checks and event protocol; no automatic REST envelope migration |
| Jobs and maintenance | Explicit trusted process entry | No fabricated Flask context/principal; retain domain invariants |

Before implementation, enumerate exact routes/methods, including disabled-command outcomes, against registrations and existing tests. Do not restore the obsolete public user-by-UUID prefix described in older architecture notes.

## Response and exception contract

Proposed REST failure shape: `{"error":{"code":"auth_token_invalid","message":"Authentication required"},"requestId":"..."}`. Success payloads/statuses remain unchanged. `X-Request-ID` carries the same server ID on Flask-produced successes and failures. This is an intentional error-contract migration in MOD-019/028A, not a behavior-preserving folder refactor.

Proposed authentication codes: `auth_token_missing` (401), `auth_token_invalid` (401, invalid or expired), and the existing principal-resolution codes/statuses. Only `auth_token_invalid` permits browser refresh. Missing/ambiguous profile mappings remain 403 and never trigger refresh. Retain resource-specific concealed 404 behavior; do not globally turn PermissionError into 403 or ValueError into 400.

Services raise explicit transport-independent domain failures; adapter/error translation assigns safe status/code/message. Repositories propagate operational failures for rollback; unexpected errors become generic 500 responses with correlated internal diagnostics. Never return SQL, tokens, provider bodies or arbitrary exception strings. Existing local catches require explicit adoption; global handlers cannot normalize errors already returned by an endpoint.

Register centralized handlers for framework errors and unhandled exceptions, preserving relevant HTTP headers such as Allow. Response finalization applies request ID, CORS and appropriate cache/security policy to early denials and handled errors as well as success. Preserve current CORS origins/methods and expose the request-ID header; do not expand origin access. Use no-store for authenticated/private responses and errors; retain intentional public caching only where explicitly specified. Choose concrete security headers with deployment evidence in MOD-019 rather than introducing HSTS/CSP indiscriminately.

Teardown handles cleanup, not commits or payload construction. Request metrics use bounded fields (route template, method, status, duration and request ID); no tokens, request bodies, query-string secrets or private rows. Use existing logs, with no external telemetry subscription. Responses generated by Render before Flask cannot be promised the Flask JSON shape or headers.

## Browser outbound policy

- Attach or automatically refresh Supabase bearer credentials only for the configured API origin and API path scope, using parsed URLs. Skip-auth calls remain explicit. Reject authenticated destinations outside that scope rather than forwarding credentials. Authentication-bearing calls must not follow redirects to unintended destinations.
- Refresh only on the structured `auth_token_invalid` 401 from the API authentication boundary. The server guarantees this response occurs before a domain mutation executes. Never refresh on 400, permission 403, profile mapping failures, concealed 404, 429, 500 or message substrings.
- Share one in-flight refresh across concurrent failures; retry each eligible request at most once. Do not replace caller-supplied Authorization with the user's session or refresh it automatically.
- Rebuild requests from replayable inputs. Do not retry consumed Request bodies/streams. A mutation may be replayed only after the designated pre-execution authentication denial, never after timeout/network failure or ambiguous completion. No general mutation retry policy is introduced.
- Honor caller cancellation on the initial call, refresh wait and replay. Use a finite default request timeout, overridable for documented long operations; concrete durations follow a call inventory. Timeout/cancellation means outcome unknown for a submitted mutation, not permission to retry.
- Adapt frontend error consumers before switching server error shapes. During rollout, consumers may read legacy errors for display; refresh must not fall back to text matching. Deploy compatible client parsing before server envelope adoption.

## Backend provider outbound policy

Provider adapters own base URLs, credentials, finite connect/read timeouts, parsing and safe failures. Never forward a user's bearer token. Unify the configured ESPN timeout behavior when this client is touched. Default to no new automatic retries; future retries require an operation-specific idempotency and total-budget decision. Avoid provider network waits inside database transactions during new service design. Existing provider/job recovery behavior changes require their own scope and tests.

## Deferred decisions and costs

Rate limiting is explicitly deferred: no counters, storage, quota values, 429 policy or limiter library. Revisit when observed abuse, sustained resource pressure or unexpected usage costs justify it. A later decision must establish proxy trust, keys, endpoint costs, multiworker consistency, exemptions and outage behavior before implementation. Do not represent Render hosting as proof of application-level rate enforcement.

Exact proxy topology, deployed instance/worker configuration, request limits and timeout values remain evidence tasks. They do not block agreement on layer ownership. Render bills compute and metered usage; this design adds no required paid service and no guaranteed bill reduction.

## Work ownership and MOD-038 consequences

| Work | Owner |
| --- | --- |
| Architecture/order and exemptions | MOD-041 decision |
| Safe REST errors, payload bounds, headers and future rate enforcement | MOD-019 |
| API-origin token handling, structured auth recovery and client parsing | MOD-028A; coordinate MOD-028B consumer errors |
| Request correlation and sanitized operational metrics | MOD-024 with MOD-019 |
| Dependency injection, hook registration and separate listener/job startup | MOD-034 |
| Actor types, domain failures, service transactions and repository connections | MOD-038; pilot MOD-040 |
| Provider timeout/retry implementation | Separately bounded provider work; no implicit implementation authorization |

MOD-038 may proceed with its selected incremental hybrid after this decision is approved. Domain services cannot depend on Flask `g`, jsonify, HTTP status codes or middleware invocation. Request metadata is optional execution context, separate from authority; jobs can supply execution IDs without acquiring interactive privileges. Compatibility facades preserve existing callers until deliberately migrated.

## Verification required for implementation

Use synthetic identities, fake providers and isolated backend tests; never use deployment or production rows as verification.

- Public/protected/bootstrap/OPTIONS/disabled routes retain their explicit behavior; forged body identities and job flags cannot grant access.
- Missing/invalid JWT and missing/ambiguous profile outcomes have distinct codes; service work is never invoked on authentication denial.
- Success, early denial, validation failure, 404/405/413 and unexpected 500 have intended headers and safe bodies. Preserve 405 Allow and configured CORS behavior.
- Cross-origin/path destinations, redirects and caller-supplied credentials cannot leak or trigger replacement of bearer credentials.
- Concurrent expired requests share refresh; retry occurs once; permission denial never refreshes; consumed bodies and ambiguous mutation failures never replay.
- Cancellation and timeout cover initial and replay calls; provider failures respect finite budgets and do not leak secrets.
- Existing authorization/replay/atomicity suites remain green. Test app construction with injected dependencies and no network/listener startup under MOD-034.
- Multiworker limiter consistency tests are deferred with the limiter; no such guarantee is claimed.

This document records a design, not passing implementation tests. User approval completes the MOD-041 decision scope; implementation plans and MOD-038's detailed architecture remain separate work.

## References

- [Flask request lifecycle](https://flask.palletsprojects.com/en/stable/lifecycle/): hook short circuits, error handling and response finalization.
- [Flask proxy guidance](https://flask.palletsprojects.com/en/stable/deploying/proxy_fix/): trust only verified proxy topology.
- [Render pricing](https://render.com/pricing): hosting costs versus optional infrastructure.
