import json
import logging
import math
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine


class DraftModel:
    def __init__(self, db: Engine):
        self.db = db

    # NEW: conference cap helpers (kept private to DraftModel for now)
    def _get_conference_info_for_team(
        self,
        conn,
        sport_team_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns:
          { sportConferenceId, conferenceName, maxTeamsPerOwner }
        or None if the team has no conference membership (Independent).
        Assumes ConferenceMembership.seasonYear IS NULL (your current data).
        """
        sql = text("""
            SELECT
              sc.id                 AS "sportConferenceId",
              c.name                AS "conferenceName",
              sc."maxTeamsPerOwner" AS "maxTeamsPerOwner"
            FROM "ConferenceMembership" cm
            JOIN "SportConference" sc
              ON sc.id = cm."sportConferenceId"
            JOIN "Conference" c
              ON c.id = sc."conferenceId"
            WHERE cm."sportTeamId" = :sportTeamId
              AND cm."seasonYear" IS NULL
            LIMIT 1
        """)
        row = conn.execute(sql, {"sportTeamId": sport_team_id}).fetchone()
        return dict(row._mapping) if row else None

    def _count_member_teams_in_sport_conference(
        self,
        conn,
        league_id: int,
        member_id: int,
        week_number: int,
        sport_conference_id: int,
    ) -> int:
        """
        Counts how many teams this member owns (for the given week) in this sportConferenceId.
        Uses DISTINCT to avoid double counting if ConferenceMembership has duplicates.
        """
        sql = text("""
            WITH owned AS (
              SELECT lts."sportTeamId"
              FROM "LeagueTeamSlot" lts
              WHERE lts."leagueId"     = :leagueId
                AND lts."memberId"     = :memberId
                AND lts."acquiredWeek" <= :weekNumber
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
            )
            SELECT COUNT(DISTINCT o."sportTeamId")::int AS cnt
            FROM owned o
            JOIN "ConferenceMembership" cm
              ON cm."sportTeamId" = o."sportTeamId"
            WHERE cm."sportConferenceId" = :sportConferenceId
              AND cm."seasonYear" IS NULL
        """)
        row = conn.execute(
            sql,
            {
                "leagueId": league_id,
                "memberId": member_id,
                "weekNumber": week_number,
                "sportConferenceId": sport_conference_id,
            },
        ).fetchone()

        return int(row._mapping["cnt"]) if row else 0

    def _assert_member_can_add_team_conference_cap(
        self,
        conn,
        league_id: int,
        member_id: int,
        sport_team_id: int,
        acquired_week: int,
    ) -> None:
        """
        Raises ValueError if the member has already hit maxTeamsPerOwner
        for the conference of sport_team_id.

        Policy for teams with no conference membership:
          - allowed (treated as Independent).
        """
        conf = self._get_conference_info_for_team(conn, sport_team_id)
        if conf is None:
            # Independent / no membership: allow
            return

        max_allowed = int(conf["maxTeamsPerOwner"])
        if max_allowed <= 0:
            # 0 or negative = treat as "no cap"
            return

        sport_conference_id = int(conf["sportConferenceId"])
        current_count = self._count_member_teams_in_sport_conference(
            conn=conn,
            league_id=league_id,
            member_id=member_id,
            week_number=acquired_week,
            sport_conference_id=sport_conference_id,
        )

        if current_count >= max_allowed:
            conference_name = conf.get("conferenceName") or "Unknown Conference"
            raise ValueError(
                f"Conference cap reached for {conference_name}: "
                f"{current_count}/{max_allowed}."
            )

    def create_draft_pick(
        self,
        league_id: int,
        member_id: int,
        sport_team_id: int,
        acquired_week: int = 1
    ) -> Dict[str, Any]:
        """
        Creates a DraftPick row AND a LeagueTeamSlot row in a single transaction.

        - Computes overallPickNumber / roundNumber / pickInRound based on
          existing picks and League.numPlayers (snake draft).
        - Fails if the team is already owned in this league for that week.
        - NEW: Fails if the member has already hit maxTeamsPerOwner for the team’s conference.
        """

        with self.db.begin() as conn:
            # 1) Get league info (numPlayers) to compute rounds
            league_row = conn.execute(
                text('SELECT "numPlayers" FROM "League" WHERE id = :leagueId'),
                {"leagueId": league_id},
            ).fetchone()

            if not league_row:
                raise ValueError(f"League {league_id} not found")

            num_players = league_row._mapping["numPlayers"]

            # 2) Make sure this team isn't already owned in this league for this week
            ownership_row = conn.execute(
                text("""
                    SELECT 1
                    FROM "LeagueTeamSlot"
                    WHERE "leagueId" = :leagueId
                      AND "sportTeamId" = :sportTeamId
                      AND "acquiredWeek" <= :week
                      AND ("droppedWeek" IS NULL OR "droppedWeek" > :week)
                    LIMIT 1
                """),
                {"leagueId": league_id, "sportTeamId": sport_team_id, "week": acquired_week},
            ).fetchone()

            if ownership_row:
                raise ValueError("Team is already owned in this league for this week")

            # NEW: 2b) Enforce conference cap (maxTeamsPerOwner) for this member
            self._assert_member_can_add_team_conference_cap(
                conn=conn,
                league_id=league_id,
                member_id=member_id,
                sport_team_id=sport_team_id,
                acquired_week=acquired_week,
            )

            # 3) Count existing picks to get next overall pick number
            pick_count_row = conn.execute(
                text('SELECT COUNT(*) AS cnt FROM "DraftPick" WHERE "leagueId" = :leagueId'),
                {"leagueId": league_id},
            ).fetchone()

            existing_picks = pick_count_row._mapping["cnt"]
            overall_pick = existing_picks + 1

            # 4) Compute roundNumber & pickInRound for snake draft
            round_number = math.ceil(overall_pick / num_players)
            pos_in_round = overall_pick - (round_number - 1) * num_players

            if round_number % 2 == 1:
                # odd round: pick order 1..num_players
                pick_in_round = pos_in_round
            else:
                # even round: reversed order
                pick_in_round = num_players - pos_in_round + 1

            # 5) Insert DraftPick
            draft_sql = text("""
                INSERT INTO "DraftPick"
                    ("leagueId", "overallPickNumber", "roundNumber", "pickInRound",
                     "memberId", "sportTeamId")
                VALUES
                    (:leagueId, :overallPickNumber, :roundNumber, :pickInRound,
                     :memberId, :sportTeamId)
                RETURNING id, "createdAt", "leagueId",
                          "overallPickNumber", "roundNumber", "pickInRound",
                          "memberId", "sportTeamId"
            """)

            draft_row = conn.execute(
                draft_sql,
                {
                    "leagueId": league_id,
                    "overallPickNumber": overall_pick,
                    "roundNumber": round_number,
                    "pickInRound": pick_in_round,
                    "memberId": member_id,
                    "sportTeamId": sport_team_id
                },
            ).fetchone()

            if not draft_row:
                raise RuntimeError("Failed to insert DraftPick")

            draft_pick = dict(draft_row._mapping)

            # 6) Insert into LeagueTeamSlot as the roster ownership
            slot_sql = text("""
                INSERT INTO "LeagueTeamSlot"
                    ("leagueId", "memberId", "sportTeamId",
                     "acquiredWeek", "acquiredVia")
                VALUES
                    (:leagueId, :memberId, :sportTeamId,
                     :acquiredWeek, :acquiredVia)
                RETURNING id
            """)

            slot_row = conn.execute(
                slot_sql,
                {
                    "leagueId": league_id,
                    "memberId": member_id,
                    "sportTeamId": sport_team_id,
                    "acquiredWeek": acquired_week,
                    "acquiredVia": "Draft",
                },
            ).fetchone()

            draft_pick["leagueTeamSlotId"] = slot_row._mapping["id"]

        logging.debug("Created draft pick: %s", draft_pick)
        return draft_pick


    def get_rounds(self, sportId):
        with self.db.begin() as conn:
            rounds = conn.execute(
                text('SELECT "maxDraftRounds" FROM "Sport" WHERE id = :sportId'),
                {"sportId": sportId},
            ).scalar_one_or_none()

        return rounds