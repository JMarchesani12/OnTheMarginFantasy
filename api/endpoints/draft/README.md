# Draft domain boundaries

HTTP routes resolve a verified `UserActor` and call a service. Services own policy and transactions; repositories own named SQL queries and use the supplied connection. No service/repository imports the configured engine, Flask handlers, jobs, or legacy model.

| Operation | Service | SQL owner |
| --- | --- | --- |
| Member snapshot, completed-state repair, next unpicked turn | `snapshot_service.py` | `snapshot_repository.py` |
| Commissioner order/start/pause/resume/finalize; settings and turn seeding | `control_service.py` | `control_repository.py` |
| Live/manual allocations, caps, random buckets, timeout rotation/auto-pick, membership/round lookups | `pick_service.py` | `pick_repository.py` |

`DraftPickService.pick_live(actor, ...)` is the interactive allocation boundary. `pick_live_for_job`, `allocate_manual_for_job`, and `process_timeout_for_job` identify trusted operations. Manual HTTP allocation remains disabled (410). The timeout worker calls the trusted service; its deadline query is also in the repository. Listener snapshots call `snapshot_for_job`; sockets retain their verified-session membership check before a trusted snapshot. No worker/listener startup behavior changes here.

`draftModel.py` is a SQL-free compatibility facade. It inherits pick behavior, preserving legacy public/private helper dispatch and db-only construction; existing control/snapshot wrappers remain. Keep it while tests/tools/jobs outside this domain still use its historical API. Do not add new SQL or transport policy to it.

Allocation, slot insertion, state advance and finalization use one connection/transaction. Existing notification placement is preserved: ordinary live pick publication remains HTTP post-commit; ordinary auto-skip does not gain notifications. MOD-023 publication reliability, MOD-025 replay/permutation/concurrent-start policy and MOD-034 startup ownership remain separate.

Fresh backend/native verification and current source hashes: [completion evidence](../../../docs/modernization/evidence/mod-038-draft-complete-postgres-2026-10-30.json). Earlier reports are historical; the completion report reruns all prior draft slices.
