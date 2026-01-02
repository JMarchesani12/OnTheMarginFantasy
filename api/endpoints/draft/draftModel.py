import logging
import math
from sqlalchemy.exc import IntegrityError
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Engine


class DraftModel:
    def __init__(self, db: Engine):
        self.db = db

    def is_supabase_user_in_league(self, league_id: int, supabase_uuid: str) -> bool:
        """
        supabase_uuid should be the JWT 'sub' claim (a UUID string).
        """
        sql = text("""
            SELECT 1
            FROM "LeagueMember" lm
            JOIN "User" u ON u.id = lm."userId"
            WHERE lm."leagueId" = :leagueId
              AND u.uuid = :uuid::uuid
            LIMIT 1
        """)
        with self.db.connect() as conn:
            row = conn.execute(sql, {"leagueId": league_id, "uuid": supabase_uuid}).fetchone()
            return row is not None

    def _get_draft_settings(self, conn, league_id: int) -> Dict[str, Any]:
        row = conn.execute(
            text('SELECT settings, "numPlayers" FROM "League" WHERE id = :leagueId'),
            {"leagueId": league_id},
        ).fetchone()
        if not row:
            raise ValueError(f"League {league_id} not found")

        settings = row._mapping["settings"] or {}
        draft = (settings.get("draft") or {})

        # Exact keys based on what you provided
        draft_type_raw = (draft.get("draftType") or "SNAKE")
        selection_time = draft.get("selectionTime")
        number_of_rounds = draft.get("numberOfRounds")
        timeout_action_raw = (draft.get("timeoutAction") or "AUTO-SKIP")
        grace_seconds = draft.get("graceSeconds", 0)

        try:
            selection_time = int(selection_time)
            number_of_rounds = int(number_of_rounds)
            grace_seconds = int(grace_seconds)
        except Exception as e:
            raise ValueError("Invalid draft settings types. Expected integers for selectionTime/numberOfRounds/graceSeconds.") from e

        if selection_time <= 0:
            raise ValueError("League settings draft.selectionTime must be > 0")
        if number_of_rounds <= 0:
            raise ValueError("League settings draft.numberOfRounds must be > 0")
        if grace_seconds < 0:
            raise ValueError("League settings draft.graceSeconds must be >= 0")

        draft_type = str(draft_type_raw).upper()
        if draft_type not in ("SNAKE", "STRAIGHT"):
            raise ValueError("League settings draft.draftType must be SNAKE or STRAIGHT")

        timeout_action = str(timeout_action_raw).upper()
        if timeout_action not in ("AUTO-PICK", "AUTO-SKIP"):
            raise ValueError("League settings draft.timeoutAction must be AUTO-PICK or AUTO-SKIP")

        num_players = int(row._mapping["numPlayers"])
        if num_players <= 0:
            raise ValueError("League numPlayers must be > 0")

        return {
            "draftType": draft_type,                 # "SNAKE" | "STRAIGHT"
            "selectionTime": selection_time,         # seconds
            "numberOfRounds": number_of_rounds,
            "timeoutAction": timeout_action,         # "AUTO-PICK" | "AUTO-SKIP"
            "graceSeconds": grace_seconds,
            "numPlayers": num_players,
        }

    def _compute_round_and_pos(self, overall_pick: int, num_players: int) -> tuple[int, int]:
        """round_number is 1-indexed; pos_in_round is 1..num_players"""
        round_number = math.ceil(overall_pick / num_players)
        pos_in_round = overall_pick - (round_number - 1) * num_players
        return round_number, pos_in_round

    def _draft_order_for_pick(self, draft_type: str, round_number: int, pos_in_round: int, num_players: int) -> int:
        """
        Returns the draftOrder (1..num_players) who is on the clock for this pick.
        """
        if draft_type == "STRAIGHT":
            return pos_in_round
        # SNAKE
        if round_number % 2 == 1:
            return pos_in_round
        return num_players - pos_in_round + 1

    def _member_id_for_draft_order(self, conn, league_id: int, draft_order: int) -> int:
        row = conn.execute(
            text("""
                SELECT id
                FROM "LeagueMember"
                WHERE "leagueId" = :leagueId AND "draftOrder" = :draftOrder
                LIMIT 1
            """),
            {"leagueId": league_id, "draftOrder": draft_order},
        ).fetchone()
        if not row:
            raise ValueError(f"Missing LeagueMember for draftOrder={draft_order} in league={league_id}")
        return int(row._mapping["id"])

    # -----------------------------
    # Live draft pick (safe)
    # -----------------------------

    def create_draft_pick_live(
        self,
        league_id: int,
        member_id: int,
        sport_team_id: int,
        acquired_week: int = 1,
    ) -> Dict[str, Any]:
        """
        Live draft pick (concurrency-safe):
        - Locks DraftState FOR UPDATE
        - Enforces on-the-clock member
        - Allows late picks only within graceSeconds
        - Inserts DraftPick + LeagueTeamSlot
        - Advances DraftState and resets expiresAt
        """

        with self.db.begin() as conn:
            cfg = self._get_draft_settings(conn, league_id)
            num_players = cfg["numPlayers"]
            rounds = cfg["numberOfRounds"]
            selection_time = cfg["selectionTime"]
            grace_seconds = cfg["graceSeconds"]
            draft_type = cfg["draftType"]

            total_picks = rounds * num_players

            # 1) Lock DraftState
            state = conn.execute(
                text("""
                    SELECT "leagueId", status, "currentOverallPickNumber", "currentMemberId", "expiresAt"
                    FROM "DraftState"
                    WHERE "leagueId" = :leagueId
                    FOR UPDATE
                """),
                {"leagueId": league_id},
            ).fetchone()

            if not state:
                raise ValueError(f"DraftState not found for league {league_id}")

            status = str(state._mapping["status"])
            current_overall = int(state._mapping["currentOverallPickNumber"])
            current_member = state._mapping["currentMemberId"]

            if status != "live":
                raise ValueError(f"Draft is not live (status={status})")

            if current_overall > total_picks:
                raise ValueError("Draft already completed")

            if current_member != member_id:
                raise ValueError("Not your turn")

            # 2) Enforce expiry + grace (server-side)
            # Allow pick if now() <= expiresAt + graceSeconds
            expires_at = state._mapping["expiresAt"]
            if expires_at is not None:
                # expires_at is timezone-aware (timestamptz), compare in UTC
                now_utc = datetime.now(timezone.utc)
                deadline = expires_at + timedelta(seconds=grace_seconds)
                if now_utc > deadline:
                    raise ValueError("Pick window expired")

            # 3) Your existing “already owned” check (still valuable)
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

            # 3b) Conference cap check (keep your current helper)
            self._assert_member_can_add_team_conference_cap(
                conn=conn,
                league_id=league_id,
                member_id=member_id,
                sport_team_id=sport_team_id,
                acquired_week=acquired_week,
            )

            # 4) Compute round/pickInRound based on DraftState
            round_number, pos_in_round = self._compute_round_and_pos(current_overall, num_players)
            pick_in_round = self._draft_order_for_pick(draft_type, round_number, pos_in_round, num_players)

            # 5) Insert DraftPick (unique constraints protect races)
            try:
                draft_row = conn.execute(
                    text("""
                        INSERT INTO "DraftPick"
                            ("leagueId", "overallPickNumber", "roundNumber", "pickInRound",
                             "memberId", "sportTeamId")
                        VALUES
                            (:leagueId, :overallPickNumber, :roundNumber, :pickInRound,
                             :memberId, :sportTeamId)
                        RETURNING id, "createdAt", "leagueId",
                                  "overallPickNumber", "roundNumber", "pickInRound",
                                  "memberId", "sportTeamId"
                    """),
                    {
                        "leagueId": league_id,
                        "overallPickNumber": current_overall,
                        "roundNumber": round_number,
                        "pickInRound": pick_in_round,
                        "memberId": member_id,
                        "sportTeamId": sport_team_id,
                    },
                ).fetchone()
            except IntegrityError as e:
                raise ValueError("Pick conflict (team already drafted or slot already filled).") from e

            if not draft_row:
                raise RuntimeError("Failed to insert DraftPick")

            draft_pick = dict(draft_row._mapping)

            # 6) Insert LeagueTeamSlot
            slot_row = conn.execute(
                text("""
                    INSERT INTO "LeagueTeamSlot"
                        ("leagueId", "memberId", "sportTeamId",
                         "acquiredWeek", "acquiredVia")
                    VALUES
                        (:leagueId, :memberId, :sportTeamId,
                         :acquiredWeek, :acquiredVia)
                    RETURNING id
                """),
                {
                    "leagueId": league_id,
                    "memberId": member_id,
                    "sportTeamId": sport_team_id,
                    "acquiredWeek": acquired_week,
                    "acquiredVia": "Draft",
                },
            ).fetchone()

            draft_pick["leagueTeamSlotId"] = int(slot_row._mapping["id"])

            # 7) Advance DraftState
            next_overall = current_overall + 1

            if next_overall > total_picks:
                conn.execute(
                    text("""
                        UPDATE "DraftState"
                        SET status = 'complete',
                            "currentOverallPickNumber" = :nextOverall,
                            "currentMemberId" = NULL,
                            "expiresAt" = NULL,
                            "lastPickAt" = now(),
                            "updatedAt" = now()
                        WHERE "leagueId" = :leagueId
                    """),
                    {"leagueId": league_id, "nextOverall": next_overall},
                )

                conn.execute(
                    text("""
                        UPDATE "League"
                        SET status = 'POST-DRAFT',
                            "updatedAt" = now()
                        WHERE id = :leagueId
                    """),
                    {"leagueId": league_id},
                )
                
                draft_pick["draftComplete"] = True
                return draft_pick

            next_round, next_pos = self._compute_round_and_pos(next_overall, num_players)
            next_draft_order = self._draft_order_for_pick(draft_type, next_round, next_pos, num_players)
            next_member_id = self._member_id_for_draft_order(conn, league_id, next_draft_order)

            conn.execute(
                text("""
                    UPDATE "DraftState"
                    SET "currentOverallPickNumber" = :nextOverall,
                        "currentMemberId" = :nextMemberId,
                        "expiresAt" = now() + (:selectionTime || ' seconds')::interval,
                        "lastPickAt" = now(),
                        "updatedAt" = now()
                    WHERE "leagueId" = :leagueId
                """),
                {
                    "leagueId": league_id,
                    "nextOverall": next_overall,
                    "nextMemberId": next_member_id,
                    "selectionTime": selection_time,
                },
            )

            draft_pick["draftComplete"] = False
            draft_pick["nextMemberId"] = next_member_id
            draft_pick["nextOverallPickNumber"] = next_overall

            return draft_pick

    # -----------------------------
    # Timeout processing (AUTO-SKIP / AUTO-PICK)
    # -----------------------------

    def process_expired_pick_if_needed(self, league_id: int) -> Optional[Dict[str, Any]]:
        """
        Call this from a scheduler/cron loop.
        If the current pick is expired past grace, apply timeoutAction:
          - AUTO-SKIP: advance state to next member
          - AUTO-PICK: (stub) you choose a team and call create_draft_pick_live-like insertion
        Returns a dict describing what happened, or None if nothing happened.
        """

        with self.db.begin() as conn:
            cfg = self._get_draft_settings(conn, league_id)
            num_players = cfg["numPlayers"]
            rounds = cfg["numberOfRounds"]
            selection_time = cfg["selectionTime"]
            grace_seconds = cfg["graceSeconds"]
            draft_type = cfg["draftType"]
            timeout_action = cfg["timeoutAction"]

            total_picks = rounds * num_players

            state = conn.execute(
                text("""
                    SELECT "leagueId", status, "currentOverallPickNumber", "currentMemberId", "expiresAt"
                    FROM "DraftState"
                    WHERE "leagueId" = :leagueId
                    FOR UPDATE
                """),
                {"leagueId": league_id},
            ).fetchone()

            if not state:
                return None

            if str(state._mapping["status"]) != "live":
                return None

            current_overall = int(state._mapping["currentOverallPickNumber"])
            if current_overall > total_picks:
                # already past end
                return None

            # If no expiresAt, treat as not expirable
            if state._mapping["expiresAt"] is None:
                return None

            is_expired = conn.execute(
                text("""
                    SELECT now() > ("expiresAt" + (:graceSeconds || ' seconds')::interval) AS isExpired
                    FROM "DraftState"
                    WHERE "leagueId" = :leagueId
                """),
                {"leagueId": league_id, "graceSeconds": grace_seconds},
            ).fetchone()

            if not is_expired or not bool(is_expired._mapping["isExpired"]):
                return None

            # Expired beyond grace: act
            if timeout_action == "AUTO-SKIP":
                next_overall = current_overall + 1
                if next_overall > total_picks:
                    conn.execute(
                        text("""
                            UPDATE "DraftState"
                            SET status = 'complete',
                                "currentOverallPickNumber" = :nextOverall,
                                "currentMemberId" = NULL,
                                "expiresAt" = NULL,
                                "updatedAt" = now()
                            WHERE "leagueId" = :leagueId
                        """),
                        {"leagueId": league_id, "nextOverall": next_overall},
                    )
                    return {"type": "AUTO-SKIP", "draftComplete": True}

                next_round, next_pos = self._compute_round_and_pos(next_overall, num_players)
                next_draft_order = self._draft_order_for_pick(draft_type, next_round, next_pos, num_players)
                next_member_id = self._member_id_for_draft_order(conn, league_id, next_draft_order)

                conn.execute(
                    text("""
                        UPDATE "DraftState"
                        SET "currentOverallPickNumber" = :nextOverall,
                            "currentMemberId" = :nextMemberId,
                            "expiresAt" = now() + (:selectionTime || ' seconds')::interval,
                            "updatedAt" = now()
                        WHERE "leagueId" = :leagueId
                    """),
                    {
                        "leagueId": league_id,
                        "nextOverall": next_overall,
                        "nextMemberId": next_member_id,
                        "selectionTime": selection_time,
                    },
                )

                return {
                    "type": "AUTO-SKIP",
                    "skippedOverallPickNumber": current_overall,
                    "nextOverallPickNumber": next_overall,
                    "nextMemberId": next_member_id,
                    "draftComplete": False,
                }

            # AUTO-PICK is intentionally a stub because I can't guess your ranking logic.
            # Implement:
            # - choose_best_available_team(conn, league_id, member_id, acquired_week)
            # - then insert DraftPick + LeagueTeamSlot, advance state like create_draft_pick_live
            if timeout_action == "AUTO-PICK":
                raise NotImplementedError("AUTO-PICK requires your team ranking/selection logic.")

            return None

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
    
    def start_draft(self, league_id: int) -> Dict[str, Any]:
        """
        Sets DraftState to live and initializes:
        - currentOverallPickNumber = 1
        - currentMemberId = member with draftOrder=1
        - expiresAt = now + selectionTime
        """
        with self.db.begin() as conn:
            cfg = self._get_draft_settings(conn, league_id)
            selection_time = cfg["selectionTime"]
            num_players = cfg["numPlayers"]

            # Validate draft order is complete (has 1..num_players)
            missing = conn.execute(
                text("""
                    SELECT gs AS missingOrder
                    FROM generate_series(1, :numPlayers) gs
                    LEFT JOIN "LeagueMember" lm
                      ON lm."leagueId" = :leagueId AND lm."draftOrder" = gs
                    WHERE lm.id IS NULL
                    ORDER BY gs
                """),
                {"leagueId": league_id, "numPlayers": num_players},
            ).mappings().all()

            if missing:
                missing_orders = [int(r["missingOrder"]) for r in missing]
                raise ValueError(f"Draft order incomplete. Missing draftOrder values: {missing_orders}")

            first_member = conn.execute(
                text("""
                    SELECT id
                    FROM "LeagueMember"
                    WHERE "leagueId" = :leagueId AND "draftOrder" = 1
                    LIMIT 1
                """),
                {"leagueId": league_id},
            ).fetchone()

            if not first_member:
                raise ValueError("No member found with draftOrder=1")

            first_member_id = int(first_member._mapping["id"])

            # Upsert DraftState row
            conn.execute(
                text("""
                    INSERT INTO "DraftState"
                        ("leagueId", status, "currentOverallPickNumber", "currentMemberId", "expiresAt", "updatedAt")
                    VALUES
                        (:leagueId, 'live', 1, :currentMemberId, now() + (:selectionTime || ' seconds')::interval, now())
                    ON CONFLICT ("leagueId") DO UPDATE
                    SET status = 'live',
                        "currentOverallPickNumber" = 1,
                        "currentMemberId" = EXCLUDED."currentMemberId",
                        "expiresAt" = EXCLUDED."expiresAt",
                        "updatedAt" = now()
                """),
                {
                    "leagueId": league_id,
                    "currentMemberId": first_member_id,
                    "selectionTime": selection_time,
                },
            )

            conn.execute(
                text("""
                    UPDATE "League"
                    SET status = 'Drafting',
                        "updatedAt" = now()
                    WHERE id = :leagueId
                """),
                {"leagueId": league_id},
            )

            return self.get_draft_state_snapshot(league_id, conn=conn)

    def pause_draft(self, league_id: int) -> Dict[str, Any]:
        with self.db.begin() as conn:
            state = conn.execute(
                text("""
                    SELECT status FROM "DraftState"
                    WHERE "leagueId" = :leagueId
                    FOR UPDATE
                """),
                {"leagueId": league_id},
            ).fetchone()

            if not state:
                raise ValueError("DraftState not found. Start draft first.")

            if str(state._mapping["status"]) == "complete":
                raise ValueError("Draft is complete")

            conn.execute(
                text("""
                    UPDATE "DraftState"
                    SET status = 'paused',
                        "expiresAt" = NULL,
                        "updatedAt" = now()
                    WHERE "leagueId" = :leagueId
                """),
                {"leagueId": league_id},
            )

            return self.get_draft_state_snapshot(league_id, conn=conn)

    def resume_draft(self, league_id: int) -> Dict[str, Any]:
        with self.db.begin() as conn:
            cfg = self._get_draft_settings(conn, league_id)
            selection_time = cfg["selectionTime"]

            state = conn.execute(
                text("""
                    SELECT status FROM "DraftState"
                    WHERE "leagueId" = :leagueId
                    FOR UPDATE
                """),
                {"leagueId": league_id},
            ).fetchone()

            if not state:
                raise ValueError("DraftState not found. Start draft first.")

            if str(state._mapping["status"]) == "complete":
                raise ValueError("Draft is complete")

            conn.execute(
                text("""
                    UPDATE "DraftState"
                    SET status = 'live',
                        "expiresAt" = now() + (:selectionTime || ' seconds')::interval,
                        "updatedAt" = now()
                    WHERE "leagueId" = :leagueId
                """),
                {"leagueId": league_id, "selectionTime": selection_time},
            )

            return self.get_draft_state_snapshot(league_id, conn=conn)

    def get_draft_state_snapshot(self, league_id: int, conn=None) -> Dict[str, Any]:
        """
        Snapshot for frontend reconnect:
        - DraftState
        - members in draft order
        - picks so far
        - league draft settings (draft object)
        """
        def _run(c):
            league = c.execute(
                text('SELECT id, "numPlayers", settings FROM "League" WHERE id = :leagueId'),
                {"leagueId": league_id},
            ).fetchone()
            if not league:
                raise ValueError(f"League {league_id} not found")

            settings = league._mapping["settings"] or {}
            draft_settings = settings.get("draft") or {}

            state = c.execute(
                text("""
                    SELECT "leagueId", status, "currentOverallPickNumber", "currentMemberId", "expiresAt", "lastPickAt", "updatedAt"
                    FROM "DraftState"
                    WHERE "leagueId" = :leagueId
                """),
                {"leagueId": league_id},
            ).mappings().fetchone()

            members = c.execute(
                text("""
                    SELECT id AS "memberId", "userId", "teamName", "draftOrder"
                    FROM "LeagueMember"
                    WHERE "leagueId" = :leagueId
                    ORDER BY "draftOrder", id
                """),
                {"leagueId": league_id},
            ).mappings().all()

            picks = c.execute(
                text("""
                    SELECT
                      dp.id,
                      dp."createdAt",
                      dp."overallPickNumber",
                      dp."roundNumber",
                      dp."pickInRound",
                      dp."memberId",
                      lm."teamName" AS "memberTeamName",
                      dp."sportTeamId",
                      st."displayName" AS "sportTeamName"
                    FROM "DraftPick" dp
                    JOIN "LeagueMember" lm ON lm.id = dp."memberId"
                    JOIN "SportTeam" st ON st.id = dp."sportTeamId"
                    WHERE dp."leagueId" = :leagueId
                    ORDER BY dp."overallPickNumber"
                """),
                {"leagueId": league_id},
            ).mappings().all()

            return {
                "leagueId": league_id,
                "draftSettings": draft_settings,
                "state": dict(state) if state else None,
                "members": [dict(m) for m in members],
                "picks": [dict(p) for p in picks],
            }

        if conn is not None:
            return _run(conn)

        with self.db.begin() as conn2:
            return _run(conn2)

    # Optional but recommended: prevent changing order mid-live draft
    def set_draft_order(self, league_id: int, member_ids_in_order: List[int]) -> Dict[str, Any]:
        if not member_ids_in_order:
            raise ValueError("memberIdsInOrder is required")

        with self.db.begin() as conn:
            # Block re-ordering once draft is live/paused/complete
            state = conn.execute(
                text('SELECT status FROM "DraftState" WHERE "leagueId" = :leagueId'),
                {"leagueId": league_id},
            ).fetchone()
            if state and str(state._mapping["status"]) in ("live", "paused", "complete"):
                raise ValueError("Cannot change draft order after draft has started")

            # Ensure all ids belong to this league
            rows = conn.execute(
                text("""
                    SELECT id
                    FROM "LeagueMember"
                    WHERE "leagueId" = :leagueId
                      AND id = ANY(CAST(:ids AS bigint[]))
                """),
                {"leagueId": league_id, "ids": member_ids_in_order},
            ).fetchall()

            if len(rows) != len(member_ids_in_order):
                raise ValueError("One or more memberIds are not in this league")

            # 1) bump everything out of the way
            conn.execute(
                text("""
                    UPDATE "LeagueMember"
                    SET "draftOrder" = "draftOrder" + 100000
                    WHERE "leagueId" = :leagueId
                """),
                {"leagueId": league_id},
            )

            # 2) set final order
            conn.execute(
                text("""
                    WITH input AS (
                        SELECT
                            unnest(CAST(:ids AS bigint[])) AS member_id,
                            generate_series(1, array_length(CAST(:ids AS bigint[]), 1)) AS new_order
                    )
                    UPDATE "LeagueMember" lm
                    SET "draftOrder" = i.new_order
                    FROM input i
                    WHERE lm.id = i.member_id
                      AND lm."leagueId" = :leagueId
                """),
                {"leagueId": league_id, "ids": member_ids_in_order},
            )

            updated_members = conn.execute(
                text("""
                    SELECT id AS "memberId", "userId", "teamName", "draftOrder"
                    FROM "LeagueMember"
                    WHERE "leagueId" = :leagueId
                    ORDER BY "draftOrder", id
                """),
                {"leagueId": league_id},
            ).mappings().all()

        return {"members": [dict(m) for m in updated_members]}