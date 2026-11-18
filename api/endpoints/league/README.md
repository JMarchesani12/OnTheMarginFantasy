# League domain

Edit implementations in the cohesive packages:

| Package | Responsibility |
| --- | --- |
| `admission/` | Join-request lifecycle and admission failures |
| `members/` | Member edits and commissioner removal |
| `administration/` | League creation, updates and deletion |
| `reads/` | Discovery, details, rules, conference and member summaries |
| `lifecycle/` | Ordered global status synchronization |

Routes and `leagueEndpoints.py` own HTTP composition, including explicit schedule
and lifecycle service callbacks. Services own policy/transaction
scope; repositories receive connections and own SQL. Shared rules stay in
`api/rules`; scheduling algorithms remain in the schedule domain.

Use canonical package paths for imports/patch targets. Root contracts.py remains an alias for admission.contracts because serialized legacy exception paths remain supported and tested. Domain services do not import Flask handlers, configured engines or compatibility models.
