-- MOD-010. Preserve half-open/empty/adjacent/future intervals; never repair rows.
-- Requires MOD-008's LeagueMember(leagueId,id) key. Enables standard btree_gist
-- using the platform-supplied extension; no packages/downloads or new service.
BEGIN;
SET LOCAL row_security = off;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;
LOCK TABLE public."LeagueTeamSlot" IN SHARE ROW EXCLUSIVE MODE;
DO $migration$
DECLARE
    existing record;
    league_column smallint;
    member_column smallint;
    team_column smallint;
BEGIN
    IF EXISTS (SELECT 1 FROM public."LeagueTeamSlot" WHERE "acquiredWeek"<0 OR "droppedWeek"<"acquiredWeek")
       OR EXISTS (SELECT 1 FROM public."LeagueTeamSlot" s LEFT JOIN public."LeagueMember" m ON m.id=s."memberId"
                  WHERE m.id IS NULL OR m."leagueId" IS DISTINCT FROM s."leagueId")
       OR EXISTS (SELECT 1 FROM public."LeagueTeamSlot" a JOIN public."LeagueTeamSlot" b
                  ON a.id<b.id AND a."leagueId"=b."leagueId" AND a."sportTeamId"=b."sportTeamId"
                  WHERE (a."droppedWeek" IS NULL OR a."droppedWeek">a."acquiredWeek")
                    AND (b."droppedWeek" IS NULL OR b."droppedWeek">b."acquiredWeek")
                    AND a."acquiredWeek"::bigint<coalesce(b."droppedWeek"::bigint,9223372036854775807)
                    AND b."acquiredWeek"::bigint<coalesce(a."droppedWeek"::bigint,9223372036854775807)) THEN
        RAISE EXCEPTION 'MOD-010 blocked: ownership history requires reviewed remediation';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid='public."LeagueTeamSlot"'::regclass AND NOT attisdropped
               AND ((attname IN ('leagueId','memberId','sportTeamId','acquiredWeek') AND NOT attnotnull)
                 OR (attname='droppedWeek' AND attnotnull))) THEN
        RAISE EXCEPTION 'MOD-010 blocked: unexpected ownership null policy';
    END IF;
    SELECT attnum INTO STRICT league_column FROM pg_attribute WHERE attrelid='public."LeagueTeamSlot"'::regclass AND attname='leagueId';
    SELECT attnum INTO STRICT member_column FROM pg_attribute WHERE attrelid='public."LeagueTeamSlot"'::regclass AND attname='memberId';
    SELECT attnum INTO STRICT team_column FROM pg_attribute WHERE attrelid='public."LeagueTeamSlot"'::regclass AND attname='sportTeamId';

    SELECT contype,convalidated,connoinherit,pg_get_expr(conbin,conrelid) AS expression INTO existing
      FROM pg_constraint WHERE conrelid='public."LeagueTeamSlot"'::regclass AND conname='LeagueTeamSlot_interval_check';
    IF FOUND THEN
        IF existing.contype<>'c' OR NOT existing.convalidated OR existing.connoinherit OR existing.expression IS DISTINCT FROM
          '(("acquiredWeek" >= 0) AND (("droppedWeek" IS NULL) OR ("droppedWeek" >= "acquiredWeek")))' THEN
            RAISE EXCEPTION 'MOD-010 blocked: interval constraint has an unexpected definition';
        END IF;
    ELSE
        ALTER TABLE public."LeagueTeamSlot" ADD CONSTRAINT "LeagueTeamSlot_interval_check"
          CHECK ("acquiredWeek">=0 AND ("droppedWeek" IS NULL OR "droppedWeek">="acquiredWeek"));
    END IF;

    SELECT contype,convalidated,condeferrable,conkey,confrelid,confkey,confdeltype,confupdtype,confmatchtype INTO existing
      FROM pg_constraint WHERE conrelid='public."LeagueTeamSlot"'::regclass AND conname='LeagueTeamSlot_same_league_member_fkey';
    IF FOUND THEN
        IF existing.contype<>'f' OR NOT existing.convalidated OR existing.condeferrable
           OR existing.conkey IS DISTINCT FROM ARRAY[league_column,member_column]
           OR existing.confrelid<>'public."LeagueMember"'::regclass
           OR existing.confkey IS DISTINCT FROM ARRAY[
               (SELECT attnum FROM pg_attribute WHERE attrelid='public."LeagueMember"'::regclass AND attname='leagueId'),
               (SELECT attnum FROM pg_attribute WHERE attrelid='public."LeagueMember"'::regclass AND attname='id')]
           OR existing.confdeltype<>'c' OR existing.confupdtype<>'a' OR existing.confmatchtype<>'s' THEN
            RAISE EXCEPTION 'MOD-010 blocked: ownership member constraint has an unexpected definition';
        END IF;
    ELSE
        ALTER TABLE public."LeagueTeamSlot" ADD CONSTRAINT "LeagueTeamSlot_same_league_member_fkey"
          FOREIGN KEY ("leagueId","memberId") REFERENCES public."LeagueMember" ("leagueId",id) ON DELETE CASCADE;
    END IF;

    SELECT pc.contype,pc.convalidated,pc.condeferrable,pc.conkey,pc.conexclop,
           i.indisvalid,i.indisready,i.indisexclusion,i.indpred,
           pg_get_expr(i.indexprs,i.indrelid) AS expression,a.amname INTO existing
      FROM pg_constraint pc LEFT JOIN pg_index i ON i.indexrelid=pc.conindid
      LEFT JOIN pg_class r ON r.oid=i.indexrelid LEFT JOIN pg_am a ON a.oid=r.relam
      WHERE pc.conrelid='public."LeagueTeamSlot"'::regclass AND pc.conname='LeagueTeamSlot_no_overlap';
    IF FOUND THEN
        IF existing.contype<>'x' OR NOT existing.convalidated OR existing.condeferrable
           OR existing.conkey IS DISTINCT FROM ARRAY[league_column,team_column,0::smallint]
           OR existing.conexclop IS DISTINCT FROM ARRAY['=(bigint,bigint)'::regoperator::oid,'=(bigint,bigint)'::regoperator::oid,'&&(anyrange,anyrange)'::regoperator::oid]
           OR NOT existing.indisvalid OR NOT existing.indisready OR NOT existing.indisexclusion OR existing.indpred IS NOT NULL OR existing.amname<>'gist'
           OR existing.expression IS DISTINCT FROM 'int8range(("acquiredWeek")::bigint, ("droppedWeek")::bigint, ''[)''::text)' THEN
            RAISE EXCEPTION 'MOD-010 blocked: overlap constraint has an unexpected definition';
        END IF;
    ELSE
        ALTER TABLE public."LeagueTeamSlot" ADD CONSTRAINT "LeagueTeamSlot_no_overlap" EXCLUDE USING gist
          ("leagueId" WITH =, "sportTeamId" WITH =,
           int8range("acquiredWeek"::bigint,"droppedWeek"::bigint,'[)') WITH &&);
    END IF;
END
$migration$;
COMMIT;
