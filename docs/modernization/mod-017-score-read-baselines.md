# MOD017 stored-score reads — 2026-11-15

Audit only; actual performance implementation remains deferred until audit completion. No application SQL/index/tuning/scoring/auth or deployment change. [Current manifest](evidence/mod-017-scores-current-2026-11-15.json) references [raw evidence](evidence/mod-017-scores-aa7989a288fe4127b78a1f6907d8d8ad.json). Previous H2H deliverables and prior runners/evidence are preserved.

## Scope and fixture

Capture actual ScoringRepository.weekly_points, season_points and weekly_ranks. Compile expanding week-list bindings using SQLAlchemy's own parameterized compiler, including empty/duplicate input, rather than interpolating values. Run actual ScoringReadService.get_weekly_points_for_job for weekly cases; this trusted job-read method normalizes weeks and opens a pooled connection only for nonempty selections. It does not calculate/write scores or measure authenticated HTTP/full scoring/job orchestration.

Use marked-loopback PostgreSQL17.6, baseline001 + exact MOD006/008/010, without platform/RLS/deployed-role/schema equivalence. Three tiers100/1000/5000 leagues initially contain9600/96000/480000 member-week scores. Delete only the target league's member8 scores (12rows), retaining the member. Final scorecounts9588/95988/479988. Each league has8members,12scoredweeks and13calendarweeks; target has7scored members. Existing base fixture ownership/league data unchanged. No game/provider setup.

Fifteen cases: weekly all12weeks/one/sparse/duplicate/empty/unscored/missing league; current/missing season totals; ranks all/subset/empty/unscored/foreign-week/missing league. Full independent expectations include dates/IDs/names/points/ranks/totals. Weekly results84/7/21/7rows, season8rows including zero for retained member8, ranks7 or1; other selected cases empty. Rank subset includes an unscored member and a foreign member. Unique ranks only; equal-rank order is unmeasured. Unordered season/rank results are sorted by memberID only for evidence comparison and observed order is recorded. Application ordering remains unchanged.

Season SUM(bigint) is PostgreSQLnumeric/Python Decimal; canonical evidence serializes these totals as strings (including zero). This is an evidence fingerprint convention, not an HTTP representation change. Largest weekly response is84rows/16,546 canonical JSON bytes; bytes are a representation-size proxy, not wire/heap/HTTP measurements. Larger per-league member/week cardinalities remain unmeasured; no hard league limit is inferred from8-member fixtures.

## Method and results

Baseline versus separate weekly covering index, season covering index and both. Candidates exist only in owned UUID databases, dropped between configurations. One warmup+EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON)+five SQL execute/fetch samples; actual job reader one warmup+five samples.180SQL and84service records preserve independently expected complete output. All SQL/params,9 source hashes, settings, sample distributions and build/storage facts retained. SQL times stop before dict conversion; job-reader times include normalization, pooled connection and row mapping. Do not subtract independent medians to infer overhead. Fixed-order warm samples, no statistical confidence/cold-cache/concurrency/write/WAL/production latency claim.

Client medians in milliseconds:

| Score rows | Full weekly baseline → both | Season total baseline → both | All ranks baseline → both |
| ---: | ---: | ---: | ---: |
|9,588|0.733 →0.739|0.347 →0.383|0.235 →0.323|
|95,988|2.349 →2.457|0.384 →0.377|0.318 →0.344|
|479,988|0.853 →0.944|0.392 →0.397|0.334 →0.327|

Largest full-weekly separate candidates: weekly0.918ms, season1.005ms. Actual full-weekly job reader1.630ms baseline and1.630ms both; separate weekly1.476ms, season1.500ms. Medium timings exceed largest timings for some cases; this variability is preserved, not a monotonic scaling or speedup claim.

Existing WeeklyTeamScore_identity_key already scopes selected league reads. Largest baseline full-weekly plan reads84scores, then joins Week and LeagueMember by their primary keys; server0.113ms. Season baseline0.045ms and rank baseline0.006ms. Extra indexes change selected paths (rank can use weekly index-only, season can use member index-only), but do not yield meaningful consistent client gains in this fixture.

Largest candidate definitions and storage:

- Weekly `(leagueId,weekId,rank) INCLUDE(memberId,pointsAwarded,pointDifferential)`:32,448,512bytes (30.9MiB), observed separate build96ms.
- Season `(leagueId,memberId) INCLUDE(pointsAwarded)`:19,513,344bytes (18.6MiB), separate build51ms.
- Both51,961,856bytes (49.6MiB), observed individual builds84/51ms. Baseline total WeeklyTeamScore relation76,095,488bytes; candidate storage is substantial relative to already small scoped reads. Build times do not establish ongoing write/lock/vacuum/WAL cost or safe production builds.

**No added score index is supported by these measurements.** Preserve this no-change conclusion for the final optimization plan; do not add indexes merely because their column order resembles the filters. This does not invalidate earlier own-league global aggregation findings, nor prove full scoring is fast. Full scoring query counts, tiebreak/postseason/bonus paths, larger member counts and ingestion remain separate.

## Verification and cleanup

Five new runner tests failed before module creation, then29 total measurement tests pass. All3 native tiers/180SQL/84service full signatures, expected counts, SQL/params, five samples/medians and9 provenance hashes independently checked by author. Empty job selection opens no connection in unit coverage. Unique RUNNING/PASS/FAILED artifacts, stale-PASS replacement before provenance/connection, UUID-owned cleanup and cleanup-gated PASS reused.

Zero task databases observed; exact labeled loopback container removed, no persistent mounts, remaining score taskcontainers0. Docker/cache retained. No configured DSN/provider/application/jobs started; trusted read method exercised directly only. Work uncommitted/undeployed. [Closeout evidence](evidence/mod-017-scores-summary-2026-11-15.json).

Remaining limits: synthetic unique ranks/fixed8-member/12-week distributions, production traffic/schema/roles/RLS, cold-cache/cache pressure, concurrent writers and full scorer/ingestion behavior. MOD017 and remaining cards stay open; all actual optimization implementation remains deferred until audit completion.

Independent final review: Critical0/Important0/Minor0. Reviewer passed29 units, reconstructed all expected rows and verified180SQL/84service signatures, captured bindings, five-sample statistics,9source hashes/raw digest/manifest, recorded cleanup, report figures and selected plan paths. Reviewer supports the no-added-score-index conclusion. Live removal remains direct author evidence; H2H was separately reviewed. Production/RLS/auth/HTTP/full scoring/postseason/ingestion, equal-rank order, larger per-league cardinalities, cold caches/concurrent writes/maintenance costs remain outside this claim.
