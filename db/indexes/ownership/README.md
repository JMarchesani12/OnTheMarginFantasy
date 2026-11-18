# Member-led ownership index

The index `mod017_owner_member_team` on LeagueTeamSlot(leagueId,memberId,sportTeamId), including acquiredWeek/droppedWeek, is **already applied** on the observed application target. Its stored name is retained for compatibility. See the [execution receipt](../../history/20261117_ownership_index.json).

This package retains the exact guarded SQL for other separately approved environments and recovery reference. It is not an automatic startup migration. No game/transaction index alternative is included.

Use PostgreSQL 17 and psql with autocommit, never an enclosing transaction or --single-transaction. preflight.sql inspects column types, complete index definitions/equivalence, validity/readiness and constraint backing. Existing equivalents skip/review rather than duplicate; same-name drift fails. Concurrent catalog changes still need operator coordination and fresh review. Set an appropriate lock/statement budget before approving a target rollout.

create.sql uses CREATE INDEX CONCURRENTLY and captures a same-session identity receipt. verify.sql checks the resulting valid equivalent definition. Save the transcript and before/after catalog. A failed concurrent build can leave an invalid index; never blind-retry or remove integrity/baseline indexes.

recovery.sql requires explicit same-session approval and exact newly created OID/name/definition/nonconstraint proof. It does not infer ownership after interruption/reconnect or remove existing equivalents. Missing proof/invalid build cleanup needs a separately reviewed recovery. Do not fabricate a creation receipt or use CASCADE.
