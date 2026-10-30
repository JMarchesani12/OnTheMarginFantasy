# MOD-041 Architecture Follow-through Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to execute an approved implementation plan task-by-task. This document sequences decision work; it does not authorize product implementation. Steps use checkbox syntax for tracking.

**Goal:** Record MOD-041 approval and carry its contracts into MOD-038 before producing bounded product implementation plans.

**Architecture:** Existing Flask hooks own application HTTP behavior, Render retains hosting responsibilities and browser/provider clients own separate outbound policies. MOD-038's incremental hybrid keeps authorization and transactions in services and connection-scoped SQL in repositories.

**Tech Stack:** Existing Flask, SQLAlchemy, React/TypeScript, Supabase Auth and Render; Markdown decision records.

**Spec:** [Approved MOD-041 design](../specs/2026-10-29-mod-041-boundaries-design.md).

## Global Constraints

- Rate limiting is explicitly deferred.
- Require no new paid service, gateway, Redis, monitoring subscription or larger instance.
- No deployment or application changes are authorized by this document.
- Retain the intentionally suspended listener; do not start application infrastructure for a documentation review.

## Review Focus

- Missing-profile bootstrap must remain available to a verified subject.
- Ordinary permission denials must never trigger session refresh.
- A timeout after a mutation must never imply that replay is safe.
- Existing hidden-resource 404 responses must not become global 403 responses.
- Render-generated failures cannot promise Flask's error envelope.

## Task 1: Record decision acceptance

**Files:** MOD-041 spec above; `docs/modernization/backlog.md`; `docs/modernization/progress.md`.

**Interfaces:** Consumes explicit user approval. Produces approved architecture status, without claiming implemented behavior or fresh application-test results.

- [x] Mark the design approved on 2026-10-29.
- [x] Mark MOD-041 complete only in architecture-decision scope and retain deferred facts.
- [x] Link this follow-through sequence from the backlog and progress record.

## Task 2: Finish MOD-038 architecture review

**Files:** Read `api/endpoints/transaction/{routes.py,transactionEndpoints.py,transactionModel.py}`, `api/utils/authorization.py`, `api/authenticatedPrincipal.py`, `api/cronJobs/cronComputeWeeklyScores.py`; write `docs/superpowers/specs/2026-10-29-mod-038-layering-design.md` after discussion.

**Interfaces:** Consumes MOD-041's error, identity and transport ownership contracts. Produces a user-approved MOD-038 responsibility map, read/command call graphs, dependency rules and bounded pilot criteria.

- [ ] Review the real transaction-list read and trade command with their HTTP and trusted callers.
- [ ] Propose explicit interactive/trusted actor entry points, domain failure contracts, connection passing and compatibility facades. Resolve the existing authorization helper's dependency on LeagueModel without broad rule consolidation.
- [ ] Define domain-local file/test placement and import/startup rules; coordinate MOD-034 without making every correctness fix wait.
- [ ] Check bootstrap, concealed denials and absence of Flask dependencies in jobs/services against the Review Focus cases.
- [ ] Present the detailed architecture for approval before creating a structural implementation plan.

## Task 3: Produce separate bounded implementation plans when implementation is requested

**Files:** Future plans under `docs/superpowers/plans/`; approved architecture records and relevant modernization cards as inputs.

**Interfaces:** Consumes approved MOD-038/041 contracts and evidence inventories. Produces exact file/interface/test plans, individually reviewable and independently executable where dependencies allow.

- [ ] MOD-034: plan injectable app construction and explicit listener/job lifecycle first where needed for network-free app tests.
- [ ] MOD-028A/028B: plan compatible frontend error parsing before server envelope adoption; origin/path credential restriction, shared bounded refresh and cancellation. Pin permission-denial, consumed-body, redirect and ambiguous-mutation cases with consumer tests.
- [ ] MOD-019/024: plan middleware authentication codes, request IDs, safe errors and headers with exact route/method/exemption inventory. Preserve concealed denials and framework headers; document Render-generated response limits. Inventory legitimate payloads before selecting body/array bounds.
- [ ] MOD-040: after MOD-038 approval and relevant lifecycle/correctness prerequisites, plan one domain pilot with a read and command, stable facades and separate extraction/import-move reviews.
- [ ] Provider work: separately inventory callers and select concrete finite timeout budgets; retain no new automatic retries by default.
- [ ] For each product plan, specify fresh focused tests and the existing isolated backend suite where relevant: `python3 api/tests/run_isolated.py`. Use frontend checks appropriate to touched consumers; no production verification.

These subsystems should not become one broad implementation run. Exact signatures, timeout/limit values and test assertions belong in their individual plans after the necessary inventory and MOD-038 decisions; this sequencing document does not invent those choices.

## Documentation verification

- [x] Run `git diff --check` and verify relative Markdown links in changed files.
- [x] Confirm MOD-041 is recorded as approved, MOD-038 remains open and no application verification is claimed.

Next discussion is MOD-038, as originally requested. No execution-method selection or product implementation is needed to finish recording MOD-041 approval.
