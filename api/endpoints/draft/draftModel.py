import logging
import math
import secrets
from sqlalchemy.exc import IntegrityError
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Engine

from endpoints.draft.notifyChannel import notify_draft_updated


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
              AND u.uuid = CAST(:uuid AS uuid)
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

            expected_member_id = self._get_expected_member_for_overall(conn, league_id, current_overall)
            if expected_member_id is None:
                raise ValueError("DraftTurn missing for this pick number")
            if expected_member_id != member_id:
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
                notify_draft_updated(conn, league_id, "draft_pick")
                return draft_pick

            nxt = self._get_next_unpicked_turn_from(conn, league_id, next_overall)
            if not nxt:
                # No turns left (safety)
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
                draft_pick["draftComplete"] = True
                notify_draft_updated(conn, league_id, "draft_pick")
                return draft_pick

            next_overall, next_member_id = nxt

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
                # Safety: ensure DraftTurn exists for this overall pick
                expected_row = conn.execute(
                    text("""
                        SELECT "memberId"
                        FROM "DraftTurn"
                        WHERE "leagueId" = :leagueId
                          AND "overallPickNumber" = :overall
                    """),
                    {"leagueId": league_id, "overall": current_overall},
                ).fetchone()

                if not expected_row:
                    raise ValueError(f"DraftTurn missing for leagueId={league_id}, overallPickNumber={current_overall}")

                timed_out_member_id = int(expected_row._mapping["memberId"])

                # Find last overall pick number that is still unpicked
                last_unpicked = conn.execute(
                    text("""
                        SELECT COALESCE(MAX(dt."overallPickNumber"), 0) AS "lastUnpicked"
                        FROM "DraftTurn" dt
                        LEFT JOIN "DraftPick" dp
                          ON dp."leagueId" = dt."leagueId"
                         AND dp."overallPickNumber" = dt."overallPickNumber"
                        WHERE dt."leagueId" = :leagueId
                          AND dp.id IS NULL
                    """),
                    {"leagueId": league_id},
                ).fetchone()

                last_unpicked_overall = int(last_unpicked._mapping["lastUnpicked"] or 0)

                # If nothing left, draft is complete
                if last_unpicked_overall == 0 or current_overall > last_unpicked_overall:
                    conn.execute(
                        text("""
                            UPDATE "DraftState"
                            SET status = 'complete',
                                "currentMemberId" = NULL,
                                "expiresAt" = NULL,
                                "updatedAt" = now()
                            WHERE "leagueId" = :leagueId
                        """),
                        {"leagueId": league_id},
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
                    return {"type": "AUTO-SKIP-MOVE-TO-END", "draftComplete": True}

                # If current_overall is the last unpicked already, "moving to end" changes nothing.
                if current_overall == last_unpicked_overall:
                    conn.execute(
                        text("""
                            UPDATE "DraftState"
                            SET "expiresAt" = now() + (:selectionTime || ' seconds')::interval,
                                "updatedAt" = now()
                            WHERE "leagueId" = :leagueId
                        """),
                        {"leagueId": league_id, "selectionTime": selection_time},
                    )
                    return {
                        "type": "AUTO-SKIP-MOVE-TO-END",
                        "moved": False,
                        "reason": "already last unpicked",
                        "draftComplete": False,
                    }

                # Rotate DraftTurn assignments for remaining UNPICKED picks from current_overall..last_unpicked_overall:
                # - save member at current_overall
                # - shift later unpicked members forward (skipping already-picked slots)
                # - place saved member at the last unpicked slot
                conn.execute(
                    text("""
                        WITH params AS (
                            SELECT
                                :leagueId::bigint AS "leagueId",
                                :cur::bigint      AS "cur",
                                :last::bigint     AS "last"
                        ),
                        unpicked AS (
                            SELECT dt."overallPickNumber" AS "opn",
                                   dt."memberId"          AS "memberId"
                            FROM "DraftTurn" dt
                            JOIN params p ON p."leagueId" = dt."leagueId"
                            LEFT JOIN "DraftPick" dp
                              ON dp."leagueId" = dt."leagueId"
                             AND dp."overallPickNumber" = dt."overallPickNumber"
                            WHERE dt."overallPickNumber" BETWEEN p."cur" AND p."last"
                              AND dp.id IS NULL
                            ORDER BY dt."overallPickNumber"
                        ),
                        saved AS (
                            SELECT u."memberId" AS "savedMemberId"
                            FROM unpicked u
                            WHERE u."opn" = (SELECT "cur" FROM params)
                        ),
                        shifted AS (
                            SELECT
                                u."opn" AS "opn",
                                LEAD(u."memberId") OVER (ORDER BY u."opn") AS "nextMemberId"
                            FROM unpicked u
                        )
                        UPDATE "DraftTurn" dt
                        SET "memberId" = COALESCE(
                            (SELECT s."nextMemberId" FROM shifted s WHERE s."opn" = dt."overallPickNumber"),
                            (SELECT "savedMemberId" FROM saved)
                        )
                        WHERE dt."leagueId" = (SELECT "leagueId" FROM params)
                          AND dt."overallPickNumber" IN (SELECT "opn" FROM shifted);
                    """),
                    {"leagueId": league_id, "cur": current_overall, "last": last_unpicked_overall},
                )

                # Advance DraftState to next unpicked overall (>= current_overall)
                next_row = conn.execute(
                    text("""
                        SELECT dt."overallPickNumber" AS "nextOverall",
                               dt."memberId"          AS "nextMemberId"
                        FROM "DraftTurn" dt
                        LEFT JOIN "DraftPick" dp
                          ON dp."leagueId" = dt."leagueId"
                         AND dp."overallPickNumber" = dt."overallPickNumber"
                        WHERE dt."leagueId" = :leagueId
                          AND dp.id IS NULL
                          AND dt."overallPickNumber" >= :cur
                        ORDER BY dt."overallPickNumber" ASC
                        LIMIT 1
                    """),
                    {"leagueId": league_id, "cur": current_overall},
                ).fetchone()

                if not next_row:
                    conn.execute(
                        text("""
                            UPDATE "DraftState"
                            SET status = 'complete',
                                "currentMemberId" = NULL,
                                "expiresAt" = NULL,
                                "updatedAt" = now()
                            WHERE "leagueId" = :leagueId
                        """),
                        {"leagueId": league_id},
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
                    return {"type": "AUTO-SKIP-MOVE-TO-END", "draftComplete": True}

                next_overall = int(next_row._mapping["nextOverall"])
                next_member_id = int(next_row._mapping["nextMemberId"])

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

                return {
                    "type": "AUTO-SKIP-MOVE-TO-END",
                    "timedOutOverallPickNumber": current_overall,
                    "timedOutMemberId": timed_out_member_id,
                    "movedToOverallPickNumber": last_unpicked_overall,
                    "nextOverallPickNumber": next_overall,
                    "nextMemberId": next_member_id,
                    "draftComplete": False,
                }


            # AUTO-PICK is intentionally a stub because I can't guess your ranking logic.
            # Implement:
            # - choose_best_available_team(conn, league_id, member_id, acquired_week)
            # - then insert DraftPick + LeagueTeamSlot, advance state like create_draft_pick_live
            if timeout_action == "AUTO-PICK":
                # Who is actually on the clock? Use DraftTurn as source of truth.
                turn_row = conn.execute(
                    text("""
                        SELECT dt."memberId"
                        FROM "DraftTurn" dt
                        WHERE dt."leagueId" = :leagueId
                          AND dt."overallPickNumber" = :overall
                    """),
                    {"leagueId": league_id, "overall": current_overall},
                ).fetchone()

                if not turn_row:
                    raise ValueError(f"DraftTurn missing for leagueId={league_id}, overallPickNumber={current_overall}")

                on_clock_member_id = int(turn_row._mapping["memberId"])

                # Pick truly random by conference-bucket (plus Independent bucket), retrying buckets as needed
                sport_team_id = self._choose_random_team_for_auto_pick(
                    conn=conn,
                    league_id=league_id,
                    member_id=on_clock_member_id,
                    week=1,  # draft week; adjust if your draft uses a different acquired_week
                )

                if sport_team_id is None:
                    # No valid teams exist under caps/availability => nothing to pick
                    # You can either:
                    # - return None
                    # - OR fall back to your AUTO-SKIP-MOVE-TO-END logic
                    return None

                # Insert pick + slot, advance DraftState, without expiry rejection
                return self._insert_draft_pick_and_advance_state_no_expiry_check(
                    conn=conn,
                    league_id=league_id,
                    member_id=on_clock_member_id,
                    sport_team_id=sport_team_id,
                    acquired_week=1,
                    selection_time=int(selection_time),
                    num_players=int(num_players),
                    rounds=int(rounds),
                    draft_type=str(draft_type),
                )

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
            notify_draft_updated(conn, league_id, "manual_pick")

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

            self.seed_draft_turns(conn, league_id)

            first_member_id = self._get_expected_member_for_overall(conn, league_id, 1)
            if not first_member_id:
                raise ValueError("DraftTurn not seeded correctly (missing overallPickNumber=1)")

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
        
    def seed_draft_turns(self, conn, league_id: int) -> None:
        """
        Seeds DraftTurn for ALL overall pick numbers (1..total_picks) based on your
        draft settings and LeagueMember.draftOrder.
        Idempotent: ON CONFLICT DO NOTHING.
        """
        cfg = self._get_draft_settings(conn, league_id)
        num_players = int(cfg["numPlayers"])
        rounds = int(cfg["numberOfRounds"])
        draft_type = cfg["draftType"]
        total_picks = rounds * num_players

        # Build draftOrder -> memberId map
        members = conn.execute(
            text("""
                SELECT id AS "memberId", "draftOrder"
                FROM "LeagueMember"
                WHERE "leagueId" = :leagueId
                ORDER BY "draftOrder" ASC
            """),
            {"leagueId": league_id},
        ).fetchall()

        order_to_member = {int(r._mapping["draftOrder"]): int(r._mapping["memberId"]) for r in members}

        rows = []
        for overall in range(1, total_picks + 1):
            rnd, pos = self._compute_round_and_pos(overall, num_players)
            draft_order = self._draft_order_for_pick(draft_type, rnd, pos, num_players)
            member_id = order_to_member[draft_order]
            rows.append({"leagueId": league_id, "overallPickNumber": overall, "memberId": member_id})

        conn.execute(
            text("""
                INSERT INTO "DraftTurn" ("leagueId","overallPickNumber","memberId")
                VALUES (:leagueId, :overallPickNumber, :memberId)
                ON CONFLICT ("leagueId","overallPickNumber") DO NOTHING
                """),
                rows,
            )


    def _get_expected_member_for_overall(self, conn, league_id: int, overall_pick_number: int) -> Optional[int]:
        row = conn.execute(
            text("""
                SELECT "memberId"
                FROM "DraftTurn"
                WHERE "leagueId" = :leagueId
                AND "overallPickNumber" = :overall
            """),
            {"leagueId": league_id, "overall": overall_pick_number},
        ).fetchone()
        return int(row._mapping["memberId"]) if row else None


    def _get_next_unpicked_turn_from(self, conn, league_id: int, start_overall: int) -> Optional[tuple[int, int]]:
        """
        Returns (overallPickNumber, memberId) for the next unpicked overall >= start_overall.
        Unpicked = DraftTurn exists and no DraftPick exists for that overall.
        """
        row = conn.execute(
            text("""
                SELECT dt."overallPickNumber" AS "overall",
                    dt."memberId"          AS "memberId"
                FROM "DraftTurn" dt
                LEFT JOIN "DraftPick" dp
                ON dp."leagueId" = dt."leagueId"
                AND dp."overallPickNumber" = dt."overallPickNumber"
                WHERE dt."leagueId" = :leagueId
                AND dt."overallPickNumber" >= :startOverall
                AND dp.id IS NULL
                ORDER BY dt."overallPickNumber" ASC
                LIMIT 1
            """),
            {"leagueId": league_id, "startOverall": start_overall},
        ).fetchone()

        if not row:
            return None

        return int(row._mapping["overall"]), int(row._mapping["memberId"])
    

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
                      st."displayName" AS "sportTeamName",
                      sc.id AS "sportConferenceId",
                      conf.name AS "conferenceName"
                    FROM "DraftPick" dp
                    JOIN "LeagueMember" lm ON lm.id = dp."memberId"
                    JOIN "SportTeam" st ON st.id = dp."sportTeamId"
                    LEFT JOIN "ConferenceMembership" cm
                      ON cm."sportTeamId" = dp."sportTeamId"
                     AND cm."seasonYear" IS NULL
                    LEFT JOIN "SportConference" sc
                      ON sc.id = cm."sportConferenceId"
                    LEFT JOIN "Conference" conf
                      ON conf.id = sc."conferenceId"
                    WHERE dp."leagueId" = :leagueId
                    ORDER BY dp."overallPickNumber"
                """),
                {"leagueId": league_id},
            ).mappings().all()

            on_deck = None
            in_the_hole = None
            if state and state.get("currentOverallPickNumber") is not None:
                current_overall = int(state["currentOverallPickNumber"])
                on_deck = self._get_next_unpicked_turn_from(c, league_id, current_overall + 1)
                if on_deck:
                    in_the_hole = self._get_next_unpicked_turn_from(c, league_id, on_deck[0] + 1)

            member_id_to_name = {int(m["memberId"]): m["teamName"] for m in members}

            def _turn_payload(turn):
                if not turn:
                    return None
                overall, member_id = turn
                return {
                    "overallPickNumber": overall,
                    "memberId": member_id,
                    "memberTeamName": member_id_to_name.get(member_id),
                }

            return {
                "leagueId": league_id,
                "draftSettings": draft_settings,
                "serverNow": datetime.now(timezone.utc).isoformat(),
                "state": dict(state) if state else None,
                "members": [dict(m) for m in members],
                "picks": [dict(p) for p in picks],
                "onDeck": _turn_payload(on_deck),
                "inTheHole": _turn_payload(in_the_hole),
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
    
    def _get_league_sport_id(self, conn, league_id: int) -> int:
        row = conn.execute(
            text("""SELECT sport FROM "League" WHERE id = :leagueId"""),
            {"leagueId": league_id},
        ).fetchone()
        if not row:
            raise ValueError(f"League {league_id} not found")
        return int(row._mapping["sport"])


    def _list_sport_conference_ids_for_sport(self, conn, sport_id: int) -> List[int]:
        rows = conn.execute(
            text("""
                SELECT id
                FROM "SportConference"
                WHERE "sportId" = :sportId
                ORDER BY id ASC
            """),
            {"sportId": sport_id},
        ).fetchall()
        return [int(r._mapping["id"]) for r in rows]


    def _random_choice_with_independent_bucket(self, sport_conference_ids: List[int]) -> Optional[int]:
        """
        Option A: choose a random conference uniformly.
        Independent teams are included as an extra bucket (None) with equal probability.
        """
        buckets: List[Optional[int]] = [None] + sport_conference_ids  # None = Independent
        return secrets.choice(buckets)


    def _count_owned_in_conference(
        self,
        conn,
        league_id: int,
        member_id: int,
        sport_conference_id: int,
        week: int,
    ) -> int:
        # Count currently-owned teams for this member in this conference as of 'week'
        row = conn.execute(
            text("""
                SELECT COUNT(*) AS cnt
                FROM "LeagueTeamSlot" lts
                JOIN "ConferenceMembership" cm
                ON cm."sportTeamId" = lts."sportTeamId"
                AND cm."sportConferenceId" = :sportConferenceId
                WHERE lts."leagueId" = :leagueId
                AND lts."memberId" = :memberId
                AND lts."acquiredWeek" <= :week
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week)
            """),
            {
                "leagueId": league_id,
                "memberId": member_id,
                "sportConferenceId": sport_conference_id,
                "week": week,
            },
        ).fetchone()
        return int(row._mapping["cnt"] or 0)


    def _get_conference_cap(self, conn, sport_conference_id: int) -> int:
        row = conn.execute(
            text("""
                SELECT "maxTeamsPerOwner"
                FROM "SportConference"
                WHERE id = :sportConferenceId
            """),
            {"sportConferenceId": sport_conference_id},
        ).fetchone()
        if not row:
            raise ValueError(f"SportConference {sport_conference_id} not found")
        return int(row._mapping["maxTeamsPerOwner"])


    def _pick_random_available_team_in_conference(
        self,
        conn,
        league_id: int,
        sport_conference_id: int,
        week: int,
    ) -> Optional[int]:
        """
        Returns a random sportTeamId that:
        - belongs to the sport_conference_id
        - not already drafted in DraftPick (league-wide)
        - not currently owned in LeagueTeamSlot for the target week
        """
        row = conn.execute(
            text("""
                SELECT cm."sportTeamId" AS "sportTeamId"
                FROM "ConferenceMembership" cm
                LEFT JOIN "DraftPick" dp
                ON dp."leagueId" = :leagueId
                AND dp."sportTeamId" = cm."sportTeamId"
                LEFT JOIN "LeagueTeamSlot" lts
                ON lts."leagueId" = :leagueId
                AND lts."sportTeamId" = cm."sportTeamId"
                AND lts."acquiredWeek" <= :week
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week)
                WHERE cm."sportConferenceId" = :sportConferenceId
                AND cm."seasonYear" IS NULL
                AND dp.id IS NULL
                AND lts.id IS NULL
                ORDER BY random()
                LIMIT 1
            """),
            {"leagueId": league_id, "sportConferenceId": sport_conference_id, "week": week},
        ).fetchone()

        return int(row._mapping["sportTeamId"]) if row else None


    def _pick_random_available_independent_team(
        self,
        conn,
        league_id: int,
        sport_id: int,
        week: int,
    ) -> Optional[int]:
        """
        Independent = team in this sport that has NO ConferenceMembership row.
        NOTE: This assumes SportTeam has a column "sportId".
        If your column is named differently, update this query.
        """
        row = conn.execute(
            text("""
                SELECT st.id AS "sportTeamId"
                FROM "SportTeam" st
                LEFT JOIN "ConferenceMembership" cm
                ON cm."sportTeamId" = st.id
                LEFT JOIN "DraftPick" dp
                ON dp."leagueId" = :leagueId
                AND dp."sportTeamId" = st.id
                LEFT JOIN "LeagueTeamSlot" lts
                ON lts."leagueId" = :leagueId
                AND lts."sportTeamId" = st.id
                AND lts."acquiredWeek" <= :week
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week)
                WHERE st."sportId" = :sportId
                AND cm.id IS NULL
                AND dp.id IS NULL
                AND lts.id IS NULL
                ORDER BY random()
                LIMIT 1
            """),
            {"leagueId": league_id, "sportId": sport_id, "week": week},
        ).fetchone()

        return int(row._mapping["sportTeamId"]) if row else None


    def _choose_random_team_for_auto_pick(
        self,
        conn,
        league_id: int,
        member_id: int,
        week: int,
    ) -> Optional[int]:
        """
        Option A (uniform by conference bucket, plus Independent bucket):
        - Choose a random bucket: one SportConference OR Independent
        - If bucket yields no valid teams, remove it and retry
        - Conference bucket must also satisfy maxTeamsPerOwner
        """
        sport_id = self._get_league_sport_id(conn, league_id)
        conference_ids = self._list_sport_conference_ids_for_sport(conn, sport_id)

        # Buckets: None = Independent, plus each SportConference id
        remaining: List[Optional[int]] = [None] + conference_ids

        while remaining:
            bucket = secrets.choice(remaining)

            if bucket is None:
                team_id = self._pick_random_available_independent_team(conn, league_id, sport_id, week)
                if team_id is not None:
                    return team_id
                remaining.remove(bucket)
                continue

            # Conference bucket: enforce cap first
            cap = self._get_conference_cap(conn, bucket)
            owned = self._count_owned_in_conference(conn, league_id, member_id, bucket, week)
            if owned >= cap:
                remaining.remove(bucket)
                continue

            team_id = self._pick_random_available_team_in_conference(conn, league_id, bucket, week)
            if team_id is not None:
                return team_id

            remaining.remove(bucket)

        return None


    def _insert_draft_pick_and_advance_state_no_expiry_check(
        self,
        conn,
        league_id: int,
        member_id: int,
        sport_team_id: int,
        acquired_week: int,
        selection_time: int,
        num_players: int,
        rounds: int,
        draft_type: str,
    ) -> Dict[str, Any]:
        """
        Same output shape as create_draft_pick_live, but does NOT reject for expired timer.
        Assumes caller already locked DraftState FOR UPDATE and confirmed it's the member's turn.
        """
        total_picks = int(rounds) * int(num_players)

        state = conn.execute(
            text("""
                SELECT status, "currentOverallPickNumber"
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
        if status != "live":
            raise ValueError(f"Draft is not live (status={status})")
        if current_overall > total_picks:
            raise ValueError("Draft already completed")
        
        expected_member_id = self._get_expected_member_for_overall(conn, league_id, current_overall)
        if expected_member_id is None:
            raise ValueError(f"DraftTurn missing for leagueId={league_id}, overallPickNumber={current_overall}")
        if expected_member_id != member_id:
            raise ValueError("AUTO-PICK attempted for non-on-the-clock member")


        # Compute round/pickInRound for DraftPick row (keeps your existing fields consistent)
        round_number, pos_in_round = self._compute_round_and_pos(current_overall, int(num_players))
        pick_in_round = self._draft_order_for_pick(draft_type, round_number, pos_in_round, int(num_players))

        # Insert DraftPick
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

        draft_pick = dict(draft_row._mapping)

        # Insert LeagueTeamSlot
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

        # Advance DraftState using DraftTurn order (next unpicked)
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
            notify_draft_updated(conn, league_id, "auto_pick")
            return draft_pick

        nxt = self._get_next_unpicked_turn_from(conn, league_id, next_overall)
        if not nxt:
            # Safety: treat as complete
            conn.execute(
                text("""
                    UPDATE "DraftState"
                    SET status = 'complete',
                        "currentMemberId" = NULL,
                        "expiresAt" = NULL,
                        "lastPickAt" = now(),
                        "updatedAt" = now()
                    WHERE "leagueId" = :leagueId
                """),
                {"leagueId": league_id},
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
            notify_draft_updated(conn, league_id, "auto_pick")
            return draft_pick

        next_overall, next_member_id = nxt

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
        notify_draft_updated(conn, league_id, "auto_pick")
        return draft_pick
