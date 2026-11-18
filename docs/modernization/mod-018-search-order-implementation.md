# MOD018 stable league-search ordering — 2026-11-16

Implemented the first post-audit batch: public league search now orders by `similarity(l.name,:q) DESC, l.name ASC, l.id ASC`. League ID resolves only the remaining ties. Result fields, commissioner privacy, visibility/sport filters, routes, query normalization, server limits/offset ceiling and frontend page sizes remain unchanged. No index/schema/cursor/pagination-contract or deployment change.

## Before and after

The new routed/query regression failed against actual SQL missing the final key; SQLite's incidental tied order was not accepted as PostgreSQL proof. A separate real PostgreSQL contract driver ran current repository/service reads across page sizes6(Home),20(helper default),50(server maximum), sports all/1/2 and two owned heap layouts.

[Native RED artifact](evidence/mod-018-search-order-5cb48272ee60490d942e4715085ef2d2.json) records FAILED/verified cleanup:17of18ordered walks and9terminal/boundary checks failed. Original-layout six-row all-sport walk repeated57occurrences and omitted57matches; fifty-row walk reproduced the earlier five/five issue. Three mixed-name cases already passed.

[Current manifest](evidence/mod-018-search-order-current-2026-11-16.json) now points to [native GREEN artifact](evidence/mod-018-search-order-344e5d587b2746d091c2721b672d47ab.json): all18walks,90boundary/missing/short-query checks and3mixed-name cases pass. Every expected ID appears exactly once in ascending tie order for each scope/layout/page size. Full returned fields and per-page hashes independently checked against fixture-derived rows; private/nonmatching leagues excluded. Mixed-name fixtures preserve relevance first, name second, ID last.

The fixture is unchanged between equivalent walks within each layout; no concurrent pagination guarantee is claimed. OFFSET pages can still shift if rows are inserted/deleted/renamed between requests. No large-list cursor or complete-enumeration contract is introduced, and existing offset10,000 ceiling remains.

## Verification and evidence hygiene

- Focused public search5/5, complete guarded backend782/782, measurement helpers52/52 pass.
- Native1000-league public-search fixture uses actual PostgreSQL17.6/schema001+MOD006/008/010.13recorded input hashes, exact SQL,18walk ID sets/page payloads,90boundary results and3mixed-name signatures verified.
- Audit ID probe is now idempotent when production SQL already has the tie key. Future audit output explicitly labels the no-op with probe_adds_order_key/id_probe_is_noop; old “ID absent” assertions were updated to the intended contract, not suppressed. Historical raw baseline/RED reports remain unchanged.
- No frontend source changed; no frontend test/build/browser rerun claimed. Native service checks cover its actual six-row page size; current routed API contract is covered by isolated tests. No new latency/production speedup claim; original audit already evaluated this exact extra-key probe at larger sizes.
- User-staged planning index was checksum-verified unchanged. No commit/push/deploy performed.

Owned database count0 observed after both runs; exact labeled loopback container removed with no persistent mounts, remaining search-order taskcontainers0. Docker/image cache retained. No configured DSN/provider/app/jobs accessed. [Closeout evidence](evidence/mod-018-search-order-summary-2026-11-16.json).

MOD018's equal-name ordering finding is resolved in application/local native scope. Other paging/real workload/production/role/RLS/concurrent-mutation decisions remain separate. Home tabs and tier-cache fixes have not started in this batch.

## Final review

Fresh scoped review found no critical/important findings, independently verified 13 source hashes, 18 walks, 664 full-payload page signatures, 90 boundaries and three mixed cases, and reran the five routed tests. Deferred minor: future measurement descriptions still say optimization deferred/fixture-only despite accurate no-op flags (`measure_mod018_search.py:128`); update that wording when next touching the runner, preserving historical artifacts.

Reviewer did not independently execute native services or judge cleanup, production performance/deployment, concurrent pagination or other roadmap tasks. Author observed the recorded native runs/cleanup; no claim beyond the local static contract is made.
