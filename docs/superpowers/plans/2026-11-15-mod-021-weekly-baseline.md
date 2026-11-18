# Weekly Scoring Baseline Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans; authorized inline audit continuation.

**Goal:** Measure real weekly scorer query counts and rolled-back execution, preserving scoring behavior.
**Architecture:** Actual service/repositories/native fixtures; independent totals/ranks; scoped SQL hooks; rollback each invocation.
**Tech Stack:** Python/SQLAlchemy/psycopg2/cached PostgreSQL17.6.
**Spec:** docs/superpowers/specs/2026-11-15-mod-021-weekly-baseline-design.md
## Global Constraints
Audit only, no production/application/query/index/tuning/commit/deploy change. Optimizations deferred. Fixed marked loopback, UUIDowned DBs, preserve all prior uncommitted work.
## Review Focus
- Actual scorer/schedule/rules run without substituted query results.
- Tie precedence and unresolved ordering/points exact; doubleownership/tier/positive-only/multiplier values independent.
- Querygrowth/classification counts correct including fallback settings reads and pair combinations.
- Returned and stored rows agree; every invocation rolls back and target scores remain absent.
- Timing hooks/artifact provenance/failure/cleanup/transaction limitations accurately reported.
### Task1
- [x] RED expected counts/scores/scenarios/classification/failure tests, implement runner GREEN.
### Task2
- [x] Native4/8/16members *5scenarios *6invocations, verify90runs/15records/provenance/rollback/cleanup.
### Task3
- [x] Bounded report/status/evidence, freshreview and single material fix pass if required; keep uncommitted.
