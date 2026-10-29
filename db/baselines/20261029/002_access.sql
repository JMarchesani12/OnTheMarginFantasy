-- Observed access baseline. Broad grants are deliberately preserved; tightening is separate.

CREATE FUNCTION public.rls_auto_enable()
 RETURNS event_trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog'
AS $function$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN
    SELECT *
    FROM pg_event_trigger_ddl_commands()
    WHERE command_tag IN ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO')
      AND object_type IN ('table','partitioned table')
  LOOP
     IF cmd.schema_name IS NOT NULL AND cmd.schema_name IN ('public') AND cmd.schema_name NOT IN ('pg_catalog','information_schema') AND cmd.schema_name NOT LIKE 'pg_toast%' AND cmd.schema_name NOT LIKE 'pg_temp%' THEN
      BEGIN
        EXECUTE format('alter table if exists %s enable row level security', cmd.object_identity);
        RAISE LOG 'rls_auto_enable: enabled RLS on %', cmd.object_identity;
      EXCEPTION
        WHEN OTHERS THEN
          RAISE LOG 'rls_auto_enable: failed to enable RLS on %', cmd.object_identity;
      END;
     ELSE
        RAISE LOG 'rls_auto_enable: skip % (either system schema or not in enforced list: %.)', cmd.object_identity, cmd.schema_name;
     END IF;
  END LOOP;
END;
$function$
;

CREATE EVENT TRIGGER ensure_rls ON ddl_command_end WHEN TAG IN ('CREATE TABLE','CREATE TABLE AS','SELECT INTO') EXECUTE FUNCTION public.rls_auto_enable();

ALTER TABLE public."Conference" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."ConferenceMembership" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."DraftPick" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."DraftState" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."DraftTurn" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."GameResult" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."League" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."LeagueJoinRequest" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."LeagueMember" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."LeagueTeamSlot" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."School" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."SeasonPhase" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."Sport" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."SportConference" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."SportSeason" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."SportSeasonSubdivision" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."SportTeam" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."TournamentDefinition" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."Transaction" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."TransactionVote" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."User" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."Week" ENABLE ROW LEVEL SECURITY;

ALTER TABLE public."WeeklyTeamScore" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "read own user row" ON public."User" FOR SELECT TO PUBLIC USING (uuid=auth.uid());

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;

GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;

GRANT EXECUTE ON FUNCTION public.rls_auto_enable() TO PUBLIC, anon, authenticated, service_role;

GRANT USAGE ON SCHEMA public TO PUBLIC, postgres, anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO postgres, anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres, anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO postgres, anon, authenticated, service_role;
