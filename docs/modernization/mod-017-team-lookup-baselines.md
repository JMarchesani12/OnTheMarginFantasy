# MOD017 team lookup and conference counts — 2026-11-13

Audit information only; performance implementation remains deferred until audit completion. No application SQL, search behavior, index, tuning or deployment changed. [Current manifest](evidence/mod-017-lookup-current-2026-11-13.json) points to the [raw artifact](evidence/mod-017-lookup-8a13987878304775afc4f9c1eeaf0404.json).

## Workload and method

Capture unchanged ScheduleReadRepository.search_teams plus shared distinct/grouped conference counts. Reuse the marked loopback PostgreSQL17.6/schema001 + MOD006/008/010 fixture, without RLS/platform/deployed-schema equivalence. Three tiers contain100/1000/5000 leagues,16k/160k/800k ownership-history rows and512/2048/8192 searchable teams;32 additional teams belong to another sport and must be excluded. Default16-team conferences, one2026 move of team1 from conference1 to2 and a2025 historical league exercise season-first membership and fallback. Historical slots retain the same owners. Unique padded names, one move, no real-world skew/ties/transfer claim.

Eleven SQL cases cover current/historical/missing-sport lookup, current/moved/historical/unknown-member/missing-league distinct counts and current/historical/null-member grouped counts. Exact independent values: member owns four teams, current conferences1/2 contain3/1; historical conference1 contains4. Grouped SQL has no ORDER BY: evidence sorts by conference ID for comparison and retains observed order; application ordering is unchanged.

One warm-up, EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON), five execute/fetch/row-conversion samples per SQL case/configuration;108 results preserve exact counts/values and complete fingerprints. Python dict conversion is included in this runner's SQL client timing, so comparisons to earlier runners' absolute timings are approximate. Candidate indexes run separately, never combined; team-name candidate applies only to lookup SQL, other two cover all11 cases.

Actual ScheduleReadService.search_teams_for_league also runs through a passthrough repository: seven query cases, four configurations, three tiers =84 service records with one warm-up and five samples each. Queries exercise `iowa st`, `du` (a Duke prefix despite the artifact case name `exact`), `univ`, a20-result prefix, a miss, a short query and historical labels. This is the application's ranking code, not a copied algorithm. Timings include transaction/row conversion/ranking and light counter/buffering instrumentation; byte serialization occurs after timing. Database fetch timings are components, not independently additive latency. No HTTP/browser/network measurement.

## Results: SQL client median ms

| Searchable teams / history slots | Lookup current: baseline → ownership index | Distinct conference1: baseline → ownership index | Group counts: baseline → ownership index |
| --- | ---: | ---: | ---: |
|512 /16,000|2.772 →2.201|2.437 →1.804|1.190 →0.813|
|2,048 /160,000|11.358 →7.007|7.496 →1.802|4.953 →1.170|
|8,192 /800,000|37.524 →25.519|16.044 →1.853|27.913 →11.399|

The ownership candidate `(leagueId,memberId,sportTeamId) INCLUDE(acquiredWeek,droppedWeek)` is41,123,840bytes (39.2MiB) at the largest tier. The distinct plan replaces ownership scanning across800k histories with four relevant rows (16 expired intervals filtered); other conference/ranking work remains. This reinforces earlier ownership evidence without proving a final combined index design or production write cost.

The team `(sportId,displayName)` candidate is425,984bytes; largest lookup median45.243ms versus37.524 baseline. It does not constrain search terms because normalization/filtering/ranking occur after retrieval. The conference-leading candidate is also425,984bytes and regresses largest distinct count16.044 →160.064ms. Its plan performs15 ownership GiST scans, each filtering about25,000 rows, with139,778 shared hits at that ownership node. Server execution154.653ms has no JIT section. A faster membership access path led to a worse join strategy here; do not recommend this index from column order alone. No planner settings were forced.

## Search retrieval versus returned results

| Teams fetched by every normal search | Canonical team-row JSON bytes | Alias service median: baseline → ownership index |
| ---: | ---: | ---: |
|512|73,739|5.363 →7.230ms|
|2,048|296,496|19.112 →13.768ms|
|8,192|1,193,580|63.822 →47.193ms|

These bytes are canonical JSON size proxies, not PostgreSQL wire traffic, Python heap or HTTP payload. Every normal query issues two reads (league context + all sport teams), including misses and one-result aliases; a prefix returns at most20. The short `i` query issues zero reads and fetches zero teams (its serialized empty list occupies2bytes). Largest baseline miss59.016ms and historical alias76.256ms show that a small returned result does not bound retrieval/ranking work. Warm sample variation, including the small-tier alias regression, is preserved; no statistical confidence or production latency claim.

Later optimization design should evaluate bounded search retrieval while preserving normalization, ranking, owner/conference context and complete-response contracts. A plain index or arbitrary SQL LIMIT is not a verified solution. No search rewrite, pagination or caching was implemented.

## Verification and limits

Four new tests failed before the runner existed, then all18 measurement tests pass. All3 native tiers,108 SQL and84 service records pass expected counts/values, five-sample checks, SQL/parameter consistency, result equivalence and input hashes. Per-run RUNNING/PASS/FAILED artifacts and UUID-owned database cleanup reused. Original runners/artifacts unchanged; no configured database/provider/app/job accessed.

Production workload/cardinality/roles/RLS/provider/schema equivalence, cold cache, concurrency, writes/WAL/vacuum and real data distributions remain unmeasured. Head-to-head/full scoring/ingestion and remaining performance cards are separate; this does not close all MOD017. All actual optimization implementation remains deferred until the audit ends.

Task-owned databases verified absent; exact labeled loopback container removed, no persistent mounts, remaining lookup taskcontainers0. Docker/image cache retained. Work uncommitted/undeployed. [Closeout evidence](evidence/mod-017-lookup-summary-2026-11-13.json).

Independent final review found Critical0/Important0 and passed18 units. Reviewer reconstructed complete expected rows (including owner labels) for all108 SQL/84 service fingerprints, verified11 source hashes/raw SHA/manifest/query captures/sample summaries/report figures, and injected connection failure to confirm FAILED/no database. Short-query no-transaction behavior checked. Deferred minors: runner does not independently assert owner label text, and the specified non-null unknown-member grouped-count case is absent (null-member case is covered). Current artifact values are correct; extend these assertions before future measurement reuse. Live cleanup remains author-observed; production/transfer/skew/tie/concurrency/write/RLS/rollout and competing-rank behavior remain outside this claim.
