# Draft boundaries

HTTP routes resolve a verified UserActor and call services. Services own policy/transactions; repositories use supplied connections. Snapshot, commissioner controls and allocation live in snapshot_service, control_service and pick_service with their corresponding repositories.

DraftPickService.pick_live is the interactive allocation boundary. Explicit pick_live_for_job, allocate_manual_for_job and process_timeout_for_job ports are trusted operations; manual HTTP allocation remains disabled. The timeout worker uses the trusted service. Listener/socket snapshot delivery must pass fresh session/member checks.

Allocation, slot insertion and state advance share a transaction. Ordering/start/control operations validate current membership and serialize state transitions. The web listener publishes authorized snapshots after committed changes; room membership alone does not authorize delivery. Development/production startup ownership belongs to runtime, not this domain.

Ownership helpers in utils/ownership_reads.py use the supplied connection. Services retain cap rules, locks, writes and timing. See [domain rules](../../../docs/domain-rules.md) and [operations](../../../docs/operations.md).
