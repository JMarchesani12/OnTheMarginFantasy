"""Roster persistence on a service-supplied connection; no engine or commits."""
from sqlalchemy import text
from utils.authorization import league_read_scope


class RosterRepository:
    def member_read_allowed(self, conn, league_id, member_id, user_id):
        scope, params = league_read_scope(league_id, user_id)
        return conn.execute(text('''SELECT id FROM "LeagueMember"
            WHERE id = :memberId AND "leagueId" = :leagueId ''' + scope),
            dict(leagueId=league_id, memberId=member_id, **params)).fetchone() is not None

    def get_league(self, conn, league_id, reader_user_id=None):
        scope, params = league_read_scope(league_id, reader_user_id)
        row = conn.execute(text('SELECT sport, "seasonYear" FROM "League" WHERE id = :leagueId ' + scope),
                           {'leagueId': league_id, **params}).fetchone()
        return dict(row._mapping) if row else None

    def get_week_by_number(self, conn, league_id: int, week_number: int):
        row = conn.execute(
            text("""
                SELECT id, "weekNumber", "isLocked"
                FROM "Week"
                WHERE "leagueId" = :league_id
                  AND "weekNumber" = :week_number
                LIMIT 1
            """),
            {"league_id": league_id, "week_number": week_number},
        ).fetchone()

        return dict(row._mapping) if row else None

    def next_unlocked_week_number(self, conn, league_id, week_number):
        row = conn.execute(
            text("""
                SELECT "weekNumber"
                FROM "Week"
                WHERE "leagueId" = :league_id
                  AND "weekNumber" > :week_number
                  AND "isLocked" = FALSE
                ORDER BY "weekNumber" ASC
                LIMIT 1
            """),
            {"league_id": league_id, "week_number": week_number},
        ).fetchone()
        return int(row[0]) if row else None

    def member_teams(self, conn, league_id, member_id, week_number, reader_user_id=None):
        scope, reader_params = league_read_scope(league_id, reader_user_id)
        sql = text("""
            WITH league_info AS (
              SELECT "seasonYear"
              FROM "League"
              WHERE id = :leagueId
            )
            SELECT
              lts.id                AS "slotId",
              lts."sportTeamId",
              lts."acquiredWeek",
              lts."droppedWeek",
              lts."acquiredVia",
              st."displayName",
              COALESCE(st.tier, (
                    SELECT COALESCE(MAX(tier_team.tier), 0) + 1
                    FROM "SportTeam" tier_team
                    WHERE tier_team."sportId" = st."sportId"
                  )) AS "tier",
              st."externalId",
              sc.id                 AS "sportConferenceId",
              c.name                AS "conferenceName"
            FROM "LeagueTeamSlot" lts
            JOIN "SportTeam" st
              ON st.id = lts."sportTeamId"
            CROSS JOIN league_info li
            LEFT JOIN "ConferenceMembership" cm
              ON cm."sportTeamId" = st.id
             AND cm."sportId" = st."sportId"
             AND (cm."seasonYear" IS NULL OR cm."seasonYear" = li."seasonYear")
            LEFT JOIN "SportConference" sc
              ON sc.id = cm."sportConferenceId"
             AND sc."sportId" = st."sportId"
            LEFT JOIN "Conference" c
              ON c.id = sc."conferenceId"
            WHERE lts."leagueId" = :leagueId
              AND lts."memberId" = :memberId
              AND lts."acquiredWeek" <= :weekNumber
              AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
            """ + scope + ("""
              AND EXISTS (SELECT 1 FROM "LeagueMember" target_member
                          WHERE target_member.id = lts."memberId"
                            AND target_member."leagueId" = lts."leagueId")
            """ if reader_user_id is not None else "") + """
            ORDER BY st."displayName"
        """)
        result = conn.execute(sql, {**reader_params, 'leagueId': league_id,
                                   'memberId': member_id, 'weekNumber': week_number})
        return [dict(r._mapping) for r in result]

    def available_teams(self, conn, league_id, sport_id, season_year, week_id, week_number, reader_user_id=None):
        scope, reader_params = league_read_scope(league_id, reader_user_id)
        sql = text("""
            WITH pending_adds AS (
              SELECT DISTINCT (jsonb_array_elements_text(t."toTeamIds"))::int AS team_id
              FROM "Transaction" t
              WHERE t."leagueId" = :leagueId
                AND t."weekId" = :weekId
                AND t.status = 'PENDING_APPLY'
                AND t.type = 'FREE_AGENT'
                AND t."toTeamIds" IS NOT NULL
            ),
            pending_drops AS (
              SELECT DISTINCT (jsonb_array_elements_text(t."fromTeamIds"))::int AS team_id
              FROM "Transaction" t
              WHERE t."leagueId" = :leagueId
                AND t."weekId" = :weekId
                AND t.status = 'PENDING_APPLY'
                AND t.type = 'FREE_AGENT'
                AND t."fromTeamIds" IS NOT NULL
            )
            SELECT
              st.id,
              st."displayName",
              COALESCE(st.tier, (
                  SELECT COALESCE(MAX(tier_team.tier), 0) + 1
                  FROM "SportTeam" tier_team
                  WHERE tier_team."sportId" = st."sportId"
                )) AS "tier",
              st."externalId",
              st."schoolId",
              st."sportId",
              sc.id AS "sportConferenceId",
              sc."conferenceId",
              conf.name AS "conferenceName"
            FROM "SportTeam" st
            LEFT JOIN "ConferenceMembership" cm
              ON cm."sportTeamId" = st.id
             AND cm."sportId" = st."sportId"
             AND (cm."seasonYear" IS NULL OR cm."seasonYear" = :seasonYear)
            LEFT JOIN "SportConference" sc
              ON sc.id = cm."sportConferenceId"
             AND sc."sportId" = st."sportId"
            LEFT JOIN "Conference" conf
              ON conf.id = sc."conferenceId"
            WHERE st."sportId" = :sportId
              AND st.id NOT IN (SELECT team_id FROM pending_adds)
              AND (
                NOT EXISTS (
                  SELECT 1
                  FROM "LeagueTeamSlot" lts
                  WHERE lts."leagueId" = :leagueId
                    AND lts."sportTeamId" = st.id
                    AND lts."acquiredWeek" <= :weekNumber
                    AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
                )
                OR st.id IN (SELECT team_id FROM pending_drops)
              )
            """ + scope + """
            ORDER BY conf.name, st."displayName"
        """)
        result = conn.execute(sql, {**reader_params, 'leagueId': league_id, 'sportId': sport_id,
                                   'seasonYear': season_year, 'weekId': week_id, 'weekNumber': week_number})
        return [dict(r._mapping) for r in result]
