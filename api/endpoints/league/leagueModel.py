import json
import logging
import math
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.engine import Engine


class LeagueModel:
    def __init__(self, db: Engine):
        self.db = db

    def create_league(self, league: Dict[str, Any]) -> Dict[str, Any]:
        # Make a copy so we don't mutate the original dict
        league = dict(league)

        # JSON-encode the settings dict so Postgres can cast it to jsonb
        if isinstance(league.get("settings"), (dict, list)):
            league["settings"] = json.dumps(league["settings"])

        sql = text("""
            INSERT INTO "League"
                ("name", sport, "numPlayers", status, settings, "updatedAt", "draftDate", "commissioner")
            VALUES
                (:name, :sport, :numPlayers, :status, cast(:settings as jsonb), now(), :draftDate, :commissioner)
            RETURNING id, "createdAt", "name", sport, "numPlayers", status, settings, "updatedAt", "draftDate", "commissioner"
        """)

        with self.db.begin() as conn:
            result = conn.execute(sql, league)
            created_row = result.fetchone()

        if not created_row:
            raise RuntimeError("Failed to create League")

        created = dict(created_row._mapping)

        # Create LeagueMember for commissioner
        lm_sql = text("""
            INSERT INTO "LeagueMember"
                ("leagueId", "userId", "teamName", "seasonPoints")
            VALUES
                (:leagueId, :userId, :teamName, 0)
            RETURNING id
        """)

        with self.db.begin() as conn:
            lm_row = conn.execute(
                lm_sql,
                {
                    "leagueId": created["id"],
                    "userId": created["commissioner"],
                    "teamName": "My Team",
                },
            ).fetchone()

        created["creatorMemberId"] = lm_row._mapping["id"]

        return created
    
    # 1) All leagues a user is in
    def get_leagues_for_user(self, user_id: int, stage: str = "all") -> List[Dict[str, Any]]:
        """
        stage: "all" | "active" | "completed"
        - all: no additional status filter
        - active: status != 'completed'
        - completed: status = 'completed'
        """

        stage = (stage or "all").lower()
        if stage not in ("all", "active", "completed"):
            stage = "all"

        base_sql = """
            SELECT
            -- League fields
            l.id                AS "leagueId",
            l."createdAt"       AS "leagueCreatedAt",
            l."name"            AS "leagueName",
            l."numPlayers"      AS "numPlayers",
            l.status            AS "status",
            l."updatedAt"       AS "updatedAt",
            l."draftDate"       AS "draftDate",
            l."tradeDeadline"   AS "tradeDeadline",
            l."freeAgentDeadline" AS "freeAgentDeadline",
            l."seasonYear"      AS "seasonYear",

            -- Commissioner info
            cu."displayName"    AS "commissionerDisplayName",
            cu."id"             AS "commissionerId",

            -- Sport info
            s.name              AS "sport",

            -- Member-specific fields for this user
            lm.id               AS "memberId",
            lm."teamName"       AS "teamName",
            lm."draftOrder"     AS "draftOrder",
            lm."seasonPoints"   AS "seasonPoints",

            -- Current week info (nullable if no matching week)
            w.id                AS "currentWeekId",
            w."weekNumber"      AS "currentWeekNumber",
            w."startDate"       AS "currentWeekStartDate",
            w."endDate"         AS "currentWeekEndDate"

            FROM "LeagueMember" lm
            JOIN "League"      l  ON l.id = lm."leagueId"
            JOIN "Sport"       s  ON s.id = l."sport"
            JOIN "User"        cu ON cu.id = l.commissioner

            LEFT JOIN "Week"   w
            ON w."leagueId" = l.id
            AND now() >= w."startDate"
            AND now() <= w."endDate"

            WHERE lm."userId" = :user_id
        """

        if stage == "active":
            base_sql += " AND l.status <> 'completed'"
        elif stage == "completed":
            base_sql += " AND l.status = 'completed'"

        base_sql += ' ORDER BY l.id, lm."draftOrder"'

        sql = text(base_sql)

        with self.db.connect() as conn:
            result = conn.execute(sql, {"user_id": user_id})
            rows = [dict(r._mapping) for r in result]

        logging.debug(
            "get_leagues_for_user(user_id=%s, stage=%s) -> %d rows",
            user_id,
            stage,
            len(rows),
        )
        return rows


    def get_members_for_league(self, league_id: int) -> List[Dict[str, Any]]:
        sql = text(
            """
            SELECT
              lm.id               AS "memberId",
              lm."createdAt"      AS "memberCreatedAt",
              lm."leagueId"       AS "leagueId",
              lm."userId"         AS "userId",
              lm."teamName"       AS "teamName",
              lm."draftOrder"     AS "draftOrder",
              lm."seasonPoints"   AS "seasonPoints"
            FROM "LeagueMember" lm
            WHERE lm."leagueId" = :league_id
            ORDER BY lm."draftOrder", lm.id
            """
        )

        with self.db.connect() as conn:
            result = conn.execute(sql, {"league_id": league_id})
            rows = [dict(r._mapping) for r in result]

        members: List[Dict[str, Any]] = []
        for r in rows:
            members.append(
                {
                    "id": r["memberId"],
                    "createdAt": r["memberCreatedAt"],
                    "leagueId": r["leagueId"],
                    "userId": r["userId"],
                    "teamName": r["teamName"],
                    "draftOrder": r["draftOrder"],
                    "seasonPoints": r["seasonPoints"]
                }
            )

        return members

    def get_league_conferences(self, league_id: int) -> Dict[str, Any]:
        """
        For a leagueId, returns all SportConference rows for that league's sport,
        joined to base Conference for displayName, plus team counts.
        """

        # IMPORTANT: adjust these column names if your League schema differs
        league_sql = text("""
            SELECT
              id AS "leagueId",
              sport AS "sportId",
              "seasonYear" AS "seasonYear"
            FROM "League"
            WHERE id = :leagueId
            LIMIT 1
        """)

        with self.db.begin() as conn:
            league_row = conn.execute(league_sql, {"leagueId": league_id}).fetchone()

            if not league_row:
                raise ValueError(f"League {league_id} not found")

            league = dict(league_row._mapping)
            sport_id = league["sportId"]
            season_year = league.get("seasonYear")

            if season_year is None:
                # If your League table truly doesn't store seasonYear, you can:
                # 1) require it as a query param, OR
                # 2) decide a default.
                # I'm not going to guess—so we fail loudly.
                raise ValueError("League.seasonYear is null/missing; cannot compute season-scoped memberships")

            conf_sql = text("""
                SELECT
                  sc.id AS "sportConferenceId",
                  sc."conferenceId" AS "conferenceId",
                  c.name AS "displayName",
                  sc."maxTeamsPerOwner" AS "maxTeamsPerOwner",
                  COALESCE(t."teamsInConference", 0) AS "teamsInConference"
                FROM "SportConference" sc
                JOIN "Conference" c ON c.id = sc."conferenceId"
                LEFT JOIN (
                  SELECT
                    cm."sportConferenceId",
                    COUNT(*) AS "teamsInConference"
                  FROM "ConferenceMembership" cm
                  WHERE (cm."seasonYear" IS NULL OR cm."seasonYear" = :seasonYear)
                  GROUP BY cm."sportConferenceId"
                ) t ON t."sportConferenceId" = sc.id
                WHERE sc."sportId" = :sportId
                ORDER BY c.name;
            """)

            rows = conn.execute(conf_sql, {"sportId": sport_id, "seasonYear": season_year}).fetchall()

        return {
            "leagueId": league_id,
            "sportId": sport_id,
            "seasonYear": season_year,
            "conferences": [dict(r._mapping) for r in rows],
        }