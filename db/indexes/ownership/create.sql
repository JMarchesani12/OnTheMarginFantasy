\set ON_ERROR_STOP on
SET search_path = pg_catalog;
-- psql autocommit only. Preflight checks the selected candidate before any creation.
\ir preflight.sql

\unset mod017_created_member_oid
\unset mod017_created_member_definition
\unset mod017_created_member_backend
\if :mod017_member_create
CREATE INDEX CONCURRENTLY "mod017_owner_member_team" ON public."LeagueTeamSlot" ("leagueId","memberId","sportTeamId") INCLUDE ("acquiredWeek","droppedWeek");
SELECT c.oid::bigint AS oid,pg_get_indexdef(c.oid) AS definition,pg_backend_pid() AS backend
FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace
WHERE ns.nspname='public' AND c.relname='mod017_owner_member_team' \gset mod017_created_member_
\echo 'Created member; same-session recovery receipt captured. Preserve transcript.'
\else
 \echo 'SKIP/REVIEW: equivalent member index already exists, possibly under another name or constraint'
\endif

