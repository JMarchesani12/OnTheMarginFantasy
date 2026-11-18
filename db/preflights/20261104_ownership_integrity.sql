-- Aggregate ownership integrity only: no IDs, teams, owners or private rows.
BEGIN READ ONLY;
SET LOCAL row_security = off;
SET LOCAL statement_timeout = '30s';
SELECT
    (SELECT count(*) FROM public."LeagueTeamSlot") AS total_slots,
    (SELECT count(*) FROM public."LeagueTeamSlot" WHERE "acquiredWeek"<0) AS negative_starts,
    (SELECT count(*) FROM public."LeagueTeamSlot" WHERE "droppedWeek"<"acquiredWeek") AS reversed_intervals,
    (SELECT count(*) FROM public."LeagueTeamSlot" WHERE "droppedWeek"="acquiredWeek") AS empty_intervals,
    (SELECT count(*) FROM public."LeagueTeamSlot" s LEFT JOIN public."LeagueMember" m ON m.id=s."memberId"
        WHERE m.id IS NULL OR m."leagueId" IS DISTINCT FROM s."leagueId") AS wrong_member_league_slots,
    (SELECT count(*) FROM public."LeagueTeamSlot" s JOIN public."League" l ON l.id=s."leagueId"
        JOIN public."SportTeam" t ON t.id=s."sportTeamId" WHERE t."sportId" IS DISTINCT FROM l.sport) AS wrong_sport_slots,
    (SELECT count(*) FROM public."LeagueTeamSlot" a JOIN public."LeagueTeamSlot" b
        ON a.id<b.id AND a."leagueId"=b."leagueId" AND a."sportTeamId"=b."sportTeamId"
        WHERE (a."droppedWeek" IS NULL OR a."droppedWeek">a."acquiredWeek")
          AND (b."droppedWeek" IS NULL OR b."droppedWeek">b."acquiredWeek")
          AND a."acquiredWeek"::bigint<coalesce(b."droppedWeek"::bigint,9223372036854775807)
          AND b."acquiredWeek"::bigint<coalesce(a."droppedWeek"::bigint,9223372036854775807)) AS overlapping_pairs,
    (SELECT count(*) FROM public."LeagueTeamSlot" a JOIN public."LeagueTeamSlot" b
        ON a.id<>b.id AND a."leagueId"=b."leagueId" AND a."sportTeamId"=b."sportTeamId"
        AND a."droppedWeek"=b."acquiredWeek"
        WHERE a."droppedWeek">a."acquiredWeek") AS adjacent_transfers;
COMMIT;
