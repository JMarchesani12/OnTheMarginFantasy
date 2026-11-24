-- Prepared only. Apply deliberately before deploying the bonus readers/jobs.
BEGIN;
SET LOCAL lock_timeout = '5s';
ALTER TABLE public."GameResult" ADD COLUMN "bonusTournamentCode" text
 CHECK ("bonusTournamentCode" IS NULL OR "bonusTournamentCode" IN ('NCAA_TOURNEY','FCS_PLAYOFFS','FBS_PLAYOFFS'));
CREATE TABLE public."ConferenceStandingsSnapshot" (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 "sportSeasonId" bigint NOT NULL REFERENCES public."SportSeason"(id),
 "sportConferenceId" bigint NOT NULL REFERENCES public."SportConference"(id),
 "sourceYear" integer NOT NULL,
 "sourceUrl" text NOT NULL,
 "retrievedAt" timestamptz NOT NULL DEFAULT now(),
 "regularEnd" date NOT NULL,
 "isFinal" boolean NOT NULL,
 digest text NOT NULL,
 entries jsonb NOT NULL CHECK (jsonb_typeof(entries)='array' AND jsonb_array_length(entries)>0),
 UNIQUE ("sportSeasonId", "sportConferenceId", digest)
);
CREATE INDEX "ConferenceStandingsSnapshot_lookup" ON public."ConferenceStandingsSnapshot"
 ("sportSeasonId", "sportConferenceId", "isFinal", id DESC);
CREATE TABLE public."SeasonBonusResult" (
 "leagueId" bigint PRIMARY KEY REFERENCES public."League"(id),
 result jsonb NOT NULL CHECK (jsonb_typeof(result)='object'),
 "finalizedAt" timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public."ConferenceStandingsSnapshot" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."SeasonBonusResult" ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public."ConferenceStandingsSnapshot",public."SeasonBonusResult" FROM PUBLIC,anon,authenticated;
REVOKE ALL ON SEQUENCE public."ConferenceStandingsSnapshot_id_seq" FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT ON public."ConferenceStandingsSnapshot",public."SeasonBonusResult" TO service_role;
GRANT USAGE,SELECT ON SEQUENCE public."ConferenceStandingsSnapshot_id_seq" TO service_role;
COMMIT;
