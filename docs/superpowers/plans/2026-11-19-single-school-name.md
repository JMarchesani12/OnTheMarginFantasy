# Single School Name Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-driven-development, and requesting-code-review.

**Goal:** Use shorter School.name values everywhere and retire School.shortName/SportTeam.displayName safely.
**Architecture:** Resolve team labels through schoolId, retain public API property names, preserve legacy labels as aliases, and stage live column removal after API deployment.
**Tech Stack:** Python/SQLAlchemy/PostgreSQL, existing React clients and isolated unittest fixtures.
**Spec:** docs/superpowers/specs/2026-11-19-single-school-name-design.md

## Global Constraints

Shorter canonical school names approved by user. Preserve official/old labels in SchoolAlias. Do not change team/school IDs, memberships, ownership, scores, or unlinked game names. Preserve User.displayName and API compatibility. No live column drop before compatible API deployment.

## Review Focus

- Multiple sports must display the same canonical school name.
- Imports and maintenance tools must work after physical column removal.
- Linked game labels use school names; unknown opponents retain provider names.
- All old labels and official names remain searchable after renaming.
- SQL dependencies and deployed readers must not be broken by the destructive phase.

### Task 1: Canonical reads and tests
- [x] Add regressions using tables that physically lack the retired columns; observe failures.
- [x] Update roster, draft, rules, search/catalog, transaction, ingestion and game label reads to School.name; preserve API shapes.
- [x] Update maintained test fixtures/importer and run backend/frontend suites.

### Task 2: Naming and retirement migration
- [x] Produce a reviewed name-change plan from provider labels mapped through actual school IDs; identify ambiguous/unmapped schools.
- [x] Preserve existing names as aliases, update shorter canonical names, and prepare bounded column removal without CASCADE.
- [x] Verify on the configured target with a rollback-only run; defer live column drop until deployment.
- [x] Fresh review, verification, rollout documentation and concrete deployment/drop handoff.


## Execution, review, and deployment handoff

Task 1 complete: production readers now join School.name for roster, draft,
league rules, search/catalog, transactions, and ingestion DTOs. Linked game names
resolve through School; provider names remain stored and are fallback labels for
unlinked opponents. Existing API property names and User.displayName remain.
The alias importer no longer reads either retired column. Regression tests create
real School/SportTeam tables physically lacking the old columns. Historical
minimal SQLite fixtures use a documented test-only School view bridge; explicit
canonical-schema tests bypass it. Frozen schemas/snapshots remain historical.

Task 2 preparation complete: a target-bound transaction runner maps provider IDs
to actual School IDs, preserves old names/short labels/team labels as aliases,
plans shorter names, and stages bounded DROP COLUMN without CASCADE. Dry-run
physically removed both columns inside a transaction, checked updated catalog,
rules, ingestion, roster, search, draft, trade and game SQL, then rolled back.
The configured apply-names phase committed **336 name changes**, keeping all
**366 schools, 631 teams, and 2,079 aliases**. A fresh read-only postflight plans
zero further changes; unmapped School347 is left unchanged. See school-name
plan/dry-run/rollout/postflight receipts in docs/modernization/evidence.

Fresh review found a provider ID could incorrectly rename two different schools.
Added a failing regression, rejected one-provider-to-many-school mappings, and
verified GREEN. Two sports sharing one provider/school identity remain valid.
The outdated importer documentation finding was corrected as part of planned docs.
No findings are deferred for this change.

Verification: `python3 api/tests/run_isolated.py` — 882 passing;
`node --test --experimental-strip-types tests/*.test.ts` — 266 passing;
`npm run build` — passing; `git diff --check` — clean.

**Final external step complete:** the user confirmed deployment, the public API
was independently verified to return canonical school names, and the reviewed
column-drop transaction was committed against target fingerprint 4ecd426e8efadd29.
A fresh read-only connection confirmed both retired columns absent, all 366
schools/631 teams/2,079 aliases unchanged, updated repository reads passing, and
deployed health/catalog HTTP200. Recorded local committed revision:
e2245ac8f500907f7713245d9beb90deac39e5b9 (user deployment attestation plus public
behavior verification; Render workspace metadata was not available in-session).
See school-name-column-drop and school-name-column-drop-postflight receipts.
No deployment, restart, job trigger, unsuspension or unrelated data change was
performed by the agent during final column removal.
