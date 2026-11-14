# MOD-017: isolated own-league and ownership query baselines

## Intent and chosen approach

The user selected disposable local PostgreSQL measurements at several fixture sizes, authorizing Docker startup if needed, with no index rollout. Measure actual repository queries before proposing an optimization. Production request volume, cardinality, latency and deployment index usage are unknown; these are synthetic workload baselines, not proof of the highest-volume production path or a measured production slowdown.

Choose a guarded standalone measurement script and reproducible synthetic fixtures. Read-only production profiling needs access, data/privacy and workload permissions outside this task. SQL/source inspection alone cannot establish runtime or index benefit. No application behavior, query semantics, deployment schema, hosted metadata, RLS or provider changes.

## Query scope

Capture SQL and bound parameters from actual LeagueReadRepository.own_leagues and ownership_reads.team_ownership_rows calls, using a recording connection and then executing the captured statement unchanged. Do not maintain hand-copied production SQL or import configured database/app/job modules. Own-league stages: all, active, completed. Ownership: league-wide omitted member and explicit member variants, preserving explicit NULL member semantics, half-open acquired/dropped week predicate and LIMIT1. Include found/not-found, current/historical week and representative selective/nonselective/skewed synthetic parameter sets where meaningful.

Own-league measurement excludes lifecycle synchronization writes by calling the repository directly; report that an end-to-end application request can do additional work. The global WeeklyTeamScore aggregate is part of the actual query and must remain intact. Do not rewrite/batch/paginate it during this task; identify dominating plan nodes for later MOD-018/020/021 work if supported.

## Fixture and schema provenance

Use deterministic synthetic leagues, users, memberships, weeks, scores and team-slot histories. Proposed tiers:100/1000/5000 leagues,8 members per league,12 scored weeks and4 scoring teams per member/week; corresponding score counts38,400/384,000/1,920,000. Ownership histories have five nonoverlapping intervals for each of four teams per member, including dropped and current slots. Adjust only if local resource limits demand it, recording the exact change and reason.

Keep user selectivity distinct from total population (sparse memberships plus a declared hot user), active/completed league distribution and historical ownership parameters explicit. Seed fixed payload/settings values and dates relative to one captured measurement clock so repeated comparisons return the same rows. Report generated and observed table counts, widths/distributions, parameter sets and all query result cardinalities; no claim these match actual customer usage.

Derive schema/index definitions from the versioned baseline and applicable checked-in integrity migrations, with exact provenance/hashes/catalog output. A minimal synthetic auth prerequisite is acceptable; it is not a Supabase deployment. If building a narrower fixture, preserve measured tables' column types and relevant constraints/indexes and document every omission/physical-layout limitation rather than labeling it production equivalent. Do not silently use the old database-audit snapshot as current deployment truth. No configured database connection or metadata inspection.

## Measurements and candidate experiments

Record server version/settings relevant to the plan, schema/index catalogs, ANALYZE statistics context, EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON), planning/execution time, actual/estimated rows, loops and buffer hits/reads/temp activity. Use bound parameters and normal planner choices; do not force index scans or change SQL to make a candidate look useful. Distinguish warm repeated runs from cold-cache claims; record one warm-up and five measured samples, with median and range. Keep raw plans as well as a compact comparison. Set finite connection/statement/lock budgets and record resource failures as unavailable evidence rather than manufacturing results.

Measure result payload bytes using a documented canonical JSON serialization of actual repository rows and ordered-result fingerprints; bytes are a synthetic serialized result proxy, not full HTTP/network size. Ownership LIMIT1 values and own-league ordered rows must remain equivalent before/after each experiment. Measure complete execution separately from EXPLAIN profiling and do not present either as production endpoint latency.

Compare fixture baseline indexes with a small explicit candidate set from the matrix: LeagueMember(userId,leagueId) reverse lookup and LeagueTeamSlot league/team and league/member/team variants with interval columns considered only when plans justify them. Candidate CREATE/DROP INDEX is allowed only inside this run's disposable fixture database for A/B measurement; it is not a checked-in migration or rollout. Record build time, index size and total relation size as storage/build proxies. No synthetic insert benchmark is necessary unless an index recommendation depends on its unmeasured write cost; otherwise state ongoing write overhead as unmeasured.

Inspect structural index duplication using catalog key order/expressions/predicate/uniqueness/method/included columns and dependency context, never names alone. Report candidates/uncertainties; do not remove baseline indexes or claim deployment redundancy/usage from fixture metadata. If an experiment shows no benefit or the aggregate dominates, a no-index-change conclusion is valid. Any actual migration requires a separate reviewed task with deployment provenance and tradeoffs; none is generated/applied automatically here.

## Isolation and cleanup

Reuse existing local PostgreSQL tooling and cached image when available; start installed Docker as authorized. No new infrastructure/dependency installation. Create a task-owned loopback-only, labeled, disposable PostgreSQL container with ephemeral storage if needed; never attach application volumes. Verify a synthetic-only server marker before creating a UUID-named database. Accept no configured DSN or environment credentials; use fixed local test connection settings and refuse an unmarked server. Never stop/remove unrelated containers or databases.

Own and clean up only the UUID database and container created by this run, including on failure; verify database removal and container disposal. Do not use destructive schema cleanup against a pre-existing database. Existing image cache may remain. If Docker/runtime resources are unavailable, complete unaffected script/design work and report precise unavailable native evidence; do not substitute SQLite plans for PostgreSQL measurements.

## Verification and deliverables

Add meaningful script tests for refusal of unmarked/nonlocal targets, captured-query identity/parameters, fixture cardinality/equivalence checks and cleanup ownership/failure handling. Tests must not start configured app/jobs/providers. Reproduce a failing test before implementation, then run isolated script tests, native measurements and diff checks. Existing backend tests appropriate to touched measurement infrastructure only; production query code stays unchanged.

Deliver the reproducible runner/fixture, sanitized plan artifacts and a concise baseline report containing cardinality/schema provenance, sampling method, parameterized plans, before/after outputs/buffer/runtime/index-size comparisons and supported/no-change recommendations. List unavailable production/role/RLS/traffic/cold-cache/write-cost evidence explicitly. Obtain a fresh final code/evidence review, fix material findings with reproducing regressions, update MOD-017 only for this bounded two-family baseline and retain wider query families as followups. Leave work uncommitted/undeployed. No production optimization claim or blanket index addition/drop.
