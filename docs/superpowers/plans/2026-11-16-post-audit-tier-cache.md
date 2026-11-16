# TypeScript Tier Cache Recovery Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans; preserved native inline method, one fresh review. User owns commits.

**Goal:** Prevent persistent invalid tier-cache poisoning and recover one invalid cached entry safely.
**Architecture:** Parse/schema-check before publishing, invalidate only the bad cache entry, one recovery fetch, atomic owned-temp rename. Preserve existing transport warning/error contracts.
**Tech Stack:** Existing Node/TypeScript/fs tests; canned fetch and temporary directories only.
**Spec:** [Roadmap: tier-cache contract](../../modernization/post-audit-implementation-2026-11-16.md#typescript-tier-cache); [failure evidence](../../modernization/mod-036-local-ui-tier-audit.md#separate-typescript-tier-tool-reliability).

## Global Constraints

Do not import `scripts/basketball-tiers/index.ts` during tests (top-level main). No real provider requests, user-cache cleanup, database/tier-output writes, TTL/limit/timeout/backoff/CLI policy changes. Do not change Python ingestion. Historical raw artifacts immutable, no commit/deploy.

## Review Focus

- Legitimate empty events arrays remain valid cache hits without refetch.
- Malformed/schema-invalid existing cache gets at most one recovery fetch; no loop.
- Fresh invalid JSON/schema cannot become a valid published cache; temp files cleaned on failure.
- HTTP503 warning/empty return and network rejection remain distinct/current behavior.
- Current audit helper tests assert the old poisoned-cache behavior and require an explicit new-contract update.

## Task 1 — RED existing-loader regressions

**Create:** `scripts/basketball-tiers/espn.test.ts`.

- [ ] Use actual loadSeasonScoreboards with canned globalfetch and task-owned temp directories; restore fetch/remove temp data in finally.
- [ ] RED:200malformed JSON leaves no cache; next explicit invocation can fetch again. Seed malformed legacy cache, return valid payload on one recovery fetch, verify repaired JSON and subsequent warm hit.
- [ ] Add validJSON/missing-events legacy/fresh cases, valid empty events cache/no fetch, HTTP503 two explicit invocations/no automatic retry, network rejection, read/rename failures and owned temp-file cleanup. An EACCES/read-I/O failure must propagate without deleting the entry or fetching; only invalid content gets recovery. Counts must enforce the recovery budget.
- [ ] Retain all existing nine analysis/output/conference/validation tests. A failed test must reproduce the poison/recovery defect, not just missing helper code.

## Task 2 — Minimal cache implementation

**Modify:** `scripts/basketball-tiers/espn.ts` only, plus a small local helper if required.

- [ ] Parse and require events-array structure before treating a cache entry as valid or publishing a cache file. Preserve valid empty-day caches and existing cache filenames/keys.
- [ ] Invalid legacy entry: remove/invalidate that exact file and attempt the normal fetch once. If the fetched payload is invalid, keep current warning/throw semantics and publish nothing; do not recursively refetch.
- [ ] Use unique same-directory temp files/rename for valid publication; clean only owned temporary files. Preserve filesystem-error propagation. No retry/TTL/provider-limit side changes.
- [ ] Preserve current HTTP503 warning/empty output, network error propagation and invalid-schema warning/return behavior, while refusing to cache invalid schema. This batch does not establish safe whole-CLI output publication on partial provider failure.

## Task 3 — GREEN evidence and closeout

**Modify:** `scripts/modernization/measure_mod036.mjs` provider observations and `tests/mod036.test.mjs` as needed to label the fixed contract; preserve original raw evidence.

- [ ] Replace old “bad response remains cached/no refetch” assertions with the intended contract; add a distinct seeded-invalid-cache recovery observation. Do not weaken error/call-count checks or rewrite historical outcomes.
- [ ] Run `npm run basketball:tiers:test --prefix front-end`, `npm run basketball:tiers:typecheck --prefix front-end` and the focused audit helper tests. No browser/full frontend/native database rerun needed for this isolated tool change.
- [ ] Record before/after canned call counts/cache facts/new source hashes; one fresh scoped review and material fixes once. Update MOD036 finding status, leave uncommitted.

**Done when:** invalid cache cannot trap later invocations, one-fetch recovery is enforced, invalid responses are not published, valid warm cache/empty-day behavior and original transport semantics remain correct, and all tool tests/type checks pass without network access.
