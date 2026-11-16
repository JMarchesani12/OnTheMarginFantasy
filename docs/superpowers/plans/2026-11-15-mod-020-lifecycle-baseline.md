# MOD020 Read-triggered Lifecycle Baseline Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans, inline audit-only continuation.

**Goal:** Measure real global lifecycle work inside scoped league reads.
**Architecture:** Native services, ten-group status model, callback/SQL counters, independent all-league state/timestamp sets and scoped projections.
**Tech Stack:** Python/SQLAlchemy/psycopg2/cachedlocalPostgreSQL17.6.
**Spec:** docs/superpowers/specs/2026-11-15-mod-020-lifecycle-baseline-design.md
## Global Constraints
Optimization deferred, no app/query/statuspolicy/index/deploy/commit change. Fixedmarkedloopback/UUIDowned fixtures only, preserve uncommitted MOD022 work.
## Review Focus
- Real lifecycle callback once/read before actual reader-scoped query, denied/missing target included.
- Ten-group state model/phase rowcounts/timestamp-touched IDs independent and exact.
- Ended live draft group finalstatus stable but repeatedwrites measured without changing policy.
- Returned business projection only; no full contract/JWT/HTTP/timezone-boundary claim.
- Instrumentation/commits/reset/convergence timing boundaries, stale seed facts, failure/provenance/cleanup accurate.
### Task1
- [x] RED model/count/projection/classification/failure tests, native runner GREEN.
### Task2
- [x] Three tiers/fourcalls/twomodes/sixruns=24records/144reads, verify results/counts/hash/cleanup.
### Task3
- [x] Report/status/evidence, fresh review/material fix pass asneeded, keep uncommitted.
