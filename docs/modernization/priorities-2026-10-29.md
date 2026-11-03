# Backlog priorities after MOD-001–003

2026-10-29. Planning update, not an approved architecture migration. MOD-001, MOD-002/002A and MOD-003A/B/C are complete within their recorded application scopes. Latest backend evidence is 345/345 isolated tests from MOD-003C; no tests were rerun for this document. Deployed policies, PostgreSQL concurrency and runtime configuration remain unverified.

## Recommended order

| Order | Work | Why now / execution boundary |
| --- | --- | --- |
| 1 | MOD-009 trade application guards; MOD-007 atomic score replacement | Next actionable implementation: MOD-009. Trusted jobs still reach these functions. HTTP authorization does not stop replayed ownership transfers or protect scores deleted before a replacement fails. Independent model fixes can proceed without schema changes. |
| 2 | MOD-005 baseline/provenance; MOD-004 policy/privilege evidence | Begin source-only provenance and access-matrix preparation early. Disposable PostgreSQL becomes the foundation for constraints/concurrency checks. External metadata unavailability must not stall independent fixes; no production access is authorized by this plan. |
| 3 | MOD-038 API layering discussion; MOD-041 interceptor discussion | Short decision tasks before structural refactoring and request-pipeline implementation. Can occur before or between the first correctness fixes; do not require a rewrite or delay them. |
| 4 | MOD-025 draft order/start replay; MOD-034 startup isolation; MOD-019 errors/resource limits + MOD-028A auth refresh | Protect another replay-sensitive write path; make web/job/test boundaries explicit; align auth error codes and bounded retries. Startup work implements lifecycle decisions, not a prerequisite to fixing every domain bug. |
| 5 | MOD-006 identity uniqueness; MOD-008 score/week keys; MOD-010 ownership concurrency; MOD-011 PostgreSQL verification; MOD-012 admission serialization | Follow their baseline/preflight/decision dependencies. MOD-011 code repairs already exist; validate them rather than reimplementing. Real PostgreSQL is necessary for the corresponding locking/constraint claims. |
| 6 | MOD-013 weekly completion/retry; remaining MOD-014 finalization; MOD-015 seasonal membership; MOD-016 history safeguards; MOD-023/024 draft convergence/operations | Domain integrity and recovery. Respect the original dependency graph: for example, MOD-013 follows atomicity/application/concurrency fixes; MOD-016 follows period/history decisions. MOD-014 still needs construction/completion/failure handling despite the direct model-call repair. |
| 7 | MOD-039 shared-function pilot; MOD-040 structural pilot; existing MOD-029–033 decomposition | Helpers with identical semantics can be extracted sooner alongside touched code. Domain-rule consolidation waits for correctness/policy fixes. File moves and behavior changes get separate reviews. |
| 8 | Remaining MOD-026–028 UI/auth/feedback, performance MOD-017/018/020–022, cleanup MOD-030/035–037 | Small demonstrated UX/accessibility defects can ship sooner independently. Performance work begins with measurements. Broad cleanup does not displace data integrity. |

Rows describe scheduling preference, not permission to bypass dependencies or execute multiple MODs automatically. Existing IDs remain stable. P0/P1 express urgency; this queue expresses what is actionable next. No production deployment, migration, metadata access or new infrastructure installation is authorized here.

## API structure discussion: MOD-038

Today: routes register URLs; endpoint classes parse Flask requests, resolve identity and serialize responses; large Model classes combine business orchestration, SQL and connection handling. Jobs sometimes construct endpoint objects to reach their models. Authorization and input helpers now exist, but transport error handling and resource SQL predicates still repeat.

Compare three approaches before choosing:

| Approach | Benefits | Costs / appropriate use |
| --- | --- | --- |
| Retain routes/endpoints/models, split large model responsibilities | Smallest migration; useful where a model is already cohesive | Names still obscure the difference between business operations and persistence |
| Domain packages with routes/schemas/services/repositories | Explicit transport, use-case and SQL responsibilities; shared service entry for HTTP/jobs | More interfaces and transaction ownership to design; avoid layers that merely forward every call |
| Incremental hybrid (recommended for discussion) | Define responsibility boundaries now; introduce schemas/services/repositories in one domain as justified; preserve existing facades | Temporary mixed structure needs a documented migration rule and end-state decision |

Schemas validate/serialize data; they are not an execution layer between every component. Routes and endpoint/controller responsibilities can be combined or retained based on readability. A service owns a use case and transaction boundary; repositories execute scoped SQL using the caller's connection and do not independently commit. Resource authorization stays at the service/transaction boundary even when middleware verifies identity. Jobs call services/domain logic without inventing an HTTP principal.

Illustrative candidate, not an approved target or scaffold:

```text
api/
  app.py                      # composition and lifecycle
  middleware/                 # transport-wide hooks
  shared/                     # only demonstrated cross-domain primitives
  domains/transactions/
    routes.py                 # HTTP adapter / controller
    schemas.py                # input/output boundary
    service.py                # use cases, authority, transaction ownership
    repository.py             # scoped persistence using supplied connection
  jobs/                       # service callers, explicit startup
```

Keep domain code together rather than adopting global routes/services/repositories folders by default. Compare one simple read and one transactional command using actual call graphs. Decide facade strategy, exception contracts, actor types (interactive versus trusted), connection passing, dependency direction, import/startup behavior and how test fixtures follow domains. Flask Blueprints are a registration option, not a substitute for these decisions. See [Flask Blueprints](https://flask.palletsprojects.com/en/stable/blueprints/).

## Refactoring and shared functions: MOD-039/040

Inventory duplication with callers and semantic differences before extracting. Current candidates: integer/array validation, principal/error translation, member ownership/full-read predicates, connection-aware transaction guards, JSON/date serialization and frontend API error parsing. Reuse existing `requestValidation`, `authorization`, `authenticatedPrincipal` and `apiFetch` first. Preserve intentional policy distinctions: full-read commissioner access does not grant roster-write ownership; a veto voter is not a trade participant; disabled HTTP commands cannot acquire a job bypass.

Separate four kinds of change: content extraction, import-only moves, intentional behavior fixes and performance optimization. Start with one helper used by two callers; then one domain's file-structure pilot. Do not create generic base repositories/controllers, a universal decorator stack, or a shared utilities dumping ground. Ownership/conference/scoring extraction remains MOD-033/032 after its prerequisites. Frontend content refactors remain MOD-029/031 and structure changes use MOD-040 with consumer/import checks.

## Incoming/outgoing interceptors: MOD-041

Current incoming server boundary: Flask `before_request` in authMiddleware checks public allowlists/OPTIONS, verifies JWT and writes `g.user`. Principal lookup and resource authorization occur downstream. CORS is configured in the app factory; sockets have their own authentication path. No repository-wide rate-limiting policy is established by the inspected code. Current browser `apiFetch` adds bearer credentials and has a text-based refresh condition that misses the server's invalid/expired-token message (MOD-028A).

Discuss three distinct directions rather than treating all traffic as one interceptor:

| Boundary | Proposed responsibilities to decide |
| --- | --- |
| Incoming HTTP | Trusted proxy handling and size limits; request IDs; coarse abuse limits before expensive authentication; JWT verification; principal-aware quotas after verification; route validation and transactional resource authorization. Preserve bootstrap/public/OPTIONS and disabled-route behavior deliberately. |
| Outgoing HTTP responses | Stable safe error codes/envelopes and headers, correlation ID, CORS/security/cache policy and sanitized completion metrics. Error and early-return responses must be covered. Resource-specific response projections remain explicit. |
| Outbound clients | Browser: token attachment only to intended API origins, bounded auth refresh, cancellation/timeouts and safe errors. Backend provider clients: their own credentials, timeouts/retry budgets and provider quotas; never forward a user's bearer token automatically. |

Flask offers `before_request`, `after_request` and error handlers; WSGI middleware wraps the application. Their order and exception/short-circuit behavior must be designed and tested rather than inferred from decorator names. See [Flask lifecycle](https://flask.palletsprojects.com/en/stable/lifecycle/) and [error handling](https://flask.palletsprojects.com/en/stable/errorhandling/).

Rate-limit decisions: deployment/gateway responsibilities, trusted proxy topology, unauthenticated IP versus verified-subject keys, endpoint classes and costs, body/array bounds, burst/sustained limits, multiworker shared state, 429/Retry-After contract, exemptions and outage policy. Do not select an in-process counter, Redis, quotas or a library without those answers. A rate limiter does not replace ownership checks. Never refresh sessions on ordinary permission denial or blindly retry possibly committed mutations. Avoid logging tokens, body secrets or private rows.

MOD-041 produces the decision and pipeline ownership/order; MOD-019 owns safe-error/resource/rate enforcement; MOD-028A owns browser auth refresh; MOD-024 owns operational telemetry; MOD-034 owns startup registration/injection. These are linked responsibilities, not duplicate implementations.

## Immediate next action

Choose MOD-009 for the next implementation run: inspect the locked application path and pending dispatcher, define replay outcome and add isolated fault/state tests. Keep PostgreSQL concurrent-apply verification explicitly outstanding until disposable infrastructure is available. If the user prefers the architecture conversation first, start MOD-038 as a decision-only task; present the alternatives above and obtain agreement before writing a migration design or product code.
