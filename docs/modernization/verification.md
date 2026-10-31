# Regression verification baseline

## MOD-035 league forwarding module retirement — 2026-10-30

Removed 10 pure module-alias forwarders after migrating every first-party caller to canonical package imports. Retired admission_service/repository, member_service/repository, league_admin_service/repository, league_read_service/repository and league_lifecycle_service/repository. Root contracts.py remains because the explicit old exception unpickling contract is still tested. All 8 Model facades remain for runtime/test/tool callers. Outside-repository Python consumers were not independently inventoried; these internal forwarding paths are intentionally retired. Public HTTP/data/schema/authorization/scoring behavior is unchanged.

| Verification | Result |
| --- | --- |
| Guarded baseline and full suite | 564/564 before and after; no test-count reduction |
| Test first | 10 expected retired-import subtest failures before deletion → focused3/3 GREEN |
| Retained coverage | Canonical repository patch composition; old contracts.find_class exception resolution, cross-path catch, pickle roundtrip |
| Source proof | All16 canonical implementation files byte-identical;28 migrated caller ASTs differ only in imports and league-rooted manifest literals; removed files contain only docstring/import/module-alias assignment |
| Caller/manifest audit | No active api/scripts imports of deleted modules; standalone native source manifest targets all exist and scripts compile without configured imports |
| Native league regression | Full verify_league_folders.py PASS including all admission/member/admin/read/lifecycle/callback suites; current report has40 source captures and no deleted paths |
| Independent review | Attempted; subagent failed due session usage limit and returned no review. Local manual diff/source/hash audit completed; independent review unavailable |
| Final checks | Current domain/retirement hashes, internal links and diff check pass |

[Retirement evidence](evidence/mod-035-league-forwarder-retirement-2026-10-30.json), [fresh native league evidence](evidence/mod-040-league-folders-postgres-2026-10-30.json), [ledger](../superpowers/plans/2026-10-30-league-legacy-forwarder-retirement.md). Historical reports/plans may reference removed paths as prior source captures; they are not rewritten as fresh verification. No runtime implementation, route, deployment, schema or dependency change. Only a marked owned loopback DB/container was used and removed; checkout uncommitted. Cleanup is bounded to migration-created forwarders, not a claim that every legacy model/feature/operational path can be deleted.

## MOD-038 complete transaction workflow and final backend audit — 2026-10-30

Remaining31 model SQL calls now use named workflow repository queries; fixed role/reader fragments and shared ownership routing reside there. Canonical workflow composes the untouched initial transaction pilot. Actor entry points reject missing/non-UserActor before I/O; HTTP resolves real principals, jobs call explicit trusted APIs. Model retains exact constructor/inherited helpers/constants/exception identity with no SQL. No route or policy is added.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | 557/557 |
| Test first | Seven RED cases: six missing workflow and original unregistered week-lock self.db AttributeError; GREEN7/7 |
| Full guarded backend | 564/564; reviewer independently ran full suite successfully |
| Direct workflow | Actor-before-I/O across6 operations, own/wrong proposal, role/accept/cancel/veto toggle, effective-week pending free agency/swap exception identity, post-action rollback, legacy override/db-only protocol and working unregistered lock helper |
| `python3 scripts/modernization/verify_transaction_complete.py` | PASS all33 workflow operations:31 migrated queries plus shared entitlement and week-lock operations, actual JSONB/arrays/LATERAL/executemany, actor/role/scope/status/deadline/swap/caps/pending/effective-week guards, full DTOs and dispatch/application/replay |
| Native failure/concurrency | Phase mutation rollback, real statement/deferred-commit failure, postwrite authority loss rollback, query-time personalized-read revocation and observed pg_stat_activity cancellation row-lock wait followed by replay rejection |
| Original pilot rerun | Both direct/dispatcher native trade-apply concurrency/replay and checked read projection/revocation suites PASS |
| Affected integrations | Complete schedule30-query/fake-provider/checkpoint suite and complete scoring suite PASS; changed weekly-job dependency captures refreshed |
| Independent final review | No Critical/Important/Minor findings; all33 methods/31 SQL AST proof and fresh full suite |
| Source/architecture audit | All33 original algorithms unchanged after explicit query/entitlement/role substitutions; all31 text-call ASTs and fixed role mapping exact. Model and HTTP adapter contain no SQL execution, canonical layers import no model/HTTP/configured engine. All8 domain model files now have no execute calls |

[Complete transaction results/source hashes](evidence/mod-038-transaction-complete-postgres-2026-10-30.json), [final eight-domain audit](evidence/mod-038-backend-extraction-audit-2026-10-30.json), [refreshed schedule](evidence/mod-038-schedule-complete-postgres-2026-10-30.json), [refreshed scoring](evidence/mod-038-scoring-complete-postgres-2026-10-29.json), [ledger](../superpowers/plans/2026-10-30-mod-038-transaction-complete-implementation.md). Eight complete domain reports/source hashes are current; original transaction pilot and schedule slices remain historical. The previously recorded22-method transaction remainder is resolved, with its prior inventory retained in the audit.

The unregistered week-lock helper previously failed at undefined self.db after successful validation. Its regression was watched RED and corrected by moving original UPDATE to repository/service; it stays unregistered, keeps validation/update as separate scopes and adds no public permission. HTTP trade apply stays410. Preserve existing free-agent apply validation/separate week lookup, helper connections, dispatcher preflight/application locking, reject/deadline and ownership postcheck boundaries, cap/membership/swap/projection semantics. No new schema/dependency/auth/timeout/correctness/startup policy. Only marked owned synthetic databases/container used and removed; no configured app/job/provider/hosted/deployment work. Checkout remains uncommitted.

Planned backend content extraction is complete across all8 domains. Broader MOD-040 frontend/optional folder work and separately tracked correctness/startup items remain open; SQL-free model source audit does not imply those are complete.

## MOD-038 schedule completion and rollout audit — 2026-10-30

ScheduleModel is a SQL-free facade with its original constructor/inherited helper dispatch. Canonical ingestion owns provider/config/phase/upsert/bootstrap/checkpoint operations and active-league facts; original SQL now lives in its repository. HTTP uses read service/member aggregate with original response/scopes; league callbacks/scoring builders/routes/rebuild receive canonical read/calendar capabilities without provider configuration. Season setup/ingest cron use trusted ingestion; metadata retains caller connection. Existing dotenv/startup policy and HTTP week-generation410 remain.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | 545/545 |
| Test first | Ingestion7 and composition5 cases RED for missing module/method/seam → GREEN12/12 |
| Full guarded backend | 557/557; independent reviewer also557/557 |
| Composition | Actual four read HTTP routes/envelopes/coercion/raw echoes, error mapping, disabled410 with no service call, member aggregate rule resolution/callback order; actual compiled scoring builders need no provider URL. Existing moved test seams updated without weakening assertions |
| Complete native schedule | PASS all30 query operations:7 calendar,10 read,13 ingestion; actual JSON/groups/LIMIT/phase/shared-current-membership/ON CONFLICT/null team/supplied connection, statement/deferred/caller rollback and per-game partial commits |
| Provider/checkpoint | Actual ESPN event parser with synthetic fetches only; group dedupe vs league counts, team fetch failure completion, real temporary partial/resume/force/skip/failed-day retry, complete-file-before-metadata-commit failure and retry convergence |
| Native integrations | Full league/lifecycle/callback and scoring read/remaining suites PASS; affected source captures refreshed |
| Independent final review | No Critical/Important/Minor findings; full557/557 and AST checks |
| Original-source proof | All35 original model method ASTs preserved after query/client substitutions;29 original model plus1cron SQL text-call ASTs exact. Optional team LIMIT moved intact behind same maxTeams param presence. Exact facade constructor retained, no SQL/connection acquisition there; canonical dependencies and diff checks pass |

[Complete schedule source hashes](evidence/mod-038-schedule-complete-postgres-2026-10-30.json), [refreshed league](evidence/mod-040-league-folders-postgres-2026-10-30.json), [refreshed scoring](evidence/mod-038-scoring-complete-postgres-2026-10-29.json), [plan/ledger](../superpowers/plans/2026-10-30-mod-038-schedule-complete-implementation.md). Complete report supersedes earlier calendar/member/views source captures; those remain historical. Eight domain reports are current, with transaction explicitly a partial pilot.

Original policy retained: no new global/per-run transaction; Week0 and each game may remain committed after later failure. Team bootstrap still marks bootstrapped despite individual team fetch failure. League and sport-season event counting/dedupe differ. Checkpoints are not database-atomic. Prior NULL-score/H2H/membership-duplicate behavior remains. No actual provider request, configured app/job/listener startup, hosted/schema/dependency/deployment changes. Only owned marked loopback DBs/container and temporary checkpoint folders used and removed. Work uncommitted.

**Corrected backend scope:** [Source audit](evidence/mod-038-backend-extraction-audit-2026-10-30.json) found seven SQL-free model facades and22 remaining SQL-bearing TransactionModel methods. The prior “only sport/schedule remain” count was incorrect: transaction listing/trusted-apply pilot was partial. Do not mark the backend migration or broader MOD-040 complete; remaining transaction trade/free-agency/dispatch/reads require follow-up. Audit records source hashes/method names, not a claim that every backend/job/frontend boundary has been refactored.

## MOD-038 schedule conference/team views and search — 2026-10-30

Six methods (week window, conference games, team-season games, normalization, rank and search) and six exact queries extend the existing read service/repository. Existing member/calendar behavior is unchanged; remaining12 model methods and constructor are identical. Three explicit trusted internal view/search capabilities retain caller policy. HTTP adapters, input coercion/envelopes/errors and disabled week generation are unchanged; final caller composition is separate.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | 538/538, exit0 |
| Test first | Seven tests: RED8 missing-method errors across cases/subtests, original legacy case passes; GREEN7/7 |
| `python3 api/tests/run_isolated.py` | 545/545, exit0 |
| Direct cases | Normalization/rank precedence, stable projection/limit clamp0/negative/50, short-query no-I/O and invalid limit ordering, missing league/window, separate conference scopes, optional team context/999 fallback, shared context scope, failure unwind and legacy classmethod/window overrides |
| `python3 scripts/modernization/verify_schedule_views_search.py` | PASS6 new +4 earlier read queries (combined10/10) and all7 calendar queries; native LATERAL current before latest/no-week999, NULL optional league binds, actual conference/season/date/ownership/opponent/flags/projection, rank/limits/season-global membership duplicates/missing cases/read errors/no writes/legacy |
| `python3 scripts/modernization/verify_league_folders.py` | PASS full prior league/lifecycle/callback suites; changed model dependency capture refreshed |
| Independent final review | No findings; fresh focused7/7 and AST check |
| AST/import/diff | Six moved algorithms and SQL text-call ASTs identical; existing read service/repository methods unchanged;12 remaining model methods including constructor unchanged; canonical imports independent of model/HTTP/provider/configured engine; diff check passes |

[Current views+read+calendar source hashes](evidence/mod-038-schedule-views-postgres-2026-10-30.json), [refreshed league callbacks](evidence/mod-040-league-folders-postgres-2026-10-30.json), [plan/ledger](../superpowers/plans/2026-10-30-mod-038-schedule-views-search-implementation.md). Current report supersedes earlier member/calendar source captures; previous reports retained as history. Seven completed-domain reports plus this scoped combined report hash-checked.

Original semantics retained: conference week-window lookup owns a separate transaction; team-season/search context+rows share one begin. Whole-season ownership uses current/latest/999 rather than game-date ownership. Missing optional team context falls back while search missing league raises. Season/global membership joins can duplicate search rows; no deduplication added. Limit conversion occurs before short-query guard. Prior NULL-score/H2H behavior is retained in the earlier suite rerun. Native member harness coverage is now explicitly scoped to its original4 methods; combined harness asserts all10, avoiding a false failure when the repository grows.

Only marked task-owned loopback databases/container used and removed. No schema/dependency/hosted/deployment/startup or authorization-policy changes; work uncommitted. Ingestion/bootstrap and final HTTP/job/cross-domain caller composition remain.

## MOD-038 schedule member/week reads — 2026-10-30

Four related methods now use ScheduleReadService/Repository: member-week games with tier and tournament scoring, H2H games, week row and owned teams. Read service inherits calendar; ScheduleModel inherits read service and preserves constructor/helper overrides/db-only instances. Four named trusted capabilities retain internal caller policy; HTTP/job adapter wiring remains a later schedule slice.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | 531/531, exit0 |
| Test first | RED7 missing-service errors → GREEN7/7 policy/projection/failure/legacy tests |
| `python3 api/tests/run_isolated.py` | 538/538, exit0 |
| Direct policy | Home/away/double-owned perspectives, unchanged source facts, positive-only/multiplier phases, invalid rules before query (including empty), supplied rules bypass, plain/missing projections, read failure unwind, inherited overrides |
| `python3 scripts/modernization/verify_schedule_member_reads.py` | PASS4/4 read queries plus all7 calendar queries rerun: actual ownership/league/week/season/sport/inclusive boundary filtering, acquisition/drop, tier fallback, both perspectives, double-owned, phase JSON/math, H2H direction, exact week/owned projections, missing rows, read errors/no writes and legacy |
| `python3 scripts/modernization/verify_league_folders.py` | PASS full native league/callback/lifecycle suites; dependency source capture refreshed |
| Independent final review | No findings; reviewer ran direct7/7, compared query strings and remaining methods |
| AST/import/diff | Four migrated algorithms identical after named-query substitution;18 remaining methods including constructor unchanged;4 SQL text-call ASTs exact; canonical layers import no HTTP/model/provider/configured engine; diff check passes |

[Current native read+calendar hashes](evidence/mod-038-schedule-member-reads-postgres-2026-10-30.json), [refreshed league callback report](evidence/mod-040-league-folders-postgres-2026-10-30.json), [plan/ledger](../superpowers/plans/2026-10-30-mod-038-schedule-member-reads-implementation.md). New scoped report supersedes the earlier calendar report's model source capture; earlier report retained as history. Seven completed-domain reports and the current read/calendar report are hash-checked.

Original edge semantics deliberately retained and exercised natively: member/week queries supply a missing-start fallback while H2H does not; owned-team conference joins are not season-filtered and can duplicate rows; NULL game scores propagate the existing TypeError from scoring. This is extraction, not scoring/authorization/data-policy repair. No HTTP/actor/profile policy, dependency/schema/hosted/deployment or startup changes. Marked task-owned DB/container removed; prior work retained/uncommitted. Other views/search, ingestion/bootstrap and final composition remain.

## MOD-038 schedule calendar/week foundations — 2026-10-30

First schedule slice extracts13 calendar methods and seven named queries. ScheduleModel inherits legacy methods/helper dispatch and keeps original constructor and remaining22 methods; constants are shared aliases. Canonical service needs no provider URL/client and exposes trusted week-generation/boundary/timezone capabilities. HTTP generation stays410; other reads/ingestion/bootstrap/composition remain separate.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | 524/524, exit0; prior sport work preserved |
| Direct-service tests | RED7 missing calendar service; GREEN7/7, real SQLite |
| `python3 api/tests/run_isolated.py` | 531/531, exit0 |
| Calendar behavior | Basketball opening/DST UTC plan equals persisted weeks; football Tuesday/Week0, JSON timezone precedence/fallback/weekday validation, ALL/explicit/missing subdivisions, existing reuse, missing league/season/subdivision, bulk rollback/legacy override |
| `python3 scripts/modernization/verify_schedule_calendar.py` | PASS7/7 queries, native JSON/date/timestamptz/RETURNING/phase joins, continuous ALL/postseason/final period, actual statement/deferred-commit rollback and db-only compatibility |
| `python3 scripts/modernization/verify_league_folders.py` | PASS full prior league/lifecycle suites and actual calendar-dependent callbacks; refreshed changed ScheduleModel dependency hash |
| Independent final review | No findings, reviewer independently ran7/7 |
| One-off AST/dependency checks | All13 migrated algorithms identical after query substitution; remaining22 methods including constructor unchanged; all7 SQL text-call ASTs identical; canonical layers import no configured engine/HTTP/model/provider client; diff check passes |

[Native calendar results/current hashes](evidence/mod-038-schedule-calendar-postgres-2026-10-30.json), [refreshed league report](evidence/mod-040-league-folders-postgres-2026-10-30.json), [plan/ledger](../superpowers/plans/2026-10-30-mod-038-schedule-calendar-implementation.md). Current seven completed-domain reports plus the scoped calendar report were hash-checked. Calendar report includes the still-partial schedule model; later schedule slices will supersede its source capture.

Existing per-helper begin scopes are preserved: football Week0 remains committed if numbered-week insertion later fails. This is deliberate compatibility, not a new global transaction/concurrency guarantee. No actor/route/startup/cross-domain caller policy changes. Only a task-owned marked loopback database/container was used and removed; no hosted/schema/dependency/deployment work. Schedule reads/search, ingestion/bootstrap and final composition remain, with broader frontend/correctness/startup cards separate.

## MOD-038 sport catalog — 2026-10-30

SportService owns the existing begin scope and SportRepository owns the exact original SELECT/projection. HTTP calls the public service directly; SQL-free SportModel preserves db constructor, get_sports and db-only legacy construction. Routes/public allowlist stay unchanged, no actor/profile lookup is added. Four plain-dict keys, nulls/empty list, unspecified ordering and generic HTTP500 remain.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | 518/518, exit0 |
| Test first | RED3 expected missing-service errors, original HTTP/legacy3 pass; GREEN6/6 |
| Real SQL/HTTP cases | Exact catalog projection/nulls, empty list, unauthenticated real GET200, sanitized failure500, service failure propagation/scope unwind, normal/db-only legacy |
| `python3 api/tests/run_isolated.py` | 524/524, exit0 |
| Independent final review | No findings, fresh focused6/6 |
| AST/boundaries/diff | Original SQL text-call AST identical; canonical layers import no HTTP/model/configured engine; model contains no SQL/connection acquisition; diff check passes |
| Native PostgreSQL | Not run: unchanged provider-neutral SELECT, no provider-specific parameter/type/alias/concurrency changes; guarded real SQLite plus exact SQL comparison. No PostgreSQL result claimed |

[Evidence/source hashes](evidence/mod-038-sport-catalog-2026-10-30.json), [plan/ledger](../superpowers/plans/2026-10-30-mod-038-sport-implementation.md), [domain guide](../../api/endpoints/sport/README.md). No schema/dependency/hosted/deployment work or configured application/job/listener startup; changes remain uncommitted. Schedule is the remaining backend extraction domain; broader frontend/folder/correctness/startup work remains separate.

## MOD-038 draft content completion — 2026-10-30

Remaining live picks, trusted manual allocation, timeout skip/auto-pick, conference caps/random buckets, membership and round lookups now live in service/repository layers. DraftModel retains SQL-free control/snapshot bridges and inherits pick behavior so legacy names, helper overrides and db-only construction work. HTTP picks receive UserActor; worker calls process_timeout_for_job, socket checks its verified subject before a trusted snapshot, listener calls snapshot service. Existing disabled manual HTTP410, default weeks, errors, policy and publication timing remain.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 512/512 |
| Direct-service tests | RED 6/6 missing new service; GREEN 6/6: actor-before-I/O, allocation/pointer, wrong owner/slot rollback, trusted manual/default notification, timeout no-ops, inherited overrides/db-only |
| `python3 api/tests/run_isolated.py` | Exit 0, 518/518, including final post-facade run |
| Native timeout RED → GREEN | Unquoted isExpired raised NoSuchColumnError; quoted alias exposed original :leagueId::bigint rotation SyntaxError; CAST(:... AS bigint) fixes all three bind casts; same expired rotation now passes |
| `python3 scripts/modernization/verify_draft_complete.py` | Exit 0; 40/40 named repository operations exercised and asserted; previous snapshot/finalization/controls/order suites rerun |
| Native correctness/atomicity | Live ownership/guarded INSERT revocation, turn/grace/expiry, active ownership/conflict/caps/distinct/season joins, manual/default, terminal/no-turn finalization, skip holes/last-turn/no-ops, auto buckets/caps/availability/sport, per-write/finalize/notify rollback, real statement/deferred-commit failure, actual pg_notify commit-only behavior |
| Native concurrency/composition | Observed actual pg_stat_activity lock wait for competing live pick/timeout; timeout rereads advanced unexpired state and makes no second transition; native worker deadline helper executed without configured import or worker startup |
| Independent final review | No Critical/Important/Minor findings; reviewer independently ran all518 tests |
| One-off AST comparison | 34 legacy methods match original algorithm AST after named-query/notification substitution; all38 migrated query ASTs identical except two proven SQL fixes; injected constructor/new entry points intentional |
| Boundaries/diff | Model SQL-free, canonical service/repository independent of model/transport/configured engine; original worker SQL moved unchanged; diff check and current source hashes pass |

[Current native results/source hashes](evidence/mod-038-draft-complete-postgres-2026-10-30.json), [plan/ledger](../superpowers/plans/2026-10-30-mod-038-draft-complete-implementation.md), [domain boundaries](../../api/endpoints/draft/README.md). Completion report supersedes previous draft hashes; earlier evidence is retained as history. All six completed domain reports remain current (transaction, roster, user, scoring, league, draft).

Known scope: ordinary nonterminal live picks still publish through HTTP after commit; ordinary auto-skip does not gain pg_notify. Existing restart/concurrent-start/cap/selection policies remain. MOD-023/025/034 and remaining domain/frontend architecture work are separate. No hosted/deployed/schema/dependency/frontend changes or app/worker/listener startup. Only a marked task-owned loopback PostgreSQL container/database was used and removed; work is uncommitted.

## MOD-038 draft-order control — 2026-10-30

Control service owns actor/trusted order selection, original empty-input-before-legacy-DB guard, pre/post commissioner checks, state/member validation and one bump/assign/projection transaction. Repository owns original unlocked state query, ANY bigint-array selection/count, +100000 bump, unnest/generate_series assignment and ordered member projection. Model signatures/defaults/coercion retained; HTTP uses actor service and preserves URL/body parsing and no broadcast.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 507/507 |
| Direct-service tests | RED four missing-operation assertions plus one passing legacy case; GREEN 5/5 |
| `python3 api/tests/run_isolated.py` | Exit 0, 512/512 including final fresh rerun; existing tests unchanged |
| `python3 scripts/modernization/verify_draft_order.py` | Exit 0, native PostgreSQL PASS; earlier snapshot/finalization/control suites rerun |
| Independent review | No Critical/Important/Minor findings; focused guarded suite 5/5 |
| AST/dependency/diff checks | All other model methods unchanged; control imports transport/model/configured-engine independent; diff check passes |

[Native results/source hashes](evidence/mod-038-draft-order-postgres-2026-10-30.json) verify real bigint arrays/ANY/unnest/generate_series with actual unique-order index, exact swap/partial projection and other league isolation. Empty/foreign/duplicate/missing/started/authority guards preserved. Failure after bump/assignment/member read, actual assignment statement error and deferred commit restore prior state. Separate connection changes commissioner before bump; final check rejects and rolls back member changes while preserving independent ownership change. Legacy trusted/coercion paths and prior draft suites pass; report supersedes previous draft source hashes while retaining history.

Original partial lists keep omitted orders bumped; no full-permutation, new lock or concurrent-start guard introduced. Those remain MOD-025/correctness work; picks/timeouts decomposition separate. Harness uses marked loopback server/owned random DB only, no configured DSN/.env. Database/container `otm-mod038-draft-order-20261030` removed. Checkout uncommitted; no schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-038 draft start/pause/resume — 2026-10-30

Control service now owns actor/trusted paths, pre/post commissioner checks, one transaction and same-connection trusted snapshot for start/pause/resume. Repository owns settings/turn/control SQL; draft_rules contains original settings validation and snake/straight arithmetic. Model settings/seed/expected-member/math/control helpers delegate; other commands unchanged. Start still reads settings again during seeding; resume validates config before state lock, pause does not. Original clocks/current pointer/repeated-start/upsert semantics preserved. HTTP publishes after successful commit as before.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 501/501 |
| Direct-service tests | RED five missing-operation assertions plus one passing legacy case; GREEN 6/6 |
| `python3 api/tests/run_isolated.py` | Exit 0, 507/507 including final fresh rerun after alias repair; existing tests unchanged |
| `python3 scripts/modernization/verify_draft_controls.py` | Exit 0, native PostgreSQL PASS; prior snapshot/finalization suites rerun |
| Native correctness regression | RED real incomplete-order case raised KeyError(missingOrder); quote original unquoted alias, GREEN intended ValueError missing-order validation and rollback |
| Independent review | No Critical/Important/Minor findings; focused guarded suite 6/6; alias repair reviewed |
| AST/dependency/diff checks | Other model methods unchanged; control/rules independent of transport/model/configured-engine imports; diff check passes |

[Native results/source hashes](evidence/mod-038-draft-controls-postgres-2026-10-30.json) verify actual generate_series, intervals, upsert and snake/straight rows, turn seeding, missing/complete/config guards and original restart behavior. The single SQL correctness repair quotes internal "missingOrder" so PostgreSQL returns the consumer's expected key instead of lowercase; incomplete order now raises intended ValueError/HTTP400, not KeyError/500. Failures after seed/state/league writes and deferred commit roll back all rows; separate-connection commissioner changes reject at post-check and preserve only independent ownership change. Two service/facade pause→resume cases observe actual PostgreSQL row-lock waits and end paused→live. Prior native snapshot/finalization checks pass; current report supersedes earlier draft hashes, history retained.

Original pre/post authority and state locks remain; no new replay/concurrency policy added and start can still reset state. Order/picks/timeouts remain separate. Harness uses marked loopback server/owned random DB only, no configured DSN/.env. Database/container `otm-mod038-draft-controls-20261030` removed. Checkout uncommitted; no schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-038 draft finalization — 2026-10-30

DraftControlService owns actor validation, pre/post commissioner authority, central finalization and transaction ownership. Repository contains original commissioner read, state update and season-derived league status update. Model finalizer supports trusted/caller connection, force-finalize retains None guard/integer legacy coercion and assertion facade supports remaining original controls. HTTP finalize uses actor service, then original trusted snapshot and broadcast after commit. No new lock, status/replay guard or notification.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 495/495 |
| Direct-service tests | RED five missing-module errors plus one passing legacy case; GREEN 6/6 |
| `python3 api/tests/run_isolated.py` | Exit 0, 501/501 including final fresh rerun; existing tests unchanged |
| `python3 scripts/modernization/verify_draft_finalization.py` | Exit 0, native PostgreSQL PASS; snapshot suite rerun |
| Independent review | No Critical/Important/Minor findings; focused guarded suite 6/6 |
| AST/dependency/diff checks | Other model methods including control transaction helper unchanged; control modules transport/model/configured-engine independent; diff check passes |

[Native results/source hashes](evidence/mod-038-draft-finalization-postgres-2026-10-30.json) verify final-state projection, cleared current member/expiry, preserved lastPickAt/overall pick, native timestamps and future/active/ended/inclusive season status. Missing season preserves league row with leagueStatus=None; missing state rejects. Post-state/post-league write, actual statement, deferred commit and caller rollback each restore prior state. Separate connection changes commissioner after first check; final authority check rejects and rolls back control mutations while preserving independent ownership change. Trusted supplied-connection/model coercion paths and full snapshot suite pass. Current report supersedes earlier draft source hashes; history retained.

Original pre/post checks add no row locks or guarantee beyond final check. Other controls/picks/timeouts unchanged; remaining decomposition separate. Harness used only marked loopback server/owned random DB, no configured DSN/.env. Database/container `otm-mod038-draft-finalize-20261030` removed. Checkout uncommitted; no schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-038 draft snapshot pilot — 2026-10-30

DraftSnapshotService now owns actor/trusted member policy, authorized completed-state repair, snapshot/pick/upcoming-turn orchestration and transaction scope. Repository owns original scoped league/state/member/pick/repair/turn SQL. HTTP state constructs actor from principal. Member access remains mandatory even for commissioners; query authorization precedes repair. Existing model signatures and helper use by commands remain; caller-supplied connection never opens another transaction. No pick/control/broadcast changes.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 489/489 |
| Direct-service tests | RED five missing-module errors plus one passing legacy case; GREEN 6/6 |
| `python3 api/tests/run_isolated.py` | Exit 0, 495/495 including final fresh rerun; existing tests unchanged |
| `python3 scripts/modernization/verify_draft_snapshot.py` | Exit 0, native PostgreSQL PASS |
| Independent review | No Critical/Important/Minor findings; focused guarded suite 6/6 |
| AST/dependency/diff checks | All other draft model methods unchanged; service/repository have no transport/model/configured-engine imports; diff check passes |

[Native results/source hashes](evidence/mod-038-draft-snapshot-postgres-2026-10-30.json) verify member-only access before repair, commissioner-without-membership denial, original JSON/native timestamps/envelope, season/sport-specific conference joins, independent picks, ordered members and next-turn skipping. Missing state and trusted missing-league semantics retained. Failure after repair before final read, deferred repair commit failure and caller-owned rollback preserve prior state; successful repair clears original fields. Separate-connection membership revocation immediately before scoped query denies without repair or later snapshot queries. Legacy supplied-connection calls and private turn helper work even on models without db. Existing read-time repair remains; no stronger final access/locking/realtime recovery guarantee added.

Harness used only marked loopback PostgreSQL and owned random DB, no configured DSN/.env. Database/container `otm-mod038-draft-snapshot-20261030` removed. League folder changes preserved; aliases remain for maintained legacy test/tool imports and can be retired after migration. Checkout uncommitted; no schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-040 league package organization — 2026-10-30

Moved implementation into admission/{service,repository,contracts}, members/{service,repository}, administration/{service,repository}, reads/{service,repository} and lifecycle/{service,repository}. Package initializers are lightweight; composition imports canonical paths. Legacy flat modules are sys.modules aliases of canonical modules, retaining class/exception identity, global patch behavior and old exception lookup/pickle resolution. Routes/endpoints/model stay at package root; no behavior changes.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 486/486 |
| Import compatibility tests | RED missing canonical packages (3 tests, 13 subtest/errors); GREEN 3/3 |
| `python3 api/tests/run_isolated.py` | Exit 0, 489/489 including final fresh rerun; existing tests unchanged |
| `python3 scripts/modernization/verify_league_folders.py` | Exit 0, complete native league PostgreSQL PASS through legacy harness imports |
| Independent review | No Critical/Important/Minor findings; focused guarded suite 3/3 |
| AST/dependency/diff checks | All 11 moved modules identical outside imports; model/endpoint definitions unchanged; acyclic lightweight packages and dependency boundaries preserved; diff check passes |

[Native results/source manifest](evidence/mod-040-league-folders-postgres-2026-10-30.json) rerun all 13 earlier league/member/admission slices plus lifecycle against reorganized implementations reached through old imports. Manifest covers 50 canonical/alias/package/dependency files including initializers and layout guide. It supersedes prior league source hashes while retaining historical reports. Functional data/SQL/transaction tests remain unchanged; compatibility tests exercise import identity, old repository patch targeting and exception resolution.

Harness accepts no configured DSN/.env; marked loopback server and owned random database only. Database/container `otm-mod040-league-folders-20261030` removed. League content/folder migration complete; wider domains/frontend and correctness remain separate. Checkout uncommitted; no API, behavior, schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-038 lifecycle; planned league extraction complete — 2026-10-30

LeagueLifecycleService owns one transaction and ordered pre-draft/drafting/post-draft/in-season/completed phases; repository contains original five SQL strings verbatim. Model sync delegates and retains None/error behavior; existing actor reads still invoke the same callback/facade at their original point. LeagueModel now contains no SQL literals/execution/connection acquisition. Public/helper signatures, composition and callback overrides retained; folder moves are separate.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 482/482 |
| Direct-service tests | RED three missing-module errors and one passing legacy SQL case; GREEN 4/4 |
| `python3 api/tests/run_isolated.py` | Exit 0, 486/486 including final fresh rerun; existing tests unchanged |
| `python3 scripts/modernization/verify_league_lifecycle.py` | Exit 0, native PostgreSQL PASS; all preceding league/member/admission suites rerun |
| Independent review | No Critical/Important/Minor findings; reviewer focused guarded suite 4/4; SQL strings/order match baseline |
| AST/dependency/diff checks | Other model methods unchanged; model SQL/connection-free; lifecycle service/repository independent of transport/model/configured engines; diff check passes |

[Complete native league results/source hashes](evidence/mod-038-league-complete-postgres-2026-10-30.json) verify transition matrix, future draft/live/paused/complete guards, inclusive season-start/end dates, sport/year matching, null/unchanged rows and completed-season precedence over stale draft state. Statuses converge on repeat. Injected post-update failures after each of five phases, actual PostgreSQL trigger failure and deferred commit failure each preserve entire previous state. Db-only facade returns None and real actor details/model reads invoke synchronization correctly. All earlier native league/member/admission checks pass. Combined report supersedes their source hashes; older reports historical.

Scope: league extraction complete; existing global read-time writes and possible intermediate updatedAt rewrites preserved. No concurrency/status redesign or MOD-020 completion claimed. Broader MOD-040 domains/frontend and recommended import-only subfolder pass remain separate. Harness used only marked loopback PostgreSQL and owned random DB, no configured DSN/.env. Database/container `otm-mod038-league-lifecycle-20261030` removed. Checkout uncommitted; no schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-038 member lists and daily score summaries — 2026-10-30

Read service owns actor/trusted selection, original two scoped queries in one read connection, current-week handling and unchanged timezone/date/game aggregation. Repository owns original score/member/week SQL and row accessors. HTTP wires public ScheduleModel timezone/game capabilities; model delegates preserve optional reader and deferred legacy callbacks. All original schedule methods are AST-identical; public timezone wrapper delegates to the existing implementation. Timezone still resolves after connection close even for empty/no-week results; game calls retain original kwargs.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 476/476 |
| Direct-service tests | RED five missing-operation assertions plus one passing legacy case; GREEN 6/6 |
| `python3 api/tests/run_isolated.py` | Exit 0, 482/482 including final fresh rerun; existing tests unchanged |
| `python3 scripts/modernization/verify_member_summary.py` | Exit 0, native PostgreSQL PASS; all preceding league/member/admission suites rerun |
| Independent review | No Critical/Important/Minor findings; focused guarded suite 6/6 |
| AST/dependency/diff checks | Other league methods and all existing schedule methods unchanged; service/repository transport/model/configured-engine independent; diff check passes |

[Native results/source hashes](evidence/mod-038-member-summary-postgres-2026-10-30.json) verify exact member projection, native scores/negative-week exclusion/fallback, week zero, actual public timezone lookup, local-date/naive UTC/aware/undated/out-of-range aggregation and zero fills. Null start preserves empty daily keys while weekly total remains; no current week skips games. Supplied game failure propagates, separate connection revocation before member query returns empty, legacy methods pass. Scheduling game algorithms remain unchanged; supplied facts verify summary orchestration. Existing snapshot behavior/callbacks preserved, no final access guard or batching added. All preceding native suites pass; combined report supersedes old hashes, historical evidence retained.

Harness uses marked loopback server/owned random DB only, no configured DSN/.env. Database/container `otm-mod038-member-summary-20261030` removed. Lifecycle is final planned league extraction slice. Follow-up recommendation: cohesive admission/members/administration/reads/lifecycle subfolders via import-only move preserving compatibility imports/composition; no folder move performed. Checkout uncommitted; no schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-038 league details and own listings — 2026-10-30

Read service owns actor/trusted selection, original stage normalization, explicit lifecycle synchronization before read and original transaction scopes. Repository owns unchanged scoped details SQL (highest matching week) and membership-only listing SQL with score fallback, negative-week exclusion and original overlapping-week rows. HTTP discovery/identity assertions and model signatures/deferred callback overrides remain compatible. Lifecycle algorithm unchanged; its callback still precedes the query outside its scope.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 471/471 |
| Direct-service tests | RED three missing-operation assertions plus two passing legacy cases; GREEN 5/5 |
| `python3 api/tests/run_isolated.py` | Exit 0, 476/476 including final fresh rerun; existing tests unchanged |
| `python3 scripts/modernization/verify_league_details.py` | Exit 0, native PostgreSQL PASS; all preceding league/member/admission suites rerun |
| Independent review | No Critical/Important/Minor findings; reviewer focused guarded suite 5/5 |
| AST/dependency/diff checks | Only two intended model read methods changed; read modules remain transport/model/configured-engine independent; diff check passes |

[Native results/source hashes](evidence/mod-038-league-details-postgres-2026-10-30.json) verify original interval fallback, highest current week for details, native projection/nulls, stage normalization/filtering, member-specific score sum/fallback excluding negative weeks and overlapping listing rows. Commissioner without membership remains excluded from own listings. Separate committed sync is visible in the subsequent read; revocation prevents details/list membership, and sync failure prevents SQL read. Legacy methods and all preceding native suites pass. Combined report supersedes previous league/member/admission hashes; historical reports retained.

Scope: lifecycle callback boundary verified, algorithm unchanged. Existing read-time global synchronization and overlapping-week duplication remain; no policy/concurrency redesign. Harness uses marked loopback server/owned random database only, no configured DSN/.env. Database and task-owned container `otm-mod038-league-details-20261030` removed. Two planned slices remain: member lists/daily summaries and lifecycle synchronization. Checkout uncommitted; no schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-038 league discovery/access/previews/search — 2026-10-30

LeagueReadService now owns actor/legacy reader selection, one transaction per access/preview/search query and public search strip/short-circuit/pagination bounds. Repository owns unchanged metadata, preview visibility/entitlement and pg_trgm search SQL. HTTP retains private concealment, full/preview choices and separate fresh metadata recheck; it constructs actor from principal and search remains anonymous. Access metadata remains internal entitlement facts, including a private outsider's fullAccess=false; HTTP controls visibility. Preview results remain names-only. Legacy model signatures/input behavior retained.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 465/465 |
| New direct-service tests | Initial RED five missing-operation assertions plus one legacy case passed; GREEN 6/6 |
| Adapter-unit wiring | Metadata mock target changed to service access; existing assertions retained |
| `python3 api/tests/run_isolated.py` | Exit 0, 471/471 including final fresh rerun; end-to-end JWT/public search tests unchanged |
| `python3 scripts/modernization/verify_league_discovery.py` | Exit 0, native PostgreSQL PASS; preceding league/member/admission suites rerun |
| Independent final review | No Critical/Important/Minor findings; reviewer separately ran focused guarded suite, 6/6 |
| AST/dependency/diff checks | Non-discovery model methods unchanged; read modules remain transport/model/configured-engine independent; diff check passes |

[Native results/source hashes](evidence/mod-038-league-discovery-postgres-2026-10-30.json) verify exact metadata/private/member/commissioner entitlement and names-only projection, real pg_trgm ranking/tie order, discoverability/sport filters, paging, limit clamps/offset floor, quoted bound query values and short-query no I/O before invalid pagination conversion. Separate connections revoke discoverability/membership, including immediately before preview SELECT; metadata rechecks and preview predicates observe revocation, and hidden league disappears from search. Legacy model paths and all earlier league/member/admission native suites pass. Combined report supersedes previous hashes; historical reports retained.

Only marked loopback PostgreSQL and one owned random database were used; pg_trgm extension created solely in synthetic DB, no configured DSN/.env. Database and task-owned container `otm-mod038-league-discovery-20261030` removed. Three planned league slices remain: details/my leagues, member lists/daily summaries and lifecycle synchronization. Checkout uncommitted; no application schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-038 league conference read — 2026-10-30

LeagueReadService now owns actor/trusted selection, one begin scope, missing/scoped-out league and null-season validation, and result envelope. Repository owns original scoped league read and sport-local conference counts, including null-season plus requested-season memberships, zero fallback, owner limit and name order. Original fetchone/_mapping and fetchall accessors and legacy optional-reader/db-only calls remain compatible. HTTP retains discovery/full-access gates, with the full conference branch invoking actor service. Late scoped-out read remains ValueError→400, distinct from rules-read None→404.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 460/460 |
| New direct-service tests | Initial RED five missing-operation assertions; GREEN 5/5 |
| `python3 api/tests/run_isolated.py` | Exit 0, 465/465 including final fresh rerun; existing tests unchanged |
| `python3 scripts/modernization/verify_league_conferences.py` | Exit 0, native PostgreSQL PASS; preceding league/member/admission suites rerun |
| Independent final review | No Critical/Important/Minor findings; reviewer separately ran focused guarded suite, 5/5 |
| AST/dependency/diff checks | All other model methods unchanged; read modules independent of transport/model/configured-engine imports; diff check passes |

[Native results/source hashes](evidence/mod-038-league-conferences-postgres-2026-10-30.json) verify exact conference projection, null+matching-season counts, exclusion of other seasons/sports, zero fallback, name order and empty conferences. Denied/missing/null-season reads execute no aggregate query. Separate connections revoke membership immediately before scoped league SELECT; service and legacy facade raise the original ValueError and skip aggregate. Trusted/legacy reads and all preceding native suites pass. Combined report supersedes previous league/member/admission hashes; historical reports retained.

Only marked loopback PostgreSQL and one owned random database were used; no configured DSN/.env. Database and task-owned container `otm-mod038-league-conferences-20261030` removed. Four planned league slices remain: discovery/access/previews/search, details/my leagues, member lists/daily summaries and lifecycle synchronization. No new post-SELECT final recheck/snapshot guarantee. Checkout uncommitted; no schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-038 league rules read — 2026-10-30

LeagueReadService now owns actor/trusted reader selection, one connect scope, describe_rules and deadline ISO/string/null conversion. Repository owns original scoped league query, sport-local tier fallback query, fetchone/_mapping and fetchall accessors. Missing/scoped-out league returns None before any team query. Model retains optional reader and trusted context-free behavior. HTTP retains existing metadata/discovery gates and response errors; only its full rules branch changes dependency to actor service. Details/member/conference reads and lifecycle behavior are unchanged.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 455/455 |
| New direct-service tests | Initial RED five missing-module errors; GREEN 5/5 |
| Adapter-unit fixture migration | Initial full run: two failures/one error from __new__ endpoint fixtures still mocking old dependency; inject read-service mock instead, original missing/version/serialization assertions retained |
| `python3 api/tests/run_isolated.py` | Exit 0, 460/460 including final fresh rerun; JWT/SQL authorization suites unchanged |
| `python3 scripts/modernization/verify_league_rules_read.py` | Exit 0, native PostgreSQL PASS; preceding league/member/admission suites rerun |
| Independent final review | No Critical/Important/Minor findings; reviewer separately ran focused guarded suite, 5/5 |
| AST/dependency/diff checks | All other model methods unchanged; read service/repository independent of transport/model/configured-engine imports; diff check passes |

[Native results/source hashes](evidence/mod-038-league-rules-read-postgres-2026-10-30.json) verify native rules projection/deadlines/nulls/version, case-insensitive team sorting, tier fallback with and without explicit tiers and isolation from other sports. Denied/missing reads execute no team query. Separate connections revoke membership immediately before scoped SELECT; service and legacy facade return None and skip teams. Trusted model/service paths and invalid stored-version error pass. All preceding native suites rerun. Combined report supersedes their source hashes; historical reports retained.

Scope remains original query-time access: no post-SELECT final recheck or stronger read snapshot guarantee is added. Harness accepts no configured DSN/.env, using only marked loopback PostgreSQL and an owned random database. Database and task-owned container `otm-mod038-league-rules-20261030` removed. Other reads/discovery/lifecycle remain separate. Checkout uncommitted; no schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-038 league creation — 2026-10-30

Creation now calls LeagueAdminService with UserActor. Service binds commissioner to actor, copies input, trims required team name, pins rules version and validates/defaults timezone. Repository contains unchanged league INSERT CTE and member INSERT/fetchone/_mapping, preserving native unquoted sportinfo projection and creatorMemberId. HTTP retains commissioner assertion parsing/order and supplies existing ScheduleModel.ensure_weeks_for_league as a public capability; service imports no compatibility model. Trusted model delegate retains supplied commissioner and defers schedule attribute access until the original post-commit execution point. Pure timezone ensure is shared with a legacy helper delegate.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 449/449 |
| New direct-service tests | Initial RED five missing-operation assertions and one existing legacy case passed; GREEN 6/6 |
| `python3 api/tests/run_isolated.py` | Exit 0, 455/455 including final fresh rerun; existing creation/auth/rules/schedule tests unchanged |
| `python3 scripts/modernization/verify_league_creation.py` | Exit 0, native PostgreSQL PASS; prior settings/deletion/member/admission suites rerun |
| Independent final review | No Critical/Important/Minor findings; reviewer separately ran focused guarded tests, 6/6 |
| AST/dependency/diff checks | All non-creation model methods unchanged except timezone-ensure delegate; admin service/repository transport/model/configured-engine independent; diff check passes |

[Native results/source hashes](evidence/mod-038-league-creation-postgres-2026-10-30.json) verify CTE/JSON/timestamps/sportinfo/member defaults, actor identity, trimmed name and explicit/default timezone. Real commissioner/member FK errors, missing Sport projection, failures after executed league/member inserts and deferred commit failure all preserve prior state and never invoke initializer. A supplied initializer uses a separate connection to observe committed league/member rows and create a synthetic Week. Initializer failure propagates and preserves committed creation (and any initializer writes), matching the original boundary. Trusted legacy creator and all preceding native suites pass. Combined report supersedes prior league/member/admission source hashes; historical reports retained.

Scope: scheduling capability boundary is verified; ScheduleModel week-generation algorithms are unchanged and not reimplemented by the native fixture. No new atomic scheduling/recovery/idempotency guarantee. Harness accepts no configured DSN/.env and used only marked loopback PostgreSQL and one owned random database. Database and task-owned container `otm-mod038-league-creation-20261030` removed. Reads/lifecycle remain separate. Checkout uncommitted; no schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-038 league settings/metadata updates — 2026-10-30

HTTP update now calls the actor-requiring LeagueAdminService. It preserves initial authority before validation, separate read/write transaction scopes, settings replacement/version pinning, timezone precedence/aliases, allowed fields, unknown-key ignore/empty rejection and commissioner-scoped write. Repository contains original read and update CTE/projection; shared timezone bodies moved unchanged to leagueRules, with model compatibility helper delegates. Trusted and private optional-commissioner methods preserve context-free behavior and original error types.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 442/442 |
| New direct-service tests | Initial RED six missing-operation assertions plus one passing legacy case; GREEN 7/7 |
| Existing full-suite regression | First full run had two test_league_rules_api errors after read accessor changed; original fetchone/_mapping restored, existing tests unchanged and GREEN |
| `python3 api/tests/run_isolated.py` | Exit 0, 449/449 including final fresh rerun |
| `python3 scripts/modernization/verify_league_settings.py` | Exit 0, native PostgreSQL PASS; prior deletion/member/admission checks rerun |
| Independent final review | No Critical/Important/Minor findings; reviewer separately ran focused guarded suite, 7/7 |
| AST/dependency/diff checks | Non-target model methods unchanged; timezone bodies identical to original; admin service/repository transport/model/configured-engine independent; diff check passes |

[Native results/source hashes](evidence/mod-038-league-settings-postgres-2026-10-30.json) verify actual UPDATE CTE, bound names, JSON replacement/version, native deadlines/nulls, sport projection and input immutability. Real integer statement failure, executed-update failure and deferred commit failure roll back checked and trusted writes. Separate connections change commissioner after the initial SELECT; both direct actor and legacy facade reject the later write without mutation. All prior league deletion/member/admission native checks pass again. This combined report supersedes their source hashes; historical reports retained.

Compatibility limits preserved explicitly: original unquoted `AS sportInfo` returns `sportinfo` on PostgreSQL (SQLite adapter synthesizes `sportInfo`); native fixture expectation was corrected, production SQL unchanged. If the synthetic Sport join has no row, the existing update commits before the checked PermissionError/trusted RuntimeError result guard; native tests pin that preexisting behavior. No new lost-update protection, merge/retry or transaction consolidation is claimed.

Harness used only a marked loopback server and owned random database, never configured DSN/.env. Database and task-owned container `otm-mod038-league-settings-20261030` removed. Creation/read/lifecycle extraction remain separate. Checkout uncommitted; no schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-038 commissioner league deletion — 2026-10-30

Deletion now calls LeagueAdminService with UserActor from HTTP; its legacy method still requires commissioner authority. Service owns one transaction, league lock, integer-coerced commissioner comparison, missing-league/error guards and final result. Repository owns unchanged SELECT FOR UPDATE and commissioner-scoped DELETE RETURNING. Existing identity assertion order, model db-only construction, response and operational failures remain compatible. Database constraints continue to define cascades; no schema or manual cascading added.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 437/437 |
| New direct-service tests | Initial RED: four missing-module errors and one existing compatibility case passed; GREEN 5/5 |
| `python3 api/tests/run_isolated.py` | Exit 0, 442/442 including final fresh rerun; existing authorization suites unchanged |
| `python3 scripts/modernization/verify_league_delete.py` | Exit 0, native PostgreSQL PASS; prior admission/member suites rerun |
| Independent final review | No Critical/Important/Minor findings; reviewer separately ran focused guarded suite, 5/5 |
| AST/dependency/diff checks | All other model methods unchanged; admin service/repository have no transport/model/configured-engine imports; diff check passes |

[Native results/source hashes](evidence/mod-038-league-delete-postgres-2026-10-30.json) verify authority/missing/projection, synthetic direct and multilevel cascades (members/requests/weeks/scores), unrelated league preservation, actual FK restriction and post-delete/deferred-commit rollback. A synthetic suppressing trigger confirms missing DELETE RETURNING raises the existing RuntimeError and rolls back trigger side effects. Service/facade competing deletions observe a PostgreSQL lock wait and reject replay; a deletion waiting behind commissioner change observes new authority and rejects without deleting dependents. Legacy ID coercion and every preceding admission/member native check pass. Combined report supersedes their source hashes; historical reports retained.

Only the marked loopback server and an owned random database were used; no configured DSN/.env. Database and task-owned container `otm-mod038-league-delete-20261030` removed. Settings/creation/read/lifecycle extraction remain separate. Checkout uncommitted; no schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-038 member removal and draft-order shifting — 2026-10-30

MemberService now owns actor validation, locked commissioner authority, URL-scoped target and commissioner protection, optional shifting and one transaction. MemberRepository owns original league→member locks and SQL. HTTP still parses identity assertion and strict boolean shift before invoking the actor service. The legacy context-free model method keeps integer coercion and shift truthiness. Exact errors and response projections/order remain unchanged; removal still does not recalculate draft-round settings or restrict league status.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 431/431 |
| New direct-service tests | Initial RED: five missing-operation assertion failures and one passing legacy case; GREEN 6/6 |
| `python3 api/tests/run_isolated.py` | Exit 0, 437/437 including final fresh rerun; existing authorization tests unchanged |
| `python3 scripts/modernization/verify_member_removal.py` | Exit 0, native PostgreSQL PASS; prior member/admission suites rerun |
| Independent final review | No Critical/Important/Minor findings; reviewer separately ran focused guarded suite, 6/6 |
| AST/dependency/diff checks | All non-removal model methods unchanged; member imports remain transport/model/configured-engine independent; diff check passes |

[Native results/source hashes](evidence/mod-038-member-removal-postgres-2026-10-30.json) verify authority/scope/commissioner protection, exact remaining-member projection/order, shift-off behavior, count floor, timestamp update and unchanged settings/other league/scores. A real FK restriction, injected failures after executed deletion/shifting/count update and deferred commit failure each preserve all prior state. Six service/facade concurrency cases observe PostgreSQL lock waits and league→member order: same-target replay rejects without another decrement, distinct removals serialize, and approval waiting behind removal allocates the next draft position with correct count. Legacy actor coercion/shift truthiness passes. All earlier member-profile and admission native checks rerun successfully; this combined report supersedes their source hashes while retaining historical reports.

Only marked loopback PostgreSQL and one owned random database were used; no configured DSN/.env. Database and task-owned container `otm-mod038-member-removal-20261030` removed. Broader league reads/administration and correctness-policy redesign remain separate. Checkout uncommitted; no schema, hosted DB, frontend, dependencies, listener or deployment changes.

## MOD-038 member profile updates — 2026-10-30

Extracted owner-only rename and legacy trusted allowlisted updates into MemberService/MemberRepository. The interactive service requires UserActor and a nonblank string before I/O. HTTP still rejects all other fields and preserves the raw name. The owner predicate remains in the UPDATE, concealing foreign/missing targets with 404. Legacy owner-ID method remains permissive; trusted updater keeps teamName/draftOrder/seasonPoints filtering, bound values, original error types and returned fields. Model db-only callers and constant import remain compatible.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline | Exit 0, 426/426 |
| New direct-service tests | Initial RED: four missing-module errors, one existing compatibility case passed; GREEN 5/5 |
| `python3 api/tests/run_isolated.py` | Exit 0, 431/431 including final fresh rerun; existing tests unchanged |
| `python3 scripts/modernization/verify_member_profile.py` | Exit 0, native PostgreSQL PASS; earlier admission checks rerun |
| Independent final review | No Critical/Important/Minor findings; reviewer separately ran focused guarded tests, 5/5 |
| AST/dependency/diff checks | All other model methods unchanged; member service/repository independent of transport/model/configured DB; diff check passes |

[Native results/source hashes](evidence/mod-038-member-profile-postgres-2026-10-30.json) verify exact projection/native timestamp preservation, raw quoted/bound name, owner/foreign/cross-league/missing scope, trusted allowlist and permissive legacy compatibility. Both update paths roll back after executed UPDATE and deferred commit failure. A separate ownership update holds the row lock while rename waits; after ownership changes, PostgreSQL rechecks the owner predicate and both direct service and legacy facade return LookupError without changing the name. Complete prior listing/cancellation/creation/denial/approval checks rerun successfully; this combined report supersedes prior admission source hashes while retaining historical evidence.

Harness used only the marked loopback server and an owned random database; no configured DSN/.env. Database and task-owned container `otm-mod038-member-profile-20261030` removed. Removal/draft-order shifting and wider league work remain separate. Changes uncommitted; no schema, hosted DB, frontend, dependencies, listener or deployment changes.

## MOD-038 admission approval; admission extraction complete — 2026-10-29

Approval now calls the actor-requiring admission service from HTTP. The service verifies commissioner under League FOR UPDATE, then locks the URL-scoped request, requires PENDING and owns one transaction for membership, capacity/draft rounds and request resolution. Repository SQL preserves MAX(draftOrder)+1, fallback team, zero points, original JSON CTE behavior, resolver attribution and projections. Trusted legacy approval remains explicit; model and supplied-connection private helper signatures remain compatible.

| Verification | Fresh result |
| --- | --- |
| Guarded baseline backend | Exit 0, 419/419 |
| New direct-service tests | Initial RED: six missing-operation assertion failures and one passing trusted compatibility case; GREEN 7/7 |
| `python3 api/tests/run_isolated.py` | Exit 0, 426/426, including final fresh rerun; existing authorization suites unchanged |
| `python3 scripts/modernization/verify_admission_approval.py` | Exit 0, native PostgreSQL PASS; all preceding admission checks rerun |
| Independent final review | No Critical/Important/Minor findings; reviewer separately ran focused guarded suite, 7/7 |
| AST/dependency/diff checks | Non-approval model methods unchanged from slice baseline; transport/model/configured-engine dependencies absent from admission service/repository; diff check passes |

[Native results and source hashes](evidence/mod-038-admission-complete-postgres-2026-10-29.json) verify exact request/member projections and native timestamps, authority/URL/state rejection, count/round thresholds/floor, unrelated JSON preservation, team fallback and actual jsonb_set behavior for null settings or missing draft parent. Real unique-member and resolver-FK failures roll back all tables; failures after each executed mutation and at deferred commit do likewise. Through both direct service and legacy facade, same-request competitors wait on PostgreSQL locks and reject replay without duplicate membership; distinct-request competitors wait and produce consecutive draft positions plus consistent count/round updates. Trusted audit actor and private supplied-connection compatibility also pass. Listing/cancellation/creation/denial checks rerun unchanged.

Only the marked loopback server and owned random database were used; harness accepts no configured DSN/.env. Database and task-owned container `otm-mod038-admission-complete-20261029` removed. New report supersedes prior admission source hashes; earlier evidence retained. All admission request operations are now extracted; wider league methods and MOD-012 correctness work remain separate. No new capacity limit/concurrent-creation uniqueness guarantee, schema, hosted DB, frontend, dependency, listener or deployment changes.

## MOD-038 admission creation/denial — 2026-10-29

Extended league-local admission services/repositories to creation and denial. Creation validates/trims team name before persistence, checks membership first and returns existing pending requests unchanged, including the existing 201 HTTP response. Database/FK failures retain operational-failure behavior. Commissioner denial locks league then request, verifies authority/scope/PENDING and records resolver. Trusted legacy denial remains an explicit job path unavailable through HTTP flags. Model signatures, db-only construction and supplied-connection private helper remain compatible.

| Verification | Fresh result |
| --- | --- |
| Baseline guarded backend | Exit 0, 412/412 |
| Focused direct-service tests | 7/7; initial RED was six missing-method errors, one existing trusted compatibility case passed |
| `python3 api/tests/run_isolated.py` | Exit 0, 419/419, including final fresh rerun |
| `python3 scripts/modernization/verify_admission_create_deny.py` | Exit 0, native PostgreSQL PASS; also reruns prior listing/cancellation checks |
| Independent final code review | No Critical/Important/Minor findings; reviewer's separate test import lacked SUPABASE_PROJECT_ID, so guarded parent runs supply execution evidence |
| AST/import/diff checks | All non-target league methods unchanged; service/repository remain independent of transport/model/configured-engine imports; diff check passes |

[Native results/source hashes](evidence/mod-038-admission-create-deny-postgres-2026-10-29.json) verify exact creation projection, normalization, sequential repeat without overwrite, membership and actual FK failures, insertion statement/deferred-commit rollback, denial authority/URL scope/resolver, executed-update/deferred-commit rollback and trusted/private-helper compatibility. Competing denials through direct service and legacy facade observe a PostgreSQL lock wait, league→request lock order, one DENIED transition and defined replay rejection. Listing/cancellation projection, revocation, rollback and competing lock tests also pass again. This report supersedes previous admission source hashes; earlier reports remain historical evidence.

Harness uses only the marked loopback server and its own random synthetic database, never configured DSNs/.env. Database and task-owned container `otm-mod038-admission-next-20261029` removed. Approval and capacity remain unchanged; no new concurrent-creation uniqueness guarantee, schema, hosted DB, frontend, dependencies, listener or deployment changes.

## MOD-038 admission listing/cancellation — 2026-10-29

Extracted commissioner-only join-request listing and applicant-owned cancellation into league-local admission service/repository. New HTTP entry points require UserActor; compatibility methods use explicit verified-ID/trusted bridges. Model delegates construct a lightweight service from db so actual __new__ callers remain supported. The private listing helper preserves its scope-only query behavior without adding a new precheck.

| Verification | Fresh result |
| --- | --- |
| Baseline guarded backend | Exit 0, 406/406 |
| `python3 api/tests/run_isolated.py test_admission_service.py` | Exit 0, 6/6 after initial missing-module failure |
| `python3 api/tests/run_isolated.py` | Exit 0, 412/412 |
| `python3 scripts/modernization/verify_admission_slice.py` | Exit 0, native PostgreSQL listing/cancellation checks pass |
| Independent final review | No Critical/Important/Minor findings; reviewer inspected SQL, callers and compatibility but did not separately run tests |
| AST/import/diff checks | Untouched league method bodies match pre-extraction AST; no new service/repository transport/model/configured-engine imports; diff check passes |

New direct tests verify actor requirement before I/O, one listing scope, projection/order/filter, commissioner denial/revocation, explicit trusted reads, owner cancellation/replay, wrong owner/league rejection and rollback after update. Existing listing/cancellation/creation/approval/denial and wider league tests remain unchanged. Missing league stays a client error, noncommissioner stays 403 and query-time commissioner loss still yields an empty listing. Commissioner status does not grant cancellation of someone else's request.

[Native results/source hashes](evidence/mod-038-admission-postgres-2026-10-29.json) verify exact listing fields, native dates, status/order, separate-connection commissioner revocation, cancellation owner/URL scope/resolved state, rollback after executed UPDATE and at deferred commit. Competing cancellations through both direct service and legacy facade observe a PostgreSQL lock wait, one CANCELLED transition, null resolver preservation and defined replay rejection. Private scope-only listing and db-only legacy model construction are also exercised.

Only a marked loopback server and random synthetic database were used; harness accepts no DSN/.env. Random database and task-owned container `otm-mod038-admission-20261029` were removed; other containers untouched. Creation/approval/denial and broader admission serialization are unchanged. No new admission-capacity/concurrent-approval guarantee, schema change, hosted DB, frontend checks, dependency, listener or deployment.

## MOD-038 remaining scoring domain — 2026-10-29

Extracted all remaining scoring SQL into named supplied-connection repository methods; services own weekly/season orchestration and transaction scopes; bonus award loops are pure functions. ScoringModel inherits the domain service solely to retain existing helper/subclass dispatch. HTTP season reads require UserActor and retain pre/post full-read checks. Weekly/final scoreboard builders now return services and use explicit trusted job methods. Job completion/locking/finalization state SQL is unchanged; MOD-013/014 recovery acceptance and MOD-034 configured startup are not claimed complete.

| Verification | Fresh result |
| --- | --- |
| Baseline guarded backend | Exit 0, 396/396 |
| New core/rules/actor/native-row + builder suites | 10 tests pass after expected initial failures |
| `python3 api/tests/run_isolated.py` | Exit 0, 406/406 |
| `python3 scripts/modernization/verify_scoring_complete.py` | Exit 0, native full-scoring + previous weekly-read checks pass |
| Independent final review | No Critical/Important/Minor findings; reviewer separately ran the 10 new tests |
| Dependency/diff checks | Service/rules/model contain no SQL; repository acquires no connections/commits; no service→Flask/model/configured engine imports; diff check passes |

Existing weekly atomicity/week-zero, basketball final-period, weekly tiebreak, HTTP authorization/disabled-command and operational tests remain active. Only the existing finalizer test's injected builder fixture changed to return the new service interface directly. New tests cover scoped repeat replacement, rollback on second insertion, pure bonus ties/zero exclusions, season actors/revocation, true SQLAlchemy rows and HTTP-free job builders.

**Separate demonstrated correctness repair:** original depth/latest-week helpers used `row['max_round']`, `w['id']` and rank string indexing on SQLAlchemy Row, which raises TypeError with the installed library. Three new real-Row regressions reproduced failures after extraction, then passed using `_mapping`. SQL, scoring formulas, bonus/tie order and waterfall awards are otherwise preserved. Independent review compared normalized SQL against the original model and found no changed or missing query predicates; duplicate identical queries were consolidated.

[Native PostgreSQL evidence/source hashes](evidence/mod-038-scoring-complete-postgres-2026-10-29.json) reruns weekly-points projection/normalization/revocation checks, then exercises real week/season/phase/ownership/game/score fixtures. It verifies delete+all-insert rollback on statement and deferred-commit failures; scoped repeat convergence/week zero; weekly head-to-head/waterfall; all five season tiebreak query families; all three bonus families and exclusion of non-primary postseason phases; empty phase facts; actor standings and separate-connection revocation; split/future final-period guards. Schedule reads are supplied synthetic facts, not live provider requests or new schedule-query verification.

Current full-scoring report supersedes the earlier weekly-read report's source hashes; historical evidence remains unchanged. The runner refuses unmarked servers/DSNs and uses no `.env`. Random database and task-owned container `otm-mod038-scoring-full-20261029` were removed. Existing containers untouched. No new isolation/concurrency/recovery claim, schema migration, hosted DB, frontend checks, dependency, listener startup or deployment.

## MOD-038 scoring weekly-points read — 2026-10-29

Extracted only `get_weekly_points_awarded_for_league` into an actor-requiring ScoringReadService and supplied-connection ScoringRepository. Model signature, trusted calls and PermissionError compatibility remain. HTTP original weekNumbers/results envelope is unchanged; integer conversion/deduplication/sorting/nonnegative filtering remain service behavior. Initial and final league-read checks cover empty/negative-only lists as well as scored results. Final denial occurs after closing the read connection, matching the previous guard's concealed-denial contract.

| Verification | Fresh result |
| --- | --- |
| Baseline guarded backend | Exit 0, 389/389 |
| `python3 api/tests/run_isolated.py test_scoring_read_service.py` | Exit 0, 7/7 after initial missing-module failure |
| `python3 api/tests/run_isolated.py` | Exit 0, 396/396 |
| `python3 scripts/modernization/verify_scoring_read.py` | Exit 0, native PostgreSQL weekly-points checks pass |
| Independent final review | No Critical/Important/Minor findings; reviewer inspected code/callers but did not independently execute tests |
| AST/import/diff checks | All non-pilot ScoringModel method bodies unchanged except constructor wiring; no new service/repository Flask/model/configured-engine dependency; diff whitespace check passes |

New service tests cover required actor before I/O, one read connection, normalization/order/projection, commissioner-only access, denial before normalization/data SQL, late revocation, empty-list pre/post checks and trusted empty-list no-I/O behavior. Existing scoring authorization, atomic replacement, tiebreak, bootstrap/operational and disabled-HTTP suites remain unchanged and active.

[Native PostgreSQL results/source hashes](evidence/mod-038-scoring-read-postgres-2026-10-29.json) verify expanding week binds, dates/numeric projection, ordering, league isolation, member/commissioner/outsider outcomes and legacy trusted reads. Separate-connection membership deletion before the data query and before the final empty-list check both yield ScoringReadDenied instead of private rows or empty success. These checks use PostgreSQL's default READ COMMITTED; no new isolation/snapshot or post-final-check revocation guarantee is claimed.

Only a marked loopback server and random synthetic database were used; the harness never loads `.env` or accepts a DSN. Database and task-owned container `otm-mod038-scoring-20261029` were removed; existing containers and earlier pilot source files are unchanged. No score computation/standings/job migration, schema change, hosted DB, listener, dependencies, frontend changes/checks or deployment.

## MOD-038 profile creation and UUID persistence — 2026-10-29

Continued the approved hybrid by extracting the remaining user SQL. Interactive creation requires ProfileSubject populated by the adapter from verified JWT subject/email. Service owns the at-most-two mapped-ID check and insertion transaction; legacy creation intentionally has no new existing-subject precheck. Legacy UUID lookup retains first-row semantics; HTTP UUID lookup still uses the unchanged unique-principal resolver. UserModel now contains no SQL and preserves all signatures/ValueError translations.

| Verification | Fresh result |
| --- | --- |
| Baseline guarded backend | Exit 0, 381/381 |
| `python3 api/tests/run_isolated.py test_user_creation_service.py` | Exit 0, 8/8 after initial missing-contract failure |
| `python3 api/tests/run_isolated.py` | Exit 0, 389/389 |
| `python3 scripts/modernization/verify_profile_creation.py` | Exit 0; creation + prior profile read/update native checks pass |
| Independent final review | No Critical/Important/Minor findings; reviewer independently ran 8/8 new service tests |
| Dependency and diff checks | Shared principal unchanged, model SQL-free, service/repository have no Flask/model/configured-engine imports; `git diff --check` passes |

New tests cover actor/identity requirements before I/O, one creation transaction, normalization/reload, existing/ambiguous rejection without overwrite, statement/exit integrity failure translation, unexpected failure rollback and legacy creation/UUID/missing outcomes. Existing bootstrap/profile/principal tests remain unchanged; exact HTTP validation order and response contracts stay covered.

[Native evidence and current source hashes](evidence/mod-038-profile-creation-postgres-2026-10-29.json) first rerun the earlier profile read/update checks, including statement/deferred-commit update rollback. Creation fixtures then verify real email uniqueness and auth.users FK violations, duplicate-UUID ambiguity, claim normalization, insert projection/reload, repeat conflict, legacy duplicate-subject compatibility and insert failure rollback both before statement completion and at deferred commit. Auth definitions are minimal synthetic fixtures, not full provider acceptance.

This new report supersedes the earlier profile slice's source hashes for changed user files; earlier reports remain historical and are not overwritten. No new uniqueness constraint or concurrent-bootstrap serialization is implemented. No app principal is fabricated for bootstrap; the typed ProfileSubject itself does not authenticate callers. Native harness refuses unmarked servers, accepts no DSN and uses no `.env`. Its random database and task-owned container `otm-mod038-creation-20261029` were removed; no hosted database, existing-container changes, dependencies, frontend work, listeners or deployment.

## MOD-038 profile continuation — 2026-10-29

User requested the next domain. Extracted own-profile ID reads/updates into service/repository ownership; creation, legacy UUID lookup SQL and the shared principal resolver remain unchanged. Current HTTP UUID reads still verify the subject and resolve exactly one profile before calling the actor service. Foreign-target PATCH denial occurs through service policy before JSON parsing and again before the update transaction.

| Verification | Fresh result |
| --- | --- |
| Baseline guarded backend | Exit 0, 373/373 |
| `python3 api/tests/run_isolated.py test_user_service.py` | Exit 0, 8/8 after initial missing-module failure |
| `python3 api/tests/run_isolated.py` | Exit 0, 381/381 |
| `python3 scripts/modernization/verify_profile_pilot.py` | Exit 0, native PostgreSQL profile checks pass |
| Independent final review | No Critical, Important or Minor findings; reviewer separately ran 8/8 service/adapter tests |
| AST/import inspection and diff check | Bootstrap creation and legacy UUID SQL unchanged; no new service/repository imports of Flask, model facades, dotenv or configured engine; `git diff --check` passes |

New tests verify actors required before I/O, concealed foreign read/update denials even for malformed inputs, exact profile projection, allowed-field filtering, one transaction, empty update rejection, missing rows, post-update failure rollback, trusted facade compatibility and foreign HTTP denial before malformed JSON parsing. Existing profile/bootstrap/principal tests remain unchanged and active.

[Native PostgreSQL report/source hashes](evidence/mod-038-profile-postgres-2026-10-29.json) verifies ID projection including UUID/timestamp types, bound string values, unchanged email/UUID/ID, own update, foreign/identity-only denial, missing profile and legacy facade outcomes. A BEFORE UPDATE trigger raises a real statement failure, and a deferred constraint trigger raises at commit; neither persists the attempted name. These are synthetic fixture triggers only, not schema migrations.

Only marked loopback PostgreSQL was used; the runner creates/removes its own random database, never loads `.env` and accepts no DSN. Task-owned container `otm-mod038-profile-20261029` was stopped/removed. Existing containers and prior transaction/roster evidence remain unchanged. No frontend files/checks, hosted DB access, dependencies, listener startup or deployment. This verifies the read/update slice, not a profile-creation migration or new concurrent identity guarantee.

## MOD-038 roster continuation — 2026-10-29

User requested another domain under the approved incremental hybrid. Roster was selected because its two reads combine policy and locked-week orchestration with SQL; the cohesive single-query sport model was deliberately left alone. Prior uncommitted transaction-pilot changes were preserved.

Baseline guarded suite: 366/366, exit 0. Seven direct service tests first failed on the absent service, then passed after extraction. The first SQL run exposed a missing separator before the reused access predicate; the scoped query was corrected and all cases passed. New tests verify actor requirements before I/O, one connection, commissioner/member scope, locked-week pending filters, late revocation, target-member deletion, missing-week behavior, no-future-week domain failure/legacy ValueError and explicit trusted reads. Existing roster tests remain unchanged.

| Verification | Fresh result |
| --- | --- |
| `python3 api/tests/run_isolated.py test_roster_service.py` | Exit 0, 7/7 |
| `python3 api/tests/run_isolated.py` | Exit 0, 373/373 |
| Independent review of roster code/callers and all four roster suites | No Critical/Important findings; 26/26 tests pass |
| `python3 scripts/modernization/verify_roster_pilot.py` | Exit 0, native PostgreSQL roster checks pass |
| Dependency inspection and guarded imports | No service/repository imports of Flask, model facades, dotenv or configured engine |
| `git diff --check` | Exit 0 |

[PostgreSQL evidence with source hashes](evidence/mod-038-roster-postgres-2026-10-29.json) verifies native JSONB pending moves, locked-week forwarding, exact member projection, availability ordering, season-filtered conference joins, tier fallback confined to the correct sport, commissioner/member access and outsider denials. Separate-connection revocation before each data query suppresses rows; commissioner access also cannot expose an orphaned target member. Missing next unlocked week raises the designated domain failure.

The runner refuses unmarked servers and accepts no DSN/.env; only a random synthetic database on the dedicated loopback container was used. Database and task-owned container `otm-mod038-roster-20261029` were removed, other containers untouched. Source hashes for the preceding transaction pilot still match. No hosted database, deployment, frontend changes/checks or listener startup.

Review minor deferred: the HTTP endpoint retains its existing compatibility-model attribute although both read methods now call the service directly. This costs one unused lightweight object construction per endpoint instance, with no extra engine/connection; removal is future composition cleanup. It is not an unresolved authorization/correctness issue.

## MOD-038 transaction-domain pilot — 2026-10-29

User approved the architecture and requested its bounded transaction read/trusted-apply implementation. Baseline guarded backend 359/359 passed. Seven direct service regressions initially failed on missing implementation, then passed. New cases verify required interactive actors, one read connection, commissioner/member projection, query-time revocation, explicit trusted reads, one command transaction, replay rejection, invalid types/deadlines and rollback after ownership closure. Existing HTTP authorization, model helpers, proposal/response, free-agency and operational/trade suites remain active and unchanged.

| Verification | Fresh result |
| --- | --- |
| `python3 api/tests/run_isolated.py test_transaction_service.py` | Exit 0, 7/7 |
| `python3 api/tests/run_isolated.py` | Exit 0, 366/366 |
| `python3 scripts/modernization/verify_transaction_pilot.py` | Exit 0, marked disposable PostgreSQL direct/dispatcher concurrency and transaction reads pass |
| Dependency inspection + guarded suite | New service/repository/actor paths import no Flask, model facade, dotenv or configured engine; imports remain network/listener-free |
| `git diff --check` | Exit 0 |

[PostgreSQL results and source hashes](evidence/mod-038-pilot-postgres-2026-10-29.json) record actual lock waits, one transfer, compatible ValueError replay rejection and half-open ownership intervals through both direct model facade and pending dispatcher. Native JSONB/LATERAL projections, commissioner-without-membership and member reads, denied/missing resources and query-time membership revocation also pass. Harness creates a random database only after verifying the synthetic loopback server marker and removes only its own database. Task container `otm-mod038-pilot-20261029` was stopped/removed; existing local containers were not changed.

Before: HTTP adapter → model → private LeagueModel policy / engine SQL; trusted dispatcher → model-owned trade transaction. After: HTTP adapter → UserActor → TransactionService → TransactionRepository on one supplied connection; trusted dispatcher → legacy facade → service-owned transaction → repository SQL. Legacy helper methods delegate to connection-aware service validation, preserving existing proposal/response callers without service-to-model dependencies. LeagueModel's policy method delegates to the extracted pure SQL helper.

Independent final review found no Critical, Important or Minor issues. No test required skipping or changed compatibility expectations. No frontend code changed or frontend tests/build rerun. No hosted/provider DB, production process, schema migration, listener or deployment was used. Other domain migrations, HTTP trade-response connection behavior, generic wire-error migration, broader ownership/conference consolidation and lifecycle work remain outside this pilot.

## MOD-041 authentication slice — 2026-10-29

User approved the architecture and requested implementation in the current checkout. First bounded slice covers MOD-028A plus basic HTTP correlation/cache behavior. Full architecture migration is not implemented.

| Check | Fresh result |
| --- | --- |
| `python3 api/tests/run_isolated.py` | Exit 0, 359/359; baseline 354/354 |
| frontend `node --test --experimental-strip-types tests/*.test.ts` | Exit 0, 62/62; baseline 45/45 |
| frontend `npm run build` | Exit 0, TypeScript and Vite production build |
| frontend `./node_modules/.bin/eslint src/api/client.ts src/api/authenticatedFetch.ts` | Exit 0; browser-mapping data freshness notice only |
| `git diff --check` | Exit 0 |

New auth-boundary tests initially failed against legacy string auth errors and absent response headers, then passed. Existing authorization tests were updated only where they asserted the intentionally replaced middleware error shape; resource/principal outcomes remain unchanged. Browser tests exercise the real transport with injected SDK/network boundaries and real Request/Response objects. They cover foreign origin/path/traversal and redirects, explicit bootstrap tokens, method/header/body preservation, shared/late refresh, one-retry budgets, no refresh for permission/legacy errors, no replay on ambiguous network failures, cancellation during refresh and after headers, and token-lookup timeout.

One independent final reviewer found an Important account-switch race: pending A operations could replay with B's current SDK token. Three real-facade regressions reproduced switching before refresh, during refresh and before late cached replay. All passed after subject continuity and current-token checks before every replay. No Critical/Minor findings were reported. The token subject is parsed only for session continuity; server JWT verification remains authoritative.

Limits: injected SDK/network tests do not establish live Supabase refresh behavior, deployed Render/CORS behavior or real browser compatibility. Native AbortSignal.timeout/any require modern browsers. Default total request timeout is 30 seconds, explicitly overridable with a finite positive timeoutMs. Endpoint errors remain legacy except missing/invalid middleware authentication denials; request IDs are response headers for all Flask responses and in the new auth body. Framework-wide safe-error envelopes, resource-size limits, telemetry, provider budgets and lifecycle migration remain separate work. No rate limiter, deployment, dependency installation, production process or database connection was used.

## Earlier verification records

Latest result: **MOD-003B complete** in bounded HTTP/application authorization scope. Final guarded backend **256/256 pass**, exit0, including prior profile/state/live/control/transport assertions. Diff check passes. No frontend changes/checks rerun; prior results are historical. PostgreSQL/RLS/concurrency/notification/browser/live-socket limits remain; no production used.

2026-10-28. Read with [behavior checklist](behavior-checklist.md), [backlog](backlog.md), [database audit](database-audit.md), and [progress](progress.md). Baseline is checkout `162f89a` plus the pre-existing modification to `api/startSeasonJobs/configs/ncaa-mens-basketball-2026.json` and untracked modernization docs. This is not a clean-HEAD or deployed-production result.

**Original baseline result (historical):** original suites passed (66 backend + 34 frontend utility + 9 tier-tool tests). Added 12 backend tests: 10 pass and **two fail on known profile-isolation defects**. Final backend suite is **76 passing / 78 total, exit 1**. Frontend build and tier type check pass; frontend lint has **63 pre-existing errors and 11 warnings, exit 1**. There is no all-green regression gate yet. No failure was fixed, skipped, marked expected-failure, or converted into a compatibility requirement.

## Tools, prerequisites and isolation

Used installed Python 3.14.1 and Node v22.22.2, the existing `unittest`/Node test runners, TypeScript/Vite/ESLint, and existing dependencies. No dependency installation, new browser framework, production process, network request, deployed database connection, migration, scoring job or rebuild command was run.

Installed backend versions checked: Flask 3.1.2, SQLAlchemy 2.0.44, PyJWT 2.10.1, Flask-SocketIO 5.6.0, python-dotenv 1.2.1, psycopg2-binary 2.9.11 and requests 2.32.5. Vite build reports 7.2.6. These describe this machine; the repo still lacks a documented/pinned complete runtime setup (MOD-034). Frontend `node_modules` was already present. Node must support `--experimental-strip-types`; backend prerequisites are in `api/requirements.txt`.

New `api/tests/run_isolated.py` is the canonical safe backend entry point for this baseline. It clears inherited environment values and supplies only a synthetic project ID/JWT secret, disables dotenv loading before test discovery, blocks SQLAlchemy engine creation and psycopg2.connect, and blocks common socket connection/DNS/datagram paths. It never imports the production app factory. It is a guard for these unit suites, **not an OS/network sandbox**: future tests using other native clients/subprocesses must be reviewed separately. Do not replace this command with web/CLI startup or assume arbitrary future tests are safe.

Profile tests use per-test `sqlite3.connect(':memory:')` data with `.test` emails and fixed synthetic UUIDs, real JWT signing/verification, middleware, registered user routes, endpoints and UserModel SQL. The small result adapter executes the actual compatible SQL subset; it does not simulate authorization. SQLite does **not** validate PostgreSQL types, role privileges, RLS, migrations, auth.users constraints, locking or transaction concurrency. Its minimal User fixture is test data, not a new schema baseline. Connections close after each test.

Draft contract tests use real registered handlers, serializer and room broadcast function with a substituted persistence/state model and an intercepted socket emitter. They do not open sockets or prove model transitions/room authorization. Tiebreak tests use the real resolver with hand-derived game inputs, replacing stored-game retrieval only. Existing bootstrap tests substitute providers/DB and use temporary checkpoints; their simulated ERROR output is intentional fault-path output, not an additional suite failure.

## Commands and actual results

Commands are from repository root unless the directory column says otherwise. Initial backend run was after adding the safety runner but before any new test cases; existing test files were not modified. Final runs used the same runner with all new tests discovered.

| Directory | Command / actual invocation | Actual result |
| --- | --- | --- |
| Root | `python3 --version`; `node --version` | Python 3.14.1; Node v22.22.2; exit 0. |
| Root | `python3 api/tests/run_isolated.py` — original suite | 66 tests, 66 pass; exit 0. |
| `front-end` | `node --test --experimental-strip-types tests/*.test.ts` — initial and final | 34 tests, 34 pass; exit 0 both runs. |
| `front-end` | `npm run basketball:tiers:test` — initial and final | 9 tests, 9 pass; exit 0 both runs. |
| `front-end` | `npm run basketball:tiers:typecheck` | TypeScript check passes, exit 0. |
| `front-end` | `npm run lint` | 74 findings: 63 errors / 11 warnings; exit 1. Pre-existing, no frontend files modified. |
| Temporary sanitized frontend copy | `npm run build` (`tsc -b && vite build`) | Exit 0; 220 modules transformed; build completed. Artifact discarded with temp copy; no preview/deploy/runtime test. |
| Root | `python3 api/tests/run_isolated.py 'test_profile_regression.py'` | 7 tests: 5 pass, 2 fail on known MOD-002 defects; exit 1. |
| Root | `python3 api/tests/run_isolated.py` — final | 78 tests: 76 pass, 2 failures, no errors/skips/expected failures; exit 1. Original 66 still pass. |

Targeted reproduction commands for later work (final full run already includes these files):

```sh
python3 api/tests/run_isolated.py 'test_profile_regression.py'
python3 api/tests/run_isolated.py 'test_draft_contracts.py'
python3 api/tests/run_isolated.py 'test_weekly_tiebreak_baseline.py'
```

The build was run by copying `front-end` to a Python TemporaryDirectory, excluding `.env`, `.env.*`, `node_modules`, `dist` and `.git`; symlinking the existing node_modules; removing inherited VITE_/SUPABASE_/DATABASE_ variables; setting synthetic VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY and VITE_API_BASE_URL; and invoking `subprocess.run(['npm', 'run', 'build'], cwd=copy, env=sanitized_environment)`. This avoids reading build env files/embedding live configuration. TypeScript may update ignored `node_modules/.tmp` build metadata via that symlink. The copy and bundle were discarded. A direct `npm run build` in the source checkout would load its local env and is not the exact invocation used here.

Detailed stdout/stderr was inspected during the run and kept in temporary `/tmp/modernization-*.log` files; those are ephemeral, not portable repository artifacts. The counts/failure inventory below are the durable record. Commands are reproducible; no production credentials are needed for the unit tests.

## Pre-existing failures, reproduced rather than preserved

### Profile isolation — MOD-002 / backend D01

Both new negative tests run ordinary assertions and remain in default discovery. They expose an existing defect, not a regression introduced by the tests. They expect denial (403 or 404) and no private-data exposure/write; exact denial contract remains an implementation decision.

| Test | Actual result / evidence | Limit |
| --- | --- | --- |
| `ProfileRegressionTests.test_mod_002_foreign_profile_read_is_denied` | Alice's locally signed valid token GET `/api/user/2` returns **200**, not 403/404, exposing Bob's synthetic profile. | Real middleware/route/model SQL on synthetic in-memory rows; not a production exploit or RLS test. |
| `ProfileRegressionTests.test_mod_002_foreign_profile_update_is_denied_without_changing_data` | Alice PATCHes `/api/user/2` with displayName Tampered and body userId=1; Bob's persisted synthetic displayName becomes **Tampered**, not Bob. | Demonstrates actual unintended write in fixture, not only response status. No real account changed. |

Root cause evidence: middleware validates JWT into g.user, but registered user endpoints pass URL user ID to UserModel without consuming/binding the subject. The fixture DB executes that SQL and intentionally supplies no nonexistent row-isolation layer. This matches the source audits. Deployed roles/RLS are unknown. At this baseline stage only isolation/regression evidence existed. MOD-001 resolver completion is recorded below; MOD-002 authorization remains unimplemented.

### Frontend lint — existing findings

No frontend source was changed. The lint rule totals are:

| Rule | Errors | Warnings |
| --- | --- | --- |
| `@typescript-eslint/no-explicit-any` | 47 | 0 |
| `react-hooks/rules-of-hooks` | 12 | 0 |
| `react-refresh/only-export-components` | 3 | 0 |
| `no-unsafe-finally` | 1 | 0 |
| `react-hooks/exhaustive-deps` | 0 | 11 |

The 12 conditional-hook errors are in `src/screens/League/LeagueDraftPage.tsx` at 673, 686, 709, 727, 738, 750, 782, 790, 800, 807, 823 and 839. They warrant focused reproduction/regression protection before draft structural extraction (MOD-031A); a successful TypeScript/build does not clear hook-order risk. `ManageLeaguePage.tsx:305` has no-unsafe-finally. Fast-refresh export findings are `AuthContext.tsx:148`, `currentUserContext.tsx:94` and `BonusesEditor.tsx:38`.

Complete per-file location ledger below: A = no-explicit-any, H = rules-of-hooks, R = only-export-components, F = no-unsafe-finally, W = exhaustive-deps. Lines refer to this checkout.

| Frontend file | Findings by rule / line |
| --- | --- |
| `src/components/League/LeagueScheduleTabs.tsx` | W: 295 |
| `src/components/League/PendingTransactionsPanel.tsx` | A: 58 |
| `src/components/League/TradeRequestsPanel.tsx` | A: 46, 86, 99, 112 |
| `src/context/AuthContext.tsx` | R: 148 |
| `src/context/currentUserContext.tsx` | R: 94 |
| `src/screens/Auth/ResetPassword.tsx` | A: 31 |
| `src/screens/Auth/SignIn.tsx` | A: 85, 116 |
| `src/screens/Auth/UpdatePassword.tsx` | A: 69 |
| `src/screens/CreateLeague/BonusesEditor.tsx` | R: 38 |
| `src/screens/CreateLeague/CreateLeague.tsx` | A: 101 |
| `src/screens/League/ConferenceSchedulePage.tsx` | A: 139, 193, 260 |
| `src/screens/League/DiscoverLeaguePage.tsx` | A: 53, 84, 146 |
| `src/screens/League/LeagueDetailPage.tsx` | A: 107, 143, 202, 270, 288 |
| `src/screens/League/LeagueDraftPage.tsx` | A: 87, 172, 566, 636, 902; W: 245, 370, 500, 571; H: 673, 686, 709, 727, 738, 750, 782, 790, 800, 807, 823, 839 |
| `src/screens/League/LeagueRosterPage.tsx` | A: 112, 154, 191, 235, 370, 399; W: 294, 298, 302 |
| `src/screens/League/ManageLeaguePage.tsx` | A: 269, 298, 412, 458, 488, 507, 517, 545, 565, 612; W: 285, 321, 500; F: 305 |
| `src/screens/League/TeamLookupPage.tsx` | A: 70, 105 |
| `src/screens/League/TeamSchedulePage.tsx` | A: 94, 128 |
| `src/screens/Settings/SettingsPage.tsx` | A: 40 |

## Small additions and regression intent

12 added tests in three files; no existing test was rewritten and no app file was changed.

| Test file / count | Checklist/features | Observable behavior protected / plausible break caught |
| --- | --- | --- |
| `api/tests/test_profile_regression.py` — 7 | J1 partial, K0/K1; F-002/004/022 | Anonymous/malformed/empty bearers cannot read/write; real expiry/signature/issuer/audience validation; preflight cannot update; own save/reload and JSON identity fields preserved; non-whitelisted fields cannot alter identity/email; missing/empty-update status/message contracts; two-account denial tests expose current failures. Does not automate login/signup/browser context or league list. |
| `api/tests/test_draft_contracts.py` — 3 | J3 transport slice, K6; F-013/023 | Successful pick is 201 JSON with serialized date and matching league-scoped event; rejected/expired/conflicting/constraint-failed pick returns client/conflict error with no success event; missing inputs cannot execute a pick or emit success. Model is substituted, so no assertion of real pick/concurrency/room authorization. |
| `api/tests/test_weekly_tiebreak_baseline.py` — 2 | J4 calculation slice, K7; F-009/025/032 | Head-to-head winner beats larger single-game margin; without H2H result use largest absolute margin including losses; lower untied member and differential values stay intact. Fixture expectations are literal, not computed with production helpers. |

Retained existing regression value: J2 trimmed/nonblank create/join names and rule-version pinning; J4 tier adjustment (home/away/both-owned), tournament clamp/multiplier/order, week0/opening/final-period/timezone boundaries, daily totals, schedule pagination and ranks; locked roster forwarding; bootstrap failure/checkpoint/resume; tier-analysis symmetry/conference overrides/CSV output. These are bounded model/helper tests, not full journeys. Unresolved final ties are deliberately not frozen into a new ranking policy; behavior/product review is still needed before formula changes.

Test sensitivity was checked in **temporary API copies only**, each running the guarded runner with its targeted file:

- Replacing JWT verification with unconditional claims caused `test_expiry_signature_issuer_and_audience_are_verified_before_profile_access` to fail.
- Changing draft turn/expiry conflict from 409 to 200 caused `test_rejected_or_conflicting_pick_never_emits_success` to fail.
- Removing H2H resolution before single-margin fallback caused `test_head_to_head_winner_precedes_single_margin_without_reordering_non_tied_members` to fail.

All three mutation probes exited 1 with the intended assertion failure. Repository application sources were not mutated; temporary copies were discarded. This checks three representative failure modes, not exhaustive mutation coverage.

## Unverified areas and deferred feature-specific gaps

| Area | Gap / missing prerequisite | Follow-up |
| --- | --- | --- |
| J1 account/profile/leagues; F-002–005/022 | No browser login/signup/confirmation/recovery, provider race/account-switch, current-user direct Supabase policy or Home feedback tests. Need disposable Auth/Supabase project or SDK/browser fixtures and browser harness. | MOD-001/002/004/006/026/027A/028A; F-003 recovery manual only. |
| J2 create/discover/approve; F-006–008/017–019/021/029 | No full admission, capacity/concurrent approval, delete/cascade or cold-link journey. Name/rules unit checks do not execute malformed denial SQL or real FK/status constraints. Need disposable PostgreSQL/Supabase baseline and role policy Q1/Q4; never prod deletion. | MOD-003A/005/008/011/012/027D. |
| J3 draft; F-013/014/018/020/023/024/030 | Contract tests omit real pick/state/order/timeout/locking, multi-client sockets/reconnect and membership revocation. Conditional hooks need isolated browser reproduction before component moves. Need fake timer/transport or isolated socket server and synthetic leagues. | MOD-003B/023–025/031A; address hook finding separately before extraction. |
| J4 schedule/scoring; F-009–012/025–028/031/032/035/036 | No real SQL query/constraint/index plans, score replacement rollback/concurrent jobs, season-finalization CLI lifecycle, historical rebuild ownership remap or provider correction integration. Existing “integration” test names largely use mocks. Need executable schema/disposable DB, historical fixtures and provider fakes. | MOD-005/007/008/013–017/021/022. |
| J5 transactions; F-015/016/025/033 | No end-to-end propose/respond/veto/apply, caller isolation, replay, duplicate reservation, concurrency, pending-panel refresh or job timing checks. Need Q3/Q4 policy and transaction fixtures/isolated Postgres. | MOD-003C/009/010/013/027B. |
| Database access paths | Deployed RLS/grants/owners/functions/triggers/scheduler/drift not available. SQLite profile tests cannot prove direct Supabase or privileged-backend isolation. | MOD-004/005. |
| UI/navigation/accessibility; F-001/005–021 | No browser/React render harness installed or screen-reader/keyboard/reflow tests. Known labels/modal/reorder and search-loading gaps remain. No DOM library added merely to increase coverage this run. | MOD-027A–G/029/031/036. |
| Operational health/CLIs; F-023–028/034/036 | Production scheduler, credentials, supervision, notifications/delivery/readiness and checkpoint durability unknown. Do not start app factory/jobs as a smoke test. | MOD-014/016/024/034. |
| Tier analysis / legacy; F-037–041 | Existing 9 tier tests pass; no provider/CLI/cache integration or external-usage evidence. No basis to remove dormant/deprecated alternatives. | MOD-035/036. |

No coverage percentage or all-feature contract/security guarantee is claimed. No lint/type/build check establishes runtime authorization. Existing lint and the two isolation failures remain blockers for an all-green gate; preserve their visibility, not the defective behavior.

## Concise manual smoke checklist — not executed

Prerequisite: confirmed disposable/local environment with synthetic accounts A/B, a synthetic league/season, explicit isolated URLs, known role policy and operator-controlled job/provider fixtures. Do not use production signup/email, deletes, trades, scoring or rebuilds for this checklist. Until prerequisites exist, mark **not run**, not passed.

- [ ] **J1:** Sign in as A, save display name, refresh and inspect own leagues; sign out and sign in as B in the same browser. No stale A profile/league data. Check rejected login, slow/missing profile and expired session; attempt cross-user profile read/PATCH only in isolation (known failure).
- [ ] **J2:** A creates league/team; B discovers, opens a fresh direct URL, submits join request; A approves; both refresh membership. Try blank name, wrong actor/league/request and repeated submit; use synthetic records for removal only.
- [ ] **J3:** Configure order, start, pick, pause/resume and trigger a controlled timeout in two clients; rejected picks show no success; reconnect/refresh converge; nonmember cannot receive another league's room data; finish and inspect history. Watch console for hook-order/runtime errors.
- [ ] **J4:** With fixed games/ownership, compare roster → member/team/conference schedule → standings for current and historical week, both-owned/tier-adjusted game and final period. Include empty/error/refresh-after-fixture-ingestion. Use fixture operator only for scoring.
- [ ] **J5:** Propose/accept/cancel/veto/add-drop on synthetic rosters, verify open/pending lists refresh and pending acceptance does not imply applied ownership. Controlled application once, replay/conflict rejection, refresh both clients. No production jobs.
- [ ] **Shared:** Keyboard labels/forms/order/dialog focus; direct URL/back/refresh; empty versus failed load; failed submit retains input; expired-token recovery does not duplicate mutation. Record expected failures with backlog ID rather than marking journey passed.

## Handoff boundary

Changed only test files/runner plus this verification document and progress log. No principal implementation, authorization fix, schema/application refactor, dependency/config change, migration, deployment or production test. MOD-001 remains incomplete beyond regression isolation; next implementation still starts with principal binding and MOD-002. Stop here per request.


## MOD-001 resolver verification — 2026-10-28

This section supersedes the earlier baseline handoff for MOD-001 only. Added `api/authenticatedPrincipal.py` and `api/tests/test_authenticated_principal.py`; reused the unchanged guarded runner and synthetic profile fixture. No existing profile denial test or endpoint was changed.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_authenticated_principal.py'` before implementation | Exit 1: import error for absent `authenticatedPrincipal` module; confirms the new boundary did not exist. |
| `python3 api/tests/run_isolated.py 'test_authenticated_principal.py'` after implementation | 9 tests, 9 pass; exit 0. |
| `python3 api/tests/run_isolated.py 'test_profile_regression.py'` | 7 tests, 5 pass, 2 ordinary MOD-002 failures; exit 1. |
| `python3 api/tests/run_isolated.py` | 87 tests, 85 pass, 2 ordinary failures; no errors/skips/expected failures; exit 1. |

New tests cover verified A/B subject mapping despite conflicting URL/body/query/header actor IDs, missing/expired JWTs, absent/empty/blank subject, absent/duplicate application identity, unverified request context, no-request/job/app contexts, immutable identity, and database-error propagation. Real middleware/JWT verification runs on the test-only HTTP route; resolver SQL runs against synthetic in-memory SQLite. Duplicate UUIDs are created only by loosening the disposable fixture, with no schema change. Results contain only subject/application ID; profile data is not fetched. Errors expose stable codes (401 missing request/subject, 403 missing/ambiguous mapping), to be serialized by future adopting adapters. No endpoint currently gains authorization from this addition.

The preserved failures remain exactly `test_mod_002_foreign_profile_read_is_denied` (Alice GET of Bob returns 200) and `test_mod_002_foreign_profile_update_is_denied_without_changing_data` (Bob's stored name becomes Tampered). The full suite remains red; this is expected deferred MOD-002 work, not a passing authorization gate.

Limits: no PostgreSQL/RLS/live-schema/browser verification; the resolver trusts the middleware-owned `g.user` after authentication and must be called after middleware. Trusted jobs do not receive a fallback principal or HTTP bypass. No frontend recheck, production connection/modification, listener/app startup, schema change or job execution. MOD-001 complete; next is MOD-002 adoption/public-data repair, not performed here.


## MOD-002 stage 1 verification — 2026-10-28

Selected stage: authenticated numeric-ID profile GET/PATCH only. Actual dependency inspection confirmed MOD-001 exists and uses middleware-owned `g.user.sub`; no assumption of endpoint adoption was made. `UserEndpoints.get_user/update_user` now consume it, deny URL/principal mismatches with 404 and a generic message, and serialize resolver errors (401 missing subject, 403 absent/ambiguous application mapping). Success payloads and display-name-only update behavior remain unchanged. No schema or frontend changes required for this stage.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_profile_regression.py'` before source changes | 12 tests, 14 failing assertions/subtests, exit 1. Original cross-user read/write failures reproduced; new mapping/substitution tests also fail. Expired PATCH already denied by middleware. |
| Same targeted command after implementation | 12/12 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 92/92 pass, exit 0; no errors/skips/expected failures. Includes all nine principal tests. Bootstrap fixture's simulated ERROR output is intentional. |
| `git diff --check` | Exit 0. |

Five added profile tests exercise both users' own reads and foreign GET/PATCH denial despite URL/body/query/header actor substitution, missing/ambiguous identity denial on both methods, empty subject and expired PATCH. Denial tests inspect persisted names and safe JSON; the original two MOD-002 denial assertions remain unchanged and now pass. Existing own-profile save/reload confirms identity/email cannot be rewritten via PATCH, and success payload/validation/preflight contracts continue to pass. The only fixture adapter addition is real SQLite cursor `fetchmany`, needed by the production resolver's duplicate detection query.

Boundary: this green suite verifies the numeric-ID HTTP slice in isolation, not all account access paths. `/api/user/byUuid/` remains public in the production configuration, POST provisioning still trusts supplied UUID/email, and public commissionerEmail/profile logging remain for later MOD-002 stages. No claim that full MOD-002 is complete. Q1 public projection remains unresolved. Direct browser Supabase/RLS, PostgreSQL constraints/locking and identity-remapping concurrency remain unverified. No app factory/listener, job, production access/mutation, schema/migration, dependency upgrade or frontend check was run. Next: remaining MOD-002 lookup/provisioning plus consumer coordination, then public projection/log minimization; no other task started.


## MOD-002 stage 2 verification — 2026-10-28

Bounded scope: authenticated own-subject UUID lookup and claims-bound profile provisioning, including frontend bootstrap coordination and removal of creation's raw profile log. No public search projection decision was made. The bootstrap subject helper is shared with MOD-001's principal validator; missing application identity is accepted only for this subject-bound provisioning flow. No trusted-job HTTP fallback was added.

| Command from root (frontend commands from `front-end`) | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_profile_bootstrap.py'` before implementation | Nine tests, 15 failing assertions/subtests; exit 1. Demonstrated public UUID exposure, foreign lookup and provisioning binding gaps. |
| Same targeted command after implementation and constraint-error test addition | 10/10 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 102/102 pass, exit 0; no skips/expected failures. Includes unchanged original numeric cross-user denial assertions. |
| `node --test --experimental-strip-types tests/profileApi.test.ts` initially | Five request tests: two pass, three fail, exit 1 (skipAuth, body identity fields, SDK lookup despite explicit token). |
| Same targeted command after implementation and hook tests | 8/8 pass, exit 0. |
| `node --test --experimental-strip-types tests/*.test.ts` | 42/42 pass, exit 0. |
| `./node_modules/.bin/tsc -p tsconfig.app.json --noEmit` | Exit 0. |
| `./node_modules/.bin/eslint src/api/user.ts src/api/client.ts src/context/AuthContext.tsx tests/profileApi.test.ts` | Exit 1: one existing `react-refresh/only-export-components` error at AuthContext.tsx:149; no other lint findings. Tool also emits a baseline-browser-mapping age notice; no package update made. |
| `git diff --check` | Exit 0. |

Backend tests use real JWT/middleware/routes/model SQL against synthetic SQLite, reusing the existing fixture with added insert-result `_mapping` support. They parse only the real factory's auth allowlist AST, never import/run the factory. Coverage: anonymous/invalid/expired and own/foreign UUID lookup; missing-profile → create → reload; legacy matching fields versus forged UUID/email; existing/ambiguous identity; missing subject/email; object/name validation; no creation-profile debug payload. One constraint-error test injects SQLAlchemy IntegrityError at INSERT to verify generic 400 and unchanged rows. This is error-path injection, not PostgreSQL validation. Bootstrap logs' simulated ERROR lines in the full suite remain intentional fixtures.

Frontend tests transpile actual user API/client/AuthContext modules using installed TypeScript into a VM with isolated SDK/transport/React-hook/storage/document substitutes. They verify authenticated lookup and explicit token, displayName-only creation, 404-only null behavior, SDK session fallback/explicit-token avoidance, and existing/missing/denied bootstrap decisions/storage markers. They do not render React, contact Supabase or exercise browser scheduling/account switching. Type-check covers application sources; tests run via Node TypeScript stripping/transpilation.

Deliberate contracts: UUID lookup is now authenticated/private; own missing/foreign UUID gives 404, ambiguity 403. POST trusts verified sub/email, not body identity: matching legacy fields remain accepted, conflicts 403, missing email claim 403, invalid object/name 400, existing profile 409, ambiguity 403, successful creation 201. Success profile fields remain unchanged. Backend constraint details no longer reach responses and created profile is no longer debug-logged. JWT email freshness/provider state is not checked remotely; no email-change feature added.

Limits/next: full MOD-002 still needs Q1 public league-search field decision and commissionerEmail minimization/consumer verification. UUID snapshot uniqueness/concurrent provisioning, legacy remediation and provider consolidation belong to existing MOD-006/005/026; sequential checks here do not prove race safety. Deployed DB/RLS/direct SDK access, real signup/confirmation, browser lifecycle and historical logs remain unverified. No schema/migration, job, app/listener startup, environment values, network or production mutation used. Stop after this stage.


## MOD-002 final public-search privacy verification — 2026-10-28

User decision: keep commissioner email private. Removed only `commissionerEmail` from `LeagueModel.search_leagues` SQL projection and frontend `LeagueSearchResult`; Home search cards consume commissioner display name, not email. Public discovery retains ID, name, sport, capacity, status, draft date, discoverability, commissioner ID and display name. Response shape deliberately loses email; filters/pagination/public access are unchanged. The broader Q1 role matrix remains outside MOD-002.

| Command (root unless specified) | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_public_league_search.py'` before implementation | Initial fixture setup: four errors from missing synthetic ESPN URL; supplied test-only URL without changing application code. Corrected baseline: four tests, one ordinary failure (commissioner email exposed), three pass; exit 1. |
| Same targeted command after implementation | 4/4 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 106/106 pass, exit 0, no skips/expected failures. Prior cross-user profile denial assertions remain intact and pass. |
| `front-end`: `node --test --experimental-strip-types tests/*.test.ts` | 42/42 pass, exit 0. |
| `front-end`: `./node_modules/.bin/tsc -p tsconfig.app.json --noEmit` | Exit 0; verifies consumers against the reduced search type. |
| `front-end`: `./node_modules/.bin/eslint src/types/league.ts` | Exit 0; dependency-age notice only. Full lint not rerun; previously documented errors remain. |
| `git diff --check` | Exit 0. |

Four new tests execute real registered search handlers/middleware/model SQL using SQLite synthetic discoverable/hidden leagues with a commissioner contact value that must not appear in JSON. They assert exact retained fields, no email, anonymous access, hidden-league exclusion, sport filtering, page offset/limit, short/no-match query results and invalid-parameter JSON status. Actual auth allowlist is parsed without running/importing the factory. SQLite adapts ILIKE to LIKE and substitutes constant similarity; these tests do not prove PostgreSQL trigram ranking, collation, deployed privileges or query performance. A synthetic provider URL is set only during route construction; no provider/network call occurs.

MOD-002 is complete within its documented application/API boundary across stages 1–3. No production connection/mutation, schema/migration, dependency upgrade, app/listener startup, job or deployment occurred. Real browser lifecycle, direct Supabase/deployed RLS, historical logs and PostgreSQL concurrency remain unverified. MOD-006 owns concurrent unique provisioning after MOD-005 evidence; no race-safety claim is made here. Recommended next implementation: MOD-003A with its remaining role-policy decisions, not additional MOD-002 work. Stopped after this task.


## MOD-003A stage 1 verification — 2026-10-28

Scope: existing self-service member PATCH only. Principal dependency checked in actual code; frontend caller is an own-team rename. Implemented owner-constrained teamName-only UPDATE, explicit principal errors, generic 404 for missing/foreign targets and 400 for unknown fields/non-object/nonblank-string violations. Response fields and valid rename behavior retained. Trusted general model update unchanged. Commissioner role does not bypass owner checks on this route; remaining administrative policies were not inferred.

| Command (root unless specified) | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_member_profile_authorization.py'` before implementation | Seven tests; 14 assertion/subtest failures, exit 1. Real synthetic unauthorized renames and score/order mutations reproduced; missing target returned old 400. |
| Same targeted command after implementation | 7/7 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 113/113 pass, exit 0; no errors/skips/expected failures, original MOD-002 denial assertions unchanged. Intentional bootstrap ERROR fixture output remains. |
| `front-end`: `node --test --experimental-strip-types tests/profileApi.test.ts` before frontend narrowing | 8/9 pass, one failure on score/order payload, exit 1. |
| `front-end`: `node --test --experimental-strip-types tests/*.test.ts` after narrowing | 43/43 pass, exit 0, including new rename request test. |
| `front-end`: `./node_modules/.bin/tsc -p tsconfig.app.json --noEmit` | Exit 0. |
| `front-end`: `./node_modules/.bin/eslint src/api/leagues.ts src/types/leagueMember.ts tests/profileApi.test.ts` | Exit 0; dependency-age notice only. Full lint not rerun; prior findings remain. |
| `git diff --check` | Exit 0. |

Seven new backend tests reuse the existing synthetic in-memory profile SQL result adapter and actual principal JWT/middleware/league route/model paths. Added synthetic League/LeagueMember rows for commissioner A, member B and nonmember C, with B also owning a member in another league. Own renames preserve all response/DB fields except teamName. Foreign targets, including commissioner's attempt to rename B and nonmember/cross-league substitution, fail without mutation. Extra score/order/identity/league fields cannot cause partial writes. Missing/expired auth, absent/ambiguous profile, invalid payload and missing member have explicit outcomes. Ownership is part of the UPDATE predicate; no separate check-then-write lookup. No parent league ID exists in this route; own membership defines its resource scope. The SQL fixture is not a deployed schema or PostgreSQL/RLS/concurrency test.

Frontend test executes actual API module with substituted transport and confirms even stale JavaScript extra arguments cannot serialize score/order fields. Type-check confirms the only UI caller matches the narrowed signature. No browser rendering or account-switch verification claimed.

Remaining: MOD-003A is partial; own-league listing/creation, commissioner administration, moderation/admission, week generation and scoped reads are unchanged. Next bounded recommendation: principal-bound `/api/league/byUser`; Q1 nonmember read and Q4 operational policy still need resolution for later slices. No new schema/migration, dependency, production/network/private-row access, environment values, job/app factory/listener or deployment. Stop after selected stage, not another backlog task.


## MOD-003A stage 2 verification — 2026-10-28

Scope: `/api/league/byUser` only. Actual resolver, current handler/model SQL and frontend caller checked before implementation. Body userId remains required for compatibility but must match the resolved principal; only the principal's ID reaches the listing model. Foreign ID is 403 `user_identity_mismatch`; missing/ambiguous profile or subject uses explicit resolver errors; malformed JSON objects/ID/stage types get safe 400 messages. Own successful payload and stage semantics remain unchanged. No public visibility/admin role decisions made.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_own_league_listing.py'` before implementation | Nine tests, nine assertion/subtest failures and one error; exit 1. Foreign listing and identity failures returned 200; invalid userId string raised uncaught ValueError. |
| Same targeted command after implementation | 9/9 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 122/122 pass, exit 0; no errors/skips/expected failures. Prior profile/member denial tests preserved and passing. Intentional bootstrap ERROR fixture output remains. |
| `git diff --check` | Exit 0. |

Nine added tests use actual JWT verification/middleware/registered routes/principal and model listing query with synthetic SQLite profiles, leagues, sport and memberships. They verify exact retained own fields (member-specific name/order/points, nullable current week and other league metadata), both users' isolation, commissioner/member/nonmember identity cases, empty own membership, stage active/completed/all/case/default/null/unknown-string behavior, matching numeric-string ID, forged body/header/query identities, missing/invalid/expired JWT, absent/ambiguous app identity/empty subject and invalid request shapes/IDs/stage. Denials are checked before substituted model lifecycle sync is reached.

Tests substitute `sync_due_league_statuses` to avoid unrelated lifecycle transitions; production status-sync code remains unchanged. SQL current-week interval expression is adapted to SQLite datetime with fixed now and no Week rows, and settings fixture is SQLite TEXT. These checks validate identity/query binding and compatible SQL fields, not PostgreSQL interval/JSON types, current-week boundaries, lifecycle transitions, deployed RLS/locking/concurrency or query performance. No frontend tests/type/lint rerun because frontend code is unchanged; prior results stay historical.

Remaining MOD-003A: league creation, commissioner administration/moderation/admission, operational week generation and other league-scoped reads. Recommended next: bind creation's commissioner/initial membership to the authenticated principal; Q1 nonmember read and Q4 operational decisions remain for their slices. No schema/migration/dependency/production/network/environment-value access, app factory/listener startup, job or deployment; no other backlog task started. Stopped after stage 2.


## MOD-003A stage 3 verification — 2026-10-28

Scope: principal-bound league creation and its initial membership only. Actual resolver/model/caller inspected. Commissioner remains a required compatibility field but must match principal; only resolved principal.user_id reaches the create model. Foreign commissioner returns 403 `commissioner_identity_mismatch`, invalid ID/object/missing fields JSON 400, auth/subject/profile absence/ambiguity explicit 401/403. Matching integer and numeric-string commissioner inputs remain supported. Success remains 201 with existing league/sportInfo/creatorMemberId shape; model retains team-name trimming, settings/rule/timezone handling and week initializer call. Frontend caller already conforms and is unchanged.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_league_creation_authorization.py'` before implementation | Eight tests, six assertion/subtest failures, two SQLite constraint errors on invalid commissioner values; exit 1. Foreign/missing/empty/ambiguous identities incorrectly permitted creation. |
| Same targeted command after implementation | 8/8 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 130/130 pass, exit 0; no errors/skips/expected failures. Existing denial assertions remain intact. Intentional bootstrap ERROR fixture output remains. |
| `git diff --check` | Exit 0. |

Eight tests reuse the guarded runner/profile fixture with synthetic League/LeagueMember/Sport rows, real JWT/middleware/routes/model and SQLite foreign keys. Creation fixture extracts the model's INSERT/RETURNING body from PostgreSQL CTE, replaces JSONB cast with a SQLite parameter and supplies synthetic equivalent sportInfo/settings projection. It executes real membership INSERT SQL. Tests check persisted commissioner and member user IDs for both A/B, response fields, initial points/order/name, forged body/query/header identities, required and invalid object/ID values, matching numeric-string commissioner, model name validation, and no persisted league/member or week initialization on rejection. Week initializer is substituted; this is not PostgreSQL CTE/JSON compatibility, actual scheduling, RLS, concurrency or browser verification.

No frontend checks rerun because frontend unchanged; previous frontend/lint/type results stay historical. The model's pre-existing league/member commit followed by week initialization is unchanged; initializer failure can occur after creation commits, and rollback/retry semantics for that boundary were not tested or repaired here. No schema/migration/dependency, production/network/private-row/environment values, app factory/listener, real week/job or deployment used.

MOD-003A remains partial: next recommended slice is principal-bound commissioner-only league settings PATCH, then other administration/moderation/admission/scoped-read operations. Q1 nonmember visibility and Q4 operational/week-generation policy remain open. Stop after stage 3; no other task started.


## MOD-003A stage 4 verification — 2026-10-28

Scope: commissioner-only league settings PATCH. Actual principal dependency, original update model/commissioner helper, frontend caller and existing rules tests checked. Handler now resolves principal, validates object shape and uses explicit checked `update_league_as_commissioner` model entry point. Shared update implementation verifies current commissioner before rules/settings validation and includes commissioner in final UPDATE predicate. Original trusted `update_league` remains separate from HTTP identity. Existing success fields, field allowlist (including name/capacity/status/settings/deadlines), rules-version/timezone behavior and missing-league 400 retained. No new role/lifecycle policy inferred.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_league_settings_authorization.py'` before implementation | Eight tests, six assertion/subtest failures; exit 1. Unauthorized member/nonmember/foreign commissioner and missing identity/empty-subject writes, plus stale-owner write reproduced. |
| Same command after implementation and operational-failure case addition | 9/9 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 139/139 pass, exit 0; no errors/skips/expected failures. Trusted-model rules tests and prior denial assertions unchanged and passing. Intentional bootstrap ERROR fixture output remains. |
| `git diff --check` | Exit 0. |

Nine tests use real JWT/middleware/registered route/model logic and synthetic profiles/leagues/member rows. SQL fixture extracts PostgreSQL UPDATE CTE's UPDATE/RETURNING body, adapts JSONB cast to SQLite storage and supplies equivalent synthetic sportInfo/decoded settings projection. It also executes actual league reads and parameterized owner predicate. Assertions cover valid A/B commissioner saves/response fields/persisted deadlines/name/capacity and pinned rules version; ordinary member, nonmember and another league commissioner denial; forged body/header/query actor and ownership-transfer attempts; missing/invalid/expired JWT, empty subject and missing/ambiguous application identity; existing empty-patch/settings/version/timezone/missing-target validation; non-object input; safe generic 500 on injected operational DB read error with unchanged row.

A deterministic fixture hook changes commissioner between initial read and UPDATE; former owner is denied and requested name/updatedAt do not change. This checks that final write enforces commissionership, not PostgreSQL transaction interleaving/locking or isolation levels. Shared read/write remains two transactions; no general concurrency/whole-operation atomicity guarantee. SQLite does not verify PostgreSQL CTE/JSON/types/RLS or browser behavior. Frontend unchanged; checks not rerun and historical results not claimed fresh.

Remaining MOD-003A: bind admission actors starting with join-request creation, then moderation/member removal/deletion and other scoped reads/week generation. Q1 nonmember visibility/Q4 operational policy remain open; no broader REST authorization completion claimed. No schema/migration/dependency/production/network/private-row/environment-value access, app/listener, job or deployment. Stop after stage 4; no other task started.


## MOD-003A stage 5 verification — 2026-10-28

Scope: join-request creation identity only. Actual model/caller/previous dependencies checked; legacy body userId remains required but must match verified principal. Only principal.user_id and URL league_id reach unchanged create_join_request model. Foreign userId is 403 `user_identity_mismatch`, missing/invalid ID/object JSON 400, principal absence/ambiguity/auth errors explicit 401/403. Success remains 201 with existing JSON fields; trimmed name, message, existing-member rejection and sequential own pending-repeat behavior retained.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_join_request_authorization.py'` before implementation | Nine tests, nine assertion/subtest failures; exit 1. Foreign creation/pending lookup and empty/missing identity bypasses reproduced; invalid boolean/fractional IDs also created requests. Some later subtest no-write assertions observe the preceding unauthorized fixture insert. |
| Same command after implementation | 9/9 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 148/148 pass, exit 0; no errors/skips/expected failures. Previous denial assertions remain unchanged. Intentional bootstrap ERROR fixture output remains. |
| `git diff --check` | Exit 0. |

Nine tests reuse the guarded runner and actual profile SQLite result fixture, with synthetic League/LeagueMember/LeagueJoinRequest tables, real JWT verification/middleware/registered route/model SQL. No SQL dialect adaptation needed for this query subset. Tests inspect persisted owner/league/name fields for A/B, deny forged userId before insert, prevent another user's pending response leakage through creation, ensure header/query/body actor and league fields cannot override verified owner/URL, retain own repeat response/no-overwrite, existing-member/name contracts, numeric-string ID compatibility and auth/identity/shape/type errors. Synthetic duplicate app mappings are created only in the disposable fixture. No existing assertions weakened or skipped.

No frontend changes/checks rerun; Discover already sends matching current user ID and team name. SQLite does not establish deployed PostgreSQL FK/role/RLS/concurrency behavior or browser journeys. Sequential pending reuse is not a concurrent uniqueness guarantee. Discoverability, private-league visibility, capacity/status admission policy, approval/denial/cancellation and moderator permissions are unchanged and outside this stage; broader Q1/Q4 decisions remain open. No production/network/environment/private-row access, app/listener/job, schema/migration/dependency/deployment or unrelated cleanup.

MOD-003A remains partial. Recommended next: commissioner-only join-request listing bound to principal, then remaining moderation and scoped operations. Stop after stage 5; no other task started.


## MOD-003A stage 6 verification — 2026-10-28

Scope: commissioner-only join-request listing. Actual principal/helper/model/caller and moderator rendering inspected. Required actingUserId remains compatibility assertion, must match principal (403 actor_identity_mismatch), and never grants authority. Checked model entry point verifies commissioner for URL league and final request SELECT includes commissioner EXISTS predicate; trusted original listing shares query implementation separately. Missing/ambiguous app identity/auth explicit 401/403; invalid object/actor/status types JSON 400. Existing authorized response/contact fields, status filter/descending order/empty results and missing-league 400 are preserved. No approval/denial/cancellation changes.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_join_request_listing_authorization.py'` before implementation | Nine tests, nine assertion/subtest failures, exit 1. Forged commissioner actor and stale check exposed applicant data; absent identity/empty subject also bypassed checks. Invalid status list logged DB binding error and returned 500 instead of 400. |
| Same command after implementation | 9/9 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 157/157 pass, exit 0; no errors/skips/expected failures. Existing profile/member/admission denial assertions unchanged. Intentional bootstrap ERROR fixture output remains. |
| `git diff --check` | Exit 0. |

Nine tests reuse guarded runner/profile SQLite fixture (extended result interface) with synthetic commissioners/members/nonmember and multiple leagues/request rows. Real JWT/middleware/registered routes/model/helper/parameterized SQL execute without dialect adaptation. Exact own-league response including authorized userEmail/userDisplayName, descending order, status filter/unknown/empty/null behavior, empty league, numeric-string actor, foreign roles, forged body/header/query scope, auth/identity and input errors are asserted. Synthetic role-change hook modifies commissioner immediately before final SELECT and verifies 200 empty list/no applicant data; this is intentional fail-closed data behavior after initial check passes, not a 403 race outcome or PostgreSQL concurrency/locking proof. Duplicate identity setup is disposable only.

Frontend unchanged and checks not rerun; historical results not claimed fresh. No live DB/RLS/direct Supabase/browser verification, post-query revocation guarantee, production/network/environment/private-row access, app/listener/job, schema/migration/dependency/deployment or unrelated cleanup. Q1 nonmember visibility/discoverability and Q4 operational permissions remain open.

MOD-003A remains partial. Next recommended slice: commissioner join-request approval bound to verified principal, followed by remaining moderation and scoped operations. Stop after stage 6; no other task started.


## MOD-003A stage 7 verification — 2026-10-28

Scope: principal-bound commissioner approval only. Actual model/caller inspected. Required body actingUserId remains compatibility assertion matching principal; mismatch 403 actor_identity_mismatch; malformed object/ID 400; auth/identity explicit 401/403. Checked model locks and verifies URL league commissioner inside approval transaction before mutations; request read and resolution UPDATE bind both URL league/request, and resolvedByUserId uses principal ID. Existing 200 request/member shape and pending/nonpending/replay/missing-resource contracts preserved. Trusted model remains direct-call/HTTP-independent, sharing approval transaction body and league-first lock order.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_join_request_approval_authorization.py'` before implementation | Nine tests, nine assertion/subtest failures, exit 1. Forged commissioner actor/missing identity/empty subject could approve; invalid actor types also caused mutation. Some subsequent subtest no-change assertions observed prior unauthorized fixture mutation. |
| Same command final (after trusted-call regression added and lock-order alignment) | 10/10 pass, exit 0. |
| `python3 api/tests/run_isolated.py` final | 167/167 pass, exit 0; no errors/skips/expected failures. Prior denial assertions unchanged. Approval rollback case intentionally logs synthetic exception; bootstrap ERROR output remains intentional fault fixtures. |
| `git diff --check` | Exit 0. |

Ten tests reuse guarded runner/profile fixture with synthetic applicants, commissioner/member/nonmember accounts, leagues/members/requests/sport configuration. Real JWT/middleware/registered routes/model transaction executes against SQLite; FOR UPDATE removed only in fixture, PostgreSQL UPDATE alias/RETURNING/JSONB syntax adapted, and synthetic JSON/GREATEST functions support the existing league update branch. Tests inspect both commissioners' persisted resolution actor/member owner/name/order and response shape; deny forged actor, wrong role/foreign league/request, missing/nonpending/replay, invalid actor/shape and auth/identity failures without state changes. Body/header/query cannot replace URL resource or principal. Injected failure after member INSERT proves synthetic membership/league/request state rolls back together. Trusted direct call without Flask request context remains functional and accepts audit actor metadata as before; HTTP cannot select that path.

Code review aligned trusted and checked approval entry points to league-before-request locking, avoiding opposite approval lock orders introduced by the new checked path. This is code-level ordering, not a PostgreSQL deadlock/concurrency proof. SQLite rollback is not deployed RLS/constraint/isolation/locking validation; counter/rounds/capacity policy and broader admission races remain unchanged/unverified. No frontend checks rerun (caller unchanged), production/network/environment/private-row access, app/listener/job, schema/migration/dependency/deployment or unrelated cleanup.

MOD-003A remains partial. Next: commissioner denial bound to principal, reviewing known malformed denial SQL finding before valid-flow assertions; other moderation and scoped operations/Q1/Q4 remain. Stop after stage 7; no other task started.


## MOD-003A stage 8 verification — 2026-10-28

Scope: commissioner denial authorization and its necessary canonical-status/SQL repair. Handler resolves principal, requires legacy matching actingUserId, passes only principal actor and URL scope to checked model. Checked transaction locks/verifies league commissioner before scoped request lock/update. Both checked/trusted entry points use league-first order and shared denial body, with trusted path independent of HTTP identity. Fixed lowercase pending comparison and malformed trailing-comma SQL; final UPDATE guards request ID, URL league and PENDING. Intended 200 DENIED response with principal resolver restored; wrong role/actor 403, auth/identity 401/403, malformed body/ID and missing/foreign/resolved request 400. Frontend unchanged and already conforms.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_join_request_denial_authorization.py'` before implementation | Nine tests, ten assertion/subtest failures and one error from direct model rejecting canonical PENDING; exit 1. Intended denial failed, identity/forged-actor checks were absent, and rollback path was unreachable. |
| Same command after implementation | 9/9 pass, exit 0. |
| `python3 api/tests/run_isolated.py` | 176/176 pass, exit 0; no errors/skips/expected failures. Existing assertion set preserved. Approval rollback's logged synthetic exception and bootstrap ERROR fixture output remain intentional. Denial rollback logs are captured/asserted by its test. |
| `git diff --check` | Exit 0. |

Nine tests reuse guarded runner/profile SQLite fixture with synthetic commissioners/members/nonmember, two leagues and pending/approved/denied/cancelled request rows. Fixture CHECK admits uppercase canonical statuses; only FOR UPDATE is removed from model SQL. Actual denial UPDATE/RETURNING executes, including fixed comma and scope/status predicates. Assertions verify both commissioners' successful request fields/persisted resolver and no league/member mutation; deny forged actor, wrong role/league/request, all resolved states/replay; ensure body/header/query cannot replace URL or resolver; explicit auth/missing/ambiguous identity and malformed-input errors; synthetic fault after actual UPDATE rolls back resolution; trusted direct model remains callable without HTTP request.

SQLite CHECK is synthetic, not deployed PostgreSQL verification. Row locks, concurrency/deadlocks, deployed SQL/types/RLS/status constraints and real browser flow remain unverified; no disposable PostgreSQL command run. No frontend checks rerun because caller unchanged; historical results stay historical. No schema/migration/dependency/production/network/environment/private-row access, app/listener/job or deployment.

MOD-003A remains partial. Necessary denial repair overlaps MOD-011; its backlog note now records completed denial code/synthetic checks, with cancellation and required disposable PostgreSQL validation still open. Next MOD-003A slice: authenticated own-request cancellation, reviewing its known lowercase status bug, followed by remaining moderation/scoped operations and Q1/Q4 decisions. Stop after stage 8; no broader task started.


## MOD-003A stage 9 verification — 2026-10-28

Scope: authenticated own-request cancellation and necessary canonical-status repair. Handler resolves principal, requires matching legacy userId (403 mismatch), passes verified owner/URL scope only. Model's locked owner check retained, no commissioner override; fixed PENDING comparison and guarded final UPDATE by request ID/league/user/PENDING. Intended 200 CANCELLED response/timestamp restored with resolvedByUserId unchanged (normally null). Auth/identity errors explicit 401/403, malformed object/ID 400, foreign owner 403, missing/foreign/resolved request 400. Trusted direct model remains HTTP-independent and retains request-owner enforcement.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_join_request_cancellation_authorization.py'` before implementation | Ten tests, twelve assertion/subtest failures and one direct-model error rejecting canonical PENDING; exit 1. Intended cancellation was broken and HTTP identity/actor gaps reproduced as wrong error outcomes. |
| Same command after implementation | 10/10 pass, exit 0. |
| `python3 api/tests/run_isolated.py > /tmp/mod003a-stage9-tests.log 2>&1` | 186/186 pass, exit 0; no errors/skips/expected failures. Summary inspected; existing assertions preserved. Approval rollback exception/other bootstrap ERROR fixture output remains intentional. |
| `git diff --check` | Exit 0. |

Ten tests reuse guarded runner/profile SQLite result adapter with synthetic League/LeagueMember/request rows and uppercase-status CHECK; only FOR UPDATE is removed. Actual cancellation UPDATE/RETURNING executes. Assertions inspect A/B own cancellations/exact fields/persisted status/timestamp and unchanged resolver; reject forged IDs, foreign owners including target league commissioner, foreign URL request IDs, all resolved statuses/replay, auth/missing/ambiguous identity/invalid shape/types with unchanged state. Body/header/query resource/resolver substitutions ignored. Fault injected after actual UPDATE rolls back to prior request state; logs captured. Direct model rejects nonowner and succeeds for owner without HTTP context. No existing assertions weakened/skipped.

SQLite CHECK/transaction results are not deployed PostgreSQL SQL/types/status-CHECK/RLS/row-lock/concurrency verification. No frontend checks rerun (wrapper unchanged, no screen caller found); historical frontend/type/lint results stay historical. No production/network/private-row/environment access, app/listener/job, schema/migration/dependency/deployment or unrelated cleanup.

MOD-003A remains partial: next principal-bound commissioner member removal, then deletion/remaining scoped reads/week generation with relevant Q1/Q4 decisions. MOD-011 now has denial/cancellation code repairs and synthetic regression evidence recorded; it remains open for its required disposable PostgreSQL validation. Stop after stage 9; no broader task started.


## MOD-003A stage 10 verification — 2026-10-28

Scope: authenticated commissioner member removal. Actual existing locked model and frontend caller inspected. Handler now resolves principal, treats required actingUserId as matching integer/numeric-string assertion (403 mismatch), validates JSON object/actor/boolean shift flag (400), and supplies principal ID plus URL resources to model. Existing model already locks/checks league commissioner and scoped member; wrong commissioner now PermissionError/403 instead of ValueError/400. Valid 200 response/default true/explicit false shifting, missing/foreign target/commissioner-removal 400 and replay/count/order behavior retained. Trusted direct model remains HTTP-independent with authority enforcement; frontend unchanged.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_member_removal_authorization.py'` before implementation | Twelve tests, fourteen assertion/subtest failures and one direct-model error-class mismatch; exit 1. Forged actor/missing identity could remove, invalid actor/shift inputs coerced, wrong role mapped to 400. Later subtest state assertions also observed preceding unauthorized synthetic removals. |
| Same command after implementation | 12/12 pass, exit 0. |
| `python3 api/tests/run_isolated.py > /tmp/mod003a-stage10-tests.log 2>&1` | 198/198 pass, exit 0; no errors/skips/expected failures. Previous assertions unchanged. Intentional approval rollback exception/bootstrap ERROR fixture output remains. |
| `git diff --check` | Exit 0. |

Twelve tests reuse guarded runner/profile SQLite fixture with synthetic commissioner/member/nonmember profiles, two leagues and distinct member IDs/orders. Actual JWT/middleware/routes/model SQL execute with FOR UPDATE removed and synthetic now/GREATEST functions. Tests inspect successful A/B scoped removals, exact member-list payload and retained points, default shifting and explicit no-shift, unchanged other-league data; deny forged actors/other roles/foreign member IDs, missing targets and commissioner removal; reject auth/missing/ambiguous identity/shape/actor/nonboolean flag; verify actual DELETE fault rollback and replay without extra changes; direct model outside request context still enforces commissioner.

Fixture has no dependent roster/history rows: cascading deletes/FK enforcement, historical integrity, deployed PostgreSQL roles/RLS/row locks/concurrency, browser behavior and nullable-order cases are not verified. Existing league-status policy/count algorithm not redesigned. No frontend checks rerun, schema/migration/dependency, production/network/private-row/environment-value access, app/listener/job or deployment.

MOD-003A remains partial. Next recommended slice: commissioner league deletion bound to principal, then remaining scoped reads/week generation with Q1 nonmember visibility/Q4 operator decisions. Stop after stage 10; no other task started.


## MOD-003A stage 11 verification — 2026-10-28

Scope: authenticated commissioner league deletion only. Actual locked model and frontend caller checked. Handler requires principal and matching legacy actingUserId assertion (403 mismatch), validates object/ID (400), and passes principal ID/URL league only. Existing model commissioner check now returns PermissionError/403 and final DELETE includes commissioner predicate. Valid 200 fields and missing/replay 400 retained. Trusted model remains callable without HTTP context and still enforces commissioner. No profile deletion or new retention/status policy.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_league_deletion_authorization.py'` before implementation | Nine tests, twelve assertion/subtest failures and one direct-model error-class mismatch, exit 1. Forged actor/missing identity/invalid types could delete synthetic leagues; wrong commissioner mapped to 400. Subsequent no-change assertions also observed preceding unintended fixture deletions. |
| Same command after implementation | 9/9 pass, exit 0. |
| `python3 api/tests/run_isolated.py > /tmp/mod003a-stage11-tests.log 2>&1` | 207/207 pass, exit 0; no errors/skips/expected failures. Existing assertions preserved. Intentional approval rollback exception/bootstrap ERROR fixture output remains. |
| `git diff --check` | Exit 0. |

Nine tests reuse guarded runner and removal/profile SQL result adapter, synthetic accounts/two leagues and representative SQLite ON DELETE CASCADE member/request rows. Actual JWT/middleware/registered routes/model SQL run with FOR UPDATE removed only. Assert both commissioners' own deletion and exact response, matching numeric-string identity, other-league and child preservation, forged actor/member/nonmember/foreign commissioner denial, URL versus body/header/query scope, auth/missing/ambiguous identity/shape/type errors, missing/replay contracts, actual DELETE fault rollback restoring league/children and direct-model commissioner enforcement without HTTP context. No assertions weakened/skipped.

SQLite cascade fixture is a deliberately small test schema, not a deployed schema/migration or historical-retention guarantee. Actual PostgreSQL roles/RLS/locks/concurrency/deadlocks, complete dependent FK cascades/history and browser confirmation flow unverified. No frontend checks rerun (caller unchanged); historical results remain historical. No production/network/private-row/environment-value access, app/listener/job, schema/migration/dependency/deployment or unrelated cleanup.

MOD-003A remains partial. Next requires Q1 nonmember read/preview policy for remaining league details/rules/member/conference reads and Q4 standalone HTTP week-generation authority before adopting those routes. No new global admin/operator inferred. Separate deployed-policy/schema/PostgreSQL evidence tasks remain open. Stop after stage 11; no other task started.


## MOD-003A remaining-scope policy review — 2026-10-28

Read actual league/schedule registrations and relevant read/preview/week caller paths; five routes remain grouped into two implementation stages (four league reads, then standalone week generation), plus final verification/handoff. No tests executed or application/test changes in this review; latest actual suite remains stage 11's 207/207, not a new verification run. User choices requested for open Q1 nonmember visibility and Q4 standalone generation authority; proposed limited discoverable previews/member-only full reads and commissioner-only HTTP generation await response. Automatic creation/internal week initialization is separate. No new policy or broader security guarantee claimed, and no production/network/environment-value access, app/listener/job/schema/migration/deployment occurred.


## MOD-003A final read policy and internal-only generation — 2026-10-28

Accepted policy: limited discoverable previews for authenticated nonmembers; full details/rules/member data/conferences only for members and commissioner; private leagues restricted. Standalone HTTP generation disabled, with trusted internal/automatic model calls unchanged. These user answers supersede the preceding pending Q1/Q4 proposal.

| Command / check | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_league_read_authorization.py'` before implementation | Initial 7 tests: 24 failures and 1 error, exit 1; unauthorized/private data and missing app-identity checks exposed. |
| `python3 api/tests/run_isolated.py 'test_http_week_generation_disabled.py'` before implementation | 2 tests, 12 failing subtests, exit 1; HTTP still invoked generation. |
| Frontend `node --test --experimental-strip-types tests/profileApi.test.ts` before preview helper | 9 pass / 10 total, exit 1; preview helper missing. |
| Added explicit full-projection contract, before implementing | Backend 10-test read suite: 2 failures, exit 1; nonmembers still received partial 200 responses to `view=full`. Frontend 10 pass / 11 total, exit 1; full API helpers omitted the projection parameter. Both fixed without reducing assertions. |
| First full backend run after endpoint implementation | 216 tests, 2 failures and 1 error, exit 1; three existing rules-format tests lacked newly required authenticated identity setup. Added real middleware/synthetic valid JWT/profile and full-access model fixture; original assertions unchanged. Two earlier preview failures were a new SQLite result adapter missing `.all()`, corrected in fixture only. |
| Independent review regression, before projection correction | Explicit member/commissioner details `view=preview` returned full data and invoked lifecycle sync. New 11-test read suite failed 5 assertions/subtests, exit 1. Corrected details projection condition; reduction now applies regardless of full entitlement. Static review found no further material issue. |
| Final `python3 api/tests/run_isolated.py > /tmp/mod003a-final-backend.log 2>&1` | **220/220 pass**, exit 0; no skips or expected failures. Existing profile-isolation denials pass unchanged. Intentional rollback/bootstrap fault-test messages are not suite failures. |
| Frontend `node --test --experimental-strip-types tests/*.test.ts` | **45/45 pass**, exit 0. |
| Frontend `./node_modules/.bin/tsc -p tsconfig.app.json --noEmit` | Exit 0. |
| Frontend `./node_modules/.bin/eslint src/api/leagues.ts src/types/leagueMember.ts src/screens/League/DiscoverLeaguePage.tsx tests/profileApi.test.ts` | Exit 1: three existing `no-explicit-any` errors at Discover lines 53/84/146, confirmed unchanged in HEAD. No suppression/cleanup. Tool also reports its stale browser-baseline-data notice; no dependencies updated. |
| Same focused ESLint excluding Discover | Exit 0 for API/types/tests. |
| `git diff --check` | Exit 0. |

Eleven read integration tests reuse the existing guarded harness/profile database with synthetic users, discoverable/private leagues, memberships, rules/conferences and empty week/score fixtures. They execute verified JWT middleware, actual registered endpoints and model SQL. They assert exact reduced projections, member/commissioner-without-membership full reads, private/foreign/missing restrictions, missing/expired/missing-subject and missing/ambiguous application identities, forged actor/query/header values, inability to elevate with projection parameters, explicit member/commissioner details-preview reduction without lifecycle sync, and membership/discoverability revocation immediately before scoped data queries. Preview/denial paths do not invoke global status synchronization. Two schedule tests assert no call to generation for authenticated roles/missing profiles/forged trusted flags/invalid bodies and middleware 401 for anonymous requests. Two frontend actual-module transport regressions verify authenticated reduced and explicit-full projections.

The credential-free runner disables dotenv/network/real engine construction and does not import the app factory. Tests adapt PostgreSQL interval syntax for SQLite and substitute global lifecycle synchronization; they do not establish real PostgreSQL locks/RLS/transactions/cascades/concurrency or browser rendering. No frontend production build or real browser was run in this final stage. Existing full-detail global status synchronization remains unchanged (MOD-020). Previous PostgreSQL evidence tasks, including MOD-011, stay open. No production/network/credential/environment-value access, application listener/job, migration/schema/dependency/deployment or other task implementation. MOD-003A is complete; recommended next is MOD-003B, separately scoped after dependency/policy review.


## MOD-003B stage 1 — authenticated member-only draft snapshots — 2026-10-28

Scope: only registered GET `/api/draft/state/<league_id>`. Verified principal is resolved first; initial League SELECT includes requested-league membership before draft reads and completed-state repair. Existing socket member-only policy is preserved, including denial for commissioner without membership and discoverable nonmembers. Valid snapshot and trusted default/connection model-call contracts remain. Commands, sport-round metadata and sockets are unchanged; no broader authorization-completion claim.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_draft_state_authorization.py'` before implementation | 10 tests: 12 assertion/subtest failures and 1 error for new missing reader argument, exit 1. Old handler accepted missing/ambiguous app identities, nonmembers and forged identities, returned missing league 400 and printed raw operational failures. Existing valid snapshot/repair fixtures passed. |
| Same command after implementation | **10/10 pass**, exit 0. |
| `python3 api/tests/run_isolated.py > /tmp/mod003b-stage1-backend.log 2>&1` | **230/230 pass**, exit 0; no skips or expected failures. Existing profile-denial and draft transport assertions unchanged and passing. Intentional rollback/bootstrap fault-fixture output remains. |
| `git diff --check` | Exit 0. |
| Independent focused read-only code review | No material findings; reviewer did not independently rerun tests. |

Ten tests reuse the existing synthetic profile/read SQL adapters and credential-free harness; actual verified JWT middleware, registered draft routes and snapshot model SQL execute. Fixture includes unique app identities, two member leagues, a commissioner without membership, an outsider, live/paused/stale-complete state, actual picks/conference metadata and future turns. Assertions cover exact full response fields and nested member/pick/next-turn contracts, member/league substitutions, discoverable/private/missing denial, forged body/query/header/job identities, expired/invalid/empty subject and missing/ambiguous app identities, permission removal immediately before the first scoped query, no denied DraftState reads/repair, persisted authorized repair, preflight, generic operational errors without raw stdout logging and default/supplied-connection calls outside HTTP context. Existing socket membership SQL is compared directly for uniquely mapped users; its PostgreSQL UUID cast is adapted only in the fixture. No live Socket.IO integration test or socket ambiguity repair is claimed.

The existing runner clears environment, disables dotenv/network/deployed engine creation and avoids the app factory. SQLite does not prove PostgreSQL/RLS/locking/concurrent revocation or deployed schema behavior. The initial SQL gate is not serialization against a removal during later snapshot queries. No frontend changes/build/type/lint/browser checks rerun; previous results stay historical. No production/network/private rows/credentials/environment-value access, listener/worker/job, schema/migration/dependency/deployment or unrelated cleanup. MOD-003B remains partial; next is principal-bound owned-member live picks, then commissioner controls/order and explicit manual/operator policy. Stop after this bounded stage; no other task started.


## MOD-003B stage 2 — principal-bound owned-member live picks — 2026-10-28

Scope: only POST `/api/draft/pick`, principal resolution then owned-member/requested-league check inside existing model transaction, repeated in final INSERT SELECT. No control/manual/socket/schema/algorithm adoption. Safe object/ID parsing; successful pick/slot/state/event, 409 conflicts, HTTP week default 0/model default 1 and explicit weeks preserved.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_live_pick_authorization.py'` before implementation | Initial 9 tests: 19 failures and 2 errors, exit 1. Unauthorized picks and missing app identity accepted, bool/float coercion and uncaught malformed-ID conversion observed. Also exposed fixture timestamp/COUNT-cast gaps and cascading fixture mutations after unauthorized successes. |
| Fixture correction / intermediate run | Adapted UTC timestamps and COUNT cast. Initial broad `::int` removal also damaged `::interval`; narrowed to exact COUNT-cast text. No assertions changed. Before correction, first post-implementation target had 2 failures/1 error due interval adapter; after correction 9/9 passed. |
| First full backend run after implementation | 239 tests, 6 failures, exit 1, all existing mock-domain transport tests bypassing newly required auth. Added real middleware/profile/synthetic JWT setup; all existing assertions retained. |
| `python3 api/tests/run_isolated.py 'test_draft_contracts.py'` after authenticated setup | 3/3 pass, exit 0, including exact response and matching room-event assertions. |
| `python3 api/tests/run_isolated.py > /tmp/mod003b-stage2-backend.log 2>&1` after adding commissioner-own-turn/explicit-week case | **240/240 pass**, exit 0; 10 new live authorization tests, no skips/expected failures. Existing state/profile denial and draft contract assertions pass. Intentional bootstrap/rollback fixture output remains. |
| `git diff --check` | Exit 0. |
| Independent focused read-only review | No material findings; reviewer did not independently rerun tests. |

Live tests execute actual JWT/middleware/registered routes/model transaction/ownership checks/INSERT/slot/state/snapshot and cap queries on synthetic data. Only the socket emitter is substituted. Reuses prior state/profile/read adapters with a fixture database factory hook; SQLite adapts FOR UPDATE, interval calculation, exact COUNT cast, UTC timestamp values and SQLAlchemy-style integrity exceptions. Covers successful two-user/two-league picks and commissioner own turn, default/explicit/numeric-string input contracts, foreign/missing/cross-league membership and spoofed body/header/query/job identities, expired/empty/missing/ambiguous identity, malformed object/ID errors, 409 turn/expiry/unique conflicts, same-connection ownership mutation before guarded INSERT, persisted-data rollback after slot failure, no denied success emission and trusted model calls outside HTTP context.

The late-mutation test establishes the final predicate and rollback in the synthetic transaction, not a PostgreSQL concurrent-removal guarantee; no new row locks or lock order introduced. Existing post-commit snapshot/broadcast failure boundary remains non-atomic and unchanged. Completion/finalization branches, database/RLS/locking/deadlock/concurrent role changes, browser and live Socket.IO behavior are not established by this fixture. No frontend changes/checks rerun. No production/network/private rows/credentials/environment-value access, factory/listener/worker/job, schema/migration/dependency/deployment or unrelated cleanup. MOD-003B remains partial; next is commissioner controls/order authorization, with explicit manual/operator policy before that later stage. Stop after this stage; no other task started.


## MOD-003B stage 3 — commissioner controls and order — 2026-10-28

Scope: start/pause/resume/finalize/order only. Verified principal supplies actor; body actor fields assert matching identity only, finalize retaining its required field. Existing UI/finalize commissioner role is checked before domain work and again pre-commit in the same model transaction, including force-finalize authorization/mutation. No lock hierarchy or algorithm changes. Safe JSON input errors and existing valid200/payload/event/trusted contracts preserved.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py 'test_draft_control_authorization.py'` before implementation | 10 tests, 60 assertion/subtest failures, exit 1. Noncommissioners could mutate via controls/order or forged actor; no final authority check. Legitimate success/trusted fixture cases passed. |
| First target/full runs after implementation | 10-test target and 250-test full suite each failed 3 subtests (pause/resume/finalize) because preceding start rollback left no state for the next scenario. Fixed fixture preparation to upsert valid per-case DraftState; assertions unchanged. |
| Target command after fixture correction | **10/10 pass**, exit 0. |
| `python3 api/tests/run_isolated.py > /tmp/mod003b-stage3-backend.log 2>&1` | **250/250 pass**, exit 0; no skips/expected failures. Existing profile/state/live/draft transport assertions retained. Intentional bootstrap/rollback fixture messages remain. |
| `git diff --check` | Exit 0. |
| Independent focused read-only review | No material findings; reviewer did not independently rerun tests. |

Real JWT/middleware/registered routes and domain SQL execute on the reused synthetic fixture, including actual seed turns, order changes, finalization, snapshots and rollback; only emitter substituted. Tests exercise both commissioners across all five controls and role/league/actor forgery, personal-membership-independent commissioner control, auth and missing/ambiguous identity, object/array/ID/actor validation, URL-bound order and existing foreign-member rejection, exact success envelope/event type/room (no order event), late commissioner change before the final check, finalization fault after state write, and trusted defaults/required checked finalization actor (None cannot bypass).

Adapters translate PostgreSQL generate_series, ANY/array reordering, interval/date/count casts, aliases, timestamps, locking and executemany for SQLite. This is not deployed PostgreSQL/RLS/lock/competing-transaction evidence. The role-change test mutates the same connection before the final check, then confirms rollback; it does not guarantee serialization or prevent a competing change after that check. Existing post-commit event/snapshot boundary is unchanged. Known MOD-025 subset-order/start-replay defects are not repaired or protected by valid-behavior tests. No frontend changes/checks rerun, browser or live socket verification. No production/network/private rows/credentials/environment-value access, factory/listener/worker/job, schema/migration/dependency/deployment or unrelated cleanup. MOD-003B remains partial: manual-pick operational access policy and principal adoption remain. Stop after this stage; no other task started.


## MOD-003B final manual-policy stage and completion — 2026-10-28

User explicitly chose disabled HTTP manual allocation, trusted internal model calls only. POST `/api/draft/pick-manual` returns410 `http_manual_pick_disabled` for any authenticated body/actor/job flags; no parsing or persistence. Middleware still401 for anonymous/invalid/expired JWT. Trusted model implementation/default week1/explicit week/notification SQL unchanged. No global operator role introduced.

| Command from root | Actual result |
| --- | --- |
| `python3 api/tests/run_isolated.py > /tmp/mod003b-manual-baseline.log 2>&1` | Fresh pre-stage baseline250/250 pass, exit0. |
| `python3 api/tests/run_isolated.py 'test_http_manual_pick_disabled.py'` before handler change | 3 tests,25 failures, exit1; old handler called model/parsed invalid bodies instead of rejecting all HTTP allocation. |
| `python3 api/tests/run_isolated.py 'test_manual_pick_trusted_contract.py'` before handler change | 3/3 pass, exit0; trusted default/explicit-week persistence/notification and rollback contracts already valid. |
| Target HTTP command after change | 3/3 pass, exit0. |
| `python3 api/tests/run_isolated.py > /tmp/mod003b-final-backend.log 2>&1` | **256/256 pass**, exit0; no skips/expected failures. Earlier profile/state/live/control/draft transport assertions preserved. Intentional bootstrap/rollback fault-test messages remain. |
| `git diff --check` | Exit0. |
| Final independent focused read-only review | No material findings across registered draft HTTP scope; static review only, no independent test rerun. |

HTTP tests use actual JWT/middleware/registered route with assertions that database begin, manual model allocation and socket emitter are never called. Covers synthetic roles/unknown profiles, forged actor/job/header/query claims, valid/invalid/nonobject/malformed JSON, middleware denial and preflight. Trusted tests reuse prior live/profile fixtures, execute actual model/insert/slot/cap/notification SQL outside HTTP context, assert default week1/explicit week4 and output allocation fields, and confirm rollback/no notification after slot failure. The local SQLite pg_notify function records invocation; it does not simulate PostgreSQL transactional delivery. No model source changed in this final stage.

Final registered route audit: member-only state and own-member live pick derive verified principal, commissioner controls/order derive principal and check actual role in model transaction, manual HTTP is disabled. Sport-round metadata remains JWT-protected global configuration (not actor/league data); socket subject/membership gates remain unchanged. No new administrative/operator role or job-flag bypass. Earlier stage limitations persist: no deployed PostgreSQL/RLS/locking/concurrent revocation/notification/cascade, browser or live socket proof; existing socket ambiguity behavior, post-commit event/snapshot boundary and MOD-025 order/replay defects unchanged. No frontend changes/checks rerun. No production/network/private rows/credentials/environment-value access, factory/listener/worker/job, schema/migration/dependency/deployment or unrelated cleanup. MOD-003B is complete in bounded HTTP/application scope; next recommended MOD-003C, separately scoped after dependency/role review. Stop after MOD-003B.


## MOD-003C final scoring/operational slice — 2026-10-29

- User selected disabled HTTP weekly scoring and explicit trade application; retain trusted model/job access. Both routes return 410 without model/persistence calls. Scoring reads require verified full league-read access; existing scoring/tiebreak/transaction rules unchanged.
- `python3 api/tests/run_isolated.py test_scoring_authorization.py`: 9/9 pass.
- `python3 api/tests/run_isolated.py test_operational_trusted_contract.py`: 2/2 pass. Includes real pending trade application SQL and isolated finalizer-function execution against synthetic SQLite without job module startup imports.
- `python3 api/tests/run_isolated.py`: 345/345 pass, exit 0. `git diff --check`: pass. No frontend changes/checks, production/configured jobs/schema/deployment access. Existing synthetic failure-path log messages do not represent test failures.
- MOD-003C complete only in bounded application/HTTP scope. PostgreSQL/RLS/locking/concurrent revocation/scheduler/browser guarantees remain unverified. See [current checklist](mod-003c-checklist.md). No other MOD started.


## MOD-009 — locked trade application guards — 2026-10-29

- Before implementation: `python3 api/tests/run_isolated.py test_trade_application_guards.py` ran 5 tests with 9 failures, reproducing invalid state/type application, replay and stale ownership/conference acceptance.
- Final focused run: 6/6 pass. Full `python3 api/tests/run_isolated.py` run: **351/351 pass**, exit 0, no skips/expected failures. `git diff --check` passes.
- Checks real model SQL on the existing synthetic SQLite adapter: all nonpending states and wrong type reject without ownership writes; direct/dispatcher replay rejects; dispatcher pre-read cannot override later application state; valid trade preserves half-open week2 ownership history and None success; stale ownership and conference caps reject; faults before first/second ownership insertion and completion roll back all writes. Existing trusted week1 application and J4 baseline tests pass in the full suite.
- The dispatcher stale-read fixture initially failed because FOR UPDATE is removed before the query hook; corrected the hook to target the actual locked-read SELECT shape. This models state observed by the application, not a competing PostgreSQL transaction.
- No schema, HTTP, frontend, scheduler, production or network changes/access. Existing deadline policy retained. SQLite cannot verify row locks or two concurrent applies; that MOD-009 acceptance remains outstanding on disposable PostgreSQL. Ownership concurrency across distinct commands remains MOD-010.


## MOD-007 — atomic weekly score replacement — 2026-10-29

- MOD-009 infrastructure check: `psql` and Docker clients are present; `postgres`/`initdb` are absent from PATH. Read-only Docker daemon/image inspection reports daemon unavailable. No database connection, container, installation or infrastructure startup performed; concurrent-apply evidence remains outstanding.
- `python3 api/tests/run_isolated.py test_weekly_score_atomicity.py` before implementation: 3 tests, **2 failures**, proving both failure points lose old scores. Each fault has an independent fixture so the second case cannot pass against an already emptied table. After implementation: **3/3 pass**.
- `python3 api/tests/run_isolated.py`: **354/354 pass**, exit 0. `git diff --check`: pass. Existing weekly ranking/tiebreak/week0/final-period tests included.
- Production deletion helper now requires the caller's connection; compute_weekly_scores deletes and inserts inside the same transaction. Removed the week0 fixture's deletion override so it exercises the real deletion helper. New tests run actual deletion/insertion SQL against synthetic SQLite, inject faults before first and second inserts, assert the complete old set survives, and verify exact successful rows, other league/week isolation and sequential repeat convergence.
- No scoring-rule, response, schema, frontend or job orchestration changes. Concurrent replacements/uniqueness remain MOD-008; this does not establish PostgreSQL isolation, deployed schema/RLS or concurrent job behavior. No production/network/configured database access.


## MOD-004/005 — configured Supabase metadata and provenance — 2026-10-29

- User authorized starting MOD-004/005 and asked whether Supabase tables are accessible. Used existing api/.env connection internally; no secret values printed. No connected Supabase plugin was installed; plugin discovery found an optional Supabase integration, but direct configured SQL was sufficient, so no installation requested.
- Initial sandbox connection failed; approved network execution succeeded. Connection startup read-only option was not retained (`transaction_read_only=off` on the preliminary catalog-only SELECT pass). Recollected the full artifact after explicit `SET TRANSACTION READ ONLY`; final metadata records `on`. No application-row queries or mutation statements executed in either pass.
- Dated catalog artifact: 23 public tables, 180 columns, 83 constraints, 45 indexes, one policy; table/schema/sequence/default grants, role memberships/flags, public routines/extension ownership, event triggers and publication metadata. Routine bodies, role settings and scheduler command text excluded. No cron or supabase_migrations schema observed.
- Local available all-ref Git/path/content history and SHA-256 checks establish checked-in artifact provenance; missing 20261023 migration not recovered. Name-level source/catalog comparison matches 23 tables and 180 columns; no normalized full-DDL equivalence claimed.
- Corrected db/README and season setup README missing-migration instructions; added bounded MOD-004/005 reviews and status links. Catalog JSON/claim assertions and `git diff --check` pass. No application source changed, so backend/frontend tests not rerun; previous 354/354 backend result is historical.
- Docker daemon now reachable (29.9.2); Supabase PostgreSQL 17.6.1.084 image cached. Read-only daemon/image inspection only. No container, database baseline, role test or MOD-009 concurrent test started in this evidence stage.


## MOD-004/005/009 — real PostgreSQL assessment — 2026-10-29

User recalled almost certainly applying the missing basketball SQL but cannot
locate it; recorded as recollection, not recovered migration provenance. Continued
assessment with explicit authorization and existing cached Docker image.

- `python3 scripts/modernization/assess_postgres.py`: **PASS, exit 0** on the final
  reviewed run, task-owned PostgreSQL 17.6 container, fixed loopback port 55439.
  Creates random-named databases and fixture roles, uses no .env/configured DB
  imports, validates a task-owned server marker before mutation and cleans up only
  objects successfully created by this run. Existing unrelated Supabase containers
  and volumes untouched; final container stopped/removed.
- MOD-009: actual TransactionModel direct/direct and dispatcher/dispatcher apply
  commands on two connections. First application paused after acquiring FOR UPDATE;
  second observed waiting on a real PostgreSQL lock using pg_stat_activity and
  pg_blocking_pids. After release: first returns None, second ValueError nonpending,
  one COMPLETED transaction, exactly two closed/two newly acquired ownership rows
  at week2. **Outstanding MOD-009 concurrent-apply acceptance satisfied.**
- MOD-005: source duplicates byte-identical, removed in assessment candidate;
  FK dependencies ordered; initializes with explicit synthetic auth.users/auth.uid
  and pg_trgm fixtures. Candidate/deployed collected column properties match except
  27 ordinal positions; all 83 constraints and 45 indexes match. No full sequence
  state/type modifier/collation or platform equivalence claim. Two synthetic prior
  states (subdivision absent; seasonStart correct-only or esasonStart old-only) each
  accept historical migrations and converge to candidate definitions.
- MOD-004: SQL-role fixture reproduces own-profile SELECT isolation, anon and
  missing/unknown-subject denial, browser insert/update denial, seeded Sport
  default-deny, service-equivalent BYPASSRLS/owner access. Broad anon TRUNCATE CASCADE
  succeeds locally and is rolled back; no deployed operation or PostgREST exposure
  claim. Supplemental deployed catalog-only query explicitly read-only with verified
  10s statement/2s lock timeouts retrieves rls_auto_enable definition. Replayed
  function/event-trigger enables RLS on public CREATE TABLE; original definition
  remains unchanged. Full Auth/PostgREST/role membership runtime not tested.
- Focused independent static review found cleanup could target pre-existing fixed
  roles after failed CREATE. Fixed by tracking successful creations only; reviewer
  rechecked and reported no remaining material findings. Added target marker guard
  and derived comparison count. Harness development caught quoting/DBAPI-percent
  issues and an initially unset marker; corrected before final PASS evidence.
- `python3 api/tests/run_isolated.py`: **354/354 pass**, exit0. No frontend changes
  or checks. Final JSON assertions and `git diff --check` pass. No production schema,
  policy, grant, data or job changes. MOD-004/005 remain open for reviewed/versioned
  baselines, deployment alignment, supported upgrades/recovery and migration ledger.


## MOD-004/005 — versioned baseline, adoption ledger and privilege proposal — 2026-10-29

- Added db/baselines/20261029 version/ordered SQL/SHA-256 manifest and frozen expected
  public-state reference. Initialization preserves observed access; tightening is
  a distinct unapplied proposal. Runner accepts caller transactions/savepoints;
  local CLI targets only the marked loopback synthetic server, never .env.
- TDD: initial suite 9/9 failed for missing package/runner; initial implementation
  exposed default-ACL fixture differences (explicit postgres grants were missing),
  corrected to the observed definitions. Additional RED tests reproduced unchecked
  global defaults/custom routines/column ACL/role flags, caught-error partial commit,
  disabled FK enforcement, unlogged relations and pre-existing routine replacement.
  Added rejection/savepoint guards; all final regression assertions remain active.
- `python3 -m unittest discover -s scripts/modernization/tests -p test_baseline.py`:
  **16/16 pass, exit0**, final run. Covers initialize/adopt/replay, concurrent
  initialization, checksum/ledger conflicts, schema/access drift, rollback even
  after caller catches a validation error, and nonreplacement of custom routines.
- Proposal/recovery tests enumerate SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/
  TRIGGER/MAINTAIN on 23 tables and USAGE/SELECT/UPDATE on 21 sequences for both
  browser roles. Verify retained own-profile SELECT/service privileges, new-object
  defaults for both postgres/supabase_admin and return to the frozen observed ACL
  reference. Global defaults that cannot be safely resolved schema-locally reject.
- Supplementary deployed queries were catalog-only/read-only, including exact type
  modifiers/collations, 21 sequence options, 182 internal constraint-trigger states
  and durability of 44 tables/sequences. Final package verifier matched all 20
  versioned public-state groups and routine definition. No deployed ledger writes,
  DDL, grants, application-row reads or configuration changes. Artifact records
  transaction_read_only=on, statement_timeout=10s, lock_timeout=2s and manifest hash.
- Independent static reviewer found disabled-internal-FK-trigger and unlogged-table
  drift gaps; RED regressions reproduced both. Added normalized trigger/persistence
  metadata and reviewer confirmed fixes; final initialization guard recheck also
  found no material regression. Reviewer did not independently run DB tests.
- `python3 api/tests/run_isolated.py`: **354/354 pass, exit0**. No frontend code or
  frontend checks. JSON/checksum/evidence checks and `git diff --check` pass.
- Secret-safe local config presence/comparison: API backend configured, listener
  DATABASE_URL absent from api/.env/current process, front-end server variable
  has a different exact endpoint/user tuple. This does not prove project mismatch
  or browser exposure; deployed API/listener/job role alignment remains unknown.
- [Local evidence](evidence/baseline-local-verification-2026-10-29.json),
  [deployed read-only verification](evidence/baseline-deployed-verification-2026-10-29.json),
  [baseline runbook](../../db/baselines/20261029/README.md),
  [unapplied proposal/recovery](../../db/proposals/README.md).
- MOD-004/005 remain open for the runbooks' explicit runtime/provider/upgrade/recovery
  and approval boundaries. No production rollout, new dependencies or other MOD
  work. All task-created fixture databases/roles and the disposable container removed.


## MOD-005 completion / MOD-004 real provider and runtime assessment — 2026-10-29

- Used installed Supabase CLI2.90.0 and cached provider images to start a separate
  project at local API55441/DB55442. Existing local projects untouched. Disabled
  unused services; used actual Auth/PostgREST, not minimal SQL Auth fixtures.
- `python3 scripts/modernization/assess_supabase.py`: **PASS, exit0**, final run
  after deleting/recreating only the owned disposable project. Evidence records
  `initialize_or_replay=initialized`, a successful subsequent replay with existing
  Auth/profile rows, provider versions and source/proposal/migration hashes.
- Two real signup tokens enforce own/unfiltered/cross-profile reads through
  PostgREST, anonymous/no-policy-table denial, browser write denial and preserved
  service reads. Tests pass before proposal, during proposal and after recovery;
  profile values persist. Generated tokens/status data stay under private temp,
  never in repository artifacts. Emails use synthetic.test with local Auth setup.
- Historical fixtures export actual local auth/public schema-only DDL, then restore
  to two separately created databases. Supplied explicit pg_trgm, initial public
  USAGE and database event-trigger prerequisites omitted/assumed by schema-selected
  pg_dump; event registration runs as the observed postgres function owner. Real
  restore diagnostics found missing maintenance password, initial public schema
  collision, missing event-trigger registration and owner/public-ACL assumptions;
  corrected fixture setup without changing frozen application DDL or role powers.
  Both old-only esasonStart and correct-only seasonStart cases with subdivision
  absent accept historical files, verify/adopt/replay and preserve a School row.
- Normal real-provider postgres rejects full proposal at supabase_admin default
  privileges (SQLSTATE42501). Probe always rolls back, including an unexpected
  future success, then verifies unchanged baseline state. Existing local maintenance
  account tests the full proposal/recovery; no privilege elevation. Hosted proposal
  remains unapplied and must not be partially substituted/applied as ordinary actor.
- Independent static review found no material issues; requested final evidence be
  replaced after the fresh-reset run. Final report now includes preserved-row
  assertions/input hashes and initialized rather than replay-only result.
- `python3 api/tests/run_isolated.py`: **354/354 pass, exit0**, fresh. Earlier
  16-test baseline regression result remains valid/historical; baseline code/SQL
  unchanged in this provider stage. No frontend changes/checks.
- Read-only hosted Supabase capability/activity aggregates (read_only=on, requested
  local transaction timeouts): configured postgres NOSUPERUSER/BYPASSRLS, not
  supabase_admin member. Role counts and matching-source-LISTEN last-command count
  exported only; no raw SQL text/client addresses/application rows. Zero matching
  last commands does not prove absence of listeners or map them to Render services.
- Maintainer confirms Render hosting and listener service intentionally suspended
  for cost. No restart/deploy/env changes. Source create_app also starts notify
  listener in the web process; actual Render command/revision/DSN mapping remains
  unverified. Render integration found but not installed/connected; suggested once.
- [Provider runbook](../../scripts/modernization/SUPABASE_PROVIDER.md),
  [provider evidence](evidence/supabase-provider-verification-2026-10-29.json),
  [runtime handoff](mod-004-runtime-handoff.md). JSON/hash checks and diff check pass.
  All generated restore databases/users and the owned provider project/volumes
  cleaned up; no deployed baseline/ledger/grant/policy/data changes.
- **MOD-005 complete in documented repository baseline/supported-provider scope.**
  This does not authorize hosted execution or claim arbitrary historical schemas/
  production disaster restores. MOD-004 remains partial for Render/consumer mapping
  and an authorized, versioned privilege rollout path. MOD-009 stays complete.
