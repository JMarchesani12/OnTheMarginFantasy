# MOD-038 League Discovery Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, test-first and one independent final review.

**Goal:** Extract access metadata, names-only member previews and public search while preserving visibility and pagination behavior.

**Architecture:** LeagueReadService owns actor/legacy reader selection, public search normalization/bounds and transaction scopes. Repository owns original metadata, preview entitlement and pg_trgm search SQL. HTTP retains visibility/full/preview decisions and metadata recheck; actor comes from verified principal, search stays anonymous.

**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md), user authorized continuation.

**Tech stack:** Existing Flask/SQLAlchemy/unittest, marked synthetic PostgreSQL with existing pg_trgm capability.

## Constraints and review focus

- Preserve current checkout/prior work, uncommitted delivery; no hosted/schema/dependency/deployment changes. Synthetic extension only in owned test DB.
- Metadata is internal entitlement information; retain original projection/None and fullAccess calculation even for private outsider (HTTP conceals it). Preview query rechecks discoverable OR commissioner/member and returns names-only ordered fields.
- New interactive access/preview methods require actor. Legacy reader-ID methods preserve existing inputs. HTTP pre/post metadata queries stay separate and existing 403/404/empty-preview behavior stays unchanged.
- Search remains public/discoverable-only, strip and short-query exit BEFORE integer conversion/I/O; limit clamps 1..50, offset floors0; optional sport, ILIKE wildcards, similarity DESC/name ASC and bound values preserved. No new escape/rate limit.
- Preserve one begin per legacy query and SQL row accessors. No lifecycle sync in discovery or public search.
- Remaining league slices after this: details/my leagues; member lists/daily summaries; lifecycle sync (three).

## Task 1: Policy/persistence

- [x] RED service tests for actor/no I/O, metadata entitlement/projection, preview concealment/revocation, public normalization/filter/paging/clamps/short-circuit and legacy callers.
- [x] Extend read service/repository, delegate three model methods; migrate HTTP metadata/preview/search calls with one principal-derived actor. Move adapter mock injection to access service with unchanged assertions.
- [x] GREEN focused/full backend and unchanged-model/dependency checks.

Interfaces: access(actor,league_id), access_for_reader_id(league_id,user_id), member_previews(actor,league_id), member_previews_for_reader_id(league_id,user_id), search_public(q,sport_id=None,limit=20,offset=0). Repository access_metadata(conn,...), member_previews(conn,...), search_discoverable(conn,q,sport_id,limit,offset).

## Task 2: Native/review/evidence

- [x] Native metadata/private/member entitlement, exact names-only previews, independent visibility/membership revocation and pg_trgm ranking/filter/paging/bounds/bound query values.
- [x] Rerun prior league/member/admission native suites; one independent final review, final backend, docs/evidence/hash/link/diff checks and owned-resource cleanup.

## Execution ledger

- Ruling: Retain HTTP discovery policy and rechecks; service access returns internal facts, not an externally callable unfiltered preview.
- Pre-flight: Existing __new__ adapter unit fixture already injects read service; switch metadata mock target to its access method with assertions retained. End-to-end JWT/SQL tests remain unchanged.

- Task 1: complete. Guarded baseline 465/465; focused RED five missing-operation assertions plus one passing legacy case, GREEN 6/6. Adapter mock target migrated with unchanged assertions; end-to-end JWT/public search tests unchanged. Full backend 471/471; non-discovery model AST and read dependency boundaries verified.
- Task 2: complete. [Native evidence](../../modernization/evidence/mod-038-league-discovery-postgres-2026-10-30.json) PASS: metadata/full-access/private/missing and names-only scope; actual pg_trgm ranking/tie order, filters/page/clamps/bound inputs/short-query no I/O; separate-connection visibility/membership and pre-query revocation; legacy delegates. All preceding native suites rerun. Combined report supersedes prior hashes; old reports retained.
- Independent final review no Critical/Important/Minor findings; reviewer focused guarded suite 6/6. No fixes required. Final backend 471/471; current hashes, links and diff checked.
- Owned random database (including synthetic extension) and container removed. Current checkout uncommitted. Three planned league slices remain as listed above. No application schema/hosted/frontend/dependency/startup/deployment changes.
