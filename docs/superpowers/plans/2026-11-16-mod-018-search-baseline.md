# MOD018 Search Measurement Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans, inline audit-only continuation.

**Goal:** Measure search retrieval and tied-page stability without app optimization.
**Architecture:** Actual query/service, independent fixture IDs/payloads, private ID-order probe and owned heap-layout experiment.
**Tech Stack:** Python/SQLAlchemy/psycopg2/cachedlocalPostgreSQL17.6.
**Spec:** docs/superpowers/specs/2026-11-16-mod-018-search-baseline-design.md
## Global Constraints
Optimization deferred. No app query/index/route/ranking/contract/deploy/commit change. Fixedmarkedloopback/UUID-owned fixtures only. Public sampled limit/offset bounds respected.
## Review Focus
- Current ties may vary; record rather than falsely requiring deterministic fingerprints.
- Full payload eligibility/private/sport isolation and independent ID-probe order/counts correct.
- Heap reorder/indexdrop changes only fixture, index catalogs comparable.
- Smallwalkcoverage distinguished from sampled large offsets and HTTP cap/consumer semantics.
- Actualservice shortquery noDB, five samples/timing/provenance/failure/cleanup accurate.
### Task1
- [x] RED capture/expectedpayload/offset/shortquery/failure tests, implement runner GREEN.
### Task2
- [x] Three tiers/72SQL/42service,smallwalk/layout/provenancechecks; ownedcleanup.
### Task3
- [x] Bounded report/status/evidence, freshreview/materialfixpass ifrequired, keep uncommitted.
