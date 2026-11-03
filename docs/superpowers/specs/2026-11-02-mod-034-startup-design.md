# MOD-034 explicit startup design

Status: approved and implemented on 2026-11-02. Approach and design approved by the maintainer in the implementation conversation.

## Intent

Prepare the audit branch for integration by making application, job and test startup predictable. Importing application/domain/job definitions must not load local secrets, create configured database engines, open network connections or launch background work. Explicit runtime entry points may load configuration and construct dependencies.

## Approaches

1. **Selected:** retain notification delivery in the web process, move listener startup out of `create_app`, and control it explicitly from web runtime configuration. This preserves the current Socket.IO delivery topology and supports inactive tests.
2. Disable notifications for every web startup by default. Simpler inactivity, but changes existing deployment behavior unless operators configure it.
3. Move notifications to a standalone worker. Requires a verified cross-process broadcast mechanism and deployment topology; outside MOD-034.

## Proposed behavior

- `create_app` accepts an injected database engine; it registers HTTP and socket handlers but starts no listener. Calling it without an engine may resolve runtime configuration lazily for compatibility; merely importing it must remain inactive.
- Centralize runtime configuration loading and engine construction behind explicit functions. Importing `db` does not read `.env` or construct an engine. Migrate first-party `from db import engine` consumers rather than leaving an eager compatibility global.
- Resolve required Supabase authentication configuration at explicit composition/verification time instead of indexing environment variables during module import. Preserve issuer, audience, algorithm and rejection behavior; missing runtime configuration must fail clearly without logging secret values.
- `dev.py`, `wsgi.py`, and the direct application launch path use one web composition function. Runtime dotenv paths are resolved relative to the API directory, independent of working directory.
- Proposed configuration name: `DRAFT_NOTIFY_LISTENER_ENABLED`. Default enabled at web startup to preserve current behavior. Explicit false disables listener startup. Invalid values fail clearly before launching background tasks.
- Development reload handling must start at most one listener in the serving process, not in both the reloader supervisor and child. Repeated startup wiring in one app must not duplicate the listener.
- Pass the configured engine into the notification listener; retain the existing `DATABASE_URL` notification connection and `SUPABASE_DB_URL` application connection distinction. Do not silently assume the two targets are equivalent.
- Preserve production eventlet setup in its explicit WSGI entry point. Plain module imports outside that runtime path must not monkey-patch the process.
- Make cron, timeout-worker and supported season/rebuild launch paths resolve configuration at execution time. Allow fake dependency injection for launch smoke tests; preserve job timing, calculations, transactions and scheduling behavior.
- Replace touched wildcard bootstrap imports and `from venv import logger`. Correct bootstrap's API-root calculation and remove configuration loading from import paths. Avoid unrelated module moves.
- Document supported runtime versions based on dependency compatibility and actual verification, plus backend/frontend launch and credential-free test commands. Add minimal isolated CI checks only after their commands pass under guarded configuration.

## Verification

- Fresh-process guarded imports and test discovery with configuration cleared and dotenv, engine creation, database connections and network attempts forbidden.
- App factory with fake dependencies: existing health/auth/routes/socket registration, no listener task or database access during construction.
- Fake web runtime tests for default enabled, explicit disabled, invalid configuration, duplicate startup and development reload behavior.
- Fake job/CLI launch tests prove dependencies are resolved only on execution and arguments reach the existing operations. No real job, provider call, listener or application server runs during verification.
- Full existing isolated backend suite without reducing coverage; relevant frontend checks and proposed isolated CI commands. Record tested runtime versions and any remaining compatibility limitations.

## Boundaries and sequence

No hosted configuration changes, restarts, deployment, database changes, credential exports or new paid infrastructure. Preserve the intentionally suspended Render service. Render connection is useful for a later read-only command/configuration inventory, but does not block local implementation. Unknown deployment facts remain explicit.

MOD-025 follows this work as a separate reviewed change: exact member-order permutation validation and lifecycle/concurrency-safe draft start. Its replay outcome and locking strategy will be designed against current pick/control behavior before implementation. No merge of `main` is part of MOD-034; integration and fresh regression verification follow both selected changes.
