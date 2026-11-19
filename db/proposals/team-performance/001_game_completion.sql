-- Apply before deploying the ingestion code. Unknown historical status stays NULL.
-- Re-run the existing season scoreboard ingestion to populate confirmed finals.
BEGIN;
ALTER TABLE public."GameResult" ADD COLUMN IF NOT EXISTS "isCompleted" boolean;
COMMENT ON COLUMN public."GameResult"."isCompleted" IS
  'Provider-confirmed completion; NULL means status has not been supplied. Never infer from scores.';
COMMIT;
