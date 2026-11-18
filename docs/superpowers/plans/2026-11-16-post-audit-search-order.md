# Stable League Search Ordering Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans; preserved native inline method, one fresh review at batch end. User owns commits.

**Goal:** Stop duplicate/omitted equal-name matches across static search pages.
**Architecture:** Retain similarity/name order, append unique league ID. Test actual PostgreSQL traversal and current client sizes; no new API.
**Tech Stack:** Existing Python/SQLAlchemy/PostgreSQL17.6; guarded isolated tests.
**Spec:** [Roadmap: first-tranche contracts](../../modernization/post-audit-implementation-2026-11-16.md#decisions-for-the-first-tranche); [baseline](../../modernization/mod-018-league-search-baseline.md).

## Global Constraints

No route/payload/privacy/filter/relevance/limit/offset/cursor/index changes. Home6/helper20/server50 remain unchanged. No configured DSN/deployment/commit. Historical raw artifacts immutable; preserve unrelated work.

## Review Focus

- Equal-name ties have a unique total order; different names/similarity retain precedence.
- Private/sport-filtered/absent/empty/deep pages preserve fields and bounds.
- SQLite adapters cannot prove PostgreSQL top-N tie behavior; native traversal required.
- Existing audit assertions intentionally pin the old defect and must be explicitly versioned.
- No concurrent-insert/delete or full large-enumeration guarantee is implied by an ID tie key.

## Task 1 — Reproduce the ordering defect

**Modify:** `api/tests/test_public_league_search.py`, `scripts/modernization/tests/test_mod018_search.py`.
**Create:** `scripts/modernization/verify_mod018_search_order.py` (owned marked-local fixture only).

- [ ] Add a failing actual-query capture assertion that the unique ID key is last; retain similarity/name keys and current payload/filters. Equal-name SQLite result tests alone may already pass and are insufficient RED evidence.
- [ ] Native RED: use the small equal-name fixture and actual repository/service, walk all matches at page sizes6/20/50, compare eligible IDs/counts and full fields, then repeat after owned heap reorder. Require every ID exactly once. Existing50-row baseline demonstrates the negative case; record actual failing checks before the fix.
- [ ] Include sport filters/private rows, missing query, empty/end/max-offset pages and unchanged parameter bounds. Keep the native driver's setup/cleanup guard independent of the product assertion.

## Task 2 — Minimal fix and current evidence

**Modify:** `api/endpoints/league/reads/repository.py`, `scripts/modernization/measure_mod018_search.py` as necessary for honest future measurement.

- [ ] Append `l.id ASC` after existing similarity/name order only.
- [ ] Make fixture ID-probe construction idempotent for already-fixed SQL; update old “ID absent” capture assertions to the intended fixed contract. If reusing two identical variants, label the comparison as a no-op rather than inventing a second improvement. Do not alter old raw reports.
- [ ] GREEN focused isolated search checks: `python3 api/tests/run_isolated.py test_public_league_search.py` and relevant measurement tests. Run the new native driver on the owned marked-loopback fixture; verify6/20/50 traversal/fields/layout stability and exact cleanup.
- [ ] Run `python3 api/tests/run_isolated.py` for backend integration; no app startup. Measure a representative large first/max-offset case only if needed to rule out a material regression; do not promise latency improvement.

## Task 3 — Review and closeout

- [ ] Inspect diff: no HTTP/consumer/page-size changes. Create new before/after evidence with current source hashes and unique run IDs, update MOD018 status, retain historical failure data.
- [ ] One fresh scoped review; fix material findings RED→GREEN once and rerun affected checks. Leave user-owned changes uncommitted.

**Done when:** actual current SQL is uniquely ordered, all small-fixture pages contain each allowed match once across layouts and all three page sizes, existing API tests pass, and no extra pagination/rollout claim is made.
