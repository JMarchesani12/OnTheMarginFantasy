# MOD017 Team Lookup Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans, continued audit-only authorization.

**Goal:** Measure full lookup retrieval/ranking and conference counts without optimization.
**Architecture:** Exact query capture, deterministic schema fixtures, normalized unordered group evidence, actual service passthrough instrumentation; reuse isolated guards.
**Tech Stack:** Python/SQLAlchemy/psycopg2,cached local PostgreSQL17.6.
**Spec:** docs/superpowers/specs/2026-11-13-mod-017-team-lookup-design.md
## Global Constraints
No production/query/ranking/paging/index/tuning/deploy changes; previous artifacts preserved, no commits.
## Review Focus
Scalar/group exact values, historical membership/ownerlabels, real ranking not copied, earlyquery noDB, count/timing/cleanup/provenance safety.
### Task 1
- [x] Capture/value/order/ranking/failure tests RED, runner GREEN.
### Task 2
- [x] Native three-tier SQL/service measurements; validate results and cleanup owned fixture.
### Task 3
- [x] Fresh review/material fixes if needed; evidence/report/bounded status and deferred implementation recorded.
