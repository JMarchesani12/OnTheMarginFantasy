# MOD036 Local Audit Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans, inline audit-only continuation.

**Goal:** Produce bounded bundle/native component/keyboard/offline-provider evidence without product changes.
**Architecture:** Controlled Vite/esbuild outputs, standalone real-component fixture, native CDP using fresh Chrome profile, real tier-loader with canned fetch/tempcache.
**Tech Stack:** Existing Node/TypeScript/Vite/esbuild/React, installedChrome; no new dependencies.
**Spec:** docs/superpowers/specs/2026-11-16-mod-036-local-audit-design.md
## Global Constraints
No app/configured env/DB/auth/provider/job/behavior/deploy/commit change. Preserve prior MOD018 files. Only controlled build/fixture/server/profile/tempcache writes, exact cleanup; optimizations deferred.
## Review Focus
- Production build never loads repository env; component data/hook replacements and scope limits explicit.
- Manifest static/dynamic closure bytes count shared chunks once, no gzip/disk/network conflation.
- Native keyboard/focus/order evidence actual components; frame-settle timings not ReactCPU or full pages.
- Tier probes exercise existing loader/parser boundary, not Pythonclient/CLI; failures/cache effects preserved, no livefetch.
- Unique artifacts/provenance/failure and exact child/server/profile/cache cleanup verified.
### Task1
- [x] RED audit helper/closure/provider-cache tests, implement controlled runner/fixture GREEN.
### Task2
- [x] Existing checks and controlled build/native browser/provider probes; validate artifacts/cleanup.
### Task3
- [x] Bounded findings/status/report, freshreview and materialfixpass ifrequired; keep uncommitted.
