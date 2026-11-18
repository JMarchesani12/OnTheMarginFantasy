-- MOD-008 additive keys and independently validated same-league score FKs.
-- Run the aggregate preflight first. No rows are changed, repaired or deduplicated.
BEGIN;
SET LOCAL row_security = off;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
LOCK TABLE public."Week", public."LeagueMember", public."WeeklyTeamScore" IN SHARE ROW EXCLUSIVE MODE;
DO $migration$
DECLARE
    item record;
    current_key record;
BEGIN
    IF EXISTS (SELECT 1 FROM public."Week" GROUP BY "leagueId","weekNumber" HAVING count(*)>1)
       OR EXISTS (SELECT 1 FROM public."WeeklyTeamScore" GROUP BY "leagueId","weekId","memberId" HAVING count(*)>1)
       OR EXISTS (SELECT 1 FROM public."WeeklyTeamScore" s LEFT JOIN public."Week" w ON w.id=s."weekId"
                  WHERE w.id IS NULL OR w."leagueId" IS DISTINCT FROM s."leagueId")
       OR EXISTS (SELECT 1 FROM public."WeeklyTeamScore" s LEFT JOIN public."LeagueMember" m ON m.id=s."memberId"
                  WHERE m.id IS NULL OR m."leagueId" IS DISTINCT FROM s."leagueId") THEN
        RAISE EXCEPTION 'MOD-008 blocked: duplicate or inconsistent history requires reviewed remediation';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_attribute WHERE NOT attisdropped AND NOT attnotnull
          AND ((attrelid='public."Week"'::regclass AND attname IN ('id','leagueId','weekNumber'))
            OR (attrelid='public."LeagueMember"'::regclass AND attname IN ('id','leagueId'))
            OR (attrelid='public."WeeklyTeamScore"'::regclass AND attname IN ('leagueId','weekId','memberId')))
    ) THEN
        RAISE EXCEPTION 'MOD-008 blocked: unexpected nullable identity columns';
    END IF;

    FOR item IN SELECT * FROM (VALUES
        (1,'public."Week"'::regclass,'Week_league_week_number_key','u',ARRAY['leagueId','weekNumber'],NULL::regclass,NULL::text[],
          'ALTER TABLE public."Week" ADD CONSTRAINT "Week_league_week_number_key" UNIQUE ("leagueId","weekNumber")'),
        (2,'public."Week"'::regclass,'Week_league_id_key','u',ARRAY['leagueId','id'],NULL::regclass,NULL::text[],
          'ALTER TABLE public."Week" ADD CONSTRAINT "Week_league_id_key" UNIQUE ("leagueId",id)'),
        (3,'public."LeagueMember"'::regclass,'LeagueMember_league_id_key','u',ARRAY['leagueId','id'],NULL::regclass,NULL::text[],
          'ALTER TABLE public."LeagueMember" ADD CONSTRAINT "LeagueMember_league_id_key" UNIQUE ("leagueId",id)'),
        (4,'public."WeeklyTeamScore"'::regclass,'WeeklyTeamScore_identity_key','u',ARRAY['leagueId','weekId','memberId'],NULL::regclass,NULL::text[],
          'ALTER TABLE public."WeeklyTeamScore" ADD CONSTRAINT "WeeklyTeamScore_identity_key" UNIQUE ("leagueId","weekId","memberId")'),
        (5,'public."WeeklyTeamScore"'::regclass,'WeeklyTeamScore_same_league_week_fkey','f',ARRAY['leagueId','weekId'],'public."Week"'::regclass,ARRAY['leagueId','id'],
          'ALTER TABLE public."WeeklyTeamScore" ADD CONSTRAINT "WeeklyTeamScore_same_league_week_fkey" FOREIGN KEY ("leagueId","weekId") REFERENCES public."Week" ("leagueId",id) ON DELETE CASCADE'),
        (6,'public."WeeklyTeamScore"'::regclass,'WeeklyTeamScore_same_league_member_fkey','f',ARRAY['leagueId','memberId'],'public."LeagueMember"'::regclass,ARRAY['leagueId','id'],
          'ALTER TABLE public."WeeklyTeamScore" ADD CONSTRAINT "WeeklyTeamScore_same_league_member_fkey" FOREIGN KEY ("leagueId","memberId") REFERENCES public."LeagueMember" ("leagueId",id) ON DELETE CASCADE')
    ) AS expected(sequence,table_oid,name,kind,columns,reference_oid,reference_columns,ddl) ORDER BY sequence LOOP
        SELECT c.contype::text AS kind, c.convalidated, c.condeferrable, c.confrelid,
            c.confdeltype, c.confupdtype, c.confmatchtype,
            ARRAY(SELECT a.attname::text FROM unnest(c.conkey) WITH ORDINALITY k(n,ord)
                  JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.n ORDER BY k.ord) AS columns,
            ARRAY(SELECT a.attname::text FROM unnest(c.confkey) WITH ORDINALITY k(n,ord)
                  JOIN pg_attribute a ON a.attrelid=c.confrelid AND a.attnum=k.n ORDER BY k.ord) AS reference_columns,
            i.indisvalid, i.indisready, i.indnullsnotdistinct
        INTO current_key FROM pg_constraint c LEFT JOIN pg_index i ON i.indexrelid=c.conindid
        WHERE c.conrelid=item.table_oid AND c.conname=item.name;
        IF FOUND THEN
            IF current_key.kind IS DISTINCT FROM item.kind
               OR current_key.columns IS DISTINCT FROM item.columns
               OR NOT current_key.convalidated OR current_key.condeferrable
               OR (item.kind='u' AND (current_key.indisvalid IS DISTINCT FROM true
                   OR current_key.indisready IS DISTINCT FROM true OR current_key.indnullsnotdistinct IS DISTINCT FROM false))
               OR (item.kind='f' AND (current_key.confrelid IS DISTINCT FROM item.reference_oid
                   OR current_key.reference_columns IS DISTINCT FROM item.reference_columns
                   OR current_key.confdeltype<>'c' OR current_key.confupdtype<>'a' OR current_key.confmatchtype<>'s')) THEN
                RAISE EXCEPTION 'MOD-008 blocked: an identity constraint has an unexpected definition';
            END IF;
        ELSE
            EXECUTE item.ddl;
        END IF;
    END LOOP;
END
$migration$;
COMMIT;
