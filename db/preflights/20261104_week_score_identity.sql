-- Aggregate-only period/score readiness; never exports identifiers or rows.
BEGIN READ ONLY;
SET LOCAL row_security = off;
SET LOCAL statement_timeout = '30s';
WITH week_duplicates AS (
    SELECT count(*) AS rows FROM public."Week"
    GROUP BY "leagueId", "weekNumber" HAVING count(*) > 1
), score_duplicates AS (
    SELECT count(*) AS rows FROM public."WeeklyTeamScore"
    GROUP BY "leagueId", "weekId", "memberId" HAVING count(*) > 1
)
SELECT
    (SELECT count(*) FROM public."Week") AS total_weeks,
    (SELECT count(*) FROM public."WeeklyTeamScore") AS total_scores,
    (SELECT count(*) FROM week_duplicates) AS duplicate_week_groups,
    (SELECT coalesce(sum(rows),0)::bigint FROM week_duplicates) AS duplicate_week_rows,
    (SELECT count(*) FROM score_duplicates) AS duplicate_score_groups,
    (SELECT coalesce(sum(rows),0)::bigint FROM score_duplicates) AS duplicate_score_rows,
    (SELECT count(*) FROM public."Week" WHERE "leagueId" IS NULL OR "weekNumber" IS NULL) AS null_week_keys,
    (SELECT count(*) FROM public."WeeklyTeamScore" WHERE "leagueId" IS NULL OR "weekId" IS NULL OR "memberId" IS NULL) AS null_score_keys,
    (SELECT count(*) FROM public."WeeklyTeamScore" s LEFT JOIN public."Week" w ON w.id=s."weekId"
        WHERE w.id IS NULL OR w."leagueId" IS DISTINCT FROM s."leagueId") AS wrong_week_league_scores,
    (SELECT count(*) FROM public."WeeklyTeamScore" s LEFT JOIN public."LeagueMember" m ON m.id=s."memberId"
        WHERE m.id IS NULL OR m."leagueId" IS DISTINCT FROM s."leagueId") AS wrong_member_league_scores;
COMMIT;
