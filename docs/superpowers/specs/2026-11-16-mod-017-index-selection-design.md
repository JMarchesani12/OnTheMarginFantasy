# MOD017 — final controlled index selection

## Deliverable and boundary

This is the final section of the local post-audit implementation roadmap: compare the remaining justified index candidates against current queries and produce evidence-backed recommendations plus reviewable migration proposals. It is not automatic SQL rollout or complete production/browser/operational acceptance. User requested combined design/plan; native inline execution and user-owned integration remain selected.

Use a staged comparison rather than an all-candidate Cartesian benchmark: baseline and isolated alternatives on a representative1000-league fixture, then verify shortlisted configurations at100/5000leagues and required density boundaries. Native fixture indexes only; no configured database metadata reads/changes or published migrations until separately authorized.

## Exact candidate families

1. Ownership: team-led `(leagueId,sportTeamId) INCLUDE(memberId,acquiredWeek,droppedWeek)` versus member-led `(leagueId,memberId,sportTeamId) INCLUDE(acquiredWeek,droppedWeek)`. Test baseline/team/member and relevant interactions with the game candidate. Recommend at most1ownership alternative; existing exclusion/GiST and integrity indexes stay.
2. Games: `(sportSeasonId,date,externalGameId)`, evaluated alone and with the ownership alternatives against current member schedule, team-season/conference reads and new tied-group H2H SQL. No home/away pair indexes from current evidence.
3. Pending transactions: `(leagueId,id) WHERE status='PENDING_APPLY'`, at0.1%/10%/50%pending densities and small/large unclosed-week backlogs. Validate actual status predicate/current workflow queries. A sparse-only win is conditional evidence, not universal endorsement.
4. History lists: `(leagueId,status,createdAt DESC,id DESC)` versus `(leagueId,createdAt DESC,id DESC) INCLUDE(status)`. Compare all-status/status-filtered lists and open trades; recommend at most1full alternative. Do not invent production workload weights. If neither dominates and observed mix/catalog is unavailable, provide a conditional decision table/defer selection rather than adding both.

Alternatives considered: deploy prior synthetic winners immediately (rejected: query shapes changed, overlap/catalog/write costs incomplete); add all plausible indexes (rejected: redundant storage/write cost); staged controlled comparison (recommended). No extra WeeklyTeamScore, reverse membership, conference-leading or DraftPick removal from this task; no JIT/global planner tuning.

## Workloads and correctness

Capture actual current SQL/parameters from canonical services/repositories: ownership point/history/member predicates, roster and distinct/grouped conference counts, current member-game/group-H2H and game listing queries, own-league aggregate as a regression control, pending list/weekly candidate selection and transaction-history/open-trade queries. Preserve API/authorization/ordering/NULL/history semantics; no product query rewrite to favor an index.

Before reusing lookup helpers, independently pin known owner-label text and add non-null unknown-member grouped-count case (expected[]), alongside existing unknown distinct-count0. Keep null-member semantics distinct. Repair fixture status/provenance/sample/cleanup assertions only when the reused path needs them. Never call the oldest fixed-output MOD017 main or overwrite frozen November11 raw.

For each configuration: same deterministic rows/statistics/settings and exact full outputs; record independently expected counts/signatures, EXPLAIN ANALYZE/BUFFERS, warmup+5read samples, actual plans/index use, build time/bytes and existing catalog definitions/constraint ownership. Static output parity alone does not establish benefit. No disabled seqscan/JIT or other planner forcing. Explicitly distinguish scanned rows, filtered rows and index-only heap fetches.

## Write/storage/lock tradeoffs and selection

Measure bounded same-data game insert/correction upserts, slot acquire/drop and transaction insert/status transitions before/after candidates in owned fixtures. Record operation counts, client times, index/relation bytes, buffers and WAL where attributable. Same-row rewrites and physical caches can bias results; label unsupported attribution and missing production durability/vacuum/concurrency costs. Do not derive a production cost model from isolated EXPLAIN totals.

Record normal/concurrent native index build behavior and bounded lock/failure recovery cases on owned data; production build duration/traffic/supervision remain unverified. Do not require universal read speedups or force a winner. Classify each family: supported proposal, conditional/deferred, or no-change. Reject unexplained material regression in a required workload or excessive overlap/write cost; never resolve it by silently adding both alternatives.

Without actual production frequency, use per-workload results and Pareto tradeoffs, not fabricated weighted averages. Existing catalog equivalence may make a new index unnecessary even when the shape wins locally. Recommendations are conditional on fresh authorized target preflight.

## Proposal package, no rollout

For supported candidates only, write documentation/proposal SQL under `docs/modernization/proposals/mod-017-indexes/` (not an automatic migration path): read-only preflight, exact schema-qualified CREATE INDEX CONCURRENTLY outside transactions, verification and guarded recovery. Candidate names are fixed per proposal after selection; equivalent existing definitions under another name imply skip/review, not duplicate creation.

Preflight must inspect actual relation/column types, constraints, index key order/direction/includes/predicate/access method, validity/readiness and same-name drift; name-only IF NOT EXISTS is insufficient. Missing/unexpected catalogs refuse, not partially apply. Record supported PostgreSQL version and operator/session requirements; no hosted credentials or role grants in the proposal.

Verification checks exact intended definition and validity, query equivalence/plans and absence of invalid residual builds. Recovery may remove only a proven newly-created nonconstraint candidate with exact identity/definition after explicit operator review, using DROP INDEX CONCURRENTLY outside transactions; never CASCADE, drop an existing baseline index or disable integrity. A failed/duplicate create requires fresh preflight rather than blind repair/retry.

Read-only/native creation here does not authorize applying proposals to any target. MOD006/008/010 prior rollouts remain historical facts, not pending work to reapply. If no candidate is sufficiently justified, the complete deliverable is no-change/conditional evidence and no speculative DDL package.

## Acceptance and remaining items

New unique RUNNING/PASS/FAILED artifacts persist before provenance/setup; record source/DDL hashes, fixture counts/densities, configuration cleanup and exact owned resource removal. Full relevant audit/backend suites and one final scoped review. Preserve raw history and user staging; no commits/push/deploy.

Local roadmap closes with supported/conditional/no-change decisions and proposal packages. Production catalog/role/traffic rollout, MOD004 privilege/MOD015 constraint proposals, hosted readiness/job checks and full browser/socket/mobile/AT acceptance remain separately tracked; this section does not claim those are complete. Builder chooses bounded fixture sizes/organization and exact proposal names, without broadening candidate families.

Status: fresh builder check found no important unanswered questions; plan self-reviewed. Combined documents ready for user review; no index or product changes.

Execution closeout: controlled selection complete locally; one ownership-only proposal, game/transaction families conditional/deferred. [Report](../../modernization/mod-017-index-selection.md). Final review found no issues; target rollout and broader acceptance remain separate.
