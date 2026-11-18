# Home Tabs Accessibility Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans; preserved native inline method, one fresh review. User owns commits.

**Goal:** Complete keyboard/focus and tab-panel semantics without changing Home's data behavior.
**Architecture:** Manual activation; arrow focus, Enter/Space/click selection, stable tab/panel IDs, one tab stop. Preserve active-only content behavior.
**Tech Stack:** Existing React/TypeScript/hook tests and isolated native Chrome fixture; no dependency installation.
**Spec:** [Roadmap: Home contract](../../modernization/post-audit-implementation-2026-11-16.md#home-tabs); [native finding/APG reference](../../modernization/mod-036-local-ui-tier-audit.md#keyboard-findings).

## Global Constraints

No auth/profile/request/Retry/paging/page-size changes, new hidden background workflows or full-screen framework. No configured app/user/provider/browser profile. Historical evidence immutable; leave uncommitted.

## Review Focus

- Arrows focus without activating/fetching; Enter/Space/click activate exactly once.
- Stable IDs/aria-controls/labelled panels match; inactive content is hidden from focus/AX.
- Native button behavior and roving tab stop preserve entry/exit and wraparound.
- Account/stage cancellation/loading/error/search paging tests remain intact.
- Existing audit native assertions expect the old gap; update intent/version rather than suppressing failures.

## Task 1 — RED semantic and behavior coverage

**Create:** `front-end/tests/homeTabs.test.ts`.
**Retain:** `front-end/tests/homeLeagueFeedback.test.ts`, existing profile/request/discovery tests.

- [ ] Pin one active tab stop, selected state and stable tab/panel relations. Exercise ArrowLeft/Right wrap, Home/End focus, Enter/Space/click activation and ordinary Tab exit.
- [ ] Assert arrow movement alone changes neither selected panel nor search/fetch calls. Assert inactive panel content cannot receive focus and existing data/Retry state is preserved.
- [ ] Run focused tests and record RED from current missing semantics; hook tests may model refs/events but do not substitute for native focus checks.

## Task 2 — Minimal Home change

**Modify:** `front-end/src/screens/Home/Home.tsx`, `Home.css` only if hidden panel CSS needs explicit protection.

- [ ] Keep manual activation. Add stable tab IDs, controls/panel labels, roving tabIndex and focus refs/key handling. Handle arrow/Home/End with preventDefault; preserve native Enter/Space/click selection.
- [ ] Preserve conditional content lifetime. If both panel shells must exist for valid controls targets, keep inactive workflow content unmounted/hidden, with computed display:none despite author CSS; do not merely hide interactive retained content visually.
- [ ] GREEN focused tests, then from front-end: `node --experimental-strip-types --test tests/*.test.ts`; `node node_modules/typescript/bin/tsc -b --pretty false`; run existing frontend import checker from repository root.

## Task 3 — Native acceptance and evidence

**Modify/create:** current `scripts/modernization/mod036_browser.mjs` expectations or a focused versioned Home acceptance entry; add an audit regression test for its changed expectations. Preserve prior raw artifacts.

- [ ] Replace the baseline assertion “ArrowRight remains on Your Leagues” with the intended movement contract. Native Chrome: arrows/wrap and Tab exit, Enter/Space activation, computed hidden-panel visibility, accessible relationships and retained focus. Use existing synthetic hooks/API fixture, not configured auth.
- [ ] A keyboard-only run need not repeat all bundle/timing measurements. If detailed repeated-mount timings are reused, first add a generation/commit marker and test it; old two-RAF readings are not precise commit measurements.
- [ ] Record current source/keyboard evidence; no full AT/mobile/production acceptance claim. One fresh scoped review, material fixes once, update MOD036 finding status and leave uncommitted.

**Done when:** native and focused checks demonstrate the chosen tab contract, existing Home freshness/feedback tests still pass and inactive panels do not expose controls. Full assistive-technology acceptance remains separately recorded.
