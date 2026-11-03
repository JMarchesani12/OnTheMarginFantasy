# MOD-038 League Deletion Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-first changes and one independent final review.

**Goal:** Extract commissioner-only league deletion into league administration service/repository with unchanged behavior.

**Architecture:** LeagueAdminService owns actor requirement, locked authority and transaction scope; LeagueAdminRepository owns SELECT FOR UPDATE and commissioner-scoped DELETE RETURNING. LeagueModel retains context-free legacy checked delegate, HTTP constructs UserActor from principal.

**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md), user-authorized next slice.

**Tech stack:** Existing Flask/SQLAlchemy/unittest and marked synthetic PostgreSQL.

## Constraints and review focus

- Current checkout, preserve prior work, uncommitted delivery. No schema/dependency/hosted/deployment changes.
- Preserve league lock, missing-league ValueError, int-converted authority PermissionError, scoped delete and missing-return RuntimeError, exact result fields.
- Both actor and legacy entry points always check authority. Legacy input coercion remains unchanged; no bypass/job flag.
- Preserve single transaction, database-defined cascades/restrictions and operational/commit errors; no new manual cascade or status guard.
- No update/settings/creation/lifecycle migration in this slice. Test only synthetic data.

## Task 1: Policy/persistence

- [x] Add direct-service RED tests for actor before I/O, checked deletion/projection/cascade/replay, authority/missing, rollback and legacy db-only/coercion.
- [x] Add league_admin_service.py/league_admin_repository.py, delegate delete_league and wire HTTP actor service; GREEN focused and guarded full backend.
- [x] AST unchanged-method and dependency checks.

Interfaces: LeagueAdminService.delete(actor,league_id), delete_for_legacy_commissioner(league_id,acting_user_id); LeagueAdminRepository.lock_for_delete(conn,league_id), delete_if_commissioner(conn,league_id,acting_user_id).

## Task 2: Native/review/evidence

- [x] Native synthetic direct/multilevel cascades, unrelated data, actual FK restriction and post-delete/deferred-commit rollback.
- [x] Observe service/facade competing deletion/replay and commissioner-revocation lock waits with checked authority.
- [x] Rerun admission/member native checks, one independent final review, fresh backend, docs/evidence/current hash/link/diff checks and owned-resource cleanup.

## Execution ledger

- Ruling: Limit this increment to deletion; settings has distinct validation/transaction contracts and remains separate.
- Pre-flight: Native suite consumes new deletion APIs plus existing prior services; repository connections remain supplied by service transactions.

- Task 1: complete. Guarded baseline 437/437; focused RED four missing-module errors and one passing legacy case, GREEN 5/5. Full backend 442/442; existing tests unchanged. Non-deletion model methods AST-identical and admin dependency boundaries verified.
- Task 2: complete. [Native evidence](../../modernization/evidence/mod-038-league-delete-postgres-2026-10-30.json) PASS: authority/projection/direct+multilevel synthetic cascades, unrelated data, real FK restriction/post-delete/deferred-commit rollback and suppressed-delete guard/trigger rollback. Four service/facade lock waits demonstrate deletion replay rejection and post-lock commissioner revocation denial. All preceding admission/member checks rerun; combined report supersedes their source hashes and preserves historical reports.
- Independent final review: no Critical/Important/Minor findings; reviewer focused guarded suite 5/5. No fixes required. Final backend 442/442; current source hashes, links and diff checked.
- Owned random database/container removed. Current checkout uncommitted; no schema/hosted/frontend/dependency/startup/deployment changes. Other league responsibilities remain separate.
