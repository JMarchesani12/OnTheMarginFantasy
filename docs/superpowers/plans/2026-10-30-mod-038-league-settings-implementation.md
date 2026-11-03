# MOD-038 League Settings Updates Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-first and one independent final review.

**Goal:** Extract league settings/metadata PATCH policy and persistence with unchanged actor/trusted/legacy behavior.

**Architecture:** LeagueAdminService owns authority, settings/rule-version/timezone policy, allowlist and original two transaction scopes; LeagueAdminRepository owns current-state read and dynamic bound UPDATE CTE. Timezone helpers join shared pure leagueRules; model helper names remain delegating compatibility methods, HTTP uses verified actor.

**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md); continued implementation authorized by user.

**Tech stack:** Existing Flask, SQLAlchemy/raw SQL, zoneinfo/unittest, marked synthetic PostgreSQL.

## Constraints and review focus

- Current checkout; preserve prior work, uncommitted delivery. No new dependencies/schema/deployment/hosted access.
- Preserve initial authority before patch/settings validation, strict commissioner equality, missing-league error, unknown-field ignore/empty rejection, bound values and exact output incl sportInfo.
- Preserve two transactions (read, write), commissioner predicate at write and late-revocation PermissionError. Do not claim lost-update prevention or introduce locks/retries/merge semantics.
- Preserve settings_for_update version pinning/replacement behavior, dict-only settings, timezone precedence/aliases and exception messages; patch input remains unmodified.
- Preserve named trusted update without authority, private _update_league optional commissioner signature and model db-only callers. Actual repository has no model subclasses/timezone overrides; compatibility helper signatures retained.
- Preserve post-write/commit failures and existing missing-result behavior (checked PermissionError vs trusted RuntimeError), even empty Sport join behavior. Creation and lifecycle remain separate.

## Task 1: Policy/persistence/rules

- [x] RED direct-service tests: actor before I/O, two scopes/projection/allowlist, authority-before-validation, version/timezone failures/input immutability, late revocation, rollback and legacy helpers/trusted compatibility.
- [x] Extend admin service/repository, move timezone pure helpers to rules/leagueRules.py with legacy delegates, replace _update_league body, actor HTTP wiring; focused GREEN/full backend.
- [x] AST checks for non-target model methods and service/repository import boundaries.

Interfaces: update(actor,league_id,patch), update_for_legacy_commissioner(league_id,user_id,patch), update_for_job(league_id,patch), internal update_in_scope(league_id,patch,commissioner_id=None). Repository current_for_update(conn,league_id), update_fields(conn,league_id,payload,commissioner_id=None). Shared get_timezone_name_from_settings(settings), validate_timezone_name(tz_name).

## Task 2: Native/review/evidence

- [x] Native original UPDATE CTE/jsonb/sport projection/deadline/null/bound fields, real constraint/post-write/deferred-commit rollback, no-result guards and separate-connection authority change after read.
- [x] Rerun prior league deletion/member/admission native suites; one independent final review, fresh backend, docs/hash/link/diff checks and owned-resource cleanup.

## Execution ledger

- Ruling: Preserve original read/validation/write boundaries and settings replacement semantics; broader concurrency/correctness redesign is separate.
- Pre-flight: Native tests consume service/facade and actual SQL; timezone helper sharing also touches creation indirectly, so full league/rules suite must remain green.

- Task 1 regression: first full suite had two existing rule-version test errors because current-state repository read changed result accessor. Restored original fetchone/_mapping contract (no test changes); guarded suite rerun required.

- Native expectation correction: original SQL uses unquoted AS sportInfo, so PostgreSQL returns sportinfo (SQLite fixture synthesizes sportInfo). Preserve SQL/output; native assertions corrected to PostgreSQL folding, no production or existing test changes.

- Task 1: complete. Guarded baseline 442/442. Focused RED six missing-operation assertions and one passing compatibility case; GREEN 7/7. First full run exposed two existing rule-version tests; restoring original result accessor made them green without test changes. Full backend 449/449. Non-target model AST and exact timezone body comparisons pass; admin dependency boundaries verified.
- Task 2: complete. [Native evidence](../../modernization/evidence/mod-038-league-settings-postgres-2026-10-30.json) PASS: actual CTE/JSON/deadlines/projection, validation order/immutability, real statement/post-update/deferred-commit rollback checked/trusted, separate-connection late revocation service/facade, trusted/private/timezone compatibility and existing empty-Sport post-commit guard. All preceding native slices rerun; combined report supersedes their hashes, old reports retained.
- Independent final review no Critical/Important/Minor findings; reviewer ran focused guarded suite 7/7. No review fixes required. Final backend 449/449; source hashes, links and diff checked.
- Owned random database/container removed. Current checkout uncommitted; no schema/hosted/frontend/dependency/startup/deployment changes. Creation/reads/lifecycle and concurrency redesign remain separate.
