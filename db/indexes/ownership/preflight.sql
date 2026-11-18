\set ON_ERROR_STOP on
SET search_path = pg_catalog;
-- Read-only catalog inspection; PostgreSQL 17 ordinary tables only.
SELECT current_setting('server_version_num')::int BETWEEN 170000 AND 179999 AS version_ok \gset mod017_
\if :mod017_version_ok
\else
  \echo 'REFUSE: package tested only on PostgreSQL 17'
  DO $mod017$ BEGIN RAISE EXCEPTION 'MOD017 refusal; see preceding diagnostic'; END $mod017$;
\endif

-- mod017_owner_member_team: structure, validity, constraint backing and same-name drift.
WITH relation AS (
 SELECT t.oid FROM pg_class t JOIN pg_namespace ns ON ns.oid=t.relnamespace
 WHERE ns.nspname='public' AND t.relname='LeagueTeamSlot' AND t.relkind='r'
), columns AS (
 SELECT array_agg(format_type(a.atttypid,a.atttypmod) ORDER BY array_position(ARRAY['leagueId','memberId','sportTeamId','acquiredWeek','droppedWeek']::text[],a.attname::text)) AS types
 FROM pg_attribute a JOIN relation r ON r.oid=a.attrelid
 WHERE a.attname=ANY(ARRAY['leagueId','memberId','sportTeamId','acquiredWeek','droppedWeek']::text[]) AND a.attnum>0 AND NOT a.attisdropped
), indexes AS (
 SELECT i.oid,i.relname,x.indisvalid,x.indisready,x.indisunique,x.indisprimary,x.indisexclusion,
 ARRAY(SELECT c.conname FROM pg_constraint c WHERE c.conindid=i.oid) AS constraints,
 (am.amname='btree' AND x.indpred IS NULL AND x.indexprs IS NULL
  AND ARRAY(SELECT pg_get_indexdef(i.oid,k,true) FROM generate_series(1,x.indnkeyatts) k)=ARRAY['"leagueId"','"memberId"','"sportTeamId"']::text[]
  AND ARRAY(SELECT pg_get_indexdef(i.oid,k,true) FROM generate_series(x.indnkeyatts+1,x.indnatts) k)=ARRAY['"acquiredWeek"','"droppedWeek"']::text[]
  AND NOT EXISTS(SELECT 1 FROM unnest(x.indoption::smallint[]) o WHERE o<>0)
 ) AS shape
 FROM pg_index x JOIN pg_class i ON i.oid=x.indexrelid JOIN relation r ON r.oid=x.indrelid JOIN pg_am am ON am.oid=i.relam
), named AS (
 SELECT i.oid FROM pg_class i JOIN pg_namespace ns ON ns.oid=i.relnamespace
 WHERE ns.nspname='public' AND i.relname='mod017_owner_member_team'
)
SELECT
 (EXISTS(SELECT 1 FROM relation) AND (SELECT types FROM columns)=ARRAY['bigint','bigint','bigint','integer','integer']::text[]
  AND NOT EXISTS(SELECT 1 FROM indexes WHERE NOT indisvalid OR NOT indisready)
  AND NOT EXISTS(SELECT 1 FROM named WHERE oid NOT IN
    (SELECT oid FROM indexes WHERE shape AND indisvalid AND indisready AND NOT indisunique AND NOT indisprimary AND NOT indisexclusion AND cardinality(constraints)=0))) AS ok,
 NOT EXISTS(SELECT 1 FROM indexes WHERE shape) AS create,
 COALESCE((SELECT json_agg(row_to_json(indexes)) FROM indexes),'[]') AS catalog
\gset mod017_member_
\echo :mod017_member_catalog
\if :mod017_member_ok
\else
 \echo 'REFUSE: missing relation/type metadata, invalid index, or same-name drift (member)'
 DO $mod017$ BEGIN RAISE EXCEPTION 'MOD017 refusal; see preceding diagnostic'; END $mod017$;
\endif

