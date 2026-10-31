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

The 10 temporary root service/repository forwarders were retired after every
first-party test/tool import and verification manifest moved to these packages.
Use canonical package paths for imports and patch targets; the retired Python
module paths intentionally no longer resolve. Canonical implementation/class
module qualifications are unchanged.

Root contracts.py remains an alias for admission.contracts because the explicit
old exception pickle path is still supported/tested. leagueModel.py and the other
domain Model facades remain while runtime/test/tool callers use their contracts.
This cleanup does not retire those interfaces or unrelated dormant features.

This organization does not change routes, authorization, lifecycle write timing,
transactions, schema, scheduling or deployment.

[Retirement ledger](../../../docs/superpowers/plans/2026-10-30-league-legacy-forwarder-retirement.md). Complete native league checks were rerun after retirement; current source capture is in the existing league-folders evidence report. Older per-slice reports are historical and may reference removed forwarders.
