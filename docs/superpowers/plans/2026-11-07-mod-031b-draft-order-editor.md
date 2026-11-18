# MOD-031B Draft Order Editor Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline and one fresh final review.

**Goal:** Extract only draft-order rendering/callback forwarding; keep parent state/API/gates.
**Architecture:** ManageLeaguePage → stateless DraftOrderEditor → LeagueMember type. Existing CSS/state/save handlers unchanged.
**Tech Stack:** React/TypeScript, controlled Node JSX tests.
**Spec:** docs/superpowers/specs/2026-11-07-mod-031b-draft-order-editor-design.md

## Global Constraints

Preserve uncommitted MOD039/MOD030 work. No behavior/CSS/API/schema/dependency/keyboard/freshness change. Parent keeps all state, handlers, dialogs, save inputs/buttons and gates. No backend/native/configured runtime/provider/deployment/commit/push.

## Review Focus

- Role/status visibility and self-remove guards stay intact.
- Original memberCount conditions differ from orderedMembers length.
- Drag-over prevents default before forwarding target; callbacks get original IDs/member.
- Parent randomize/reorder/remove/save payloads/errors and save/start messages remain unchanged.
- Component has no state/effects/API imports; parent markup, CSS and unrelated operations stay unchanged.

### Task 1: Characterize parent
- [x] Capture pre-change parent and styles; add controlled real-module hook/JSX harness.
- [x] Run role/status/loading/error/order/drag/randomize/removal/save action regressions on original component: expect PASS.

### Task 2: Extract child
- [x] Add child rendering/forwarding/count mismatch tests and observe RED missing component.
- [x] Create typed stateless components/League/DraftOrderEditor.tsx; replace only parent subtree with props/handlers.
- [x] Run original characterization and child tests; expect PASS.
- [x] Full frontend/build/import graph and parent/style boundary comparison: expect PASS.

### Task 3: Review/evidence
- [x] Fresh independent scoped review; fix material findings failure-first.
- [x] Record source hashes, exact checks and MOD031B/MOD040 scope; preserve prior work.
- [x] Final checks; leave uncommitted.
