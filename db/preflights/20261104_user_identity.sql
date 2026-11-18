-- Aggregate-only, read-only snapshot. No subject IDs, email, names or row exports.
-- Run using a role with a verified complete view of public.User; RLS-filtered
-- counts cannot establish readiness. This does not authorize hosted access.
BEGIN READ ONLY;
SET LOCAL row_security = off;
SET LOCAL statement_timeout = '30s';
WITH duplicates AS (
    SELECT count(*) AS profiles
    FROM public."User"
    WHERE uuid IS NOT NULL
    GROUP BY uuid
    HAVING count(*) > 1
)
SELECT
    (SELECT count(*) FROM public."User") AS total_profiles,
    (SELECT count(*) FROM public."User" WHERE uuid IS NULL) AS unlinked_profiles,
    count(*) AS duplicate_subject_groups,
    coalesce(sum(profiles), 0)::bigint AS profiles_in_duplicate_groups
FROM duplicates;
COMMIT;
