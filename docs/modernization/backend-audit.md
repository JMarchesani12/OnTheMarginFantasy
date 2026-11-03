# Python backend audit

2026-10-28. Documentation-only audit; no fixes implemented. Read alongside [architecture.md](architecture.md), [features.md](features.md), [behavior-checklist.md](behavior-checklist.md) and [frontend-audit.md](frontend-audit.md). Feature IDs are stable inventory IDs. Paths below are repository-relative; function names identify evidence where whole modules exceed the sampled scope.

## Scope, evidence and classification

Inspected all eight route-registration families, authentication/bootstrap/database setup, HTTP handlers, selected model paths, draft sockets/listener/worker, three cron jobs, ESPN HTTP methods, checkpoint logic and CLI call relationships. Read the relevant modernization notes. Large models were inspected around authorization, mutations, scoring, ingestion and query structure, not line by line. No application modules were imported or executed; no secrets/environment values, database connections, external requests, application tests, jobs or dependency installs were used.

- **D — demonstrated defect:** an implementation path establishes an absent control, invalid operation or failure boundary. This is source demonstration, not a production exploit or runtime reproduction. Deployment protections may change practical exposure.
- **P — measured performance problem:** **none established**. No timings, query plans, lock waits, load results or production metrics were measured. Source query loops and duplicate work are candidates for measurement.
- **M — maintainability/organization:** concrete coupling, duplication or ownership problem.
- **S — speculative improvement/investigation:** needs product agreement, runtime measurement or concurrency/failure reproduction before selecting a fix.

Every finding includes evidence/features, impact, a bounded task and future verification. Existing checklist B1–B12 are not preservation requirements. This pass strengthens several source conclusions but does not claim live authorization/RLS, deployment or scheduler behavior. Suggested checks must use mocks or an isolated database, never production by default.

## Entry points, callers and API contracts

The existing Flask registration → endpoint adapter → domain model pattern is useful; retain it. SQL is mostly parameterized via SQLAlchemy `text`; dynamic column updates use allowlists. Context-managed transactions, draft-state/transaction row locks, some uniqueness constraints, game upserts and resumable bootstrap checkpoints already provide useful protections. `rules/leagueRules.py` and `rules/tournamentRules.py` are established shared rule boundaries; extend these only where behavior really is shared.

| Surface / features | Callers to preserve or explicitly migrate | Contract / audit observations |
| --- | --- | --- |
| User GET by ID/UUID, POST, PATCH; F-002/004/022 | AuthProvider API lookup/create; Settings API PATCH; CurrentUserProvider separately reads Supabase `User` directly | Profile includes email/UUID/timestamps; UUID GET is public. POST returns 201; missing UUID lookup returns 404. Direct Supabase caller is outside Flask and requires separate deployed-policy review. Password login/recovery/OTP F-002/003/038 use Supabase SDK, not Python auth endpoints. |
| League read/create/byUser/search/rules/members/conferences/member PATCH; F-005–012/017 | Home, Create, Discover, Detail, Rules, Manage, Draft/Roster and schedule-context screens through FE API wrappers | Mixed singular/plural and camelCase paths are current contracts, not reasons to rename. byUser is a POST read; search is public GET, clamps limit to 50. Members includes computed daily/current-week differentials. Rules pins a version and exposes current tiers. |
| Join/list/approve/deny/cancel/remove/delete; F-006/008/019/021/029 | Discover/Manage/Detail; cancellation has a wrapper but no UI caller found; external clients remain unknown | Supplied actor IDs; role comparisons exist for several admin operations, but are not bound to JWT subject. Pending request reuse returns handler 201; statuses are uppercase in creation/schema. |
| Draft pick/state/start/pause/resume/finalize/order/rounds/manual; F-013/014/018/020/030 | Draft, Manage, DraftHistory; manual allocation is registered API-only | Live pick defaults acquired week 0, manual defaults 1; keep distinct until intended compatibility is decided. Conflict 409 relies partly on exception text; ordinary validation 400. State includes members/picks/on-deck/server clock, not a universal available-teams payload. Manual model also emits DB notification despite no direct handler broadcast. |
| Member/conference/team schedule, search, createWeeks; F-009/011/012/031/035 | ScheduleTabs, Conference/Team pages, lookup; createWeeks is registered API-only; LeagueModel calls ensure-weeks internally | Read handlers use stored GameResult, not live ESPN. `/all` returns rules/ownedTeams/week/games. Team-season optional league context adds ownership. Team search returns at most 50 after Python ranking; database candidate results are broader. createWeeks returns existing rows too despite `weeksCreated` name. |
| pointsAwarded, scoreWeek, scoreSeason; F-009/025/026/032/035 | Detail uses pointsAwarded; scoring-trigger/season API external callers unknown; jobs/maintenance call scoring paths | Registered season path is `/scoreSeason`, not commented `/standings`. Success dicts versus HTTP `jsonify` adapters matter to CLI callers. Season bonuses are computed, not demonstrated persisted BonusPointEvent records. |
| Roster reads and add/drop/trade commands/open/pending; F-015/016/025/033 | Roster, TradeRequestsPanel, PendingTransactionsPanel; weekly job applies pending transactions; explicit trade/apply is registered API-only | Reads are POSTs; errors mix `message`, `error`, `details`. Proposal/respond return transaction/status; accepted/pending is not applied ownership. Explicit apply currently serializes `None` as JSON null 200. Internal model return contracts must remain distinct from HTTP response contracts. |
| Socket draft join/leave/snapshot/update; F-013/023 | Browser Draft; `scripts/testSocketClient.py` diagnostic; direct HTTP broadcasts and DB LISTEN feed clients | Connect validates token; join binds `sub` to league membership. Diagnostic has hard-coded league 16 and supplies no auth, so it does not match current connect contract. Do not execute it as a readiness test. |
| Timeout worker; F-024 | Separately launched `worker/draftTimeoutWorker.py` | Processes soonest deadline, bounded 0.5–30-second sleep, exception retry; no HTTP adapter. Actual supervision/instance count unknown. |
| Ingestion/bootstrap; F-027/028/035/039 | cronIngestScoreboard, startSeason CLI, deprecated football/basketball forwarders, older ScheduleModel bootstrap helper | ESPN public GETs; season metadata transaction ends before bootstrap HTTP. Durable local checkpoints identify completed dates. Legacy wrappers still forward; no removal justified by lack of UI. |
| Maintenance/health/alternatives; F-034/036/040/041 | rebuild/rescore CLI; hosting probe; unregistered lock helper; alternative NCAA/socket-auth modules | `/health` is static success, not DB/listener readiness. Rebuild mutates periods/scores and is not a verification command. lock_week is not registered; NCAA adapter/socketAuth have no active caller established. |

Accounted for repository-visible caller categories: all FE domain API modules and direct profile SDK access; HTTP registrations including API-only capabilities; cron/worker/listener; bootstrap/rebuild/deprecated CLIs; socket diagnostic and provider helpers; existing mocked/unit test imports. No evidence establishes all external operational clients, production cron commands or integration consumers. Do not remove/rename API-only functions based on no frontend import.

## Demonstrated defects

### D01 — REST actor identity is disconnected from authenticated identity

**Evidence / features:** `authMiddleware.py:40–45` populates `g.user`; endpoint search finds no consumption of `g.user`. `userEndpoints.update_user` → `UserModel.update_user` selects only URL user ID; profile creation trusts body UUID/email. `LeagueModel.update_league` never authorizes an actor; member PATCH allowlists teamName, draftOrder and seasonPoints by arbitrary member ID. `DraftEndpoints.start/pause/resume/set_draft_order` pass only league/order, and their models have no identity check. Commissioner comparisons in `_ensure_commissioner`, delete/remove/finalize use supplied actor IDs. Transaction respond/cancel/veto validate supplied member IDs, not their ownership by the JWT subject. F-004–022/029–033; extends B1.

**Impact:** The application-layer paths admit any valid token with another actor's IDs; they do not enforce ownership or commissioner identity. Resource visibility policy for some league reads is unresolved Q1, but profile-update and actor impersonation controls are demonstrably absent. Direct SQL engine is not initialized with per-request JWT claims; live DB role/RLS restrictions remain unknown.

**Bounded task:** First bind authenticated `sub` to application user and actor/member scope for profile PATCH, league/member PATCH and draft controls; then migrate transaction/admin commands through the same explicit checks. Audit read scopes and operational-only writes against Q1/Q4. Preserve trusted job model entry points separately from HTTP principal resolution. Never accept a body actor as proof of authorization.

**Verify:** Isolated two-account matrix for own/other profile, member/commissioner/nonmember, supplied foreign user/member ID, and anonymous/expired token. Denials leave DB unchanged. Job/CLI operations work with explicitly trusted operational context; frontend visibility cannot bypass checks. Review direct Supabase profile policies independently.

### D02 — Transaction routes ignore the URL league when resolving a transaction

**Evidence / features:** `transactionEndpoints.respond_trade`, `cancel_trade`, `veto_trade`, `apply_trade` receive league_id but call models with only transaction ID and optional member ID. Models resolve the transaction's stored league, not the URL league. F-016/033; B1.

**Impact:** A route under league A can act on a transaction in league B; URL resource boundaries are unenforced even after actor binding is added.

**Bounded task:** Pass expected league ID into these command methods and verify it in the locked lookup before any mutation. Internal dispatcher can use stored league through a separate explicit contract.

**Verify:** Correctly authorized actor plus mismatched URL league is denied with no vote/status/ownership change; matching league succeeds. Pending job dispatch remains functional.

### D03 — Public responses include account contact identifiers

**Evidence / features:** `api.py` public UUID prefix and public search; `UserModel.get_user_by_uuid` returns email/UUID/createdAt; `LeagueModel.search_leagues` selects commissionerEmail. `UserModel.create_user` logs the entire returned profile at debug level. F-004/006/022; B2/Q1.

**Impact:** Anonymous callers knowing a UUID can retrieve its email; public discovery returns commissioner emails. Debug logging can persist email/UUID in logs when enabled. Actual log levels/retention and whether disclosure is intended are unknown; data flow itself is demonstrated.

**Bounded task:** Decide public/private field contract with Q1, then minimize public projection and replace whole-profile logging with non-sensitive event context. Coordinate AuthProvider's public existence lookup and search types; do not simply remove fields without consumer review.

**Verify:** Anonymous versus authenticated response-field assertions; signup existing/missing-profile behavior; search display preserved; captured debug/error logs contain no email, bearer token, secrets or full profile. Check historical retention separately.

### D04 — Join denial/cancellation disagree with canonical status; denial also contains invalid SQL

**Evidence / features:** `leagueModel.py:create_join_request` inserts `PENDING`; deny (`845–876`) and cancel (`878–910`) compare `pending`. Denial UPDATE has a comma immediately before WHERE. `db/tables.sql:153–182` permits uppercase statuses and enforces unique pending league/user. Approval uses uppercase correctly. F-006/019/029; B11/B12.

**Impact:** Ordinary created requests fail deny/cancel before mutation; lower-case legacy data, if present, would reach malformed denial SQL. A working denial flow is not a preservation requirement.

**Bounded task:** Correct canonical status comparisons and SQL together; retain commissioner/request-owner and league scope checks, with JWT actor binding tracked in D01.

**Verify:** Pending request denies/cancels, transitions record intended resolver fields, resolved requests cannot transition again, foreign request/actor denied, failure rolls back. Exercise actual SQL in an isolated Postgres fixture.

### D05 — Validation/error paths can produce uncontrolled 500s

**Evidence / features:** Draft create_pick/manual/start convert IDs with `int` before their try blocks; RosterEndpoints performs conversions/model calls without an exception mapper. `request.get_json(force=True)` inside broad generic catches can map Flask malformed-body errors to 500 (e.g. league update/user update). `LeagueEndpoints.update_league` attempts `jsonify({"message": e})` on an exception object, then has an unreachable safe fallback. `userModel.py` catches `sqlite3.IntegrityError` while executing through SQLAlchemy/Postgres. F-004/007–008/013/015/017–020/022/030; B9/B10.

**Impact:** Invalid types or bodies do not reliably produce bounded client errors; duplicate/FK errors miss the intended handler; update failure can fail again while serializing. Default Flask error bodies need not match FE JSON expectations.

**Bounded task:** Start with profile/league update and draft pick: validate object shape, required scalar types/ranges, catch conversion and framework HTTP errors intentionally, use SQLAlchemy exception class, and return safe JSON errors. Expand to other adapters incrementally, not a global blanket catch of all exceptions.

**Verify:** Missing/null/list/string body, noninteger IDs, booleans/fractional numbers, malformed JSON, duplicate email/UUID, FK failure and unexpected database error. Expected 4xx are stable; unexpected failures give safe JSON 500 and useful server diagnostics, not raw exception serialization.

### D06 — Weekly score replacement is not atomic

**Evidence / features:** `ScoringModel.compute_weekly_scores:265–289` invokes `_delete_existing_weekly_scores`, which commits in its own `db.begin` (`116–127`), then inserts replacements in another transaction. Weekly job and rebuild CLI call this model; POST scoreWeek also does. F-009/025/032/036.

**Impact:** Insert failure after deletion permanently removes previous scores; readers can observe an empty interval. Concurrent runs may interleave; exact duplicate outcome depends on live constraints/isolation, not measured here.

**Bounded task:** Replace scores in one transaction and serialize conflicting league/week recomputations; keep calculations and ranking semantics stable. Separately reconcile job completion flags (S02).

**Verify:** Seed prior scores, inject insert failure, assert old scores survive. Successful replacement has exactly one complete score set; concurrent recomputations cannot yield mixed/duplicate rows. Re-run week-zero/final-period/rank behavior checks.

### D07 — Explicit trade application bypasses transaction state/type safeguards

**Evidence / features:** `TransactionModel.apply_trade:690–798` locks Transaction but checks neither TRADE type nor PENDING_APPLY status before ownership writes/status completion. Publicly registered `TransactionEndpoints.apply_trade` calls it directly; `apply_pending_transaction` checks status/type outside the later lock and then dispatches. Free-agent apply checks both inside its transaction. F-016/025/033.

**Impact:** Direct apply can process proposed/rejected/cancelled/vetoed/completed or wrong-type transactions if other prerequisites pass. Repeated apply can create additional ownership records; the checked-in LeagueTeamSlot definition has no interval uniqueness/exclusion constraint. A row lock alone does not make the command idempotent.

**Bounded task:** Enforce type/status and ownership invariants inside the locked trade application transaction; decide replay response explicitly and apply D01/D02 at HTTP boundary. Revalidate dispatcher preconditions after acquiring the lock rather than trusting an earlier read.

**Verify:** All terminal/nontrade/proposed states cause no ownership writes; pending applies once; concurrent/repeated calls leave one intended transfer; veto versus apply has a deterministic valid outcome. Preserve pending timing policy Q3 and operational callers.

### D08 — Season-finalization CLI calls a Flask response adapter without app context

**Evidence / features:** `cronComputeFinalScoreboard.py:19–20,77` constructs ScoringEndpoints and calls `compute_end_of_year_season_standings`; handler wraps both success and errors with `jsonify`. CLI creates no Flask app context. Completion updates follow an unchecked handler return. F-026/032; B5.

**Impact:** Ordinary CLI invocation reaches a context-dependent response operation and fails; the error handler also requires context. Adding only an app context would still leave HTTP error tuples unchecked before completion flags. Model currently computes/returns standings, not durable bonus snapshots; persistence requirements are Q6.

**Bounded task:** Call a non-HTTP scoring operation from the job and use exceptions/explicit result validation before marking completion. Define intended finalization persistence rather than inventing a BonusPointEvent table.

**Verify:** Run job orchestration with fake engine/scorer outside Flask; valid season completes, scoring failure does not mark league/season complete, restart skips or resumes according to defined policy. Validate partial-league failures separately (S02).

### D09 — AUTO-SKIP draft changes are not published through the worker's notification path

**Evidence / features:** `DraftModel.process_expired_pick_if_needed:497–653` updates DraftTurn/DraftState and returns from AUTO-SKIP branches without `notify_draft_updated`; `finalize_draft` also does not notify. Worker discards returned action and relies on model pg_notify. AUTO-PICK/live/manual paths do call notify. F-013/023/024.

**Impact:** A worker-driven skip/reset is committed without triggering the documented listener broadcast; authenticated frontend does not regularly poll draft state. Clients can keep an obsolete turn/clock until another update/reload. This is missing publication in source, not a measured delivery outage.

**Bounded task:** Emit one transactional notification for each committed skip/state-change outcome, including finalization/reset outcomes where state changes. Keep timeout rotation and pick eligibility unchanged.

**Verify:** Expired middle/last turns and completion branches emit notifications only on commit; rollback/no-op emits none. Two socket clients receive current snapshot after timeout. Live/manual/auto-pick behavior remains intact; no dependence on HTTP request broadcasting.

### D10 — Draft order accepts an incomplete member list

**Evidence / features:** `DraftModel.set_draft_order:1314–1378` checks submitted IDs belong to league and count matches submitted array, but never verifies every league member was supplied. It bumps all orders by 100000 then updates only supplied IDs. F-018.

**Impact:** A valid nonempty subset can leave omitted members with displaced orders and make start_draft's required 1..numPlayers check fail. Duplicate/foreign IDs already fail the existing count check; don't replace it with weaker validation.

**Bounded task:** Require a full exact permutation of current league membership in the same transaction with a suitable league/order lock; preserve lifecycle restriction.

**Verify:** Full permutation persists; subset, duplicate, extra and foreign IDs leave original order unchanged; concurrent membership change cannot create gaps; start still sees a contiguous order.

### D11 — Restarting an existing draft resets its cursor

**Evidence / features:** `DraftModel.start_draft:982–1048` upserts any existing DraftState to live, overall pick 1 and first member with a new expiry, without checking prior state/picks. `seed_draft_turns` is conflict-do-nothing; picks are not cleared. F-013/018/020.

**Impact:** A repeated start request can move an in-progress draft back to a picked slot; UI hiding a start button does not protect API callers/retries. Precise downstream recovery via snapshot repair is unverified, but unconditional cursor reset is demonstrated.

**Bounded task:** Define legal initial-start/replay transitions under a draft/league lock. Return current state or explicit conflict on duplicate start; reserve destructive restart as a separately authorized feature if ever wanted.

**Verify:** Start twice before/after a pick, while paused and after completion; no committed pick/cursor is reset by replay. Concurrent starts converge on one initial state; ordinary resume retains intended clock behavior.

## Maintainability and organization findings

### M01 — Scoring jobs depend on transport adapters

**Evidence / features:** Both scoring cron builders create ScoringEndpoints; weekly job reaches through `.scoringModel`, final job calls the adapter itself. Rebuild already constructs ScoringModel directly. Endpoint season comments also refer to `/standings` and BonusPointEvent unlike registration/model. F-025/026/032/036.

**Impact:** Transport concerns leak into CLI orchestration (D08), and comments misdescribe contracts.

**Bounded task:** Construct ScoringModel consistently for jobs and leave jsonify/status mapping in ScoringEndpoints; correct misleading comments separately. Add a small finalization coordinator only if job atomicity policy requires one (S02).

**Verify:** Model is callable without request/app context, HTTP contract remains unchanged during extraction, weekly/rebuild/final job adapters share explicit result/error expectations. D08 behavior correction is a separate review item.

### M02 — ScheduleModel owns unrelated read, calendar and provider operations

**Evidence / features:** `scheduleModel.py` is 1,626 lines: week generation, league/season configuration, ESPN ingestion, game upsert/phase classification, bootstrap checkpoints, member/conference/team read projections and search. LeagueModel constructs it just to ensure weeks and compute member displays; scoring consumes schedule calculations. F-007/009/011/012/025/027/028/031/035/036.

**Impact:** Changes to provider bootstrap are reviewed beside scoring reads; cross-domain code reaches private helpers such as `_get_league_timezone`. Initialization/env requirements blur responsibilities.

**Bounded task:** First extract ingestion/bootstrap orchestration behind existing ScheduleModel forwarding methods; reuse ESPN parser/client, rules and checkpoint helper. Later isolate week-calendar operations only when their transaction contract is addressed, retaining facade for CLI/tests.

**Verify:** Same game upsert keys/phase metadata, checkpoint identity/resume flags and week boundaries; no provider call added to read endpoints; all cron/bootstrap/legacy/rebuild callers resolve through stable forwarding methods during migration.

### M03 — Ownership rules and state mutations have overlapping implementations

**Evidence / features:** TransactionModel 1,601 lines includes `_apply_trade` plus `apply_trade`, conference-count/ownership helpers, free agency, proposal/response/veto and list enrichment. DraftModel 1,759 lines repeats conference membership/count/cap logic across live/manual/auto allocation and transaction model. ScoringModel 1,450 lines combines SQL, weekly ranking and season bonuses/tiebreakers. Existing rules modules already centralize tier/tournament margin semantics. F-013/015/016/024/025/030/033/035.

**Impact:** Fixes to season membership, conference limits or ownership writes can diverge. Similar code is not automatically equivalent: live picks, manual allocation, future-week moves and historical scoring have different timing rules.

**Bounded task:** Document invariants and compare two conference/ownership helper implementations; extract one connection-taking shared helper only after fixtures demonstrate equivalence. Consolidate transaction application entry points with explicit state guards; keep command orchestration distinct from pure scoring formulas.

**Verify:** Current/season-neutral conference membership, independent teams, cap boundaries, historical week ownership and pending moves match intended semantics. Characterize live/manual week defaults before sharing them. Don't turn an internal extraction into a silent rule change.

### M04 — Import/bootstrap and naming conventions obscure execution contracts

**Evidence / features:** Imports assume `api/` on sys.path; cron modules use `from bootstrap import *`, while `bootstrap.py` computes its parent as API_ROOT (repository root), despite its name; startSeason documents `PYTHONPATH=.`. `db.py` loads env and creates engine at import; `supabaseAuth.py` requires env at import; create_app starts listener immediately. Some comments name wrong directories/routes; LeagueEndpoints imports logger from `venv`. F-022–028/034/036/039/041.

**Impact:** Working-directory/launch conventions affect CLI discovery and test isolation; constructing an HTTP app also starts a background connection. No import failure is asserted merely from this layout.

**Bounded task:** Document and check supported launch commands first; replace wildcard bootstrap imports with explicit setup where needed and inject listener startup/config for isolated app construction. Use module logging. Do not rename every camelCase module just for consistency.

**Verify:** Supported dev/WSGI/cron/worker/bootstrap/rebuild launch smoke checks in subprocesses with fake dependencies; no secrets read or network opened merely by unit-level construction when configured for isolation. Import paths and compatibility launchers remain documented.

## Speculative investigations and performance candidates

### S01 — Repeated queries/global updates and unbounded work need measurement

**Evidence / features:** `LeagueModel.get_league/get_leagues_for_user` call sync_due_league_statuses, which executes five global UPDATE statements on ordinary reads. Members computes per-member games; weekly scoring also loads games per member and further tie queries; each default get_member_games resolves league rules again. Team search loads sport candidates then ranks/slices in Python; output limit is not DB work limit. pointsAwarded accepts an arbitrarily long week list; own leagues, pending/open transactions and season schedules have no pagination. Sports/rosters are naturally domain-sized but not hard response caps. F-005/008/009/011–016/025/032.

**Impact hypothesis:** More leagues/members/history can increase latency, memory, lock contention and connection use. No slow query or N+1 timing has been measured; databases may optimize subqueries differently from their appearance.

**Bounded task:** Capture query counts, durations/plans and result sizes for one representative detail/member/score journey at realistic scale. Begin with redundant rule/league reads and global status sync; evaluate scoped updates or scheduled lifecycle work against freshness requirements. Add bounded input/results only where measured or abuse-control needs justify contract changes.

**Verify:** Same current-week/day totals, lifecycle transitions, ranks and historical schedules; report fixture sizes, query counts, p50/p95 latency, payload bytes and lock behavior before/after. Coordinate paging/batch limits with FE and operational callers; no blanket caching/index/repository-layer mandate.

### S02 — Multi-step workflows lack a shared completion/locking boundary

**Evidence / features:** League+creator commits before ensure_weeks (`LeagueModel.create_league`); ensure-weeks checks existing then inserts week0 and later weeks in separate transactions. Weekly job scores, then marks/locks, then applies all pending across leagues; no-week branch returns before pending application, and failed leagues are not excluded from global pending selection. Final job marks leagues separately then season; a failed pending application aborts remaining loop. Admission approval computes MAX(draftOrder)+1 before later league lock. Transaction helpers open separate connections while caller holds locks. F-007/018/019/025/026/028/031/036.

**Impact hypothesis:** Partial initialization, duplicate/reordered work, stale validation and overlapping job races are possible. Some are deliberate resumable steps; live uniqueness constraints and scheduler singleton guarantees are unverified. No specific production duplication claimed.

**Bounded task:** Reproduce failure/retry at create→weeks and score→complete→apply boundaries. Decide Q3 transaction timing and Q5 operational guarantees; use league/week scoped locking and explicit progress/retry semantics only where needed. Pass existing connections to helpers needing the same transaction view.

**Verify:** Fault injection at each boundary, concurrent job instances, concurrent approval/start/order and repeated bootstrap. No misleading completion, lost scored data, duplicate membership/order or ownership. Specify whether one league failure permits other leagues to progress; pending changes do not stall or apply early contrary to policy.

### S03 — Duplicate commands and reservation checks need concurrency tests

**Evidence / features:** Pending join reuse plus schema partial unique index protects sequential duplicates, but concurrent check→insert may return an unhandled constraint failure. Trade proposal inserts each time; free-agent pending-add/drop and swap-limit checks occur before insert without a common reservation lock. Snapshot has no generic command idempotency token. Veto deliberately toggles, so repeating it reverses a vote. Draft live/timeout use DraftState FOR UPDATE; game ingest uses ON CONFLICT; these protections should be preserved. F-006/013/015/016/019/024/027/028/030/033.

**Impact hypothesis:** Lost-response retries or simultaneous distinct transactions can duplicate proposals or reserve the same team; toggle replay is not idempotent by design. No exact replay/concurrency outcome was executed.

**Bounded task:** Test two simultaneous pending adds for one team and retries after committed-but-lost responses. Choose per-command replay policy; consider idempotency keys for commands where replay must repeat the original result, not blanket retry of all writes. Review live schema constraints before migrations.

**Verify:** Barrier-based Postgres tests establish one intended reservation/transfer and stable replay result; rejected conflicts leave no partial rows; veto retains explicit toggle policy or separately approved set-state semantics. Don't infer transaction safety solely from context-managed begin.

### S04 — Ingestion duplicates global work and has limited retry controls

**Evidence / features:** cronIngestScoreboard loops active league IDs; `ingest_scoreboard_for_date_for_league` fetches the same sport/date/group scoreboard for leagues sharing a season, then globally upserts GameResult. Each event looks up two team IDs and phase information before its own upsert transaction. Sport-season ingestion already deduplicates external IDs across groups; league wrapper does not. ESPN uses requests.get + raise_for_status with explicit 10-second timeouts, but scoreboard hardcodes 10 instead of configured timeout; no Session/retry/backoff/Retry-After policy found. F-027/028/035/037/041 (F-037 is separate TS ESPN integration, not a Python caller).

**Impact hypothesis:** Unnecessary upstream traffic/DB round trips and transient ingestion gaps; cumulative job time unknown. It is incorrect to claim HTTP calls have no timeouts. A requests timeout is not a total season/job deadline.

**Bounded task:** Measure duplicate sport-season/date/group calls on a multi-league fixture; route cron through one shared ingestion operation per unique season/day if equivalent. Separately define bounded retries for transient GET failures, a consistent timeout configuration and no retry for permanent/provider-data errors. Keep checkpoints marking only successful dates.

**Verify:** Same GameResult/phase outputs for leagues sharing a season; exact provider request counts before/after; timeout/429/5xx/malformed JSON cases; bounded attempt/deadline counts; resume retries failed dates and never marks partial bootstrap complete. Audit the TS integration policy independently rather than imposing a Python change on it.

### S05 — Background delivery and blocking behavior need fault/load verification

**Evidence / features:** Listener starts per app factory, connects using DATABASE_URL while model uses SUPABASE_DB_URL, then waits/polls synchronously. Connection/poll exceptions outside inner handlers terminate task; snapshot exceptions are swallowed. Direct pick broadcast plus transactional pg_notify can generate duplicate update events. WSGI monkey-patches eventlet and launches one Gunicorn worker; no multiworker queue configured. Worker retries exceptions with sleep but supports no explicit stop/health signal; saved socket claims/membership are not revalidated continuously after join. F-013/023/024/034.

**Impact hypothesis:** DB disconnect can silently stop updates; duplicate snapshots cost work; mixed eventlet/psycopg2/select scheduling may block unrelated requests. Matching DSNs, hub behavior, token revocation and room-membership freshness are unverified; don't assert total worker blocking or loss-free delivery.

**Bounded task:** Fault-test listener reconnect/visibility and measure health/request latency during snapshot/DB waits under actual launch mode. Add bounded reconnect/backoff and surfaced task health only after defining delivery/freshness expectations. Do not increase Gunicorn workers without an explicit Socket.IO room/broadcast coordination design.

**Verify:** Forced DB disconnect recovers, errors are observable without secrets, missed notifications recover by snapshot, duplicate event handling is safe, app restart does not multiply listeners unexpectedly, connected clients losing eligibility follow agreed policy. Record pool/hub latency and connection usage under load.

### S06 — Logging and rate/resource limits need explicit operational policy

**Evidence / features:** Source searches found no Flask rate limiter, per-identity/IP quotas, app MAX_CONTENT_LENGTH or DB statement/lock timeout configuration. Public search clamps count but allows arbitrary query/offset; pointsAwarded and trade arrays lack general length bounds. Error handling mixes print/traceback, module logging, missing logs and swallowed listener exceptions. `free_agency_add_drop` returns raw exception details; socket join returns str(exception). `supabaseAuth` catches every verification exception as invalid token without distinguishing internal configuration failure. F-004/006/013/015/016/022–028/032/034.

**Impact hypothesis:** Abuse/resource exhaustion, weak failure diagnosis and SQL/identifier/PII disclosure through errors are possible. Actual gateway rate limits, Gunicorn/proxy bounds, logging levels/redaction and database timeouts are unknown; no exploitation or sensitive error payload was observed.

**Bounded task:** Inventory deployed gateway/database controls; define targeted public-search/socket-join and costly mutation budgets, bounded request sizes and safe structured error logging. Remove raw unexpected error details from client contracts with consumer review; keep useful validation feedback. Avoid adding an arbitrary global limit that breaks bootstrap/jobs or shared-network users.

**Verify:** Over-budget requests fail predictably without partial writes; normal FE and explicit operator flows stay within limits. Captured logs/errors distinguish validation, denied access, provider failure and internal failure with correlation/resource identifiers and no tokens/credentials/email dumps. Test oversized arrays/body and slow-query timeout recovery.

## Package dependencies and limited target boundaries

Read-only AST scan parsed **65 Python files**, found **96 local literal import edges** and **no syntax errors or cycles** in that graph. It resolves absolute imports relative to `api/` and relative imports, includes test/function-local imports, and does not model runtime sys.path mutation, dynamic imports, package dependencies or deployment import order. `api/api.py` versus an `api` package depends on launch context. No circular-import reorganization is justified. Syntax parsing does not validate SQL strings, SQLAlchemy runtime behavior or dependency installation.

requirements.txt pins dependencies but lists direct and transitive packages together. No repository Python runtime pin or dependency vulnerability scan was performed; pinned versions are not evidence of current advisories or exploitability. Actual environment compatibility is remaining coverage, not a recommendation to upgrade everything.

Keep existing endpoint families, rules, job directories and SQLAlchemy patterns. Add only these boundaries when the associated tasks are undertaken:

```text
api/
  authMiddleware.py                 # JWT verification + request identity entry
  authz.py                          # D01: explicit principal/user/member/role checks
  endpoints/
    schedule/
      scheduleModel.py              # existing facade/read consumers retained
      scheduleIngestion.py          # M02: provider/date/bootstrap orchestration
    scoring/
      scoringModel.py               # non-HTTP API for jobs and adapters
      scoringEndpoints.py           # HTTP parsing/response mapping only
    transaction/
      transactionModel.py           # explicit command state/connection boundaries
  rules/                            # retain pure rules; share only proven equivalents
  cronJobs/                         # retain operator entry paths/compatibility
```

`authz.py` is warranted by actual missing principal binding, not by architectural symmetry. Its introduction changes access behavior and belongs to D01, not a pure extraction. An ownership helper under rules would be misleading if it issues SQL; choose a domain helper only after M03 comparison, and pass the transaction connection explicitly. No generic repository/service stack or framework migration proposed.

**File moves/renames:** None required immediately. Retain public paths, camelCase modules and CLI paths. A later extraction may relocate ingestion functions into scheduleIngestion with forwarding methods; that is internal refactoring, not a bulk move. Do not delete legacy NCAA/socket helpers or forwarder CLIs without confirming Q7 callers.

**Internal refactoring:** M01 model construction/transport separation, M02 ingestion extraction, M03 proven shared helpers, M04 explicit bootstrap/logging setup. Preserve response shapes, acquired-week defaults, scoring rules, checkpoint identities and execution contracts during these changes. Pure moves/extractions should be independently reviewable.

**Intentional behavior/API changes:** D01–D11; newly enforced permissions/URL scope, status/validation errors, atomic replacement, replay policies, notifications and draft start/order validation. S01–S06 only become changes after measurement/reproduction or policy resolution. Pagination, quotas, error redaction and auth/public-field projection require coordinated client/operational contract checks. Do not freeze data-exposure or invalid workflow behavior as compatibility requirements.

## Documented stopping boundary and next tasks

This is a bounded source audit across all registered endpoint families and caller categories, not every branch in roughly 9,800 top-level endpoint/cron Python lines plus helpers/rules/CLIs. No runtime performance problem, live exploit, passing tests or production readiness is claimed.

Remaining coverage:

- Isolated end-to-end actor/member/league authorization matrix for all REST operations, including API-only manual picks, week creation, scoring and explicit apply; deployed DB grants/RLS and direct Supabase profile access.
- Fault/concurrency tests for score replacement, job re-entry, pending reservations, veto/apply, approval/order/start, overlapping ownership intervals, and response loss after commit. Check live constraints/indexes against snapshot/migrations before designing DB changes.
- Full rules/bonus/tiebreaker and provider event/phase branch review; historical ownership/tier semantics and finalization persistence remain product/data-integrity questions. Reconcile missing tournament migration separately.
- Query plans/timing, indexes, result sizes, statement/pool timeouts and load with representative leagues/games; profiling of synchronous work under actual eventlet deployment.
- Deployment scheduler cadence/singleton guarantees, process supervision, listener readiness/recovery, matching DSNs, socket claim revocation policy and all external API/CLI consumers.
- Full malformed-body/value/boundary contract matrix, timestamps/timezones/serialization, provider retry/partial-data behavior and dependency/runtime compatibility. Existing tests are mostly unit/mocked domain coverage; no execution in this audit.
- Gateway rate/body limits, logs/redaction/retention, sensitive exception responses and operational health criteria. External infrastructure controls cannot be inferred from repository absence.

Priority: D01/D02 isolation and D03 public-field decision first; D07 transaction state and D06 score atomicity next; D04/D05 contract failures and D08 job context; D09–D11 draft workflow invariants. Reproduce S02/S03 before expanding job/concurrency changes. M01–M04 can be staged in small independent tasks, with characterization checks and compatibility facades. Collect S01/S04/S05 measurements before treating query, ingestion or concurrency work as a performance fix.
