\set ON_ERROR_STOP on
SET search_path = pg_catalog;
-- Recovery only in the SAME psql session that successfully created an index.
-- No receipt means REFUSE. Interrupted builds need separately reviewed evidence;
-- this script deliberately cannot infer that an arbitrary existing index is ours.
\if :{?mod017_recovery_approved}
\else
 \echo 'REFUSE: explicit operator review required; set mod017_recovery_approved true'
 DO $mod017$ BEGIN RAISE EXCEPTION 'MOD017 refusal; see preceding diagnostic'; END $mod017$;
\endif
\if :mod017_recovery_approved
\else
 DO $mod017$ BEGIN RAISE EXCEPTION 'MOD017 refusal; see preceding diagnostic'; END $mod017$;
\endif

\if :{?mod017_created_member_oid}
SELECT EXISTS (
 SELECT 1 FROM pg_class i JOIN pg_namespace ns ON ns.oid=i.relnamespace
 JOIN pg_index x ON x.indexrelid=i.oid
 WHERE i.oid=:'mod017_created_member_oid'::oid AND ns.nspname='public'
 AND i.relname='mod017_owner_member_team' AND pg_get_indexdef(i.oid)=:'mod017_created_member_definition'
 AND pg_backend_pid()=:'mod017_created_member_backend'::int
 AND NOT x.indisprimary AND NOT x.indisexclusion AND NOT x.indisunique
 AND NOT EXISTS(SELECT 1 FROM pg_constraint c WHERE c.conindid=i.oid)
) AS ok \gset mod017_recovery_member_
\if :mod017_recovery_member_ok
DROP INDEX CONCURRENTLY public."mod017_owner_member_team";
\unset mod017_created_member_oid
\else
 \echo 'REFUSE: member receipt/session/OID/definition/constraint drift'
 DO $mod017$ BEGIN RAISE EXCEPTION 'MOD017 refusal; see preceding diagnostic'; END $mod017$;
\endif
\else
 \echo 'SKIP: no newly-created member receipt in this session'
\endif

