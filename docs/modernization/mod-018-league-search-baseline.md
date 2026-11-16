# MOD018 league-search baseline — 2026-11-16

Audit measurements only; optimizations remain deferred until audit completion. No application query/index/ranking/route/page contract or deployment changed. [Current manifest](evidence/mod-018-search-current-2026-11-16.json) references [raw evidence](evidence/mod-018-search-f19d74870f2c42f0a44870aa8dfe18c9.json).

## Finding: tied pages repeat and omit leagues

Actual search orders by similarity descending and name ascending, without a final unique key. In an unchanged1,000-league fixture with700 public equal-name matches, a14-page walk returned700 rows but only695 distinct IDs. League1 appeared six times (five duplicate occurrences), while IDs72/143/214/285/356 were omitted. After a private heap reorder, ID997 appeared six times and five different IDs were omitted. This occurred without concurrent inserts/deletes.

A **fixture-only** variant appending `l.id ASC` returned all700 matches exactly once, in independent expected ID order, in both layouts. Current first-page IDs changed after heap reorder at all three sizes; the ID-ordered probe stayed identical. Current fingerprints within the five repeated samples are recorded rather than assumed stable. Equal sort keys do not guarantee a total order even when several repeated calls happen to agree.

Source inspection confirms Home uses offset paging (`page * SEARCH_LIMIT`, currently6) and replaces each displayed page. The native reproduction uses50-row pages, not Home’s6-row setting; no browser/6-row reproduction is claimed. The non-total query order is relevant to that consumer, but the exact missing/repeated IDs are fixture/page-size-specific.

This supports a narrow ordering correction in the final implementation phase. It does not justify shipping a cursor API, query pushdown, new index or response-shape change now. Existing search code remains unchanged; MOD018 stabilization/implementation is still open.

## Scope and fixture

Capture unchanged LeagueReadRepository.search_discoverable and execute actual LeagueReadService.search_public. Native marked-loopback PostgreSQL17.6/schema001 + exact MOD006/008/010; no platform/RLS/deployed-role equivalence.

Search-only fixtures1,000/10,000/100,000 leagues, two sports, one commissioner. Groups(id−1)%10:0..6 public “Audit League”;7“Different League”;8“Other League”;9private “Audit League”. Sport2 whenID divisible by7, otherwise sport1. Thus700/7,000/70,000 equal-name public matches. Private and sport filters independently checked. Every returned field is independently constructed from ID/name/sport/visibility/commissioner/status; no commissioner email is exposed. Stored numPlayers8 is a projection value; no member/score/slot rows are seeded or member-growth capacity inferred. No lifecycle sync is invoked by this search service.

All matching names are identical and have identical similarity to the query. This deliberately isolates tied pagination; it does not measure different relevance scores, real name distributions, wildcard behavior, abbreviations or every search consumer. Earlier [team-lookup evidence](mod-017-team-lookup-baselines.md) remains separate and no team ranking/pushdown changed.

Six SQL cases: all first page, middle offset capped10,000, max offset10,000, sport1 first page, sport2 first page, absent query. Limit50 and sampled offsets respect the current HTTP bounds. Current SQL and ID-order probe run before/after owned heap reordering:72SQL records. Actual service adds a short query:42service records. Each record has a warmup and five samples; short query performs zero database calls, other service calls one. Projection/within-page uniqueness/eligibility/count checked for every result; exact ID-probe ordering checked independently. Current tied order differences are observations, not runner failures.

Heap probe: create temporary descending-ID index, CLUSTER only owned fixture League, drop index, ANALYZE. Before/after schema index definitions match; physical index bytes/layout/cache may differ. No production index/heap operation or planner-setting change. This is not a storage/maintenance/realistic-physical-cache experiment.

## Retrieval cost and sizes

Original-layout SQL execute/fetch medians in milliseconds:

| Leagues / matching rows | Current first page | Current offset10,000 | ID probe first page | ID probe offset10,000 |
| --- | ---: | ---: | ---: | ---: |
|1,000 /700|1.31|1.18 (empty)|1.24|1.26 (empty)|
|10,000 /7,000|8.58|8.25 (empty)|8.46|8.61 (empty)|
|100,000 /70,000|46.57|51.91|44.41|52.21|

At100,000 leagues, reordered-layout current first/deep medians43.58/51.06ms and ID-probe55.06/66.40ms. The tie key is a correctness hypothesis, not a proven speedup. Actual service first-page medians2.340/9.789/45.372ms in original layouts. Timings stop before SQL row-to-dict conversion; service includes transaction/acquisition/mapping and lightweight query-count instrumentation. Do not subtract separate medians to infer precise overhead. Fixed-order warm samples, no statistical confidence/HTTP/production latency claim.

Original first-page50rows serialize to9,044 canonical JSON bytes at each tier; this is a size proxy, not wire/heap/HTTP traffic. Pages remain capped50; result count alone hides match scanning and sorting. Largest original current first-page EXPLAIN server46.698ms uses parallel scanning and top-N sort; offset10,000 server55.059ms includes an external-merge sort (reported node disk space2,872KiB). Plan node rows/timings are parallel/nested observations, not independent totals to sum. No cold-cache/global tuning/index-build/write-cost claim.

Only the small fixture was fully walked (current/probe, two layouts =4walks). Larger tiers sample offsets; no full large traversal claimed. At70,000 matches, the existing HTTP offset ceiling10,000 and limit50 cannot enumerate every match using that endpoint's offset interface. Whether complete enumeration or cursors are needed is a separate consumer/resource-bound decision; do not silently change that contract or page complete draft/roster snapshots. No cursor/paging implementation is justified solely by this bounded latency comparison.

## Verification, cleanup and next work

Five initial tests failed before runner creation; all51 measurement tests pass. Author independently checked72SQL/42service records,4small walks, all projected signatures/expected counts/IDs/visibility/sport filters, five samples/medians/SQL parameters/catalog equivalence and12 source hashes. ID probe exact output stable across layouts. Current duplicate/missing results preserved as findings, not hidden by normalizing order.

Zero owned databases observed; exact labeled loopback container removed, no persistent mounts, remaining search taskcontainers0. Docker/image cache retained. No configured DSN/provider/app/HTTP/browser/jobs accessed. Work uncommitted/undeployed. [Closeout evidence](evidence/mod-018-search-summary-2026-11-16.json).

MOD018's bounded search measurement is complete, with stable tie ordering left for the final implementation phase. Real relevance distributions, concurrent page mutations, other large lists, production/RLS/roles/traffic and large complete traversal remain unmeasured. MOD036 rendering/accessibility/tier-tool audit remains separate. All actual optimizations remain deferred.

Independent final review: Critical0/Important0/Minor0. Reviewer passed51units and verified72SQL/42service/foursmallwalks/five samples/medians/counts/complete expected payload signatures/SQLcaptures,12source hashes/raw digest/index definitions/plan/report figures. Current repeated/missing IDs and private ID-probe complete order independently confirmed; app unchanged. Later source-only consumer annotation independently checked by author: Home SEARCH_LIMIT6, helper default20; native50-row reproduction remains separate.

Live cleanup/RED/timing reproduction remain author evidence; production/other relevance distributions/concurrent mutations/large complete traversal are outside scope.
