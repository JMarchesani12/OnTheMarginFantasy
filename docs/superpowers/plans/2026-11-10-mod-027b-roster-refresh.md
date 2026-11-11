# MOD-027B Roster Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refresh related roster/trade/pending resources after confirmed mutations without optimistic ownership changes or remounting forms.

**Architecture:** Page-owned monotonic revision and guarded callback; existing resource effects consume revision and latest-request scopes. Successful writes notify the coordinator; reads retain independent errors/retries.

**Tech Stack:** React/TypeScript, existing Node controlled module harness, Vite.

**Spec:** docs/superpowers/specs/2026-11-10-mod-027b-roster-refresh-design.md

## Global Constraints

- Preserve prior uncommitted MOD-027A files; no commits/deployment or live services.
- No dependencies/API/schema changes; use authoritative reads, preserve pending timing.
- Keep account/league/week/partner and disposal guards; preserve form drafts on failed writes and newer selections on late successes.

## Review Focus

- Confirmed write with failed refresh must not cause mutation replay.
- Partner changes during proposal must preserve newer selections.
- Cutoff before render must suppress obsolete success and child actions.
- Superseded reads must not re-enable stale ownership actions.
- Overlapping writes/refreshes must converge without old finally hiding current work.

### Task 1: Coordinator and integration regressions

**Files:** Modify LeagueRosterPage.tsx, TradeRequestsPanel.tsx, PendingTransactionsPanel.tsx; create front-end/tests/rosterRefresh.test.ts using actual page/panels and controlled transport.
**Interfaces:** Panels consume refreshRevision:number; TradeRequestsPanel consumes onMutationSuccess:()=>void. Parent exposes no public API. Existing useRequestScope guards remain.

- [x] Write tests for add/drop and proposal sibling invalidation, all trade action callbacks, pending acceptance preserving ownership, authoritative applied reads, failed write selection retention, partial refresh failure/read-only retry, state preservation, overlapping reads, account/partner/week/disposal races.
- [x] Run from front-end `node --experimental-strip-types --test tests/rosterRefresh.test.ts`; expect missing refresh/state assertions RED before production changes.
- [x] Implement page-owned revision, resource readiness/error/retry, guarded success callbacks, submitted-selection reconciliation and panel refresh effects. Preserve standalone panel compatibility with optional props/defaults where current tests require it.
- [x] Run targeted new and existing league/panel scope tests; expect PASS.
- [x] Run full frontend suite, production build, import verifier and diff checks; expect PASS.

### Task 2: Review and evidence

**Files:** docs/modernization/{backlog.md,verification.md,priorities-2026-10-29.md,evidence/mod-027b-roster-refresh-2026-11-10.json}.
**Interfaces:** Consumes Task1 verified implementation; produces bounded audit evidence.

- [x] Fresh final read-only review per executing-plans; fix material findings once with RED→GREEN/full green, record minors/rulings.
- [x] Record exact checks/hashes/limits and mark MOD-027B complete only when verified.
- [x] Final diff/status checks; retain branch and ignored ledger, leave uncommitted/undeployed.
