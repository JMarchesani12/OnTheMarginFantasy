# MOD017 Transaction Baselines Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans, combined design/implementation requested.

**Goal:** Add bounded native transaction-read evidence with reliable failure/count reporting.
**Architecture:** New runner reuses prior guarded schema/seed/measurement utilities, captures three actual repositories, validates expected counts and owned cleanup, unique artifacts/current-run manifest.
**Tech Stack:** Python/SQLAlchemy/psycopg2, cached local PostgreSQL17.6/Docker.
**Spec:** docs/superpowers/specs/2026-11-13-mod-017-transactions-design.md
## Global Constraints
No production code/query/index changes or rollout; preserve old runner/evidence, no dependency install/commit/deploy.
## Review Focus
Failed runs cannot retain current PASS, exact authorization/count/output equivalence, candidate scope, partial-index low-density limits, owned cleanup only.
### Task 1
- [x] Tests RED for capture/count/failure-manifest ownership contracts.
- [x] Implement fixture/capture/native measurement/unique artifacts and safe cleanup reporting; unit GREEN.
### Task 2
- [x] Start authorized Docker if needed, use cached image/owned marked loopback tmpfs fixture, run three native tiers, verify results and cleanup.
### Task 3
- [x] Fresh code/evidence review, material fixes RED→GREEN/native rerun if needed; report bounded results/provenance/limits, leave uncommitted.
