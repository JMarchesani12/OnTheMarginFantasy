# MOD017 Stored-score Reads Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans, inline audit-only continuation.

**Goal:** Baseline stored-score reads without optimizing them.
**Architecture:** Exact repository capture with SQLAlchemy expanding-bind compilation, independently computed full rows, evidence-only unordered normalization, actual trusted job reader.
**Tech Stack:** Python/SQLAlchemy/psycopg2/cachedlocalPostgreSQL17.6.
**Spec:** docs/superpowers/specs/2026-11-15-mod-017-score-reads-design.md
## Global Constraints
No app SQL/index/tuning/scoring/auth/deploy/commit change. Optimizations deferred. Fixed marked loopback/UUIDowned fixtures only; preserve current H2H files/artifacts.
## Review Focus
- Expanding/empty/duplicate week lists remain parameterized and equivalent.
- Dates/names/points/ranks/zero aggregates independently correct, no unseen ties-order claim.
- Unscored/foreign members, foreign week and missing leagues cannot leak scope.
- Service trusted-job normalization and no connection for empty input; not full scoring/auth HTTP.
- Failure-aware artifacts/provenance/cleanup and separate/combined storage costs accurately bounded.
### Task1 — Tests and runner
- [x] RED tests capture/expansion/full values/normalization/empty-service/failure/sample behavior.
- [x] Implement measure_mod017_scores.py, combined measurement tests GREEN.
### Task2 — Native evidence
- [x] Three disposable tiers,180SQL/84service complete expected records/hashes verified; exactowned cleanup.
### Task3 — Closeout
- [x] Report/status/evidence, fresh review, one material fix pass if needed; keep uncommitted.
