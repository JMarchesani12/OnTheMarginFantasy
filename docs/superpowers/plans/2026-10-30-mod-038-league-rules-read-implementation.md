# MOD-038 League Rules Read Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-first and one independent final review.

**Goal:** Extract full league rules read into actor-aware read service and supplied-connection repository, preserving wire/model behavior.

**Architecture:** LeagueReadService selects actor/trusted scope, owns one read connection, pure rule description and deadline conversion. LeagueReadRepository owns original scoped league query and tier-fallback team query. HTTP retains existing metadata/discovery policy and calls actor service only in full rules branch; model retains optional-reader compatibility.

**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md); continued slices authorized.

**Tech stack:** Existing Flask, SQLAlchemy/raw SQL, leagueRules, unittest and marked synthetic PostgreSQL.

## Constraints and review focus

- Current checkout, preserve previous work, uncommitted delivery; no schema/dependency/hosted/deployment changes.
- Actor required before I/O. Scoped query denies outsiders even for discoverable leagues; no full rules via preview, original HTTP 403/404 behavior and late scope rejection preserved.
- One connect scope; missing/scoped-out league returns None without querying teams. Preserve fetchone/_mapping and fetchall accessors and SQL fields/parameters/order/tier fallback.
- Describe_rules behavior/version/team sorting and native deadline ISO conversion/null/string fallback retained. No new final access recheck or snapshot/locking guarantee after the league SELECT.
- Named trusted rules read, legacy optional-reader method and db-only callers remain. Actual repository has no model subclasses/read-scope overrides.
- Details/member/conference reads, discovery policy, lifecycle writes and scheduling remain separate.

## Task 1: Policy/persistence

- [x] RED tests for actor/no I/O, scoped projection/order/tier fallback/deadlines, denied/missing skip teams, revocation at query and trusted/legacy compatibility.
- [x] Add league_read_service.py/repository.py, delegate get_league_rules and wire full HTTP rules branch to actor service; focused GREEN/full backend.
- [x] AST non-target model and dependency checks.

Interfaces: rules(actor,league_id), rules_for_reader_id(league_id,user_id), rules_for_job(league_id), internal _rules(league_id,reader_user_id=None). Repository rules_league(conn,league_id,reader_user_id=None), rules_teams(conn,sport_id).

## Task 2: Native/review/evidence

- [x] Native actual read SQL/tier fallback/sport isolation/version/deadline projection, missing/denied no-team-query and separate-connection revocation before scoped read.
- [x] Rerun prior league creation/settings/deletion/member/admission suites. One independent review, fresh backend, docs/evidence/hash/link/diff checks and owned-resource cleanup.

## Execution ledger

- Ruling: Extract cohesive rules read only; retain HTTP discovery policy and other read/lifecycle branches unchanged.
- Pre-flight: HTTP already gates rules to full access; repository retains its own actor predicate for revocation between precheck and SELECT. No new post-SELECT revocation promise.

- Ruling: Three adapter-unit tests construct LeagueEndpoints with __new__ and inject the old model method. After intentional HTTP dependency migration, inject the read-service mock instead; keep all assertions unchanged and avoid a production fallback to a deprecated path. Full JWT/SQL authorization tests unchanged.

- Task 1: complete. Guarded baseline 455/455; focused RED five missing-module errors, GREEN 5/5. First full run identified three adapter mock-wiring cases, updated dependency injection only with assertions unchanged. JWT/SQL authorization tests unchanged. Full backend 460/460; all non-rules model AST and read dependency checks pass.
- Task 2: complete. [Native evidence](../../modernization/evidence/mod-038-league-rules-read-postgres-2026-10-30.json) PASS for actual projection/tier fallback/sport isolation/deadlines, denied/missing no-team queries, legacy/trusted/version and separate-connection pre-SELECT membership revocation service/facade. Every prior league/member/admission native suite rerun. Combined report supersedes prior hashes; historical reports retained.
- Independent final review no Critical/Important/Minor findings; reviewer focused guarded suite 5/5. No production review fixes needed. Final backend 460/460; hashes, links and diff checked.
- Owned random database/container removed. Current checkout uncommitted; no schema/hosted/frontend/dependency/startup/deployment changes. Other reads/discovery/lifecycle remain separate.
