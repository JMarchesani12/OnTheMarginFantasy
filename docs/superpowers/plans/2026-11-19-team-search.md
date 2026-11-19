# Team Search Implementation Plan

> Superseded storage decision: the user subsequently approved database-owned aliases. See `docs/superpowers/specs/2026-11-19-school-alias-database-design.md` and its implementation plan. JSON remains offline seed/test data only; the frontend bundled copy was removed.
> **For agentic workers:** Use superpowers:executing-plans inline with test-driven-development. Review with requesting-code-review before completion.

**Goal:** Recognize alternate team names and misspellings consistently across team searches.
**Architecture:** Versioned provider alias catalog, matching Python/TypeScript utilities, shared behavioral cases, and list-level strong-match-first fallback. Keep current APIs and display names.
**Tech Stack:** Python/Flask, React/TypeScript, JSON data; unittest and Node tests.
**Spec:** docs/superpowers/specs/2026-11-19-team-search-design.md

## Global Constraints

No renamed records, automatic selections, fuzzy short abbreviations, lost authorization, or runtime external requests. Keep tier/conference/date filters. Preserve API shapes and limits.

## Review Focus

- Ambiguous aliases and overlapping school names must not leak unrelated identities.
- Typo fallback must not overwhelm exact results or split one query between opponents.
- Punctuation, accents, Saint/State, and Unicode normalization agree in both languages.
- Long or repeated-token queries remain bounded and cannot reuse one candidate token.
- Backend/frontend catalogs and matcher behavior remain synchronized after independent deployments.

### Task 1: Catalog and shared matching policy

**Files:** api/data/team_search_aliases.json; front-end/src/data/teamSearchAliases.json; scripts/team-search/; api/utils/team_search.py; front-end/src/utils/teamSearch.ts; shared behavior fixtures and tests.
**Interfaces:** rank_team_search_match(name, query) / rankTeamSearchMatch(name, query) -> number; normalize helpers; strong rank >= 50, fuzzy 1..49; filterTeamSearch<T>(items, query, names) -> T[].
- [x] Seed aliases from public metadata with source URLs/date and repeatable generation; no network in tests/runtime.
- [x] Write literal behavior cases for aliases, ranking, ambiguity, typo boundaries, and malformed/long queries; run RED.
- [x] Implement both matchers and catalog checks; run GREEN.

### Task 2: Connect all team search surfaces

**Files:** api/endpoints/schedule/read_service.py; draft, roster, conference schedule TSX; dailyScoreboard.ts; UI hints; integration tests.
**Interfaces:** Existing endpoints and payloads unchanged. Filter strong matches first; show fuzzy matches only if no strong result satisfies current filters.
- [x] Write backend service and actual frontend behavior regressions; run RED.
- [x] Connect shared matching and list fallback; retain server-side scope and grouping.
- [x] Run complete backend/frontend tests and frontend build; inspect diff and request fresh review. Fix important findings with regression tests.


## Execution and validation

Implemented inline in the current workspace, retaining the session's established sandbox fallback for Git worktree creation. No commits, deployment, or hosted database changes.

Task 1 complete: 864 provider identities, offline rebuild/sync script, vetted UConn/USC/OSU overrides, shared Python/TypeScript matchers, bounded edit distance and candidate caches, and literal cross-language behavior fixtures. Search uses bundled data and introduces no dependencies or schema migration.

Task 2 complete: backend team lookup, draft, roster/free agents/trade partners, conference schedule, and daily scoreboard use the shared rules. Strong-match-first fallback runs after current eligibility/conference/tier filters. Scoreboard names are matched separately. API shapes, scope, limits, displayed names, and team IDs stay intact. Inputs describe names/abbreviations/typos with associated accessible hints.

Fresh review identified an important identity leak: accepting a known name prefix allowed USC Upstate to inherit USC Trojans aliases (and Iowa Wesleyan to inherit Iowa aliases). Observed failing fixtures in both languages, removed arbitrary-prefix identity assignment, and generated only actual school-name/known-mascot combinations from provider metadata. The regression fixtures pass in both languages. No important findings remain; no minor findings deferred.

Verification: `python3 api/tests/run_isolated.py` — 869 passing; `node --test --experimental-strip-types tests/*.test.ts` from front-end — 261 passing; `npm run build` — passing; `git diff --check` — clean. Added utility boundary fixtures also pass separately. Browser components were exercised through the existing synthetic harness; no live browser/deployed-service check is claimed.
