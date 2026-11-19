-- Destructive phase: run only AFTER all API/job deployments use School.name.
-- Caller owns the bounded transaction and alias/name preservation verification.
DO $guard$
BEGIN
    IF current_setting('onthemargin.school_names_verified', true) IS DISTINCT FROM 'true' THEN
        RAISE EXCEPTION 'Use the reviewed school-name migration runner after deployment';
    END IF;
END
$guard$;
ALTER TABLE public."School" DROP COLUMN IF EXISTS "shortName";
ALTER TABLE public."SportTeam" DROP COLUMN IF EXISTS "displayName";
-- Deliberately no CASCADE: unexpected dependent objects must stop the migration.
