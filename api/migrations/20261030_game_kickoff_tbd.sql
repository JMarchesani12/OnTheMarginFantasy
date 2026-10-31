-- Apply before deploying the schedule API. Reingest schedules afterward to
-- populate ESPN timeValid flags; do not infer TBD from clock time alone.
ALTER TABLE "GameResult"
    ADD COLUMN IF NOT EXISTS "timeTBD" boolean NOT NULL DEFAULT false;
