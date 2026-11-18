# Audit closeout inventory implementation plan

> **For agentic workers:** execute inline using superpowers:executing-plans; user owns integration. No staging/commits/push/deploy.

**Goal:** Capture a fresh metadata-only hosted snapshot and a concrete remaining-decision register.
**Architecture:** Guarded Python collector reuses baseline catalog queries, coordinates pg_dump with an exported read-only snapshot, and publishes checksummed artifacts only after secret screening and completeness checks. Hosted service verification remains read-only and evidence-labelled.
**Tech stack:** Python/psycopg2/SQLAlchemy, existing dotenv configuration, cached PostgreSQL17.6 Docker client.
**Spec:** ../specs/2026-11-17-audit-closeout-inventory-design.md

## Global constraints

Read-only hosted transactions/TLS, no application rows or mutation, no credentials in Git/output, immutable frozen baseline and dated snapshots, preserve unrelated services/user integration. Direct/session connection required; don't pretend transaction pooler supports LISTEN/session locks. Render installation alone doesn't prove tool availability.

## Review focus

- Snapshot schema/catalog consistency and incomplete outputs cannot be labelled successful.
- Secret-bearing definitions/configuration must not be exposed by logs or committed artifacts.
- Exact target/actor and metadata scope are explicit; schema-only is not a full platform/data backup.
- Existing equivalent/invalid/constraint indexes are not approved for creation/removal by observation.
- Missing runtime and browser evidence cannot be represented as verified deployment.

## Task1 snapshot collector

- [x] RED tests for existing-output refusal, secret-screening refusal, read-only/TLS/session endpoint guards, dump failure leaves no PASS, manifest checksum completeness.
- [x] Implement scripts/modernization/capture_db_snapshot.py and tests/test_snapshot_capture.py; no imports of app/runtime/jobs.
- [x] Capture public schema/catalog with same exported snapshot, explicit source hashes and platform exclusions; verify checksums and review generated definitions. Run existing MOD015 counts only and read-only MOD017 preflight classification.

## Task2 closeout register and verification

- [x] Inspect current browser Supabase consumers, live grants/defaults/actor authority, constraint counts and hosted index state; document actual decisions and recommended sequencing.
- [x] Verify connected Render service metadata if tools become exposed; otherwise record exact remaining access requirement and continue independent work.
- [x] Write docs/modernization/audit-closeout-2026-11-17.md, snapshot maintenance README and links. Run focused tests/full affected audit suite, one final scoped review, and preserve user-owned integration. Do not execute proposals or claim full hosted/browser acceptance.

Local preparation/inventory execution complete with one scoped review and single material-fix pass. Explicit additional user approvals permitted the independently recorded MOD017/MOD015 live rollouts; both applied/verified with dated snapshots. This is not full hosted/browser/security acceptance: release/privilege/Vercel/runtime/job follow-ups remain in [closeout](../../modernization/audit-closeout-2026-11-17.md). User integration untouched.
