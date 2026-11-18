# MOD-004 owner-scoped hardening handoff — November 18, 2026

Status: **owner-scoped production transition applied and verified** after the maintainer explicitly approved SQL and confirmed leagues load normally. Provider-owned defaults remain deferred. The sections below retain preparation history; see the final rollout record at the end. [Immutable reviewed package and recovery runbook](../../db/proposals/mod004-owner-v1/README.md).

[Fresh access catalog](evidence/mod-004-access-refresh-2026-11-18.json) matches the November 17 post-MOD015 snapshot across tables, policies, object/default/schema ACLs and observed role flags/memberships. All 23 tables and 21 sequences still carry broad browser privileges. The configured postgres actor is NOSUPERUSER, BYPASSRLS, not a supabase_admin member. No grants were changed during collection.

[Exact read-only preflight](evidence/mod-004-owner-preflight-2026-11-18.json) matches the package's before state on the configured database. The migration/recovery files were never sent to that database. This is a point-in-time preflight, not permission to skip fresh guards/snapshots before any later application.

[Native acceptance](evidence/mod-004-owner-native-2d70e37b84b84832b35a21ba519c2642.json): 12 cases passed in a dedicated disposable PostgreSQL 17.6 container. The postgres application owner is a nonsuperuser without supabase_admin membership. The exact packaged SQL applies, refuses replay, removes effective browser access, preserves service reads, denies browser access to future postgres-created objects and restores the exact original state on recovery. Controls cover extra table/view, explicit column grants, unexpected ACL/policy/global defaults, inherited browser role, BYPASSRLS, an injected failed postcondition with rollback, and recovery refusal on ACL/new-object drift. The intentionally deferred provider defaults still grant browser access to a synthetic future provider table. All fixture databases and the owned container were removed. Earlier failed fixture reports remain historical failures, not passing evidence.

## Deployed application checks

[Vercel](evidence/vercel-production-followup-2026-11-18.json) is READY on main commit `514f11574e5cbb6bd2c3a580bf0f68b2033de9b9`, matching the verified Render listener release. Source profile bootstrap reads/provisions through the authenticated backend API; Supabase usage is authentication only. The maintainer previously confirmed no external direct-table consumers.

[Unauthenticated negative checks](evidence/production-auth-boundary-2026-11-18.json): the profile API rejects with 401, permits the expected frontend CORS origin, and the WebSocket server rejects a connection without credentials. This proves entry-point denials only; it does not prove authenticated profile loading, authorized snapshot delivery, reconnect behavior or account isolation.

The user has been asked to confirm basic signed-in profile/league/draft reload behavior and privately check the API and active cron database role/connection mode. No account credentials, JWTs or connection URLs should be provided. Render connector metadata cannot establish environment values. Further authenticated acceptance and remote configuration remain open until evidence is supplied.

### Maintainer response and connection correction

The maintainer cannot exercise drafts during the active season. Draft acceptance is deferred to an approved isolated environment or the next suitable window; no league unlock, new draft, trade or scoring run is authorized to force acceptance. Their response does not separately establish signed-in profile acceptance.

The maintainer reported the Supabase shared pooler on port **6543**, identifying transaction mode. This is a confirmed configuration follow-up, not an unknown connection-mode status. [Supabase connection documentation](https://supabase.com/docs/guides/database/connecting-to-postgres) identifies the same shared pooler on **5432** as session mode. The repository listener and cron session advisory locks require session preservation; current /ready 200 does not establish that guarantee under transaction pooling.

Use the Render Dashboard to change the effective pooler port to 5432 in SUPABASE_DB_URL for the API and both active crons. Align DATABASE_URL as well if present, because runtime requires matching targets. Preserve credentials/other URL options and privately confirm the role is postgres (pooler usernames normally include a project suffix). [Render documents](https://render.com/docs/configure-environment-variables) Save and deploy as applying environment changes to the existing build. Verify the subsequent deployment/startup and /ready; do not trigger real cron work as a test. The connector can update values but cannot read existing secret values, so copying local credentials over unknown remote configuration is inappropriate. No environment changes were made by the assistant.

Keep the owner hardening unapplied while correcting this configuration. Afterward, use the fresh snapshot/approval sequence in the package runbook. The deferred in-season draft acceptance remains explicit rather than silently marked passed.

Maintainer subsequently reports SUPABASE_DB_URL changed and DATABASE_URL absent. [Deployment follow-up](evidence/session-pooler-deployment-check-2026-11-18.json) shows newer live weekly/ingestion deployments at 15:14 UTC, while the API still reports its earlier 14:55:58 UTC deployment. Public health/readiness remain 200/connected, but that does not prove the API has loaded the updated environment. Request API Save and deploy/redeployment, then recheck. Connector metadata cannot independently establish secret URL contents or database role. No jobs were manually triggered and no production privileges changed.

Subsequent API redeployment is now verified: [fresh evidence](evidence/session-pooler-api-live-2026-11-18.json) records live deployment `dep-dbus302jnfac73e5hbv0`, commit `514f115`, finished November 18 at 09:18:11 CST. Health and readiness both return 200, enabled listener connected. This resolves the API-redeployment follow-up based on the maintainer-reported environment correction; the connector still cannot independently inspect secret values or backend role. Draft acceptance remains deferred for the active season. Owner-scoped privilege SQL remains unapplied.

## Approved production rollout — November 18, 2026

The maintainer confirmed leagues load normally and explicitly approved production SQL. The [execution receipt](evidence/mod-004-owner-rollout-2026-11-18-a93560b2a43245678069a2a6ffc5dc06.json) records the exact package hashes, configured target fingerprint, fresh preflight, COMMIT acknowledgement and postcommit verification. Applied only `mod004-owner-v1/apply.sql`, SHA256 `25da872a0bd8dcc1780ec2b5c14739c5add3622fa0f499eb876f32072c39865d`, as the reviewed postgres owner over TLS/session transport. No older proposal, recovery, role elevation, baseline adoption or unrelated migration was run.

Both [before](../../db/snapshots/2026-11-18-before-mod004-owner/manifest.json) and [after](../../db/snapshots/2026-11-18-after-mod004-owner/manifest.json) snapshots pass checksum verification. Only table ACLs, sequence grants and postgres table/sequence defaults changed. All other captured catalog sections match: 23 tables, 21 sequences, 56 indexes and 103 constraints preserved, all nine seasonal consistency counts zero. No application-row statements were executed by the rollout.

Postcommit state exactly matches `after.json`: browser effective table/sequence privileges are zero; service/backend grants, owners, policies, RLS, schema ACLs, function defaults and supabase_admin defaults remain unchanged. Health/readiness remain 200 with listener connected. The reviewed package remains byte-for-byte immutable, including its preparation-time status; this dated receipt is authoritative for application history. Do not rerun it: its before-state guard will reject the hardened state.

Please repeat the normal signed-in leagues/profile load after the change. Authenticated draft acceptance remains explicitly deferred during the season. Provider-created future public objects can still regain browser grants; full provider-default hardening requires a separately authorized platform path. No cron was triggered or added and the timeout worker remains intentionally suspended.

Maintainer postchange acceptance: leagues load successfully. The requested leagues check is now confirmed; no draft or broader account-isolation acceptance is implied.

## Next action

Independent scoped review found no Critical/Important issues and verified manifest/input/native source hashes, exact guard/state correspondence, the intended privilege delta and unchanged frozen baseline/old proposals. One Minor is deferred: the native verifier checks package hashes but does not itself compare manifest.input_sha256 with input_evidence. That input hash was independently verified for this package; a future evidence edit could otherwise leave the harness reporting PASS without detecting the changed input. Recheck that hash manually for rollout until the harness is strengthened.

Preparation stayed in the maintainer-owned checkout without Git mutations. The future immutable rollout receipt, rather than a new database ledger table, records execution history; retain it with the snapshots. Neither decision changes application runtime behavior.

After review and the acceptance/configuration checks, request explicit approval for the exact owner-scoped production SQL. Capture fresh before/after schema snapshots and an execution receipt if applied. Keep supabase_admin default hardening open; this package does not resolve it. Do not run either old proposal or replay MOD015/MOD017 rollouts.

The [service inventory](evidence/render-operating-followup-2026-11-18.json) still shows two active crons and the intentionally suspended timeout worker. Refresh and finalization remain unscheduled. Before enabling either, controlled staging validation and an explicit cadence/operating decision are still needed. No service or job was created, changed or triggered here.
