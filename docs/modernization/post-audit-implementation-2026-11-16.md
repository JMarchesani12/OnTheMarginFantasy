# Post-audit implementation roadmap — 2026-11-16

This consolidates the audit into an ordered implementation queue. It is a plan, not evidence of deployed fixes or permission to apply SQL. Current application changes remain deferred; this planning pass modifies documentation only. Preserve existing audit artifacts and user-owned uncommitted work. Continue native inline execution with one final review per bounded implementation batch; the user handles commits and integration.

The local source/fixture audit has enough evidence to begin narrow fixes. It does not establish complete browser/assistive-technology acceptance, production performance, current hosted metadata or external-consumer ownership. Those limits belong to their release/design gates; they do not require another open-ended audit before the first fix.

## Recommended sequence

| Order | Batch / original card | Evidence and outcome | Execution status |
| ---: | --- | --- | --- |
|1|Stable league-search ordering / MOD018|700 rows but695unique IDs in equal-name pagination; unique-ID fixture probe completes traversal. Append ID as last sort key, preserve contracts.|Small, ready-to-review plan: [search](../superpowers/plans/2026-11-16-post-audit-search-order.md).|
|2|Home tab keyboard/ARIA / MOD036|Native ArrowRight does not move focus; both tabs in Tab sequence, no tab/panel linkage. Complete manual-activation tab semantics.|Small, ready-to-review plan: [Home tabs](../superpowers/plans/2026-11-16-post-audit-home-tabs.md).|
|3|Tier-tool invalid cache recovery / MOD036|HTTP200 malformed JSON is cached; next invocation fails without refetch. Validate before publishing, recover invalid cached data once.|Small–medium, ready-to-review plan: [tier cache](../superpowers/plans/2026-11-16-post-audit-tier-cache.md).|
|4|Lifecycle read/write boundary / MOD020|Five global UPDATEs before scoped SELECT; converged5k fixture still1kupdates/500unrelated leagues. Preserve visible lifecycle while removing global writes from normal reads.|Design first; requirements below, then one bounded implementation at a time.|
|5|Weekly scoring per-run context and batching / MOD021|16members:52statements untied,204unresolved including120pair reads. Reuse immutable context, then one measured retrieval path.|Design first; native equivalence before claiming gains.|
|6|Ingestion unit deduplication / MOD022|16same-season leagues:32fetches/64upserts/640SQL versus existing season helper2/3/29 on identical duplicates.|Design conflicting-event/report/failure policy first; retry policy separate.|
|7|Own-league scoped score aggregation / MOD017|Sparse result remains expensive despite reverse membership index; global score grouping dominates.|Bounded query design/implementation after semantic fixture inventory.|
|8|Supported index selection / MOD017|Ownership, game season/date and sparse pending candidates have evidence; exact choice depends on final query shapes/catalog/workload.|Controlled comparison + migration proposal only, then separately authorized rollout.|

The three first plans are independent and intentionally small. Start with order1; do not bundle all three into one review or combine them with broad rendering/provider cleanup. Orders4–7 are preferred scheduling order, not an assertion that every task depends on all earlier tasks. Index evaluation may inform them earlier, but final redundant/overlap decisions follow stabilized query shapes.

## Decisions for the first tranche

### Search ordering

Keep `similarity(l.name,:q) DESC, l.name ASC`; add `l.id ASC` last. No new pagination/cursor/count API, no relevance normalization, no public query/limit/offset changes. Home uses six-row pages; API helper default20 and server max50 remain distinct. Prove complete static-fixture traversal at6/20/50 rows, sport/private isolation and heap-layout independence. Concurrent inserts/deletes remain outside an OFFSET guarantee.

### Home tabs

Retain manual activation: arrows move focus, Enter/Space or click activates. Add roving tab stops and stable tab/panel relationships; do not activate a search/fetch merely on arrow focus. Keep existing state, cancellation, error/Retry, paging, auth and identity behavior. Hidden panel shells may exist for ARIA targets, but inactive workflow content must retain its current active-only lifetime and stay out of focus/AX exposure.

### TypeScript tier cache

Validate syntax and an `events` array before publishing a successful payload. A valid empty array remains cacheable. Invalid legacy cache entries are invalidated and get one recovery fetch; no loop or generic transport retry. Malformed fresh JSON still fails and leaves no poisoned cache. Invalid-schema responses keep the existing warning/return contract but are not cached. Preserve HTTP503 warning/empty behavior and network-error propagation for this batch. Atomic temp-file/rename publication and owned temp cleanup must be tested. No TTL, provider limit, timeout/backoff or whole CLI-output policy change.

These are proposed implementation contracts for the next user-reviewed batches, not product changes made by this document.

## Design requirements for larger application work

### Lifecycle / MOD020

Files: `api/endpoints/league/lifecycle/{service,repository}.py`, `reads/service.py`, `leagueEndpoints.py`; any new scheduled entry point is a separate explicit decision.

1. Reproduce the ten-group fixture and existing timezone/boundary/rollback tests, including Completed → Drafting → Completed churn in an ended season. Define status convergence versus zero repeat writes separately.
2. Inventory HTTP, internal reader, trusted job and admission/draft callers. Decide authorization and transaction scope before writes; endpoint prechecks are not a substitute for a race-safe internal contract. Do not turn direct denied-reader probes into claims about HTTP exposure.
3. Choose the explicit transition boundary: authorized target/set refresh and/or supervised global job with an agreed freshness/cadence/failure contract. Ordinary reads must not retain hidden global UPDATEs. Do not silently remove current freshness behavior or register a new job without its operational design.
4. Preserve completed-season precedence, UTC/local calendar resolution, draft guards, lock order and rollback. Do not add a blanket Completed exclusion that changes active-season policy merely to eliminate the observed ended-season churn.
5. Compare statement counts/touched IDs and repeated no-op writes, not only final statuses. Native delayed/retried transition and permission/lock cases must pass. Scheduler rollout remains separate.

Deliverable before coding: reviewed boundary/call graph and cadence decisions plus a bounded task plan. Do not implement a new status policy based only on the performance report.

### Weekly scorer / MOD021

Files: scoring service/repository, schedule read service/repository, weekly orchestration tests.

1. First share immutable league/rules context within one supplied-connection scoring run; no global/cross-league cache. Explicitly decide the snapshot/locking contract for mutable settings, tiers and phase facts before reuse; do not silently freeze changing inputs. Keep public/trusted signatures backward compatible or explicitly inventory consumers.
2. Then batch one hot retrieval path. Preserve raw H2H precedence, current nonrecursive tie ordering, largest absolute adjusted margin fallback, member-ID ordering, waterfall points, half-open ownership, dual ownership, tier and phase rules.
3. Preserve caller connection, week lock, atomic replacement, final-period guards and failure/retry behavior. Include existing-score replacement and rollback checks, not just an initially empty score table.
4. Add mixed ties, history/ownership transfers, postseason/zero/split/future periods and cross-league runs beyond the five-case performance fixture. Require exact stored/returned equivalence and a measured query-count reduction; no promised production speedup.

Deliverable: first context-sharing plan, followed by one separately reviewed batch query. Do not rewrite the scoring algorithm.

### Python ingestion / MOD022

Files: `cronIngestScoreboard.py`, ingestion service/repository, real ESPN client, existing bootstrap/checkpoint boundaries.

1. Decide canonical key and conflicting duplicate precedence before changing routing. Existing league and season summaries/fetch-failure wrappers differ; an existing season helper is not automatically interchangeable.
2. Preserve observable per-league processed/failure reporting, date/timezone windows, per-season reference validation, corrections/phase overrides, committed partial progress and continued processing of other seasons. Define what all leagues sharing a failed key report.
3. Deduplicate one logical season/date/group unit; distinguish logical fetch count from transport retry attempts. Test identical and conflicting group overlaps, multiple seasons/sports/dates and explicit retry recovery.
4. Treat bootstrap/checkpoint completion and HTTP timeout/retry/backoff/Retry-After policy as separate contracts. Existing request timeout must not disappear. No unbounded retries or accidental completion after partial failure.

Deliverable: policy/call graph plus orchestration-dedup plan; transport retry and bootstrap adjustments are subsequent bounded plans. No live provider calls needed for deterministic failure tests.

### Own-league score aggregation / MOD017

Files: `api/endpoints/league/reads/repository.py` and current listing authorization/projection tests.

Scope aggregation to the requested user's eligible leagues/members before expensive score grouping, while retaining public result completeness. Pin hot/sparse/absent users, all/active/completed filters, week0 inclusion, nullable current-week context, persisted fallback/COALESCE points and commissioner/member projections. Do not introduce pagination or stale caching of complete own-league/draft/roster results. Native equivalent ordered results and scoped read cost are required; do not infer that another membership index alone solves this query.

## Index work: measured candidates, not a rollout list

Before reuse, harden/version the earliest fixed-name measurement runner: unique RUNNING/PASS/FAILED outputs, expected counts/samples and failure cleanup. Never overwrite the frozen November11 raw artifact. Verify current catalogs and real query shapes; use synthetic low/high densities and representative current constraints. Capture before/after plans/outputs, build/storage and write/WAL/lock considerations.

| Candidate family | Next controlled comparison | Explicit exclusions |
| --- | --- | --- |
|LeagueTeamSlot covering|Compare team-led `(leagueId,sportTeamId) INCLUDE(memberId,acquiredWeek,droppedWeek)` versus member-led `(leagueId,memberId,sportTeamId) INCLUDE(acquiredWeek,droppedWeek)` across point, roster/count, H2H and schedule joins. Accumulated member/count evidence makes member-led worth first evaluation.|Choose one if supported; do not add both automatically. Keep GiST/exclusion integrity.|
|GameResult season/date|Evaluate `(sportSeasonId,date,externalGameId)` with the chosen ownership path and final schedule/scoring SQL.|Do not add paired home/away structures from the current evidence; no benefit claim for every schedule query.|
|Pending Transaction partial|Evaluate `(leagueId,id) WHERE status='PENDING_APPLY'` at sparse/dense pending and backlogged weeks.|Sparse0.1% fixture is not all workloads; partial predicate must match real status/query semantics.|
|Full Transaction list|Choose status-first versus time-first covering alternative based on observed all-status/filtered workload and existing catalog.|Do not ship both. Open-trade JIT/aggregation cost remains separate; no global JIT disable.|

No extra WeeklyTeamScore index is currently supported; neither an isolated reverse-member index nor a conference-leading membership index is justified by these fixtures. Do not drop DraftPick's apparently overlapping index without deployed dependency/constraint/usage evidence. Do not promise synthetic speedups in production. Each selected migration needs a reviewable preflight, exact DDL, verification/recovery and authorized target execution; no SQL is applied by this roadmap.

## Evidence maintenance before reuse

Historical raw reports remain immutable. New runs get new IDs/current timestamps/source hashes and explicit before/after policy labels. Some current audit tests intentionally assert the old observed defect; update them to the new intended contract explicitly rather than treating frozen baseline behavior as a forever requirement.

- Search: make the ID probe idempotent once production SQL has the ID key; label any no-op/current-versus-historical comparison honestly. Add actual six-row client-size traversal.
- Lifecycle: assert statement sequence as well as counts when removing the global callback.
- Tier tool/Home: update the old malformed-cache/unchanged-arrow observations when fixes land; preserve old raw artifacts. Before detailed MOD036 timing reuse, add a per-render generation/commit marker. Keyboard-only checks need not repeat all bundle/timing probes.
- Ownership lookup: independently assert owner label text and include the non-null unknown-member grouped-count case before selecting a covering index.
- Ingestion: refresh active/completed fixture facts after synthetic status overrides; retain the annotation on the old artifact.
- Other recorded sample/boundary/cleanup test-strength gaps should be addressed when the relevant runner is reused, not bundled into every product fix. Old scratch base labels are traceability notes, not product defects.

## Rollout and acceptance, distinct from local implementation

- MOD006/008/010 records say APPLIED_AND_VERIFIED on their then-configured target. Do not reapply them as pending audit work or infer every future environment matches that target.
- MOD004 browser privilege proposal remains unapplied. Re-inventory direct browser data consumers after MOD026's API-owned profile changes; the older own-User SELECT assumption may be historical. Reconfirm catalog/roles/authorized maintenance actor/default privileges and external clients before choosing exact scope. Do not partially apply or broaden privileges to bypass a failed guard.
- MOD015 composite conference/game constraints remain a preflight/proposal, not an authored migration. Review nullable sportId/dirty rows/parent keys/delete semantics and missing mappings; never invent independent buckets/backfills. Require native upgrade/replay/dirty-refusal proof and explicit target rollout.
- MOD024 hosted readiness/listener/job cadence/direct-session/pooling/singleton/supervision checks remain an operational checklist, not an assumed deployment. Any lifecycle job needs that same design.
- Full authenticated browser flows, real sockets/reconnect, mobile/drag/touch and assistive technology require a separate acceptance pass. Isolated native fixtures reduce uncertainty but do not close those claims. Product fixes may proceed locally without pretending acceptance is complete.
- MOD035 uncertain external/operator ownership remains keep/no-change; no dormant route registration or retirement based only on absent imports.
- MOD028 SDK-auth F002 messages remain outside the completed REST safe-error scope. Gateway/distributed quota enforcement and external consumer contracts also retain their earlier decisions/evidence limits; do not add an arbitrary global limiter or count those boundaries as silently implemented.

## Deliberate non-work and separate feature

Do not add broad memoization/caching/virtualization, catch-all/error-boundary framework, arbitrary pagination, provider limit changes or a database rename campaign from this audit alone. Investigate these only when a concrete failure/workload warrants a bounded change.

Fair draft-round scaling is a **separate feature/policy design**, not an audit cleanup: numPlayers is current membership, membership is uncapped, and equal roster sizes/eligible supply/conference limits must guide the design. Historical remapping/snapshots also remain separate from MOD016's completed safeguards. Neither is silently included in the queue above.

## Execution gates and completion

For each implementation batch: reproduce the defect with a meaningful RED test, implement minimally, run focused tests and required whole-domain checks, verify native behavior where SQL/browser semantics require it, then one fresh review and a single material-fix pass. Record deferred minors honestly. Native fixture calls may use already-authorized owned local resources; no configured jobs/providers/database rollout follows implicitly.

Use `python3 api/tests/run_isolated.py` for backend isolated checks, existing frontend Node tests/type/build/import checks, and owned marked-local native harnesses only where relevant. Baseline test counts are historical; record current counts and failures for each batch. Do not rerun unrelated native suites merely to pad verification. Rollout approval, if needed, comes after the exact migration/deployment result is concrete and reviewable.

This roadmap creates no application changes, migrations or deployment actions. First execution recommendation: search ordering, then Home tabs, then tier cache. Larger work gets its own reviewed design rather than being smuggled into these fixes.

## Implementation progress — 2026-11-16

The first three batches are implemented locally: [search ordering](mod-018-search-order-implementation.md), [Home tabs](mod-036-home-tabs-implementation.md), [tier cache](mod-036-tier-cache-implementation.md). MOD020's approved scoped refresh/read boundary is also [implemented locally](mod-020-scoped-lifecycle-implementation.md), preserving current phase policy; scheduler/repeated-write cleanup remain separate. Next is MOD021's immutable per-run scoring-context design before any batching. These follow-ups supersede the initial deferred/ready-to-review execution labels above; they do not establish deployment.

### MOD021 rules-only context — 2026-11-16

Supplied-connection weekly scoring now resolves rules once per call, preserving scores, other SQL reads, locks and no-conn behavior. Backend804/804, audit55/55 and native count/equivalence/rollback/boundary checks pass; review found no material issues. [Implementation/evidence/deferred notes](mod-021-weekly-rules-context-implementation.md). Local, uncommitted/undeployed; H2H/game batching and full input consistency remain separate.

### MOD021 tied-group H2H implementation — 2026-11-16

Supplied weekly H2H uses1raw statement per tied group, preserving static scores/pair arithmetic and no-conn behavior with an explicit per-group snapshot. Backend813/813, audit56/56 and PostgreSQL counts/parity/recovery checks pass; review found no material defects. At16members H2H-decides157→38statements, fallback173→54; no production latency claim. [Report/evidence/deferred trace note](mod-021-head-to-head-batch-implementation.md). Local, uncommitted/undeployed; member-game batching/full-input consistency remain separate.

### MOD022 shared live ingestion — 2026-11-16

Live cron shares season/date/group work across leagues with later-valid-wins, identical-skip and shared failure fanout, preserving committed progress and per-league reporting. Backend823/823, audit57/57 and native fields/counters/recovery/real-gate checks pass; review no material issues. At16leagues32→2fetches,64→3upserts,640→76SQL in the fixture. [Report/evidence/limits](mod-022-shared-scoreboard-implementation.md). Local/uncommitted/undeployed; transport retry/bootstrap/checkpoint policy remains separate.

### MOD017 scoped own-league aggregate — 2026-11-16

Own-league score SUM now filters eligible user/member/league/stage/refreshed IDs before grouping; outer results/fallbacks unchanged. Backend827/827, audit60/60 and native100/1000/5000comparison/plan checks pass; review no findings. Sparse5000-league case aggregates12scores instead of480k; hot scans remain disclosed. [Implementation/evidence/tradeoffs](mod-017-own-score-scope-implementation.md). Local/uncommitted/undeployed; index comparisons/rollout remain separate.

### MOD017 final index selection — 2026-11-16

The final local controlled-comparison section is complete: [evidence and decisions](mod-017-index-selection.md). Recommend one member-led ownership covering index through the [reviewable proposal package](proposals/mod-017-indexes/README.md); game and transaction families are conditional/deferred because plans, density and workload tradeoffs conflict. Backend827/audit71;976read records/4880samples,270write probes and9proposal cases pass; fresh review no findings. Task-owned resources removed. No configured-target DDL, rollout or user integration performed. Operational/schema/browser gates above and separate features remain outstanding; this closes local selection rather than deployed acceptance.
