# MOD-038: API layering and dependency ownership

Date: 2026-10-29. Status: draft for user approval. The incremental hybrid is the user's selected approach; concrete interfaces, file placement and pilot below are architecture proposals. MOD-041 is approved; its authentication slice is implemented locally. No structural implementation is performed by this decision task.

## Intent, scope and constraints

Separate transport, use cases and persistence so HTTP and jobs share domain operations without constructing HTTP adapters. Keep domain code together and migrate only when a bounded extraction improves ownership. Retain Flask, SQLAlchemy/raw SQL, existing routes, table names and the current Render service. No new dependencies, paid infrastructure, schema changes or rate limiter.

Avoid pass-through layers on every method, generic CRUD base classes, repository-per-table rules and a global utilities bucket. A cohesive existing model may remain unchanged. New services must own real policy/orchestration or transaction boundaries; schemas and repositories appear where they separate actual responsibilities.

This decision defines an incremental end state, not a repository-wide rewrite. Existing correctness cards retain their scope. Tests and transaction guarantees must survive extraction; a file move is not evidence of correctness or performance improvement.

## Approaches and selection

| Approach | Benefit | Cost |
| --- | --- | --- |
| Retain routes/endpoints/models, split large files | Least disruption | Model naming still hides use-case versus SQL ownership |
| Convert all domains to routes/schemas/services/repositories | Uniform layout | Broad migration, many unnecessary interfaces and transaction risks |
| **Incremental hybrid, selected by user** | Explicit ownership introduced domain by domain with stable facades | Temporary mixed layout requires clear migration rules |

## Responsibility map

| Boundary | Owns | Does not own |
| --- | --- | --- |
| Application composition | Dependency construction, route registration, lifecycle configuration | Business rules or implicit listener/job startup in reusable imports |
| HTTP adapter | Request parsing, verified-principal resolution, command construction, response serialization and safe error/status translation | SQL, commits, resource authority inferred from body IDs |
| Schema/contracts | Plain validated command/result structures and wire conversion where needed | Executing use cases, DB access or permission decisions |
| Service | Resource/role/state authorization, business orchestration, connection/transaction scope | Flask globals, jsonify, HTTP status codes or provider credentials |
| Repository | Parameterized queries, scoped reads/writes, explicit row-lock queries using supplied connection | Creating engines, independent connections, commits or deciding who has business authority |
| Domain rules | Pure rules and policy decisions using supplied facts | Transport or hidden I/O |
| Jobs/workers/listeners | Explicit trusted operation selection and scheduling/recovery | Constructing endpoints or synthesizing an interactive principal |

Schemas start with existing requestValidation helpers and standard-library dataclasses/TypedDict where useful. No mandatory Pydantic/Marshmallow layer. Transport validation checks shape/types; services still enforce business invariants for every caller. A DTO is not proof of authentication.

## Proposed layout and dependency rules

For the first extraction, add files within the existing domain package rather than moving every domain into a new top-level directory:

```text
api/
  authenticatedPrincipal.py       # existing Flask subject-to-user resolver
  actors.py                       # canonical transport-independent UserActor
  utils/authorization.py         # existing helpers; scoped extractions below
  endpoints/transaction/
    routes.py                    # existing registration
    transactionEndpoints.py      # existing HTTP adapter
    transactionModel.py          # remaining methods + compatibility facade
    contracts.py                 # only pilot commands/results/failures
    service.py                   # pilot use cases and transaction ownership
    repository.py                # pilot SQL on supplied connection
  tests/
    ...                          # existing suites keep their import paths
    transaction/                 # new pilot fixtures/suites when runner supports discovery
```

Keep the existing `endpoints` parent name during the pilot; its historical name is not a dependency permission. A later import-only move to `api/domains/transaction` is optional MOD-040 work, only after caller/import evidence justifies it. No promise to rename every existing domain.

Allowed dependencies: adapters and jobs → service/contracts; service → repository/pure policy; repository → SQLAlchemy and plain contracts. Neither service nor repository imports endpoints, configured `db`, the app factory or compatibility models. The model facade may call the service, never the reverse. Cross-domain calls use a deliberately exposed capability/policy, not another model's private methods.

New files use simple snake_case module names; existing mixed-case import paths stay stable. New test subdirectories require `__init__.py` and verification that `api/tests/run_isolated.py` discovers them; retaining new tests directly under `api/tests` is preferable if nested fixtures complicate imports. Test layout must not force a production folder move.

## Actor and trusted-entry contracts

Propose immutable `UserActor(user_id: int, subject: str)` in `api/actors.py` as the canonical transport-independent application identity value shared by adopting domains. HTTP constructs it only from the existing resolved principal; client-provided user/member IDs remain resource selectors to authorize, not actor identity. Keep optional request/execution metadata separate from authority. Services do not read Flask `g`.

Expose user-facing methods requiring an actor, for example `list_transactions(actor, league_id, status)` and, in a later slice, `respond_to_trade(actor, command)`. An omitted actor is an error; `None` must not mean unrestricted access in a new interactive API.

Trusted operations have named entry points, for example `apply_trade_for_job(transaction_id)` and `list_transactions_for_job(league_id, status)` if an actual trusted read caller needs migration. Do not create unused trusted methods. These operations never accept an HTTP principal or an `is_job`/`skip_auth` boolean. Their name expresses the composition boundary, not an unforgeable Python security capability; only approved process wiring exposes them. Domain state/type/deadline/ownership invariants still apply.

## Representative call graphs: read

Observed registered read:

```text
GET /api/league/<league_id>/transaction/pending
  → TransactionEndpoints.get_transactions_for_league
  → resolve_authenticated_principal(engine)
  → TransactionModel.get_transactions_for_league(reader_user_id=principal.user_id)
  → LeagueModel._league_read_scope
  → existence/access query, then projection query with repeated access scope
```

Proposed pilot:

```text
same route → same adapter → principal → UserActor
  → TransactionService.list_transactions(actor, league_id, status)
  → connection scope owned by service
  → repository access query and scoped projection query
  → plain result → same adapter serialization/status
```

Keep default `PENDING_APPLY`, explicit status filtering, projection keys and ordering. Preserve commissioner-or-member full-read policy and concealed League-not-found 404 semantics. Preserve the access predicate on the data query; a successful earlier access check cannot authorize an unscoped later read. Do not promise serializable reads or immediate concurrent revocation guarantees.

The service supplies one read connection for participating queries. This is an intentional connection-ownership change, not an import-only move; review it separately and retain statement-level access predicates and the configured isolation behavior. Do not add locks or change isolation to disguise race guarantees.

## Representative call graphs: command and job

Observed trusted command:

```text
weekly scoring job → TransactionModel.apply_pending_transaction
  → advisory transaction type/status read
  → TransactionModel.apply_trade
  → begin → SELECT transaction FOR UPDATE
  → locked type/status check → deadline and scoped week lookup
  → trade ownership/conference validation
  → close ownership intervals → insert new ownership → COMPLETED → commit
```

Proposed trade-only pilot:

```text
existing dispatcher/facade → TransactionService.apply_trade_for_job(id)
  → service begins transaction
  → repository locks and returns transaction facts
  → service checks state/type, loads facts and enforces rules
  → repository closes/inserts ownership and marks complete
  → service transaction commits, or rolls back on any failure
```

The dispatcher may remain a compatibility caller during this pilot. Its advisory read never replaces the locked check. Preserve the MOD-009 contract: only pending trades apply; replay raises a compatible ValueError through the legacy facade; success returns None. Ownership intervals, deadlines, scoped week lookup, locks and failure rollback remain unchanged.

Do not route a service back through legacy model validation: extract the minimum helper/rule/query closure needed for the command. If this closure would pull in the entire transaction model, reduce the pilot to the read first and size the command extraction separately. Free-agent dispatch remains on its current implementation unless separately included.

HTTP trade application stays disabled (authenticated 410). Do not expose a job method through the existing disabled route. User trade responses remain outside the first extraction: the inspected response path calls a helper that opens another connection inside the command transaction, and moving that lookup changes connection behavior. Track and design that separately rather than silently fixing it during a folder move.

## Transaction and cross-domain policy ownership

Services call `engine.begin()` for commands and supply the resulting connection to every participating repository/helper. Repositories accept a connection explicitly and cannot commit or hide additional connections. Keep lock order and isolation unchanged unless a separately reviewed correctness change requires otherwise.

When a larger use case truly spans domains, one orchestrating service owns the outer transaction and calls explicit connection-aware capabilities. Do not call two engine-owning public service methods and pretend they are atomic. Introduce an internal `..._in_transaction(conn, ...)` capability only for a demonstrated caller; do not scaffold a generic unit-of-work framework.

The transaction read currently imports `LeagueModel._league_read_scope`; `utils.authorization.league_read_access` also imports LeagueModel internally. Extract only the demonstrated full-read SQL policy into a connection-neutral helper in `utils/authorization.py`, with stable parameter names and no I/O/commit. LeagueModel may delegate to it to preserve imports, and new repositories may reuse it. Retain owned-member checks separately: commissioner full-read access does not imply roster/trade ownership. Leave broader ownership/conference rule consolidation to MOD-033.

## Failure and compatibility strategy

New contracts define explicit domain failures for concealed resource denial, rejected command and missing trusted resource. They carry stable internal codes and safe approved messages, never HTTP status codes. Repository/driver exceptions propagate out of the service transaction to trigger rollback.

Adapters map specific failures to existing resource outcomes; they do not globally map every PermissionError to 403 or ValueError to 400. MOD-041 owns the target wire envelope; MOD-019 adopts broader safe-error translation. Structural extraction initially preserves current response bodies/statuses rather than migrating every error contract at once.

Legacy model methods retain signatures, constants, dict/None return shapes and appropriate built-in exception compatibility through thin delegation/translation. In particular omitted `reader_user_id` preserves trusted legacy behavior only inside the compatibility facade, never inside the new interactive service. Existing monkeypatch points are inventoried: do not keep a fake facade whose delegation silently bypasses patched collaborators in real jobs/tests. Retire a facade only after all HTTP/job/CLI/test callers are migrated and removal is independently reviewed.

## Composition, lifecycle and effects

Construct services/repositories from injected engine dependencies at the route/job composition root. Imports must not load dotenv, create a configured engine, open network connections, register global handlers or start listeners. MOD-034 owns injectable app construction and explicit listener/job startup. The pilot can test service and registration modules independently without finishing every MOD-034 concern, but must not use production app startup as verification.

Keep provider calls and nontransactional effects outside command transactions. Existing notification behavior is preserved; reliable post-commit delivery/outbox infrastructure is not added by this architecture decision. New effect guarantees require explicit design and their own task.

## Pilot acceptance and sequencing

1. Plan one protected transaction-list read and the trusted trade-apply command as separately reviewable slices. Inventory callers and helper dependencies before choosing exact extraction size.
2. Extract demonstrated policy/helpers and domain content before any optional folder move. Keep behavior fixes and wire-error changes separate.
3. Preserve HTTP paths, projections, default status, hidden-resource outcomes, disabled commands and direct model/job signatures.
4. Verify no cycles or service-to-model back edges; imports work without environment/DB/listener startup. Verify real route registration and compatibility mocks/CLIs/jobs affected by the extraction.
5. Run the existing isolated backend authorization, trade replay and rollback suites plus focused service/repository tests. Retain real PostgreSQL concurrent-apply evidence by rerunning the affected disposable tests before claiming unchanged lock/concurrency guarantees; SQLite/fakes alone cannot reestablish those guarantees after extraction.
6. Pilot rejection conditions: a repository commits, an actor defaults to trusted, a job constructs endpoints, a service imports Flask/model facades, a resource predicate disappears, or an import-only move includes behavior changes.

No application tests are rerun for this decision draft. Historical MOD-041 application results remain 359 backend / 62 frontend tests, build and targeted lint passing; those results do not verify a future extraction.

Builder check: independent planning review found no important unanswered questions. No architecture approval or implementation completion is implied by that check.

## What remains to the implementation planner

Choose exact method signatures/types and command extraction size after the dependency inventory; retain the ownership rules and compatibility contracts above. Pick test fixture placement compatible with current discovery, without framework installation. Write a bounded MOD-040 implementation plan after user approval; do not infer approval for a repository-wide migration.
