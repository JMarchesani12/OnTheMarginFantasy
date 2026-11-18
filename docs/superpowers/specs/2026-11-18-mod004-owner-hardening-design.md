# MOD-004 owner-scoped browser hardening

The maintainer chose preparation/testing of owner-scoped hardening on November 18. Production execution is a separate approval. The deployed frontend and API are on `514f115`; the frontend uses Supabase Auth and the authenticated backend profile API, and the maintainer confirmed no external direct-table consumers.

Remove PUBLIC/anon/authenticated privileges from all existing public tables and sequences, including authenticated User SELECT. Remove public table/sequence defaults for creator postgres. Preserve service_role/backend access, owners, RLS/policies, routines, Auth/storage schemas and all supabase_admin defaults. Provider-created future objects can therefore still regain browser grants: this is bounded hardening, not completion of all future-object hardening.

Approaches considered: full two-creator hardening needs unavailable platform authority; deferring everything preserves unnecessary current grants. The maintainer selected owner-scoped preparation. No role elevation or partial execution of the old proposal.

Use a new versioned review package, leaving the old proposal/baseline immutable. Exact before/after catalog state guards must refuse drift, extra public relations, inherited/privileged browser roles, column grants or unexpected defaults. Apply and recovery are standalone atomic transactions with timeouts and effective privilege postconditions. Recovery accepts only the exact hardened state and restores the exact observed ACLs/defaults. A versioned manifest pins sources and states; a live rollout receipt will serve as the execution ledger if separately approved. No migration ledger table or application rows are added.

Native tests run in a dedicated disposable loopback PostgreSQL container with a nonsuperuser postgres owner, a separate fixture administrator and synthetic objects. Prove denial, backend preservation, future postgres denial, deliberately preserved provider defaults, drift refusal, rollback and recovery. Authenticated production/browser delivery and remote database role confirmation remain separate acceptance gates.
