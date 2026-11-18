# Database upgrade preflights

These aggregate SQL checks are for explicitly authorized targets. Inspect schema/state first; a clean preflight is a point-in-time observation, not permission to apply SQL. Existing application rollouts are recorded in [history](../history/README.md) and must not be replayed blindly.

| Read-only check | Upgrade / invariant |
| --- | --- |
| 20261104_user_identity.sql | api/migrations/20261104_user_identity_unique.sql; linked profile UUID uniqueness, nullable legacy UUIDs preserved |
| 20261104_week_score_identity.sql | api/migrations/20261104_week_score_identity.sql; league/week/member score identity and same-league references |
| 20261104_ownership_integrity.sql | api/migrations/20261104_ownership_integrity.sql; same-league member ownership and nonoverlapping half-open intervals |
| 20261105_seasonal_consistency.sql | api/migrations/20261117_seasonal_reference_integrity.sql; conference/game sport-season/phase/team consistency and effective mappings |

Before a change: capture a fresh schema/catalog snapshot, confirm PostgreSQL version/actor and current definitions, run the relevant check read-only, then review SQL/timeouts/recovery and obtain target-specific approval. Nonzero inconsistency counts require reviewed remediation; never guess conference assignments, merge identities, erase history or deduplicate rows automatically. Null UUIDs and permitted empty/adjacent ownership intervals have intentional semantics; use the migration's exact guards.

Apply only the reviewed transaction/script using a stop-on-error client. The migrations refuse dirty data/catalog drift and preserve existing delete behavior; do not bypass those guards. Inspect both statement and commit outcomes. Verify definitions and aggregate counts afterward, capture the resulting snapshot and retain an execution receipt. Other environments may differ from recorded production history.

Ownership index creation is separate: [index runbook](../indexes/ownership/README.md) requires concurrent-DDL/autocommit semantics. [Browser privilege SQL](../changes/README.md) is also separately scoped and has an exact-state recovery contract. Do not mix either with baseline initialization or an unrelated migration transaction.
