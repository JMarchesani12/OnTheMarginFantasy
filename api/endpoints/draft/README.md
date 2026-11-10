# Draft domain boundaries

HTTP routes resolve a verified `UserActor` and call a service. Services own policy and transactions; repositories own named SQL queries and use the supplied connection. No service/repository imports the configured engine, Flask handlers, jobs, or legacy model.

| Operation | Service | SQL owner |
| --- | --- | --- |
| Member snapshot, completed-state repair, next unpicked turn | `snapshot_service.py` | `snapshot_repository.py` |
| Commissioner order/start/pause/resume/finalize; settings and turn seeding | `control_service.py` | `control_repository.py` |
| Live/manual allocations, caps, random buckets, timeout rotation/auto-pick, membership/round lookups | `pick_service.py` | `pick_repository.py` |

`DraftPickService.pick_live(actor, ...)` is the interactive allocation boundary. `pick_live_for_job`, `allocate_manual_for_job`, and `process_timeout_for_job` identify trusted operations. Manual HTTP allocation remains disabled (410). The timeout worker calls the trusted service; its deadline query is also in the repository. Listener snapshots call `snapshot_for_job`; sockets retain their verified-session membership check before a trusted snapshot. No worker/listener startup behavior changes here.

The former `draftModel.py` facade is retired. Tests and tools call pick, control and snapshot services directly, including explicit job and verified-user-ID operations. Pick helper overrides remain on `DraftPickService`; no replacement facade is introduced.

Allocation, slot insertion, state advance and finalization use one connection/transaction. Existing notification placement is preserved: ordinary live pick publication remains HTTP post-commit; ordinary auto-skip does not gain notifications. MOD-023 publication reliability, MOD-025 replay/permutation/concurrent-start policy and MOD-034 startup ownership remain separate.

Fresh backend/native verification and current source hashes: [completion evidence](../../../docs/modernization/evidence/mod-038-draft-complete-postgres-2026-11-02.json). Earlier reports are historical; the completion report reruns all prior draft slices.


## Shared ownership reads — MOD-033, 2026-11-09

Draft live/manual existence and scalar conference counts plus free-agent
league/member existence and grouped counts delegate through their existing
repository methods to `utils/ownership_reads.py`. Helpers use only the supplied
connection and return the raw result; services retain authorization, cap policy,
locks, writes and timing. Draft DISTINCT-team counts and free-agent active-row
counts intentionally differ. Explicit NULL member filtering stays constrained;
only omitting that helper argument requests a league-wide existence read.

Auto-pick/trade-specific query migration and alternate trade-helper retirement
remain follow-ups. Existing `_apply_trade` transfer and checked `apply_trade`
application are distinct contracts. No caching or query reduction is claimed.
Current [local evidence](../../../docs/modernization/evidence/mod-033-ownership-reads-2026-11-09.json)
and [native PostgreSQL evidence](../../../docs/modernization/evidence/mod-033-ownership-reads-postgres-2026-11-09.json)
cover this extraction; earlier stage reports remain historical.
