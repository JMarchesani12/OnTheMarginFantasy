"""Named schedule member-read SQL using the caller's connection."""
from sqlalchemy import text


class ScheduleReadRepository:

    def member_games(self, conn, params):
        return conn.execute(text("""
            WITH target_week AS (
            SELECT
                COALESCE(
                    w."startDate",
                    w."endDate" + interval '1 microsecond' - interval '7 days'
                ) AS "startDate",
                w."endDate",
                l."sport"        AS "sportId",
                l."seasonYear"   AS "seasonYear",
                ss.id            AS "sportSeasonId"
            FROM "Week" w
            JOIN "League" l
                ON l.id = w."leagueId"
            JOIN "SportSeason" ss
                ON ss."sportId"    = l."sport"
            AND ss."seasonYear" = l."seasonYear"
            WHERE w."leagueId"   = :leagueId
                AND w."weekNumber" = :weekNumber
            LIMIT 1
            ),
            member_teams AS (
            SELECT lts."sportTeamId"
            FROM "LeagueTeamSlot" lts
            WHERE lts."leagueId"   = :leagueId
                AND lts."memberId"   = :memberId
                AND lts."acquiredWeek" <= :weekNumber
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
            ),
            max_tier AS (
            SELECT COALESCE(MAX(st.tier), 0) AS "maxTier"
            FROM "SportTeam" st,
                target_week tw
            WHERE st."sportId" = tw."sportId"
            )
            SELECT
            gr.id,
            gr."externalGameId",
            gr.date,
            tw."sportId",
            gr.broadcast,
            COALESCE(sp.rules, '{}'::jsonb) AS "phaseRules",
            gr."homeTeamId",
            gr."awayTeamId",
            gr."homeTeamName",
            gr."awayTeamName",
            gr."homeScore",
            gr."awayScore",
            (gr."homeTeamId" IN (SELECT "sportTeamId" FROM member_teams)) AS "ownsHome",
            (gr."awayTeamId" IN (SELECT "sportTeamId" FROM member_teams)) AS "ownsAway",
            COALESCE(home_st.tier, mt."maxTier" + 1) AS "homeTeamTier",
            COALESCE(away_st.tier, mt."maxTier" + 1) AS "awayTeamTier",
            (home_st.tier IS NULL) AS "homeTeamUnranked",
            (away_st.tier IS NULL) AS "awayTeamUnranked",
            CASE
                WHEN gr."homeTeamId" IN (SELECT "sportTeamId" FROM member_teams)
                    AND gr."awayTeamId" IN (SELECT "sportTeamId" FROM member_teams)
                THEN 0
                WHEN gr."homeTeamId" IN (SELECT "sportTeamId" FROM member_teams)
                THEN gr."homeScore" - gr."awayScore"
                WHEN gr."awayTeamId" IN (SELECT "sportTeamId" FROM member_teams)
                THEN gr."awayScore" - gr."homeScore"
                ELSE 0
            END AS "rawMemberPointDiff"
            FROM "GameResult" gr
            LEFT JOIN "SeasonPhase" sp ON sp.id=gr."seasonPhaseId"
            CROSS JOIN target_week tw
            CROSS JOIN max_tier mt
            LEFT JOIN "SportTeam" home_st
                ON home_st.id = gr."homeTeamId"
            LEFT JOIN "SportTeam" away_st
                ON away_st.id = gr."awayTeamId"
            WHERE gr.sport           = tw."sportId"
            AND gr."sportSeasonId" = tw."sportSeasonId"
            AND gr.date BETWEEN tw."startDate" AND tw."endDate"
            AND (
                gr."homeTeamId" IN (SELECT "sportTeamId" FROM member_teams)
                OR
                gr."awayTeamId" IN (SELECT "sportTeamId" FROM member_teams)
            )
            ORDER BY gr.date, gr."externalGameId";
        """), params)

    def head_to_head_games(self, conn, params):
        return conn.execute(text("""
            WITH target_week AS (
            SELECT
                w."startDate",
                w."endDate",
                l."sport"        AS "sportId",
                l."seasonYear"   AS "seasonYear",
                ss.id            AS "sportSeasonId"
            FROM "Week" w
            JOIN "League" l
                ON l.id = w."leagueId"
            JOIN "SportSeason" ss
                ON ss."sportId"    = l."sport"
            AND ss."seasonYear" = l."seasonYear"
            WHERE w."leagueId"   = :leagueId
                AND w."weekNumber" = :weekNumber
            LIMIT 1
            ),
            a_teams AS (
            SELECT lts."sportTeamId"
            FROM "LeagueTeamSlot" lts
            WHERE lts."leagueId"   = :leagueId
                AND lts."memberId"   = :memberA
                AND lts."acquiredWeek" <= :weekNumber
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
            ),
            b_teams AS (
            SELECT lts."sportTeamId"
            FROM "LeagueTeamSlot" lts
            WHERE lts."leagueId"   = :leagueId
                AND lts."memberId"   = :memberB
                AND lts."acquiredWeek" <= :weekNumber
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
            )
            SELECT
            gr.id,
            gr."externalGameId",
            gr.date,
            gr."homeTeamId",
            gr."awayTeamId",
            gr."homeTeamName",
            gr."awayTeamName",
            gr."homeScore",
            gr."awayScore",
            (gr."homeTeamId" IN (SELECT "sportTeamId" FROM a_teams)) AS "homeOwnedByA",
            (gr."awayTeamId" IN (SELECT "sportTeamId" FROM a_teams)) AS "awayOwnedByA",
            (gr."homeTeamId" IN (SELECT "sportTeamId" FROM b_teams)) AS "homeOwnedByB",
            (gr."awayTeamId" IN (SELECT "sportTeamId" FROM b_teams)) AS "awayOwnedByB"
            FROM "GameResult" gr,
                target_week tw
            WHERE gr.sport           = tw."sportId"
            AND gr."sportSeasonId" = tw."sportSeasonId"
            AND gr.date BETWEEN tw."startDate" AND tw."endDate"
            AND (
                (gr."homeTeamId" IN (SELECT "sportTeamId" FROM a_teams)
                AND gr."awayTeamId" IN (SELECT "sportTeamId" FROM b_teams))
                OR
                (gr."homeTeamId" IN (SELECT "sportTeamId" FROM b_teams)
                AND gr."awayTeamId" IN (SELECT "sportTeamId" FROM a_teams))
            )
            ORDER BY gr.date, gr."externalGameId";
        """), params)

    def week(self, conn, params):
        return conn.execute(text("""
            SELECT
                w.id,
                w."createdAt",
                w."leagueId",
                w."weekNumber",
                COALESCE(
                    w."startDate",
                    w."endDate" + interval '1 microsecond' - interval '7 days'
                ) AS "startDate",
                w."endDate",
                w."isLocked",
                w."scoringComplete"
            FROM "Week" w
            JOIN "League" l
              ON l.id = w."leagueId"
            JOIN "SportSeason" ss
              ON ss."sportId" = l.sport
             AND ss."seasonYear" = l."seasonYear"
            WHERE w."leagueId"   = :leagueId
              AND w."weekNumber" = :weekNumber
            LIMIT 1
        """), params)

    def owned_teams(self, conn, params):
        return conn.execute(text("""
            WITH member_teams AS (
                SELECT lts."sportTeamId"
                FROM "LeagueTeamSlot" lts
                WHERE lts."leagueId"     = :leagueId
                AND lts."memberId"     = :memberId
                AND lts."acquiredWeek" <= :weekNumber
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
            )
            SELECT
                st.id              AS "teamId",
                st."displayName"   AS "teamName",
                COALESCE(st.tier, (
                  SELECT COALESCE(MAX(tier_team.tier), 0) + 1
                  FROM "SportTeam" tier_team
                  WHERE tier_team."sportId" = st."sportId"
                )) AS "tier",
                sc.id              AS "sportConferenceId",
                c.name             AS "conferenceName"
            FROM member_teams mt
            JOIN "SportTeam" st
            ON st.id = mt."sportTeamId"
            LEFT JOIN "ConferenceMembership" cm
            ON cm."sportTeamId" = st.id
            AND cm."sportId" = st."sportId"
            LEFT JOIN "SportConference" sc
            ON sc.id = cm."sportConferenceId"
            AND sc."sportId" = st."sportId"
            LEFT JOIN "Conference" c
            ON c.id = sc."conferenceId"
            ORDER BY st."displayName";
        """), params)

    def week_window(self, conn, params):
        return conn.execute(text("""
            SELECT
                COALESCE(
                    w."startDate",
                    w."endDate" + interval '1 microsecond' - interval '7 days'
                ) AS "startDate",
                w."endDate"
            FROM "Week" w
            JOIN "League" l
              ON l.id = w."leagueId"
            JOIN "SportSeason" ss
              ON ss."sportId" = l.sport
             AND ss."seasonYear" = l."seasonYear"
            WHERE w."leagueId" = :leagueId
              AND w."weekNumber" = :weekNumber
            LIMIT 1
        """), params)

    def conference_games(self, conn, params):
        return conn.execute(text("""
            WITH sc AS (
                SELECT id, "sportId", "conferenceId"
                FROM "SportConference"
                WHERE id = :sportConferenceId
                LIMIT 1
            ),
            ss AS (
                SELECT s.id AS "sportSeasonId"
                FROM "SportSeason" s
                JOIN sc ON sc."sportId" = s."sportId"
                WHERE s."seasonYear" = :seasonYear
                LIMIT 1
            ),
            conf_teams AS (
                SELECT st.id AS "sportTeamId"
                FROM "ConferenceMembership" cm
                JOIN sc
                  ON sc."sportId" = cm."sportId"
                 AND sc.id = cm."sportConferenceId"
                JOIN "SportTeam" st
                  ON st.id = cm."sportTeamId"
                 AND st."sportId" = sc."sportId"
                WHERE (cm."seasonYear" IS NULL OR cm."seasonYear" = :seasonYear)
            )
            SELECT
                gr.id,
                gr."externalGameId",
                gr.date,
                gr.sport,
                gr."sportSeasonId",
                gr."seasonPhaseId",
                gr."roundOrder",
                gr."homeTeamId",
                gr."awayTeamId",
                gr."broadcast",
                gr."homeTeamName",
                gr."awayTeamName",
                gr."homeScore",
                gr."awayScore",
                home_lm.id AS "homeOwnerMemberId",
                home_lm."teamName" AS "homeOwnerTeamName",
                home_u."displayName" AS "homeOwnerDisplayName",
                away_lm.id AS "awayOwnerMemberId",
                away_lm."teamName" AS "awayOwnerTeamName",
                away_u."displayName" AS "awayOwnerDisplayName",
                (gr."homeTeamId" IN (SELECT "sportTeamId" FROM conf_teams)) AS "homeInConference",
                (gr."awayTeamId" IN (SELECT "sportTeamId" FROM conf_teams)) AS "awayInConference"
            FROM "GameResult" gr
            JOIN ss ON ss."sportSeasonId" = gr."sportSeasonId"
            LEFT JOIN "LeagueTeamSlot" home_lts
              ON home_lts."leagueId" = :leagueId
             AND home_lts."sportTeamId" = gr."homeTeamId"
             AND home_lts."acquiredWeek" <= :weekNumber
             AND (home_lts."droppedWeek" IS NULL OR home_lts."droppedWeek" > :weekNumber)
            LEFT JOIN "LeagueMember" home_lm
              ON home_lm.id = home_lts."memberId"
            LEFT JOIN "User" home_u
              ON home_u.id = home_lm."userId"
            LEFT JOIN "LeagueTeamSlot" away_lts
              ON away_lts."leagueId" = :leagueId
             AND away_lts."sportTeamId" = gr."awayTeamId"
             AND away_lts."acquiredWeek" <= :weekNumber
             AND (away_lts."droppedWeek" IS NULL OR away_lts."droppedWeek" > :weekNumber)
            LEFT JOIN "LeagueMember" away_lm
              ON away_lm.id = away_lts."memberId"
            LEFT JOIN "User" away_u
              ON away_u.id = away_lm."userId"
            WHERE (
                gr."homeTeamId" IN (SELECT "sportTeamId" FROM conf_teams)
                OR gr."awayTeamId" IN (SELECT "sportTeamId" FROM conf_teams)
            )
              AND gr.date >= :weekStart
              AND gr.date <= :weekEnd
            ORDER BY gr.date, gr."externalGameId";
        """), params)

    def team_owner_context(self, conn, params):
        return conn.execute(text("""
            SELECT
                COALESCE(current_week."weekNumber", latest_week."weekNumber", 999) AS "weekNumber"
            FROM "League" l
            LEFT JOIN LATERAL (
                SELECT w."weekNumber"
                FROM "Week" w
                WHERE w."leagueId" = l.id
                  AND now() >= COALESCE(
                    w."startDate",
                    w."endDate" + interval '1 microsecond' - interval '7 days'
                  )
                  AND now() <= w."endDate"
                ORDER BY w."weekNumber" DESC
                LIMIT 1
            ) current_week ON true
            LEFT JOIN LATERAL (
                SELECT w."weekNumber"
                FROM "Week" w
                WHERE w."leagueId" = l.id
                ORDER BY w."weekNumber" DESC
                LIMIT 1
            ) latest_week ON true
            WHERE l.id = :leagueId
            LIMIT 1
        """), params)

    def team_season_games(self, conn, params):
        return conn.execute(text("""
            WITH st AS (
                SELECT id, "sportId"
                FROM "SportTeam"
                WHERE id = :sportTeamId
                LIMIT 1
            ),
            ss AS (
                SELECT s.id AS "sportSeasonId"
                FROM "SportSeason" s
                JOIN st ON st."sportId" = s."sportId"
                WHERE s."seasonYear" = :seasonYear
                LIMIT 1
            )
            SELECT
                gr.id,
                gr."externalGameId",
                gr.date,
                gr.sport,
                gr."broadcast",
                gr."sportSeasonId",
                gr."seasonPhaseId",
                gr."roundOrder",
                gr."homeTeamId",
                gr."awayTeamId",
                gr."homeTeamName",
                gr."awayTeamName",
                gr."homeScore",
                gr."awayScore",
                (gr."homeTeamId" = :sportTeamId) AS "isHome",
                CASE
                    WHEN gr."homeTeamId" = :sportTeamId THEN gr."awayTeamId"
                    ELSE gr."homeTeamId"
                END AS "opponentTeamId",
                CASE
                    WHEN gr."homeTeamId" = :sportTeamId THEN gr."awayTeamName"
                    ELSE gr."homeTeamName"
                END AS "opponentTeamName",
                owner_lm.id AS "ownerMemberId",
                owner_lm."teamName" AS "ownerTeamName",
                owner_u."displayName" AS "ownerDisplayName"
            FROM "GameResult" gr
            JOIN ss ON ss."sportSeasonId" = gr."sportSeasonId"
            LEFT JOIN "LeagueTeamSlot" owner_lts
              ON :leagueId IS NOT NULL
             AND owner_lts."leagueId" = :leagueId
             AND owner_lts."sportTeamId" = :sportTeamId
             AND owner_lts."acquiredWeek" <= :weekNumber
             AND (owner_lts."droppedWeek" IS NULL OR owner_lts."droppedWeek" > :weekNumber)
            LEFT JOIN "LeagueMember" owner_lm
              ON owner_lm.id = owner_lts."memberId"
            LEFT JOIN "User" owner_u
              ON owner_u.id = owner_lm."userId"
            WHERE (gr."homeTeamId" = :sportTeamId OR gr."awayTeamId" = :sportTeamId)
            ORDER BY gr.date, gr."externalGameId";
        """), params)

    def search_league_context(self, conn, params):
        return conn.execute(text("""
            SELECT
                l.sport,
                l."seasonYear",
                COALESCE(current_week."weekNumber", latest_week."weekNumber", 999) AS "weekNumber"
            FROM "League" l
            LEFT JOIN LATERAL (
                SELECT w."weekNumber"
                FROM "Week" w
                WHERE w."leagueId" = l.id
                  AND now() >= COALESCE(
                    w."startDate",
                    w."endDate" + interval '1 microsecond' - interval '7 days'
                  )
                  AND now() <= w."endDate"
                ORDER BY w."weekNumber" DESC
                LIMIT 1
            ) current_week ON true
            LEFT JOIN LATERAL (
                SELECT w."weekNumber"
                FROM "Week" w
                WHERE w."leagueId" = l.id
                ORDER BY w."weekNumber" DESC
                LIMIT 1
            ) latest_week ON true
            WHERE l.id = :leagueId
            LIMIT 1
        """), params)

    def search_teams(self, conn, params):
        return conn.execute(text("""
            SELECT
                st.id AS "teamId",
                st."displayName" AS "teamName",
                c.name AS "conferenceName",
                lm.id AS "ownerMemberId",
                lm."teamName" AS "ownerTeamName",
                u."displayName" AS "ownerDisplayName"
            FROM "SportTeam" st
            LEFT JOIN "ConferenceMembership" cm
              ON cm."sportTeamId" = st.id
             AND cm."sportId" = st."sportId"
             AND (cm."seasonYear" IS NULL OR cm."seasonYear" = :seasonYear)
            LEFT JOIN "SportConference" sc
              ON sc.id = cm."sportConferenceId"
             AND sc."sportId" = st."sportId"
            LEFT JOIN "Conference" c
              ON c.id = sc."conferenceId"
            LEFT JOIN "LeagueTeamSlot" lts
              ON lts."leagueId" = :leagueId
             AND lts."sportTeamId" = st.id
             AND lts."acquiredWeek" <= :weekNumber
             AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
            LEFT JOIN "LeagueMember" lm
              ON lm.id = lts."memberId"
            LEFT JOIN "User" u
              ON u.id = lm."userId"
            WHERE st."sportId" = :sport
            ORDER BY st."displayName"
        """), params)
