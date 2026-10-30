# League domain

Edit implementations in the cohesive packages:

| Package | Responsibility |
| --- | --- |
| `admission/` | Join-request lifecycle and admission failures |
| `members/` | Member edits and commissioner removal |
| `administration/` | League creation, updates and deletion |
| `reads/` | Discovery, details, rules, conference and member summaries |
| `lifecycle/` | Ordered global status synchronization |

Routes and `leagueEndpoints.py` own HTTP composition; `leagueModel.py` preserves
legacy method contracts and schedule composition. Services own policy/transaction
scope; repositories receive connections and own SQL. Shared rules stay in
`api/rules`; scheduling algorithms remain in the schedule domain.

Root service/repository/contracts modules are compatibility aliases, not separate
implementations. Old and canonical imports resolve to the same module objects,
classes, exception types and patch targets. Prefer canonical package imports in
new code. Keep aliases while existing callers/tests/tools use those paths.

This organization does not change routes, authorization, lifecycle write timing,
transactions, schema, scheduling or deployment.
