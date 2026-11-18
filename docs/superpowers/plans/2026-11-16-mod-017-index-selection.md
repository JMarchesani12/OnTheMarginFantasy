# Final Controlled Index Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans, preserved native inline workflow and one fresh final review. User owns commits; no staging/push/deploy/configured-target SQL.

**Goal:** Decide the four justified index families using current-query evidence and produce conditional migration proposals, not rollout.
**Architecture:** Shared guarded catalog/evidence helpers support ownership+game and transaction comparisons. Screen isolated alternatives at1000leagues, validate shortlist/boundaries at100/5000, then assess write/build costs and author proposals only where justified.
**Tech Stack:** Existing Python/SQLAlchemy/PostgreSQL17.6, cached image, canonical repositories and guarded tests. No dependencies/providers/browser.
**Spec:** [Design](../specs/2026-11-16-mod-017-index-selection-design.md).

## Global Constraints

No product query/scoring/transaction/API changes, planner forcing/JIT disable, baseline index drops or new candidate families. Preserve exclusion/GiST/identity integrity. Exact outputs required before performance claims. No fabricated production workload weights; conditional/defer/no-change are valid. Unique failure-aware artifacts, historical raw immutable, marked task-owned loopback resources only. Proposals under docs are not authorization to run DDL on any target.

## Review Focus

- Existing equivalent/constraint-backed/invalid indexes cannot be mistaken for new safe-to-create/drop candidates using names alone.
- Current group-H2H/scoped own-list shapes, ownership history/labels and NULL/unknown-member cases must remain correctly measured.
- Sparse pending benefit cannot be generalized to dense pending/backlogged weeks or used to justify both full transaction alternatives.
- Read gains must be assessed alongside storage/write/WAL/build costs without attributing global/background effects as precise per-index cost.
- Proposal CREATE/DROP CONCURRENTLY must stay outside transactions, refuse catalog drift and never remove baseline/integrity indexes.

## Files and interfaces

Create `scripts/modernization/mod017_index_support.py`: exact candidate registry, `index_signature(catalog_row)` (relation/access method/key expressions+order/includes/predicate/validity/constraint ownership), `snapshot_catalog(conn)`, guarded owned fixture/configuration helpers and atomic evidence persistence. Reuse existing marked-local UUID/schema/seed/save_json/verify_cleanup utilities; never oldest fixed-name main. Only created fixture indexes with task prefix `mod017_final_` may be removed by configuration teardown; compare catalog/constraints to baseline after each configuration.

Create `scripts/modernization/compare_mod017_indexes.py`: `run(directory=None,families=('ownership_game','transactions'),connect=None)` orchestrates staged comparisons and explicit case registry. Add a family/size filter for bounded reruns; every artifact records actual matrix/case/sample completeness rather than implying unrun families. Each required family must have a completed decision before final closeout.

Create `scripts/modernization/verify_mod017_index_costs.py` for shortlisted write/build/failure probes; tests in `scripts/modernization/tests/test_mod017_indexes.py`. Reuse current canonical query captures/fixtures where valid; extend lookup expected-owner labels/unknown grouped member before reuse. Do not rewrite unrelated old reports/helpers.

Supported proposals live in `docs/modernization/proposals/mod-017-indexes/`: README decision/target gate, preflight.sql, create.sql, verify.sql, recovery.sql. Candidate names/DDL frozen in the package after selection; no files in an automatic migration execution directory. Final report `docs/modernization/mod-017-index-selection.md` plus summary/decision JSON.

## Task 1 — Guarded comparison substrate and current workload contracts

- [x] RED tests `test_signature_distinguishes_keys_order_include_predicate_and_validity`, `test_equivalent_other_name_is_not_a_new_candidate`, `test_teardown_refuses_unowned_or_constraint_index`, `test_provenance_failure_overwrites_stale_pass_before_connect`, `test_incomplete_configuration_or_samples_cannot_pass`. Inputs are literal synthetic catalog rows and fake connection failures; assert decisions/state/exit behavior, not source strings alone.
- [x] Run `python3 -m unittest discover -s scripts/modernization/tests -p 'test_mod017_indexes.py'`; expected RED from missing behavior, then implement helpers/registry/runner guards and rerun PASS. Persist RUNNING before source reads/connection; only PASS after expected matrix and cleanup verified. Never drop arbitrary names or equivalent baseline indexes.
- [x] Registry exact alternatives: ownership team `(leagueId,sportTeamId) INCLUDE(memberId,acquiredWeek,droppedWeek)`, member `(leagueId,memberId,sportTeamId) INCLUDE(acquiredWeek,droppedWeek)`; game `(sportSeasonId,date,externalGameId)`; pending `(leagueId,id) WHERE status='PENDING_APPLY'`; history status-first `(leagueId,status,createdAt DESC,id DESC)` versus time-first `(leagueId,createdAt DESC,id DESC) INCLUDE(status)`. Bind data values; names/DDL are fixed task constants.
- [x] Capture current ownership point/history/miss, distinct/group conference count, team lookup/member schedule/team-season/conference/group-H2H, own-league regression, pending/workflow/weekly candidates and history/open-trade SQL from canonical repositories/services. Pin source hashes and inputs before candidate creation. Add independent owner-label text assertion and non-null unknown-member grouped-count[] control; distinct unknown-count remains0. Preserve NULL-member semantics and literal ordered values.
- [x] Run affected lookup/audit tests and full guarded backend; expected PASS. Old native artifacts remain frozen. New matrix must include current batch H2H rather than claiming old pair-query results transfer automatically.

## Task 2 — Ownership and game comparison

- [x] Build deterministic1000-league screening fixture with current integrity migrations, ownership point/history/transfer/NULL/absent cases, member counts, schedule/group-H2H and own-list regression. Validate expected data/field signatures before measuring. Record existing catalog/constraints/settings/relation sizes; skip equivalent existing definitions transparently.
- [x] Compare baseline, team-led, member-led, game-only, team+game and member+game in isolated sequential configurations. Drop only created task indexes, restore/verify catalog after each, ANALYZE consistently. Per actual SQL/service case: warmup+5samples and EXPLAIN ANALYZE/BUFFERS; exact independent outputs first. Do not change product SQL or server planner settings.
- [x] Shortlist ownership at most1 and conditional game pairing based on per-workload results/read paths/storage; validate baseline and shortlist at100/5000, including team-point regressions, group-H2H and hot/sparse supplied own lists. If alternatives conflict, report workload conditions rather than adding both or fabricating usage frequencies.
- [x] Native expected PASS: all rows/counts/labels/ordering/NULL/history cases identical, required configuration/sample counts complete, existing integrity/catalog restored. Report actual scans/buffers/heap fetches, build time/index bytes and all distributions. A faster query alone does not authorize selection without Task4 costs.

## Task 3 — Transaction density/history alternatives

- [x] At1000leagues compare baseline/pending partial at0.1%/10%/50%pending density and bounded small/large unclosed-week backlog. Fixture metadata must report actual prepared status/week counts. Exercise current pending lists/workflow and weekly candidates, including empty/absent cases; confirm exact partial predicate compatibility.
- [x] Compare full history status-first versus time-first separately at representative all-status/status-filtered query shapes; retain open trades as a regression/control. Use identical data/order/timestamps and parameter cases across configurations; preserve unordered aggregate/order limits honestly. No global JIT disable or open-trade algorithm rewrite.
- [x] Validate shortlisted/conditional cases at100/5000 and combined pending+at-most1history choice to check interaction/overlap. Use no synthetic weighted overall winner without known production mix. Dense/backlog regressions produce explicit conditional/defer/no-change decisions.
- [x] Same exact-output/catalog/sample/EXPLAIN/size gates as Task2. Run audit tests before expensive validation; no redundant full matrix at every tier.

## Task 4 — Write/build costs and candidate decisions

- [x] For shortlisted configurations compare bounded game insert/correction, ownership acquire/drop and transaction insert/status-change statements on identical owned fixtures. Use canonical write repository operations where possible; label representative SQL probes versus full workflow acceptance. Record counts/times/buffers/WAL/index/relation bytes and rollback/commit mode; expected persisted state must remain correct.
- [x] Prefer per-statement EXPLAIN(ANALYZE,BUFFERS,WAL) for attributable probes; a global WAL-LSN delta includes background/other work and must be labelled. No production vacuum/durability/concurrency cost model from these small probes. Preserve physical/cache caveats and HOT/update effects.
- [x] Test native concurrent index build completion/validity and bounded blocker/failure cleanup in owned fixtures, with deterministic barriers/timeouts. Verify invalid residual detection and exact newly-created index recovery. Do not lock configured tables, force an integrity index drop or infer production build duration.
- [x] Produce one decision record per family: supported proposal, conditional/deferred, or no-change, with workload/plan/output evidence, storage/write/lock tradeoffs and overlap catalog. At most1ownership and1full-history recommendation; pending/game each require their own evidence. Investigate repeatable material regressions rather than silently accepting/adding indexes; no arbitrary latency pass threshold.
- [x] Run `python3 -m unittest discover -s scripts/modernization/tests -p 'test_mod0*.py'` and `python3 api/tests/run_isolated.py`; expected all PASS with actual counts. Native artifacts must cover required shortlist/density boundaries and verified owned DB/index/container cleanup.

## Task 5 — Proposal packages and final roadmap closeout

- [x] For supported candidates only, write read-only preflight that inspects exact relations/types/key order/directions/includes/predicate/access method/validity/readiness/constraint ownership. Existing equivalent index under any name means skip/review; same-name drift/missing metadata refuses. Do not rely on name-only IF NOT EXISTS.
- [x] Author exact schema-qualified CREATE INDEX CONCURRENTLY outside transaction blocks; no automatic target execution. Verify definition/validity/queries afterward. Handle races/failures with fresh preflight, not blind retry. Recovery requires proven newly-created OID/name/definition/nonconstraint identity and explicit operator review before DROP INDEX CONCURRENTLY, never CASCADE or baseline removal.
- [x] Native proposal tests: empty/equivalent/different-name/invalid/same-name-wrong-definition and constraint-backed cases; drift refuses without partial mutation. Validate create/verify/guarded recovery on owned data. Packages state supported PostgreSQL versions/session requirements and remaining target catalog/role/traffic approval. If selection is conditional/no-change only, document that fully and omit speculative executable DDL.
- [x] Write final report/decision summary linking all evidence and proposal gates. Mark this local roadmap section complete without claiming MOD004/MOD015 proposals, hosted readiness, production rollout or full browser/socket/mobile/AT acceptance are complete. List remaining separately tracked gates briefly.
- [x] One fresh final scoped review via executing-plans with spec/plan/Review Focus/ledger rulings/evidence; one material RED→GREEN fix pass/full affected tests, no rereview. Record deferred minors/declined scopes. Preserve user index/uncommitted work; no stage/commit/push/deploy. Remove exact owned containers/DBs/temp roles, retain Docker/cache/other services.

## Self-review and handoff

Task1 owns trustworthy comparison/catalog contracts, Tasks2–3 current read shapes/density boundaries, Task4 costs/selection, Task5 proposal safety/review/closeout. Review Focus has explicit gates in owning tasks. Registry matches roadmap; staged tiers avoid an unneeded full Cartesian run. Conditional/no-change decisions prevent guessing production workload weights or deploying all alternatives. No migration applies merely because a local fixture passes.

Combined design/plan ready for review; fresh builder check found no important unanswered questions. No product/index/target change during planning. Native inline method remains selected.

Execution complete locally: [report](../../modernization/mod-017-index-selection.md). One ownership proposal; other families conditional/deferred. Backend827/audit71 and native evidence pass; final review no findings. No target DDL or integration. Rulings/progress ledger retained while user-owned changes remain uncommitted.
