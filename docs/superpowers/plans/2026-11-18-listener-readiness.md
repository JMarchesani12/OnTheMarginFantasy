# Worker-local listener readiness implementation plan

> Execute inline with superpowers:executing-plans and TDD; one final scoped review. No user Git integration/production mutation.

**Goal:** Start/stop listener in serving workers while preserving developer startup and readiness semantics.
**Architecture:** Deferred entire WSGI app/runtime construction plus explicit app runtime starter invoked by Gunicorn post_worker_init; standard autoload shim retains explicit config compatibility.
**Tech stack:** Existing Flask/SocketIO/Gunicorn/eventlet/Python.
**Spec:** ../specs/2026-11-18-listener-readiness-design.md

## Constraints/review focus

No live DB/app jobs; synthetic-only child environment. No master-owned listener under preload. Both config paths work; worker replacement gets fresh controller and graceful shutdown stops it. Disabled readiness200, failed/starting enabled readiness503 remain unchanged. Preserve import isolation and default development/reloader behavior. Production root cause inferred from matching reproduction; effective server preload flag unconfirmed.

## Task1 lifecycle fix

- [x] RED deferred-composition/hook tests and real preload reproduction.
- [x] Implement runtime/wsgi/hooks/autoload shim, adjust startup contract tests.
- [x] GREEN focused/full isolated tests; preserve development and readiness contracts.

## Task2 real startup proof/closeout

- [x] Real synthetic Gunicorn normal/preload ×autoload/explicit, disabled and worker-replacement/shutdown checks; close every owned child/server.
- [x] Record source-pinned unique evidence/settings/limits, scoped review, one material fix pass if needed. No rereview; document limits and deployment handoff.

Local execution complete: source-pinned proof4104eaa7647c4ca0bee9db02bfa56ccb,834backend/71audit tests PASS; fresh review no blocking findings. One native-harness failure-cleanup minor deferred. User-owned deployment/hosted acceptance remains open.
