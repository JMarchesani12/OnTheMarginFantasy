# MOD-038 Member Profile Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-first changes and one independent final review.

**Goal:** Extract owner-only member rename and existing trusted member updates without changing HTTP/legacy behavior.

**Architecture:** MemberService owns actor/field policy and transaction scope; MemberRepository executes supplied-connection scoped updates. LeagueModel remains compatible, including db-only construction. HTTP constructs UserActor from principal.

**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md). User authorized continued slices.

**Tech stack:** Existing Flask/SQLAlchemy/unittest and marked loopback PostgreSQL.

## Constraints and review focus

- Current checkout, uncommitted delivery; preserve previous work. No dependencies/schema/hosted/deployment changes.
- Owner identity and UPDATE share one predicate; foreign/missing target remains concealed 404. No commissioner bypass through interactive operation.
- HTTP rejects all fields except teamName; preserve raw nonblank string without trimming. New interactive service checks actor and nonblank name before I/O; legacy owner-ID method preserves original permissive input semantics.
- Trusted updater retains teamName/draftOrder/seasonPoints allowlist, ignored unknown keys, bound values, dictionary order, empty-input/missing-member ValueError and no ownership precondition.
- Preserve returned fields, transaction/commit errors and rollback. Removal, reads, lifecycle, administration remain separate.

## Task 1: Policy/persistence

- [x] Add direct-service failing tests for actor/name validation, owner scope/projection/raw string, trusted allowlist and rollback/legacy compatibility.
- [x] Add member_service.py/member_repository.py, two model delegates and HTTP wiring; retain legacy constant import compatibility.
- [x] Focused GREEN and full guarded backend; untouched model methods AST check and dependency checks.

Interfaces: MemberService.rename(actor,member_id,team_name), rename_for_owner_id(member_id,user_id,team_name), update_for_job(member_id,updates); MemberRepository.rename_owned(conn,member_id,user_id,team_name), update_member(conn,member_id,payload).

## Task 2: Native/review/evidence

- [x] Native projection/owner scope, SQL-bound values, trusted allowlist, post-update/deferred-commit rollback and ownership revocation under actual row-lock contention.
- [x] Rerun all admission native checks because model/HTTP source hashes change; keep old reports historical and record current combined evidence.
- [x] One independent review; fixes if needed test-first. Fresh backend, diff/link/hash checks, docs/runbook update and owned resource cleanup.

## Execution ledger

- Ruling: Select member edits as next bounded slice; removal and league reads remain separate. Approved hybrid and current-checkout preference persist.
- Pre-flight: Native verification consumes new services plus model/HTTP facades; signatures above align. Preserve legacy permissive inputs while new actor API enforces existing HTTP name rule.

- Task 1: complete. Baseline guarded backend 426/426. RED four missing-module errors and one passing legacy case, GREEN five direct-service tests; full guarded backend 431/431. Model AST comparison confirms all other methods unchanged; imports follow approved boundaries.
- Task 2: complete. [Native evidence](../../modernization/evidence/mod-038-member-profile-postgres-2026-10-30.json) PASS for member projection/scope/bound values/allowlist, post-update/deferred-commit rollback, observed service/facade row-lock waits and owner recheck following revocation. All preceding admission checks rerun. Combined report supersedes prior admission source hashes; old reports historical.
- Independent final review: no Critical/Important/Minor findings; focused guarded tests 5/5. Only subsequent production adjustment was formatting SQL literals, no semantic change. Final full guarded suite 431/431. Links/hashes/diff checked.
- Owned random database and container removed; working changes uncommitted. Removal/draft-order shifting and broader league methods remain separate. No schema/hosted/frontend/dependencies/startup/deployment changes.
