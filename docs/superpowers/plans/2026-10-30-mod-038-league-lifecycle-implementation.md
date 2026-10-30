# MOD-038 League Lifecycle Extraction Plan

> Use superpowers:executing-plans inline, test-first and one independent final review.

**Goal:** Complete planned league extraction with unchanged global status synchronization.
**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md).
**Architecture:** LeagueLifecycleService.synchronize_for_job owns one transaction and fixed transition ordering; supplied-connection repository owns five original update queries. Model sync method is compatibility facade; read callbacks retain existing timing and overrides.

## Constraints

- Current checkout/prior work preserved, uncommitted; no schema/dependency/hosted/deployment changes or folder moves.
- Preserve global scope, pre-draft/live/paused/complete guards, sport+season matching, inclusive season dates and completed-last precedence. No new actor/job flags or status redesign.
- Preserve now/date casts/updatedAt predicates, None success, statement/commit rollback and operational propagation. Repeated statuses converge; stale draft rows can still produce intermediate timestamp writes.
- Keep read-time global writes/callback order. Removing these side effects is separate MOD-020 work; no performance/concurrency policy claim.
- Final league model should contain no SQL; legacy helper/public signatures and schedule composition remain. Subfolder reorganization remains independent import-only follow-up.

## Task 1

- [x] RED lifecycle service tests using adapted SQLite actual SQL for transition matrix, rollback after each phase, repeated statuses and db-only legacy facade.
- [x] Add lifecycle service/repository, delegate model sync and remove unused model SQL imports; GREEN focused/full backend, untouched method/dependency/SQL-absence checks.

Interfaces: LeagueLifecycleService(engine,repository=None).synchronize_for_job(); repository mark_pre_draft/mark_drafting/mark_post_draft/mark_in_season/mark_completed(conn).

## Task 2

- [x] Native date boundaries/status matrix/precedence/unrelated rows, each post-update and deferred-commit rollback, real model sync plus detail callback integration.
- [x] Rerun all prior native suites; one independent review, final backend, docs/evidence/current hashes/links/diff checks and owned-resource cleanup.

## Ledger

- Ruling: This completes extraction scope, not correctness backlog or read-time side-effect removal. Preserve all existing lifecycle behavior and global write scope.
- Pre-flight: Existing read capability calls model facade; moving its body preserves callback overrides and endpoint test substitution. No adapter behavior change required.

- Task 1 complete: baseline 482/482; RED three missing-module errors/one passing legacy case, GREEN 4/4; full backend 486/486. Existing tests unchanged. Non-lifecycle model methods AST-identical; SQL/execute/begin/connect/commit absent from model. Lifecycle imports respect boundaries.
- Task 2 complete: [native evidence](../../modernization/evidence/mod-038-league-complete-postgres-2026-10-30.json) PASS for original matrix/date boundaries/guards/year/sport/null/unchanged rows/completed-last/status convergence, rollback after each phase/real statement/deferred commit and real legacy/actor-read callback. Every earlier native suite rerun. Current combined report supersedes previous hashes; historical reports retained.
- Independent final review no findings; focused suite 4/4, all five SQL strings/order confirmed exact. No fixes required. Final backend 486/486; current hashes, links and diff checked. Owned DB/container removed; uncommitted checkout; no hosted/schema/frontend/dependency/startup/deployment changes.
- Planned league extraction complete. Import-only folder organization and MOD-020/correctness/broader MOD-040 remain separate.
