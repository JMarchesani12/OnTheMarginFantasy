-- MOD015 PREPARED ONLY: requires separate target rollout approval.
-- PostgreSQL17; additive integrity keys, no rows/backfills/repairs or baseline drops.
BEGIN;
SET LOCAL row_security = off;
SET LOCAL search_path = pg_catalog, public;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
LOCK TABLE public."ConferenceMembership",public."GameResult",public."SeasonPhase",
 public."SportConference",public."SportSeason",public."SportTeam" IN SHARE ROW EXCLUSIVE MODE;
DO $migration$
DECLARE item record; existing record;
BEGIN
 IF current_setting('server_version_num')::int NOT BETWEEN 170000 AND 179999 THEN
  RAISE EXCEPTION 'MOD-015 blocked: PostgreSQL17 required';
 END IF;
 IF EXISTS(SELECT 1 FROM public."ConferenceMembership" cm
   LEFT JOIN public."SportTeam" st ON st.id=cm."sportTeamId"
   LEFT JOIN public."SportConference" sc ON sc.id=cm."sportConferenceId"
   WHERE cm."sportId" IS NULL OR st.id IS NULL OR sc.id IS NULL
    OR cm."sportId" IS DISTINCT FROM st."sportId" OR cm."sportId" IS DISTINCT FROM sc."sportId")
 OR EXISTS(SELECT 1 FROM public."GameResult" g
   LEFT JOIN public."SportSeason" ss ON ss.id=g."sportSeasonId"
   LEFT JOIN public."SeasonPhase" sp ON sp.id=g."seasonPhaseId"
   LEFT JOIN public."SportTeam" h ON h.id=g."homeTeamId"
   LEFT JOIN public."SportTeam" a ON a.id=g."awayTeamId"
   WHERE ss.id IS NULL OR g.sport IS DISTINCT FROM ss."sportId"
    OR (g."seasonPhaseId" IS NOT NULL AND (sp.id IS NULL OR g."sportSeasonId" IS DISTINCT FROM sp."sportSeasonId"))
    OR (g."homeTeamId" IS NOT NULL AND (h.id IS NULL OR g.sport IS DISTINCT FROM h."sportId"))
    OR (g."awayTeamId" IS NOT NULL AND (a.id IS NULL OR g.sport IS DISTINCT FROM a."sportId"))) THEN
  RAISE EXCEPTION 'MOD-015 blocked: inconsistent references require reviewed remediation';
 END IF;
 IF EXISTS(SELECT 1 FROM pg_attribute WHERE attrelid='public."GameResult"'::regclass
  AND attname IN ('homeTeamId','awayTeamId','seasonPhaseId') AND NOT attisdropped AND attnotnull) THEN
  RAISE EXCEPTION 'MOD-015 blocked: nullable game-reference policy drift';
 END IF;
 -- Preserve the actual existing single-column FK/delete semantics; no replacement.
 FOR item IN SELECT * FROM (VALUES
 ('public."ConferenceMembership"'::regclass,'ConferenceMembership_sportTeamId_fkey','sportTeamId','public."SportTeam"'::regclass,'a'),
 ('public."ConferenceMembership"'::regclass,'ConferenceMembership_sportConferenceId_fkey','sportConferenceId','public."SportConference"'::regclass,'a'),
 ('public."GameResult"'::regclass,'GameResult_sportSeasonId_fkey','sportSeasonId','public."SportSeason"'::regclass,'c'),
 ('public."GameResult"'::regclass,'GameResult_seasonPhaseId_fkey','seasonPhaseId','public."SeasonPhase"'::regclass,'n'),
 ('public."GameResult"'::regclass,'GameResult_homeTeamId_fkey','homeTeamId','public."SportTeam"'::regclass,'a'),
 ('public."GameResult"'::regclass,'GameResult_awayTeamId_fkey','awayTeamId','public."SportTeam"'::regclass,'c')) AS expected(table_oid,name,column_name,parent_oid,delete_action) LOOP
  SELECT c.*,ARRAY(SELECT a.attname::text FROM unnest(c.conkey) WITH ORDINALITY k(n,ord)
    JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.n ORDER BY k.ord) AS columns,
   ARRAY(SELECT a.attname::text FROM unnest(c.confkey) WITH ORDINALITY k(n,ord)
    JOIN pg_attribute a ON a.attrelid=c.confrelid AND a.attnum=k.n ORDER BY k.ord) AS parent_columns
  INTO existing FROM pg_constraint c WHERE c.conrelid=item.table_oid AND c.conname=item.name;
  IF NOT FOUND OR existing.contype<>'f' OR NOT existing.convalidated OR existing.condeferrable
   OR existing.columns IS DISTINCT FROM ARRAY[item.column_name]::text[]
   OR existing.confrelid IS DISTINCT FROM item.parent_oid OR existing.parent_columns IS DISTINCT FROM ARRAY['id']::text[]
   OR existing.confdeltype::text IS DISTINCT FROM item.delete_action
   OR existing.confupdtype<>'a' OR existing.confmatchtype<>'s' THEN
   RAISE EXCEPTION 'MOD-015 blocked: original reference/delete definition drift';
  END IF;
 END LOOP;

 -- Every expected constraint is verified by fields, never name-only replay.
 FOR item IN SELECT * FROM (VALUES
 ('public."SportTeam"'::regclass,'SportTeam_sport_identity_key','u',ARRAY['id','sportId']::text[],NULL::regclass,ARRAY[]::text[],' ',ARRAY[]::text[],'ALTER TABLE public."SportTeam" ADD CONSTRAINT "SportTeam_sport_identity_key" UNIQUE ("id","sportId")'),
 ('public."SportConference"'::regclass,'SportConference_sport_identity_key','u',ARRAY['id','sportId']::text[],NULL::regclass,ARRAY[]::text[],' ',ARRAY[]::text[],'ALTER TABLE public."SportConference" ADD CONSTRAINT "SportConference_sport_identity_key" UNIQUE ("id","sportId")'),
 ('public."SportSeason"'::regclass,'SportSeason_sport_identity_key','u',ARRAY['id','sportId']::text[],NULL::regclass,ARRAY[]::text[],' ',ARRAY[]::text[],'ALTER TABLE public."SportSeason" ADD CONSTRAINT "SportSeason_sport_identity_key" UNIQUE ("id","sportId")'),
 ('public."SeasonPhase"'::regclass,'SeasonPhase_season_identity_key','u',ARRAY['id','sportSeasonId']::text[],NULL::regclass,ARRAY[]::text[],' ',ARRAY[]::text[],'ALTER TABLE public."SeasonPhase" ADD CONSTRAINT "SeasonPhase_season_identity_key" UNIQUE ("id","sportSeasonId")'),
 ('public."ConferenceMembership"'::regclass,'ConferenceMembership_team_sport_fkey','f',ARRAY['sportTeamId','sportId']::text[],'public."SportTeam"'::regclass,ARRAY['id','sportId']::text[],'a',ARRAY[]::text[],'ALTER TABLE public."ConferenceMembership" ADD CONSTRAINT "ConferenceMembership_team_sport_fkey" FOREIGN KEY ("sportTeamId","sportId") REFERENCES public."SportTeam" ("id","sportId") MATCH SIMPLE ON DELETE NO ACTION ON UPDATE NO ACTION'),
 ('public."ConferenceMembership"'::regclass,'ConferenceMembership_conference_sport_fkey','f',ARRAY['sportConferenceId','sportId']::text[],'public."SportConference"'::regclass,ARRAY['id','sportId']::text[],'a',ARRAY[]::text[],'ALTER TABLE public."ConferenceMembership" ADD CONSTRAINT "ConferenceMembership_conference_sport_fkey" FOREIGN KEY ("sportConferenceId","sportId") REFERENCES public."SportConference" ("id","sportId") MATCH SIMPLE ON DELETE NO ACTION ON UPDATE NO ACTION'),
 ('public."GameResult"'::regclass,'GameResult_season_sport_fkey','f',ARRAY['sportSeasonId','sport']::text[],'public."SportSeason"'::regclass,ARRAY['id','sportId']::text[],'c',ARRAY[]::text[],'ALTER TABLE public."GameResult" ADD CONSTRAINT "GameResult_season_sport_fkey" FOREIGN KEY ("sportSeasonId","sport") REFERENCES public."SportSeason" ("id","sportId") MATCH SIMPLE ON DELETE CASCADE ON UPDATE NO ACTION'),
 ('public."GameResult"'::regclass,'GameResult_phase_season_fkey','f',ARRAY['seasonPhaseId','sportSeasonId']::text[],'public."SeasonPhase"'::regclass,ARRAY['id','sportSeasonId']::text[],'n',ARRAY['seasonPhaseId']::text[],'ALTER TABLE public."GameResult" ADD CONSTRAINT "GameResult_phase_season_fkey" FOREIGN KEY ("seasonPhaseId","sportSeasonId") REFERENCES public."SeasonPhase" ("id","sportSeasonId") MATCH SIMPLE ON DELETE SET NULL ("seasonPhaseId") ON UPDATE NO ACTION'),
 ('public."GameResult"'::regclass,'GameResult_home_sport_fkey','f',ARRAY['homeTeamId','sport']::text[],'public."SportTeam"'::regclass,ARRAY['id','sportId']::text[],'a',ARRAY[]::text[],'ALTER TABLE public."GameResult" ADD CONSTRAINT "GameResult_home_sport_fkey" FOREIGN KEY ("homeTeamId","sport") REFERENCES public."SportTeam" ("id","sportId") MATCH SIMPLE ON DELETE NO ACTION ON UPDATE NO ACTION'),
 ('public."GameResult"'::regclass,'GameResult_away_sport_fkey','f',ARRAY['awayTeamId','sport']::text[],'public."SportTeam"'::regclass,ARRAY['id','sportId']::text[],'c',ARRAY[]::text[],'ALTER TABLE public."GameResult" ADD CONSTRAINT "GameResult_away_sport_fkey" FOREIGN KEY ("awayTeamId","sport") REFERENCES public."SportTeam" ("id","sportId") MATCH SIMPLE ON DELETE CASCADE ON UPDATE NO ACTION')) AS expected(table_oid,name,kind,columns,parent_oid,parent_columns,delete_action,null_columns,ddl) LOOP
  SELECT c.contype::text AS kind,c.convalidated,c.condeferrable,c.confrelid,c.confdeltype,c.confupdtype,c.confmatchtype,
   ARRAY(SELECT a.attname::text FROM unnest(c.conkey) WITH ORDINALITY k(n,ord)
    JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.n ORDER BY k.ord) AS columns,
   ARRAY(SELECT a.attname::text FROM unnest(c.confkey) WITH ORDINALITY k(n,ord)
    JOIN pg_attribute a ON a.attrelid=c.confrelid AND a.attnum=k.n ORDER BY k.ord) AS parent_columns,
   ARRAY(SELECT a.attname::text FROM unnest(c.confdelsetcols) WITH ORDINALITY k(n,ord)
    JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.n ORDER BY k.ord) AS null_columns,
   i.indisvalid,i.indisready,i.indisunique,i.indnullsnotdistinct,i.indpred,i.indexprs,i.indnkeyatts,i.indnatts,am.amname,
   NOT EXISTS(SELECT 1 FROM unnest(i.indoption::smallint[]) o WHERE o<>0) AS ascending_keys
  INTO existing FROM pg_constraint c LEFT JOIN pg_index i ON i.indexrelid=c.conindid
   LEFT JOIN pg_class ix ON ix.oid=i.indexrelid LEFT JOIN pg_am am ON am.oid=ix.relam
  WHERE c.conrelid=item.table_oid AND c.conname=item.name;
  IF FOUND THEN
   IF existing.kind IS DISTINCT FROM item.kind OR NOT existing.convalidated OR existing.condeferrable
    OR existing.columns IS DISTINCT FROM item.columns
    OR (item.kind='u' AND (existing.indisvalid IS DISTINCT FROM true OR existing.indisready IS DISTINCT FROM true
      OR existing.indisunique IS DISTINCT FROM true OR existing.indnullsnotdistinct IS DISTINCT FROM false
      OR existing.indpred IS NOT NULL OR existing.indexprs IS NOT NULL OR existing.amname IS DISTINCT FROM 'btree'
      OR existing.indnkeyatts IS DISTINCT FROM cardinality(item.columns)
      OR existing.indnatts IS DISTINCT FROM cardinality(item.columns) OR NOT existing.ascending_keys))
    OR (item.kind='f' AND (existing.confrelid IS DISTINCT FROM item.parent_oid
      OR existing.parent_columns IS DISTINCT FROM item.parent_columns
      OR existing.confdeltype::text IS DISTINCT FROM item.delete_action OR existing.confupdtype<>'a'
      OR existing.confmatchtype<>'s' OR existing.null_columns IS DISTINCT FROM item.null_columns)) THEN
    RAISE EXCEPTION 'MOD-015 blocked: prepared constraint definition/validation drift';
   END IF;
  ELSE
   EXECUTE item.ddl;
  END IF;
 END LOOP;
 ALTER TABLE public."ConferenceMembership" ALTER COLUMN "sportId" SET NOT NULL;
END
$migration$;
COMMIT;
