# endpoints/roster/rosterModel.py
from typing import Any, Dict, List
from sqlalchemy import text
from sqlalchemy.engine import Engine

class RosterModel:
    def __init__(self, db: Engine):
        self.db = db

    def _get_week_by_number(self, conn, league_id: int, week_number: int):
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

    def _get_next_unlocked_week_number(self, conn, league_id: int, week_number: int) -> int:
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

        if not row:
            raise ValueError(f"No unlocked future week found after week {week_number}")

        return int(row[0])

    def get_member_teams_for_week(
      self,
      league_id: int,
      member_id: int,
      week_number: int
  ) -> List[Dict[str, Any]]:
      sql = text("""
          SELECT
            lts.id                AS "slotId",
            lts."sportTeamId",
            lts."acquiredWeek",
            lts."droppedWeek",
            lts."acquiredVia",
            st."displayName",
            st."externalId",
            c.name                AS "conferenceName"
          FROM "LeagueTeamSlot" lts
          JOIN "SportTeam" st
            ON st.id = lts."sportTeamId"
          LEFT JOIN "ConferenceMembership" cm
            ON cm."sportTeamId" = st.id
          LEFT JOIN "SportConference" sc
            ON sc.id = cm."sportConferenceId"
          LEFT JOIN "Conference" c
            ON c.id = sc."conferenceId"
          WHERE lts."leagueId" = :leagueId
            AND lts."memberId" = :memberId
            AND lts."acquiredWeek" <= :weekNumber
            AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
          ORDER BY st."displayName"
      """)

      with self.db.connect() as conn:
          result = conn.execute(
              sql,
              {
                  "leagueId": league_id,
                  "memberId": member_id,
                  "weekNumber": week_number,
              },
          )
          return [dict(r._mapping) for r in result]


    def get_available_teams_for_week(
        self,
        league_id: int,
        week_number: int,
    ) -> List[Dict[str, Any]]:
        """
        Returns all SportTeams in the league's sport that are NOT owned by
        any member in this league for the given week.

        Includes:
          - sportConferenceId
          - conferenceId
          - conferenceName
        so the frontend can group by conference.
        """

        # 1) Get the league's sport so we only include teams from that sport
        league_sql = text('SELECT sport FROM "League" WHERE id = :leagueId')

        with self.db.connect() as conn:
            league_row = conn.execute(league_sql, {"leagueId": league_id}).fetchone()
            week_info = self._get_week_by_number(conn, league_id, week_number)
            if week_info and week_info.get("isLocked"):
                week_number = self._get_next_unlocked_week_number(
                    conn,
                    league_id=league_id,
                    week_number=week_number,
                )
                week_info = self._get_week_by_number(conn, league_id, week_number)

        if not league_row:
            return []
        if not week_info:
            return []

        sport_id = league_row._mapping["sport"]
        week_id = int(week_info["id"])

        # 2) Query available teams with conference info
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
              st."externalId",
              st."schoolId",
              st."sportId",
              cm."sportConferenceId",
              sc."conferenceId",
              conf.name AS "conferenceName"
            FROM "SportTeam" st
            JOIN "ConferenceMembership" cm
              ON cm."sportTeamId" = st.id
            JOIN "SportConference" sc
              ON sc.id = cm."sportConferenceId"
            JOIN "Conference" conf
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
            ORDER BY conf.name, st."displayName"
        """)

        with self.db.connect() as conn:
            result = conn.execute(
                sql,
                {
                    "leagueId": league_id,
                    "sportId": sport_id,
                    "weekId": week_id,
                    "weekNumber": week_number,
                },
            )
            return [dict(r._mapping) for r in result]
