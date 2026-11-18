# MOD017 Head-to-head Measurement Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans, continued user-authorized inline audit work.

**Goal:** Measure head-to-head reads and actual service mapping, without optimizing application code.
**Architecture:** Reuse guarded fixture/method helpers, isolated transfer/pair fixture, independent full expected rows, temporary separate/combined indexes.
**Tech Stack:** Python/SQLAlchemy/psycopg2/cached PostgreSQL17.6.
**Spec:** docs/superpowers/specs/2026-11-15-mod-017-head-to-head-design.md
## Global Constraints
Audit only; fixed marked loopback, UUID-owned DBs, preserve prior artifacts. No application/production query/index/tuning/deploy/commit change. Optimization deferred until audit ends.
## Review Focus
- Complete flag/name/date/order values independently correct for both orientations and swapped members.
- Inclusive date endpoints and half-open [7,10) transfer, including return.
- Same/unknown member and missing week/league empty results.
- Failure replaces stale PASS before provenance/connection and verifies owned cleanup.
- Service mapping measurement excludes scoring/HTTP/engine acquisition; combined index cost and warm timing limits explicit.
### Task 1 — Runner and tests
- [x] Write capture/full expectations/boundary/transfer/validator/failure tests; watch RED before module exists.
- [x] Implement scripts/modernization/measure_mod017_h2h.py; combined unit suite GREEN.
### Task 2 — Native evidence
- [x] Run three disposable PostgreSQL tiers; verify132 SQL/132 service records and source hashes, exact owned cleanup.
### Task 3 — Closeout
- [x] Write bounded report/evidence/status. Fresh read-only review, grade/fix material issues once with RED→GREEN/full checks; defer minors. Keep uncommitted.
