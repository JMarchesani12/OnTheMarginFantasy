# MOD017 game/schedule baseline — 2026-11-13

Audit information only: performance changes remain deferred until audit completion. No application SQL/index/tuning or rollout change. [Current manifest](evidence/mod-017-games-current-2026-11-13.json) points to the [unique raw artifact](evidence/mod-017-games-9110dad45a77426bb2a7afbe7e3270e0.json).

## Workload and method

Actual member-week, conference-week and team-season SQL is captured from ScheduleReadRepository, including half-open ownership, owner/no-owner context and season-first conference membership. Reuse guarded PostgreSQL17.6/schema001+MOD006/008/010, add exact20261030_game_kickoff_tbd migration. No RLS/platform/deployed-schema equivalence claim; prior runners/artifacts unchanged.

| Total games | Seasons | Current-season games | Sport teams | Current-season fraction |
| ---: | ---: | ---: | ---: | ---: |
|10,000|20|500|512|5%|
|100,000|50|2,000|512|2%|
|500,000|100|5,000|512|1%|

One sport,32 default16-team conferences; team1 moves from conference1 to2 for2026.513 membership rows exercise season precedence without duplicates. Deterministic home/away pairs,91-day date distribution, scores and5%TBD flags; one anchor game ensures the moved team is visible in the current window. These are synthetic stress distributions, not real sport/provider schedules. Previous100/1000/5000-league ownership fixtures contain16,000/160,000/800,000 history slots.

Twelve cases cover current/historical member weeks, missing member/week, team-season owner/no-owner/past/missing context and conference precedence/missing context. Expected counts derive independently from fixture arithmetic, not source query output. Warm-up, one EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON) and5 execute/fetch samples per case/configuration; **108 results** preserve expected counts and complete ordered fingerprints/bytes. Readings are client execute/fetch medians, not HTTP latency. Raw server/buffer/JIT settings also recorded; no forced planner or cold-cache claim.

## Results (client median ms)

| Games | Member current: baseline → season/date | Team season with owner: baseline → season/date | Conference1 current: baseline → season/date |
| ---: | ---: | ---: | ---: |
|10,000|1.378 →1.425|1.556 →1.165|2.883 →2.279|
|100,000|5.677 →5.835|9.386 →5.035|25.992 →21.002|
|500,000|16.146 →16.122|26.759 →16.126|283.847 →277.597|

Paired home/away indexes yield15.962ms team-season,16.579ms member and272.733ms conference1 at500,000 games. These small differences do not justify both alternatives. Season/date index is29,548,544bytes (28.2MiB), about19.5% of baseline total GameResult relation151,330,816bytes; paired indexes total67,600,384bytes (64.5MiB), about44.7%. Warm build timings338ms single versus110/108ms paired individually are fixture observations, not production build/write-cost estimates.

## Where time remains

Conference2 returns34 games at the largest tier: baseline353.360ms, season/date337.063ms, paired351.583ms. Game filtering improves: baseline GameResult sequential scan visits500,000 rows and returns34 in20.571ms; season/date index returns34 after407 filtered rows in0.660ms. Yet the two ownership joins each loop34 times.

The existing ownership GiST plan uses team-based access and filters many historical/other-league rows: home-owner scan removes about15,441 rows per loop, with205,930 shared hits and11,570 reads; away-owner about9,558 per loop,129,403 hits and5,252 reads. Candidate game indexes leave that work largely intact. Do not add node times/buffers as independent wall time, and do not confuse cache hits versus reads with cold-cache proof. The earlier ownership covering-index investigation is relevant, but this batch does not test combined indexes or implement that candidate.

## Audit conclusions

- Record season/date as a candidate for later workload-informed evaluation, principally team-season reads here. It does not solve full member/conference cost by itself.
- Do not justify paired home/away index rollout from this fixture: twice the structures/storage, little additional measured end-to-end advantage over season/date. Actual sport/season/team selectivity and workload mix can differ.
- Follow repeated ownership join cost into the final optimization plan, using the earlier ownership evidence. No query cast/rewrite, combined-index experiment, JIT/global tuning or ownership behavior change occurred.
- Largest fixture team-season result is20 games, conferences29/34. These results do not justify pagination; no complete schedule/draft/roster response is silently paged.

## Verification and limits

Four new runner tests RED before module existed, then combined14 runner tests pass. All3 native tiers/108 case-configurations, SQL/params/provenance/counts/fingerprints/five samples checked. Unique RUNNING/PASS/FAILED artifacts and UUID-owned cleanup reused; no raw application/configured DSN/provider/job startup.

Unmeasured: production workload/cardinality/schema/roles/RLS/provider/physical-cache/concurrency/write/WAL/vacuum costs, other sports, skewed/null team identifiers and real schedule distributions. Full service scoring/head-to-head/team-search/ingestion paths remain separate; this does not close all MOD017/performance work. All optimization implementation stays deferred to the end of the audit. Work uncommitted/undeployed.

Final review: Critical0/Important0/Minor test-strength gaps. Reviewer independently passed14 units and verified all10 input hashes and108 SQL/parameter/count/fingerprint/sample/median/report comparisons. Deferred minors: new count/sample unit does not directly reject a four-sample record, and broad arithmetic test does not specifically assert inclusive date boundaries. Shared validator/count enforcement and current native artifacts are verified; no observed defect. No native rerun or implementation change required.

Author cleanup: zero MOD017 databases, exact owned labels/no persistent mounts checked, container removed, remaining game taskcontainers0. Docker/image cache retained. [Closeout/decisions](evidence/mod-017-games-summary-2026-11-13.json).
