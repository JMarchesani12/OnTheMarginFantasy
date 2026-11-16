# MOD022 Ingestion Baseline Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans; inline audit-only continuation.

**Goal:** Measure repeated league ingestion versus existing season helper without changing behavior.
**Architecture:** Actual service/repositories/parser, injected canned fetch only, SQL hooks, independent counts/committed-game checks.
**Tech Stack:** Python/SQLAlchemy/psycopg2/cached PostgreSQL17.6.
**Spec:** docs/superpowers/specs/2026-11-15-mod-022-ingestion-baseline-design.md
## Global Constraints
Optimizations/retries deferred. No network/configured DSN/cron/jobgate/checkpoint/bootstrap/app/query/index/deploy/commit change. Fixedmarkedloopback/UUIDowned fixtures only.
## Review Focus
- Only fetch transport substituted, actual parsing/mapping/validation/upserts execute.
- Existing league raw-event/nondedup versus season dedup semantics and correction IDs preserved, no implicit equivalence across conflicting duplicates.
- Provider and SQL count formulas correct, reference locks and metadata included.
- Failed group leaves prior committed games, explicit rerun succeeds without new retry policy.
- Timing/sample/provenance/failure/cleanup boundaries, no provider latency/production claim.
### Task1
- [x] RED cannedtransport/parser/count/correction/classifier/provenance tests, implement runner GREEN.
### Task2
- [x] Native1/4/16leagues *2paths *2cases *6invocations; two failure/rerun probes; outputs/counts/hashes/cleanup.
### Task3
- [x] Report/status/evidence, fresh scoped review/material fix pass if required, keep uncommitted.
