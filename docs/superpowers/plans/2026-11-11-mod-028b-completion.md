# MOD-028B Completion Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans; user requested finish remaining migration.

**Goal:** Complete safe error consolidation for application HTTP APIs/consumers.
**Architecture:** Shared response/JSON boundary, classified read/write fallbacks, existing trusted UI formatter; preserve special statuses and transport.
**Tech Stack:** TypeScript/React, existing controlled Node harness and nativeResponse.
**Spec:** docs/superpowers/specs/2026-11-11-mod-028b-completion-design.md
## Global Constraints
No authSDK/refresh/backend/schema/transport retries/dependencies/deployment/commits. Preserve prior transaction batch working files.
## Review Focus
Profile404/409, draft denial statuses, multi-step-save uncertainty, cancellation and read-only retries remain intact.
### Task 1: HTTP APIs
- [x] Inventory/property and transport-equivalence tests RED, shared response/JSON helpers and all data API migration GREEN.
### Task 2: UI consumers
- [x] Read/admin/draft/settings feedback regressions RED; trusted catches with read/write messages GREEN; retain old meaningful regressions.
### Task 3: Review/closure
- [x] Full frontend/build/import/diff and fresh review; material fixes RED→GREEN; inventory/evidence/status bounded completion.
