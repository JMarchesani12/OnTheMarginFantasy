# MOD-004 access-policy evidence — 2026-10-29

Status: versioned observed access baseline and separately tested privilege proposal/recovery implemented locally. Approved least-privilege rollout, external consumers and deployed runtime alignment remain open. No deployed DDL, grants, policy changes or application-row reads performed.

## Evidence scope

[Catalog evidence](evidence/supabase-catalog-2026-10-29.json) comes from the database configured by `api/.env`'s `SUPABASE_DB_URL`. Connection values are excluded. PostgreSQL reports 17.6. The final collection explicitly executes `SET TRANSACTION READ ONLY` and records `transaction_read_only=on`. Startup connection options alone did not retain read-only mode on this connection; the preliminary pass executed only catalog SELECTs, and was replaced by the explicit-transaction collection. Statements/timeouts were requested through connection options; their effective timeout values were not recorded.

This establishes the configured backend database's metadata on the observation date. It does not independently establish that every deployed web process/listener uses this database. No account rows, emails, UUIDs, transaction payloads, role settings, routine bodies or scheduler command text collected.

## Observed boundaries

| Access path | Observed metadata/source | Interpretation and remaining check |
| --- | --- | --- |
| Browser profile lookup | `currentUserContext.tsx` directly SELECTs public.User by uuid. User's sole policy is permissive SELECT to PUBLIC with `uuid = auth.uid()`. | Policy expression matches own-profile reads. Execute synthetic anon/A/B role tests on a disposable database; no actual users queried. |
| Other public tables via browser roles | All 23 tables have RLS enabled, none forced. No policies on the other 22 tables. anon/authenticated each have SELECT/INSERT/UPDATE/DELETE/REFERENCES/TRIGGER/TRUNCATE grants on all 23 tables. | RLS normally denies row access without a matching policy for these roles. Broad object privileges are separate from row policies; TRUNCATE/REFERENCES are not row-filtered by RLS. This is not proof these operations are exposed by PostgREST. Define least-privilege grants and test effective API/SQL boundaries before proposing changes. |
| Backend SQLAlchemy engine | Configured connection is postgres; all 23 tables owned by postgres; role has BYPASSRLS. | RLS does not constrain this backend connection. Application principal/resource authorization remains necessary. Separate operational and application DB roles need a reviewed deployment plan. |
| Trusted jobs | Source shares backend engine. service_role also has BYPASSRLS and broad table privileges. | Do not assume a job uses service_role: this configured engine uses postgres. Runtime job configuration and least-privilege requirements remain unverified. |
| Draft listener | Source reads DATABASE_URL; main engine uses SUPABASE_DB_URL. | Listener's actual DSN/role/target alignment not verified. Do not print either DSN to compare. |
| Views/RPC/functions | No public views/materialized views; 32 public routines, 31 pg_trgm extension members. One remaining routine: rls_auto_enable, SECURITY DEFINER, owner postgres, search_path=pg_catalog. EXECUTE ACL includes PUBLIC, anon, authenticated, service_role. | Routine body and complete function access semantics not audited. No claim of exploitability or safe RPC exposure from ACL alone. It is referenced by the ensure_rls event trigger. |
| Triggers/Realtime/scheduler | No user table triggers in public; 9 database event triggers, including ensure_rls on CREATE TABLE/CREATE TABLE AS/SELECT INTO. No public publication memberships; no cron schema observed. | A deployed RLS auto-enable mechanism exists despite its absence from repository SQL. Do not infer absence of externally scheduled jobs or all non-public triggers/functions. |

The artifact includes columns, constraints, indexes, table/column grants, sequence/schema/default ACLs, role memberships/BYPASSRLS, routine metadata, event triggers, extension ownership and publication memberships. Catalog visibility follows the inspected postgres session; it is not a dump of every schema/object definition.

## Work identified at initial metadata stage (results below)

1. Define intended per-role/table privileges: browser needs own-profile SELECT in inspected source; server/job needs must be derived from actual commands. Preserve intentional API authorization distinctions.
2. Reproduce observed User SELECT policy and relevant grants on disposable PostgreSQL/Supabase-compatible fixtures; test anon/A/B/service/owner behavior without using deployed rows.
3. Review rls_auto_enable definition and event-trigger behavior through a separately bounded metadata review; determine whether to version its definition or record it as an explicit platform prerequisite. Broader non-public custom routines remain unreviewed.
4. Verify deployed API/listener/job connection alignment and runtime roles without recording credentials. Version only reviewed policy/grant changes with recovery instructions; no production application is authorized by this document.

MOD-004 is not complete: metadata evidence is available now, but isolated effective access tests and a reviewed privilege/policy baseline are still required.


## Disposable role and event-trigger results

[Harness and commands](../../scripts/modernization/README.md) and
[results](evidence/postgres-assessment-2026-10-29.json) reproduce the relevant
observed table-level grants, RLS flags, own-User SELECT expression and BYPASSRLS
semantics on synthetic PostgreSQL 17.6 data:

- Anonymous reads return no profiles; authenticated A/B each see only their own
  profile even without a UUID filter. Missing/unknown authenticated subjects see
  no profiles. Browser-role User updates affect zero rows and inserts reject.
- A seeded Sport row is invisible to anonymous/authenticated roles because there
  is no matching policy. Service-equivalent BYPASSRLS and owner see both profiles
  and that catalog row. This is not a row-by-row test of all 22 other tables.
- Anonymous `TRUNCATE School CASCADE` succeeds with the reproduced SQL grants;
  the probe is rolled back. This establishes broad SQL privilege behavior, not
  PostgREST exposure or access to a deployed SQL execution channel.
- A separately scoped read-only metadata query collected
  [rls_auto_enable](evidence/rls-auto-enable-2026-10-29.json). It returns
  event_trigger, uses SECURITY DEFINER/search_path=pg_catalog, loops DDL command
  objects, and enables RLS on public tables. It catches exceptions and logs a
  failure rather than failing table creation. It does not create row policies or
  restrict grants. Replaying its definition and ensure_rls registration locally
  proves public CREATE TABLE automatically enables RLS on the test probe. Its
  event_trigger return type is not an ordinary scalar RPC contract.

The supplemental deployed query verified read-only=on, statement_timeout=10s and
lock_timeout=2s. No deployed function or trigger was changed. Full Auth/JWT provider
semantics, PostgREST exposure, deployed role assumptions and all non-public custom
routines remain outside this fixture.

## Proposed privilege direction for later review

Source currently demonstrates browser database need for own-User SELECT only.
A least-privilege candidate would retain authenticated own-profile SELECT and
remove unnecessary browser-role table writes/DDL-related grants and other direct
table access; keep server/job privileges separate. Before authoring/applying the
final policy/grant migration, confirm external consumers, inherited/default grants,
recovery instructions, and actual server/listener/job roles. Revoke changes must
account for default grants and PUBLIC/inherited privileges, not merely direct
ACL entries. No role transition or grant/policy deployment is implemented here.

MOD-004 remains open for that reviewed versioned access baseline and runtime
alignment; isolated SQL tests no longer require deployed-row access.


## Versioned access baseline and unapplied proposal — 2026-10-29

The [baseline access SQL](../../db/baselines/20261029/002_access.sql) now versions
the observed RLS/policy/grants/ensure_rls mechanism without silently tightening
permissions during initialization/adoption. [Read-only verification](evidence/baseline-deployed-verification-2026-10-29.json)
confirms the frozen reference matches the configured database, including role
flags/memberships and global/schema default ACLs. No ledger or permission changes
were made remotely.

The separate [proposal/recovery runbook](../../db/proposals/README.md) supplies
reviewable browser table/sequence revokes, authenticated own-User SELECT retention
and future-object default changes for postgres/supabase_admin. It refuses unexpected
inherited roles, privileged browser flags, column/schema grants and global defaults
that schema-specific revokes cannot safely resolve. It is not applied as part of
the baseline and has not been applied to Supabase.

Local tests enumerate all browser object privileges on all 23 tables and 21
sequences, verify own-profile reads and service access, test new objects created
by both observed creators, and restore the original ACL reference with the scoped
recovery SQL. Final PostgreSQL suite: 16/16 pass; independent review findings were
reproduced and fixed. See [verification evidence](evidence/baseline-local-verification-2026-10-29.json).

[Local configuration comparison](evidence/local-role-config-check-2026-10-29.json)
found no listener DATABASE_URL in api/.env or the current process; this does not
establish its deployed environment. A server connection variable also exists in
front-end/.env with a different endpoint/user tuple. That does not prove different
projects or browser credential exposure (it is not VITE-prefixed). No DSNs were
printed and no configuration was altered.

MOD-004 remains open for external-consumer confirmation, deployed API/listener/job
role alignment and an approved/versioned least-privilege rollout. Changing
supabase_admin defaults requires an actor authorized by the platform; do not grant
broader powers or partially apply SQL to work around that boundary. The proposed
recovery restores this exact observed starting state, not arbitrary later changes.


## Real provider acceptance and Render boundary — 2026-10-29

[Actual Auth/PostgREST tests](evidence/supabase-provider-verification-2026-10-29.json)
now pass before/proposal/after recovery, with generated local users/tokens and no
fake Auth schema/functions. The normal Supabase postgres role rejects the full
proposal's supabase_admin defaults (SQLSTATE42501); rollback retains the entire
observed reference. The existing local maintenance account can test the full
proposal/recovery without changing role powers. Do not infer hosted capability.

Maintainer confirms Render hosting and an intentionally suspended listener
service. The [runtime handoff](mod-004-runtime-handoff.md) records that preference,
the source factory's additional in-process listener startup, sanitized role/activity
aggregates and remaining service-command/environment mapping. No Render operation
or deployed Supabase mutation occurred. The installed tool set still lacks a
connected Render integration; the discovered optional integration was suggested.

MOD-004 remains open specifically for that runtime/consumer mapping and a reviewed,
versioned rollout path for the privileged proposal. Provider HTTP/setup validation
is no longer the outstanding item; MOD-005 is complete in its documented scope.
