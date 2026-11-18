# MOD-017 Query Baselines Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans, established native execution.

**Goal:** Reproducible isolated PostgreSQL evidence for own-league and ownership queries.
**Architecture:** Guarded UUID database runner, captured production SQL, deterministic schema/fixtures, normal-plan A/B experiments and owned cleanup.
**Tech Stack:** Python/SQLAlchemy/psycopg2, installed Docker/cached PostgreSQL17.6.
**Spec:** docs/superpowers/specs/2026-11-11-mod-017-query-baselines-design.md
## Global Constraints
No configured DSN/app/job/provider, deployment/index rollout, production-query edits, dependencies or commits. Scope all created resources to task ownership.
## Review Focus
Refuse unmarked/nonlocal targets, cleanup only owned UUID resources, exact captured SQL/params, canonical output equivalence, honest warm synthetic measurement limits.
### Task 1: Runner and safeguards
- [x] Read existing baseline/native conventions; add guard/query/equivalence/cleanup regression tests RED.
- [x] Implement runner with derived schema provenance, deterministic three-tier data, five measured/warm-up executions and native JSON plans, narrow candidate indexes/storage/catalog comparison.
- [x] Isolated runner tests GREEN; retain timeout/failure/cleanup evidence.
### Task 2: Native experiment
- [x] Start authorized Docker if needed; inspect cached image, create owned loopback ephemeral fixture and marker.
- [x] Run measurements, inspect every tier/plan/equivalence; clean only owned database/container and verify.
### Task 3: Review/report
- [x] Fresh final code/evidence review; fix material findings with RED→GREEN and appropriate native rerun.
- [x] Record report/provenance/artifacts/limits and bounded MOD017 status; leave uncommitted/undeployed.
