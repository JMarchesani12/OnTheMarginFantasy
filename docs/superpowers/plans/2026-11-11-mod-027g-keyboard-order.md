# MOD-027G Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans, established native execution.

**Goal:** Finish MOD027 application work with keyboard draft order moves.
**Architecture:** Parent adjacency handler mutates existing IDs/ranks; editor owns only focus/announcement presentation.
**Tech Stack:** React/TypeScript and existing Node harness.
**Spec:** docs/superpowers/specs/2026-11-11-mod-027g-keyboard-order-design.md

## Global Constraints
Keep authorization/save/drag/remove/randomization contracts, preserve earlier working files; no commit/deploy.
## Review Focus
Boundary focus must stay with member; stale/invalid movement cannot corrupt permutation.
### Task 1
- [x] Actual editor/parent regressions RED, then minimal move/focus/status implementation GREEN.
- [x] Full frontend/build/import/diff, fresh review and material fixes if needed.
- [x] Audit bounded MOD027 closure/evidence; explicitly retain browser/runtime followups and minors.
