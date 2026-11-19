# School Alias Database Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-driven-development, and requesting-code-review.

**Goal:** Make SchoolAlias the runtime source of truth and migrate the authorized configured target.
**Architecture:** Additive table and idempotent seeded import; aliases joined in server search; public cached metadata catalog for frontend search by actual team IDs.
**Tech Stack:** PostgreSQL/SQLAlchemy/Python, React/TypeScript.
**Spec:** docs/superpowers/specs/2026-11-19-school-alias-database-design.md

## Global Constraints

No school/team renames, new school records, score/ownership changes, browser direct writes, globally unique aliases, runtime JSON alias source, or deployment. Preserve typo matching and league scope. Five-minute shared client cache.

## Review Focus

- Provider IDs cannot be treated as School IDs; ambiguous mappings block import.
- Replay preserves manual aliases and existing source records.
- Team-ID mapping prevents shared names from borrowing another school's aliases.
- Cache failures retry; unmounted requests cannot update replacement state.
- Migration and seed are one transaction, with target identity and bounded locks.

### Task 1: Storage and import
- [x] Add SchoolAlias migration/schema description, pure import planner, transaction-aware importer, real SQL tests and replay/ambiguity regressions.
- [x] Run configured preflight and dry run; apply only this additive change and verify receipt.

### Task 2: Database-backed API and browser search
- [x] Test and implement metadata endpoint and lookup alias join; remove runtime JSON matching.
- [x] Test shared cache/hook and team-ID matcher; wire existing search surfaces and retry states.
- [x] Run full suites/build and fresh review, fix important findings, document deployment prerequisite and migration result.


## Execution and verification

Completed inline in the established workspace. No app deployment or Git commit was performed.

Task 1 complete: additive SchoolAlias DDL, normalized per-school uniqueness, School FK, RLS and browser grant revocation; explicit bounded import maps provider external IDs to existing school IDs, includes School/short/team names, rejects ambiguous identities, and preserves existing aliases/sources on replay. Configured preflight and rollback-only dry run succeeded. Reviewed apply then committed **2,079 aliases for 366 schools**, leaving **631 teams and 366 schools unchanged**. Result APPLIED_AND_VERIFIED; see docs/modernization/evidence/school-alias-rollout-2026-11-19.json.

Task 2 complete: public metadata-only catalog endpoint and actual database lookup alias join; browser cache deduplicates loads for five minutes, retries failures, and discards obsolete hook results. All search surfaces resolve aliases by actual database team ID; name-only fallback requires an unambiguous exact displayed name. Runtime JSON imports were removed and the generated frontend copy deleted. Seed JSON remains offline only. Existing displays, league scope, and lookup response projection are preserved.

Read-only runtime verification exercised the new HTTP handler against the configured database, confirmed 631 catalog teams, Northern Iowa team IDs 369/525 both linked to School369, working alias/typo queries, actual PostgreSQL lookup JSON aggregation, RLS, and no direct anon/authenticated table privileges. The TypeScript matcher independently consumed that actual API payload and resolved UNI/Northern Iowa/Nothern Iowa to IDs369/525. Evidence: docs/modernization/evidence/school-alias-runtime-2026-11-19.json.

Final suites: `python3 api/tests/run_isolated.py` — 874 passing; `node --test --experimental-strip-types tests/*.test.ts` from front-end — 266 passing; `npm run build` — passing; `git diff --check` — clean. Synthetic browser harnesses cover alias failure/retry and obsolete response handling; this is not a deployed-browser smoke check.

Fresh review: no blocking findings. The stale README finding was addressed by the already-planned maintenance documentation rewrite.
Final: minor (deferred): deeper existing-table schema/security drift checks on migration replay. Current target had no SchoolAlias table and received the exact reviewed DDL; applied RLS/grants and lookup behavior were verified. The runner validates columns and named uniqueness on replay and is explicitly documented as not a general drift-repair tool.
