# MOD-015 consumer inventory and guarantees

2026-11-05. User policy: every draftable team is assigned to a conference; there is
no independent/uncapped fallback. Exact season first, valid default only when exact
season absent, other years ignored. Invalid exact-season data cannot be masked by
a default. SQL selection lives in `api/utils/conference_membership.py`; existing
baseline partial unique keys establish one membership per team/sport/year scope.
Read-only preflight detects duplicate/invalid scopes; no schema rollout occurred.

| Consumer | Delivered behavior / verification |
| --- | --- |
| Schedule `search_teams`, `owned_teams`, `conference_games` | One effective conference; preserved search ranking/limits/owner fields and game cardinality. Owned rows retain null metadata for missing/league-sport mismatch. |
| Roster `member_teams`, `available_teams` | One row per slot/team, nullable metadata retained; sport/year/ownership/pending/read predicates preserved. |
| Draft `snapshot_picks` | One row per pick; history retained with null metadata when missing/wrong league sport. |
| Draft `conference_info`, `member_conference_count`, `owned_conference_count`, `random_conference_team` | Same effective conference for lookup/caps/pool. Manual/live and timeout insertion validate affected/retained roster mappings; no independent bucket/helper. |
| League `season_conferences` | Effective team count per configured conference, including zero counts, exact sport/year scope. |
| Trade `conference_counts`, `incoming_confs`, trusted validation/application | League context required; effective retained/incoming counts; affected and retained mappings required before ownership writes. |
| Workflow `team_conference_info`, `member_conference_counts`, `roster_violations` | Same effective selection; free-agent submit/apply require mappings. Read-only cap-violation projection remains cap-specific. |
| Ingestion `shared_conferences` | Same effective conference for both participants and requested season, preserving phase-routing semantics. |
| Ingestion `upsert_game` | Supplied-transaction FOR SHARE validation of season sport, phase season and participant sports before insert/update. Nullable external participants/phase preserved. |
| UI draft/history/roster/team lookup/schedule/grouping | Missing metadata displays Conference unavailable. Explicit data labels and landing marketing example copy retained. |

Runtime source inventory found ConferenceMembership SQL in these repositories only.
Scoring consumes phase/game facts rather than a direct membership query; formulas,
tiers, phase rules and scoring projections were not rewritten. Sport catalog and
season metadata creation have no membership selector; no guess/backfill/import or
real provider run was added. Verification fixtures/tools deliberately upgrade old
seasonless schemas, independent candidates and duplicate-row expectations to the
new policy; stored historical evidence is not overwritten.

## Evidence and remaining schema boundary

[Native evidence](evidence/mod-015-postgres-2026-11-05.json) captures frozen schema
plus current identity/week/ownership guards, actual query families and commands,
season/current/other/missing/invalid sport cases, seasonal caps, missing-mapping
rollback, mapped-only auto selection, timeout retained-roster state rollback,
nullable cross-sport historical metadata, ingestion references/nullable opponents,
and clean/dirty aggregate preflight results. Affected prior ownership, complete
allocation/snapshot/finalization/control/order, transaction, calendar/member/view/
ingestion and roster suites are rerun in the owned marked database.

Backend672/672, frontend64/64 and production build pass. Independent review found
two material gaps: timeout insertion lacked retained-roster validation; three
historical read projections omitted league-sport agreement. Both reproduced RED
and were fixed in one pass with isolated and native regressions. No other material
findings or deferred minors. See [plan](../superpowers/plans/2026-11-05-mod-015.md).

[Preflight/proposal](../../db/preflights/MOD-015.md) is delivered, with no migration.
Arbitrary SQL/parent edits are not constrained by the new application guard.
Composite parent keys/FKs and nullable membership sportId need target catalog/data
review and an explicit migration decision before rollout; full mapping coverage
cannot be guaranteed by a basic FK. No target metadata/data access, automatic
cleanup, configured job, dependencies, scheduler change or deployment occurred.
Historical snapshots/remapping and fair draft scaling remain separate work.
