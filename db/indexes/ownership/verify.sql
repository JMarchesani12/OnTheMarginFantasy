\set ON_ERROR_STOP on
SET search_path = pg_catalog;
\ir preflight.sql
\if :mod017_member_create
 \echo 'REFUSE: no valid equivalent member index'
 DO $mod017$ BEGIN RAISE EXCEPTION 'MOD017 refusal; see preceding diagnostic'; END $mod017$;
\endif

\echo 'Catalog verification passed. Operator must separately verify current query outputs/plans under target traffic.'
