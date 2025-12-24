# endpoints/roster/rosterModel.py
from typing import Any, Dict, List
from sqlalchemy import text
from sqlalchemy.engine import Engine

class RosterModel:
    def __init__(self, db: Engine):
        self.db = db

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

        if not league_row:
            return []

        sport_id = league_row._mapping["sport"]

        # 2) Query available teams with conference info
        sql = text("""
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
              AND NOT EXISTS (
                SELECT 1
                FROM "LeagueTeamSlot" lts
                WHERE lts."leagueId" = :leagueId
                  AND lts."sportTeamId" = st.id
                  AND lts."acquiredWeek" <= :weekNumber
                  AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
              )
            ORDER BY conf.name, st."displayName"
        """)

        with self.db.connect() as conn:
            result = conn.execute(
                sql,
                {
                    "leagueId": league_id,
                    "sportId": sport_id,
                    "weekNumber": week_number,
                },
            )
            return [dict(r._mapping) for r in result]