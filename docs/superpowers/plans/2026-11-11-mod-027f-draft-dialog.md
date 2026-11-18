# MOD-027F Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans; established native execution.

**Goal:** Accessible draft completion with native modal behavior and safe focus restoration.
**Architecture:** Focused dialog lifecycle hook plus scoped page presentation; retain summary markup/styles.
**Tech Stack:** React/TypeScript, existing Node controlled harness, native HTML dialog.
**Spec:** docs/superpowers/specs/2026-11-11-mod-027f-draft-dialog-design.md

## Global Constraints
No dependencies/API/schema/controller changes; preserve user work; no commit/deploy.
## Review Focus
Obsolete contexts must not restore focus or retain old modal; native closed dialogs must stay hidden.
### Task 1
- [x] Write actual-hook/component/page regression tests and observe RED.
- [x] Implement native showModal/close lifecycle, title focus/restoration, scope-bound completion/dismissal and native styling.
- [x] Run full frontend/build/import/diff; fresh review, material fixes RED→GREEN, audit evidence with browser limits.
