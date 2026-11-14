# MOD-017: own-league and ownership baselines — 2026-11-11

This is a reproducible **synthetic two-query-family baseline**, not production profiling or an index rollout. No production query or application behavior changed. [Raw parameterized plans, samples, catalogs and fingerprints](evidence/mod-017-query-baselines-2026-11-11.json) record all measurements. Run `python3 scripts/modernization/measure_mod017.py` only against a marked disposable loopback server on127.0.0.1:55439; it accepts no DSN and owns a UUID database per tier.

## Fixture and method

PostgreSQL17.6 from the previously cached official image, digest `sha256:00bc86618629af00d2937fdc5a5d63db3ff8450acf52f0636ec813c7f4902929`. Versioned001_schema plus exact MOD006/008/010 migrations yields51 baseline indexes. Minimal synthetic auth.users prerequisite; access/RLS002 and later unrelated migrations are omitted. No deployment schema/role/Supabase equivalence claim.

| Leagues | Members | Weeks | Aggregate weekly scores | Ownership history rows |
| ---: | ---: | ---: | ---: | ---: |
|100|800|1,300|9,600|16,000|
|1,000|8,000|13,000|96,000|160,000|
|5,000|40,000|65,000|480,000|800,000|

WeeklyTeamScore has one member/week row, so its four-team contribution is represented in the value, correcting the design's fourfold row-count estimate. Each league has8 members,13 weeks (12 scored, current13),32 teams and5 adjacent nonoverlapping ownership intervals per member/team. One hot user belongs to all leagues; each other user belongs to one. One third of leagues are Completed. All payloads/settings/names are synthetic; timestamps derive from the recorded server anchor.

Actual SQL/parameters are captured from LeagueReadRepository.own_leagues (all/active/completed, hot/sparse/absent users) and team_ownership_rows (member/omitted/NULL, current/history/miss/boundary). Production SQL is executed unchanged. Lifecycle synchronization, HTTP serialization, RLS and service orchestration are excluded.

One warm-up and one EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON), then five complete execute/fetch samples per case/configuration. The table below uses client execute/fetch medians; raw server profiling time is separately recorded and must not be conflated with endpoint latency. Serialization/hash work is outside that timer. Warm-up does not imply every page fits PostgreSQL shared buffers; shared reads/temp activity remain in the raw plans. No cold-cache claim. Statement120s/lock5s/connect3s budgets. Default planner settings retained, no forced index scans.

## Results

| Leagues | Own-leagues hot baseline → reverse-member index (ms) | Sparse-user baseline → reverse-member index (ms) | Ownership member baseline → team-cover index (ms) |
| ---: | ---: | ---: | ---: |
|100|2.494 →3.011|1.886 →1.823|0.652 →0.407|
|1,000|19.061 →17.592|12.879 →12.501|5.875 →0.312|
|5,000|72.382 →70.409|34.406 →33.368|16.459 →0.423|

Every sample matches its fixture's expected row count; complete own-league ordered row fingerprints, serialized byte counts and ownership results match baseline across experiments. Canonical JSON bytes are a result-size proxy, not HTTP/network bytes.

At the largest tier, ownership member query's server EXPLAIN time falls16.237ms→0.006ms and shared hit blocks8,245→4 with the team-cover index. The member/team alternative also reaches4 hit blocks and0.006ms server time; its client median0.379ms versus0.423ms is too small a difference for a decisive choice on five sequential warm samples. Any-member lookup similarly improves16.134ms→0.368ms client median with team-cover. These are fixture-specific gains, not predicted production speedups.

## Supported decisions

- **Support a separate deployment-informed evaluation of one covering ownership index:** `(leagueId,sportTeamId) INCLUDE(memberId,acquiredWeek,droppedWeek)` targets both measured point-ownership variants. Member-first alternative also helps; unmeasured member-roster/conference scans could influence final choice. Do not add both based on this experiment. Each candidate is41,123,840bytes (39.2MiB) at800,000 slots, about24.4% of baseline total slot relation size168,755,200bytes. Warm build time about95–100ms here; ongoing write, WAL, vacuum, concurrency and production build cost unmeasured. The existing GiST integrity index stays necessary; a covering index does not replace its exclusion constraint.
- **No isolated reverse-member index recommendation from this baseline.** Sparse-user own-league lookup still costs33.4ms after indexing versus34.4ms baseline; the global WeeklyTeamScore aggregate remains substantial despite returning one league. Inspect scoped aggregation/query work under later measurement/refactoring rather than assuming an extra membership index fixes the endpoint. Hot-user5000-row responses also carry unavoidable fetch/serialization work. No SQL rewrite or pagination introduced.
- **Do not drop the observed DraftPick overlap.** Catalog keys/method/opclass/predicate/included columns match between draftpick_league_overall_idx and its unique counterpart, but uniqueness/constraint ownership differ. This identifies a possible redundant lookup structure in the fixture, not deployment usage/dependency verification or permission to drop an index.

No migration was generated or applied to deployment. Candidate indexes existed only temporarily in owned fixture databases and were removed after each comparison.

## Verification, boundaries and followups

Five isolated runner tests pass (unmarked/nonlocal/unowned refusal, owned failure cleanup, actual SQL capture/NULL semantics, fixture binds and equivalence). The first native run exposed a fixture JSON-literal bind issue; a failing regression reproduced it and JSON construction was fixed. Three native tiers subsequently pass. All expected row counts/equivalence/five-sample counts independently checked from the artifact; zero leftover MOD017 databases recorded before container cleanup.

Unavailable: actual traffic/selectivity/cardinality, deployed index/RLS/grant/role facts, production latency and physical cache state, ongoing write/storage/WAL contention costs, full Supabase behavior and hosted plans. Other matrix families (games, transaction lists, team/conference lookup, scorer queries) remain separate MOD017 followups. MOD018/020/021 timing/order/batching changes retain separate decisions. This bounded investigation does not close all performance cards.

Final review: no Critical/Important findings. Reviewer independently passed5 tests and verified all102 captured SQL/parameter/count/sample/fingerprint comparisons and report arithmetic. Two deferred runner-hardening minors: future failure should save explicit failure/cleanup status rather than retaining a priorPASS/RUNNING artifact; reusable runner should assert expected query counts itself, rather than rely on the independent artifact check used here. Future runs must inspect process status and timestamps.

Final cleanup independently performed by author: database count0, ownership labels/no persistent mounts verified, exact taskcontainer removed, remaining taskcontainers0. Installed Docker and image cache retained. [Closeout evidence/decisions](evidence/mod-017-query-baselines-summary-2026-11-11.json). Work remains uncommitted/undeployed.
