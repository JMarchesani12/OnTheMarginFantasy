# MOD-040 / MOD-030 Bonuses Editor Move Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, then one fresh final review.

**Goal:** Give the shared Bonuses Editor component ownership with no behavior change.
**Architecture:** Byte-identical move; two consumer import edits. Preserve prior MOD039 pilots.
**Tech Stack:** Existing React/TypeScript/Node checks.
**Spec:** docs/superpowers/specs/2026-11-07-mod-040-bonuses-editor-move-design.md

## Global Constraints

No content/style/payload/route/dependency change. No new facade or mirrored algorithm test. Existing audit checkout, preserve uncommitted work, no backend/native/configured runtime/provider/deploy/commit/push.

## Review Focus

- Moved component bytes and exports remain identical.
- Both consumers resolve the new canonical file without stale source paths.
- CSS remains owned/imported by existing screens with unchanged classes.
- New import graph has no cycles/unresolved literal relative TS/TSX edges.
- Prior MOD039 edits remain intact; move diff is distinguished from earlier work.

### Task 1: Baseline evidence
- [x] Capture original component and consumer bytes/hashes in this plan's ignored workspace.
- [x] Add/run a read-only TypeScript AST relative-import graph verifier before move; record baseline (no new component algorithm tests per MOD030).

### Task 2: Move and verify
- [x] Move screens/CreateLeague/BonusesEditor.tsx to components/League/BonusesEditor.tsx byte-for-byte, update exactly two import strings.
- [x] Verify expected consumer byte replacements against task1 snapshots; verify unchanged component and styles.
- [x] Run graph verifier/full frontend tests/TypeScript-production build; expect PASS, no old source consumers.

### Task 3: Review and handoff
- [x] Fresh independent scoped review; resolve material findings if any.
- [x] Record before/after import map, source hashes, exact check scope and MOD030/MOD040 status.
- [x] Final whitespace/hash check; leave uncommitted with prior work preserved.
