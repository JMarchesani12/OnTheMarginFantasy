# MOD-027C Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans, inline execution authorized.

**Goal:** End stuck loading after an ineligible query.
**Architecture:** Existing effect early-return reset; preserve cancellation.
**Tech Stack:** React/TypeScript and existing Node harness.
**Spec:** docs/superpowers/specs/2026-11-10-mod-027c-team-search-design.md

## Global Constraints
Preserve prior uncommitted work; no API/dependency/context redesign or commit/deployment.

## Review Focus
Late cancelled responses must not restore state or clear a newer request's loading.

### Task 1: Reset and verify
- [x] Add actual-component timer/transport regressions, run RED.
- [x] Add setLoading(false) to ineligible branch, run GREEN/full frontend/build/import/diff.
- [x] Fresh read-only review, record audit evidence/limits; leave uncommitted.
