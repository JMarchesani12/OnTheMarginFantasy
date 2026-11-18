# MOD015 constraint preparation implementation plan

> **For agentic workers:** execute inline with superpowers:executing-plans. User owns commits/integration. No configured-target DDL for these constraints.

**Goal:** Prepare an atomic, replay-safe additive migration and native proof for approved membership/game reference policy.
**Architecture:** One SQL transaction guards legacy catalog and dirty references, adds four parent keys and six composite FKs plus membership NOT NULL, then verifies exact replay definitions. A marked-local native harness proves clean/replay, dirty/drift refusal, direct writes/parent changes and deletion semantics.
**Tech stack:** PostgreSQL17.6, psycopg2/SQLAlchemy, existing owned UUID fixture helpers.
**Spec:** ../specs/2026-11-17-mod-015-constraint-design.md

## Global constraints

No application-data rewrite, baseline/index removal, cascade-policy changes, invented mappings or target constraint rollout. Preserve nullable participants/phase; phase SET NULL applies only seasonPhaseId. User integration untouched.

## Review focus

- Same-name constraints or altered delete/validation/index definitions must not pass replay by name.
- NULL cannot bypass required membership sport validation; valid nullable game references remain allowed.
- Parent updates/direct writes cannot break sport/season agreement.
- Failure after any additive DDL must rollback all changes and preserve rows.
- SET NULL composite phase FK must not null out mandatory season; other existing delete actions remain equivalent.

## Task1 migration and native acceptance

- [x] Native RED harness fails for missing migration; only owned local fixture databases.
- [x] Author api/migrations/20261117_seasonal_reference_integrity.sql using explicit transaction/timeouts/locks and exact catalog replay guards.
- [x] Prove clean upgrade/replay, each dirty FK/null case, legacy/same-name drift, direct bad writes/parent changes, nullable references and phase/home/away/season deletes. Verify data/catalog cleanup.
- [x] Write preflight/rollout guidance and frozen evidence. Run focused/full affected suites; one fresh combined closeout review with snapshot tooling. No target application, staging/commit/push/deploy.

Local preparation/inventory execution complete with one scoped review and single material-fix pass. Explicit additional user approvals permitted the independently recorded MOD017/MOD015 live rollouts; both applied/verified with dated snapshots. This is not full hosted/browser/security acceptance: release/privilege/Vercel/runtime/job follow-ups remain in [closeout](../../modernization/audit-closeout-2026-11-17.md). User integration untouched.
