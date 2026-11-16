# MOD017 head-to-head baseline — 2026-11-15

Audit measurements only; all actual optimizations remain deferred until audit completion. No application SQL/index/tuning/scoring or deployment change. [Current manifest](evidence/mod-017-h2h-current-2026-11-15.json) points to [successful raw evidence](evidence/mod-017-h2h-a8b3bd51fbe74c3091a1cde8f18eb514.json). Earlier evidence/runners remain unchanged.

## Workload and correctness

Capture actual ScheduleReadRepository.head_to_head_games and execute actual ScheduleReadService.get_head_to_head_games with a supplied connection. The service only maps query rows; this is not a full scorer/job/HTTP/auth/connection-acquisition measurement. Use marked-loopback PostgreSQL17.6, baseline001 and exact MOD006/008/010 + timeTBD migrations. No RLS/Supabase/deployed-schema equivalence.

| Leagues | Ownership history rows | Seasons | Total games | Current-season games |
| ---: | ---: | ---: | ---: | ---: |
|100|16,000|20|10,000|500|
|1,000|160,000|50|100,000|2,000|
|5,000|800,000|100|500,000|5,000|

512 sport teams, one sport. Each eight-team block pairs its first four against its next four, in both home/away orientations. Ten current-season games anchor week starts/ends and one-microsecond exclusions. One target-league team1 interval [7,10) moves from memberA toC; earlier/later intervals retain A. Fixture construction updates existing game rows, leaving dead-tuple/free-space effects; largest GameResult total relation250,019,840bytes reflects that construction, not a production storage estimate or a directly comparable prior-game-run layout. No VACUUM/cold-cache/write-concurrency claim.

Eleven cases cover currentAB/swappedBA/currentAC, week6AB before transfer, week7AB at acquisition, week9CB during transfer, week10AB at return, unknown member, missing week/league and same member. Independently enumerate **every expected field** (IDs/date/names/scores/TBD/ownership flags), preserve date/external-ID order and compare complete signatures, not just counts or baseline-to-candidate equivalence. Current rows2/5/7; before3/8/8; acquired0/0/4; during2/2/3; returned2/7/11. Other selected empty cases remain empty. Fixtures' adjacent weeks share endpoint instants; checks preserve current inclusive BETWEEN behavior, without changing calendar policy.

## Method and results

Four configurations: baseline, season/date game index, ownership index, both indexes. Indexes exist only in each owned UUID database and are dropped between configurations. Per SQL case: warm-up, EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON), five execute/fetch samples; per actual service case: warm-up plus five samples.132 SQL and132 service records match independent expected full results. Input SQL/params,13 source hashes, raw plans/settings, sample distributions, build/storage and cleanup are recorded.

Current-week AB SQL client median milliseconds:

| Games / slots | Baseline | Game date | Ownership | Both |
| --- | ---: | ---: | ---: | ---: |
|10,000 /16,000|1.644|1.501|0.810|0.732|
|100,000 /160,000|9.203|9.185|1.154|0.821|
|500,000 /800,000|36.953|35.949|1.652|0.746|

Largest service medians are36.149/37.346/1.492/0.908ms respectively. SQL timing stops before Python dict conversion; service timing includes row mapping and supplied-connection query execution. Separate warm samples can vary; service/SQL medians must not be subtracted to infer mapping overhead. No randomization/statistical confidence, HTTP latency or production latency claim.

Largest current-query server plans explain the difference:

- Baseline scans ownership history separately for both members and filters5,000 current-season games to7. Server37.388ms.
- Game-date candidate narrows candidate games to442 (7 returned,435 filtered), but ownership scans remain. Server34.604ms.
- Ownership covering index produces four active rows per member, filtering15/16 expired history rows; game access still filters4,993 current-season rows. Server1.094ms.
- Both use selective ownership access and date-limited games; server0.146ms, game heap node126 shared hits. None of these selected plans includes JIT. Buffer/node times are nested/parallel observations, not independent wall-time sums. Warm-up does not prove a particular physical cache state.

Largest index sizes: game `(sportSeasonId,date,externalGameId)`29,548,544bytes (28.2MiB); ownership `(leagueId,memberId,sportTeamId) INCLUDE(acquiredWeek,droppedWeek)`41,123,840bytes (39.2MiB); both70,672,384bytes (67.4MiB). Separate observed builds356/198ms; combined builds372/183ms. These are synthetic warm build observations, not ongoing write/WAL/lock/build-rollout estimates.

The ownership candidate accounts for most improvement here; date indexing has a useful additional effect once that bottleneck is removed. Preserve both hypotheses for the final workload-informed index plan, alongside earlier ownership/game/count evidence. This does not settle overlapping index choices, production workload frequency, tradeoffs or rollout. No query rewrite/batching/pagination/production index was implemented.

## Verification, cleanup and limits

Five new tests failed before runner creation. Native setup then exposed raw-driver percent/modulo formatting in the synthetic update; a sixth regression test failed before fixing it through SQLAlchemy text compilation. All24 measurement tests pass. [Failed attempt](evidence/mod-017-h2h-c1dffb62ca7043fe9a2f6865d137fd35.json) retains FAILED/verified cleanup; successful rerun uses a separate artifact. All3 tiers,132 SQL/132 service complete expected signatures/sample counts/medians/captured parameters and13 provenance hashes independently checked by author.

Zero task databases verified; exact labeled loopback container removed, no persistent mounts, remaining H2H taskcontainers0. Docker/image cache retained. No configured DSN/provider/app/jobs accessed. Work uncommitted/undeployed. [Closeout evidence](evidence/mod-017-h2h-summary-2026-11-15.json).

Unmeasured: real sports/date/team skew, ties/null scores/team IDs, other sports, ownership transfers beyond this bounded interval, production schema/RLS/roles/provider/cache/concurrency/writes/WAL, full member/season scoring and ingestion pipelines. MOD017 and remaining performance cards stay open; actual optimization implementation remains deferred until audit ends.

Independent final review: Critical0/Important0/Minor0. Reviewer passed24 units and separately reconstructed all132 SQL/132 service expected rows, ownership intervals/pairings/dates/order/flags, verified13 hashes/raw digest/captured SQL/parameters/five-sample statistics/report figures/index/build costs. No edits or native services accessed. Live cleanup remains direct author evidence; historical RED remains ledger evidence corroborated by the present GREEN suite and preserved failed artifact. Production/RLS/concurrency/write/rollout and full scoring/ingestion remain outside this scope.
