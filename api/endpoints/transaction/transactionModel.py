import json
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine


class TransactionModel:
    TYPE_TRADE = "TRADE"
    TYPE_FREE_AGENT = "FREE_AGENT"

    STATUS_PROPOSED = "PROPOSED"
    STATUS_REJECTED = "REJECTED"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_PENDING = "PENDING_APPLY"
    STATUS_VETOED = "VETOED"

    class SwapLimitExceeded(Exception):
        pass

    def __init__(self, db: Engine):
        self.db = db

    # ---------- League / settings helpers ----------

    def _get_league_settings(self, league_id: int) -> Dict[str, Any]:
        sql = text('SELECT settings FROM "League" WHERE id = :league_id')

        with self.db.connect() as conn:
            row = conn.execute(sql, {"league_id": league_id}).fetchone()

        if not row:
            raise ValueError(f"League {league_id} not found")

        settings = row._mapping["settings"]
        if isinstance(settings, str):
            settings = json.loads(settings)

        if not isinstance(settings, dict):
            raise ValueError("League.settings must be a JSON object")

        return settings

    def _get_max_swaps_for_league(self, league_id: int) -> Optional[int]:
        settings = self._get_league_settings(league_id)
        roster_settings = settings.get("roster") or {}
        max_swaps = roster_settings.get("maxSwaps")

        if max_swaps is None:
            return None

        try:
            return int(max_swaps)
        except (TypeError, ValueError):
            return None

    def _get_member_swap_count(self, league_id: int, member_id: int) -> int:
        """
        Counts how many FREE_AGENT transactions this member has in this league.
        Adjust WHERE if you later track statuses (e.g. only COMPLETED).
        """
        sql = text(
            """
            SELECT COUNT(*) AS count
            FROM "Transaction"
            WHERE "leagueId" = :league_id
              AND "memberFromId" = :member_id
              AND type = :type
            """
        )

        with self.db.connect() as conn:
            row = conn.execute(
                sql,
                {
                    "league_id": league_id,
                    "member_id": member_id,
                    "type": self.TYPE_FREE_AGENT,
                },
            ).fetchone()

        return int(row._mapping["count"])

    def _ensure_member_can_swap(self, league_id: int, member_id: int):
        max_swaps = self._get_max_swaps_for_league(league_id)

        # None or <= 0 => unlimited
        if max_swaps is None or max_swaps <= 0:
            return

        used = self._get_member_swap_count(league_id, member_id)

        if used >= max_swaps:
            raise self.SwapLimitExceeded(
                f"Member {member_id} has used {used}/{max_swaps} free agency swaps"
            )

    def _validate_members_in_league(
        self, league_id: int, member_ids: List[int]
    ):
        if not member_ids:
            return

        sql = text(
            """
            SELECT COUNT(*) AS count
            FROM "LeagueMember"
            WHERE "leagueId" = :league_id
              AND id = ANY(:member_ids)
            """
        )

        params = {
            "league_id": league_id,
            "member_ids": member_ids,
        }

        with self.db.connect() as conn:
            row = conn.execute(sql, params).fetchone()

        count = int(row._mapping["count"])
        if count != len(set(member_ids)):
            raise ValueError("One or more members do not belong to this league")

    def _assert_trade_deadline(self, conn, league_id: int) -> None:
        row = conn.execute(
            text("""
                SELECT ("tradeDeadline" IS NOT NULL AND now() > "tradeDeadline") AS "pastDeadline"
                FROM "League"
                WHERE id = :league_id
            """),
            {"league_id": league_id},
        ).fetchone()

        if not row:
            raise ValueError(f"League {league_id} not found")

        if bool(row._mapping["pastDeadline"]):
            raise ValueError("Trade deadline has passed")

    def _assert_free_agent_deadline(self, conn, league_id: int) -> None:
        row = conn.execute(
            text("""
                SELECT ("freeAgentDeadline" IS NOT NULL AND now() > "freeAgentDeadline") AS "pastDeadline"
                FROM "League"
                WHERE id = :league_id
            """),
            {"league_id": league_id},
        ).fetchone()

        if not row:
            raise ValueError(f"League {league_id} not found")

        if bool(row._mapping["pastDeadline"]):
            raise ValueError("Free agent deadline has passed")
        

    def _get_week_for_league(self, league_id: int, week_id: int) -> Dict[str, Any]:
        """
        Fetches the Week row for a league and validates ownership.
        Returns: { id, weekNumber, isLocked }
        """
        sql = text("""
            SELECT id, "weekNumber", "isLocked"
            FROM "Week"
            WHERE id = :week_id
            AND "leagueId" = :league_id
        """)

        with self.db.connect() as conn:
            row = conn.execute(
                sql,
                {"week_id": week_id, "league_id": league_id}
            ).fetchone()

        if not row:
            raise ValueError(f"Week {week_id} does not belong to league {league_id}")

        return dict(row._mapping)
    
    def _get_next_unlocked_week_for_league(
        self,
        league_id: int,
        after_week_number: int,
    ) -> Dict[str, Any]:
        """
        Returns the next unlocked week after the given week number.
        """
        sql = text("""
            SELECT id, "weekNumber", "isLocked"
            FROM "Week"
            WHERE "leagueId" = :league_id
              AND "weekNumber" > :week_number
              AND "isLocked" = FALSE
            ORDER BY "weekNumber" ASC
            LIMIT 1
        """)

        with self.db.connect() as conn:
            row = conn.execute(
                sql,
                {"league_id": league_id, "week_number": after_week_number},
            ).fetchone()

        if not row:
            raise ValueError(
                f"No unlocked future week found after week {after_week_number}"
            )

        return dict(row._mapping)


    # ------------------------------------------------------------------
    # TRADE VALIDATION (ownership + conference limits)
    # ------------------------------------------------------------------

    def _validate_trade(
        self,
        conn,
        league_id: int,
        week_number: int,
        from_member_id: int,
        to_member_id: int,
        from_team_ids: List[int],
        to_team_ids: List[int],
    ) -> None:
        # ---- ownership ----
        ownership_rows = conn.execute(
            text("""
                SELECT "sportTeamId","memberId"
                FROM "LeagueTeamSlot"
                WHERE "leagueId" = :league_id
                AND "sportTeamId" = ANY(:team_ids)
                AND "acquiredWeek" <= :week_number
                AND ("droppedWeek" IS NULL OR "droppedWeek" > :week_number)
            """),
            {
                "league_id": league_id,
                "week_number": week_number,
                "team_ids": from_team_ids + to_team_ids,
            },
        ).fetchall()

        ownership = {r._mapping["sportTeamId"]: r._mapping["memberId"] for r in ownership_rows}

        for tid in from_team_ids:
            if ownership.get(tid) != from_member_id:
                raise ValueError(f"Member {from_member_id} does not own team {tid}")

        for tid in to_team_ids:
            if ownership.get(tid) != to_member_id:
                raise ValueError(f"Member {to_member_id} does not own team {tid}")

        # ---- conference limits ----
        def conference_counts(member_id: int, exclude_ids: List[int]) -> Dict[int, int]:
            rows = conn.execute(
                text("""
                    SELECT cm."sportConferenceId", COUNT(*) AS cnt
                    FROM "LeagueTeamSlot" lts
                    JOIN "ConferenceMembership" cm
                    ON cm."sportTeamId" = lts."sportTeamId"
                    WHERE lts."leagueId" = :league_id
                    AND lts."memberId" = :member_id
                    AND lts."acquiredWeek" <= :week_number
                    AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week_number)
                    AND NOT (lts."sportTeamId" = ANY(:exclude_ids))
                    GROUP BY cm."sportConferenceId"
                """),
                {
                    "league_id": league_id,
                    "week_number": week_number,
                    "member_id": member_id,
                    "exclude_ids": exclude_ids,
                },
            ).fetchall()


            return {r._mapping["sportConferenceId"]: r._mapping["cnt"] for r in rows}

        from_counts = conference_counts(from_member_id, from_team_ids)
        to_counts = conference_counts(to_member_id, to_team_ids)

        def incoming_confs(team_ids: List[int]) -> Dict[int, int]:
            rows = conn.execute(
                text("""
                    SELECT "sportConferenceId", COUNT(*) AS cnt
                    FROM "ConferenceMembership"
                    WHERE "sportTeamId" = ANY(:team_ids)
                    GROUP BY "sportConferenceId"
                """),
                {"team_ids": team_ids},
            ).fetchall()
            return {r._mapping["sportConferenceId"]: r._mapping["cnt"] for r in rows}

        from_incoming = incoming_confs(to_team_ids)
        to_incoming = incoming_confs(from_team_ids)

        limit_rows = conn.execute(
            text("""
                SELECT id, "maxTeamsPerOwner"
                FROM "SportConference"
            """)
        ).fetchall()

        limits = {r._mapping["id"]: r._mapping["maxTeamsPerOwner"] for r in limit_rows}

        for conf_id, add in from_incoming.items():
            if from_counts.get(conf_id, 0) + add > limits.get(conf_id, 999):
                raise ValueError("Conference limit exceeded for proposing member")

        for conf_id, add in to_incoming.items():
            if to_counts.get(conf_id, 0) + add > limits.get(conf_id, 999):
                raise ValueError("Conference limit exceeded for receiving member")

    # ------------------------------------------------------------------
    # APPLY TRADE
    # ------------------------------------------------------------------

    def _apply_trade(
        self,
        conn,
        league_id: int,
        week_number: int,
        from_member_id: int,
        to_member_id: int,
        from_team_ids: List[int],
        to_team_ids: List[int],
    ) -> None:
        # 1) Close out current ownership rows for teams leaving each member
        if from_team_ids:
            conn.execute(
                text("""
                    UPDATE "LeagueTeamSlot"
                    SET "droppedWeek" = :week_number
                    WHERE "leagueId" = :league_id
                    AND "memberId" = :member_id
                    AND "sportTeamId" = ANY(:team_ids)
                    AND "acquiredWeek" <= :week_number
                    AND ("droppedWeek" IS NULL OR "droppedWeek" > :week_number)
                """),
                {
                    "league_id": league_id,
                    "member_id": from_member_id,
                    "team_ids": from_team_ids,
                    "week_number": week_number,
                },
            )

        if to_team_ids:
            conn.execute(
                text("""
                    UPDATE "LeagueTeamSlot"
                    SET "droppedWeek" = :week_number
                    WHERE "leagueId" = :league_id
                    AND "memberId" = :member_id
                    AND "sportTeamId" = ANY(:team_ids)
                    AND "acquiredWeek" <= :week_number
                    AND ("droppedWeek" IS NULL OR "droppedWeek" > :week_number)
                """),
                {
                    "league_id": league_id,
                    "member_id": to_member_id,
                    "team_ids": to_team_ids,
                    "week_number": week_number,
                },
            )

        # 2) Insert new ownership rows starting this week (executemany)
        insert_sql = text("""
            INSERT INTO "LeagueTeamSlot"
                ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia")
            VALUES
                (:league_id, :member_id, :team_id, :week_number, :acquired_via)
        """)

        if from_team_ids:
            rows = [
                {
                    "league_id": league_id,
                    "member_id": to_member_id,
                    "team_id": int(tid),
                    "week_number": week_number,
                    "acquired_via": self.TYPE_TRADE,
                }
                for tid in from_team_ids
            ]
            conn.execute(insert_sql, rows)

        if to_team_ids:
            rows = [
                {
                    "league_id": league_id,
                    "member_id": from_member_id,
                    "team_id": int(tid),
                    "week_number": week_number,
                    "acquired_via": self.TYPE_TRADE,
                }
                for tid in to_team_ids
            ]
            conn.execute(insert_sql, rows)

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def propose_trade(
        self,
        league_id: int,
        week_id: int,
        from_member_id: int,
        to_member_id: int,
        from_team_ids: List[int],
        to_team_ids: List[int],
    ) -> Dict[str, Any]:
        week = self._get_week_for_league(league_id, week_id)
        if week["isLocked"]:
            raise ValueError("Week is locked")

        self._validate_members_in_league(league_id, [from_member_id, to_member_id])

        with self.db.begin() as conn:
            self._assert_trade_deadline(conn, league_id)
            self._validate_trade(
                conn,
                league_id,
                week["weekNumber"],
                from_member_id,
                to_member_id,
                from_team_ids,
                to_team_ids,
            )

            row = conn.execute(
                text("""
                    INSERT INTO "Transaction"
                    ("leagueId","weekId",type,"memberFromId","memberToId",status,"fromTeamIds","toTeamIds")
                    VALUES
                    (:league,:week,:type,:from_id,:to_id,:status, CAST(:from_teams AS jsonb), CAST(:to_teams AS jsonb))
                    RETURNING id
                """),
                {
                    "league": league_id,
                    "week": week_id,
                    "type": self.TYPE_TRADE,
                    "from_id": from_member_id,
                    "to_id": to_member_id,
                    "status": self.STATUS_PROPOSED,
                    "from_teams": json.dumps(from_team_ids),
                    "to_teams": json.dumps(to_team_ids),
                },
            ).fetchone()

        return {"transactionId": row._mapping["id"], "status": self.STATUS_PROPOSED}

    def respond_to_trade(
        self,
        transaction_id: int,
        action: str,
        responder_member_id: int,
        reject_reason: str | None = None,
    ) -> Dict[str, Any]:
        action = action.upper()
        if action not in ("ACCEPT", "REJECT"):
            raise ValueError("Invalid action")

        with self.db.begin() as conn:
            tx = conn.execute(
                text("""
                    SELECT *
                    FROM "Transaction"
                    WHERE id = :id
                    FOR UPDATE
                """),
                {"id": transaction_id},
            ).fetchone()

            if not tx:
                raise ValueError("Transaction not found")

            txm = tx._mapping

            if txm["status"] != self.STATUS_PROPOSED:
                raise ValueError("Trade already resolved")

            if responder_member_id != txm["memberToId"]:
                raise ValueError("Only receiving member may respond")

            if action == "REJECT":
                conn.execute(
                    text("""
                        UPDATE "Transaction"
                        SET status = :status,
                            "decidedByMemberId" = :by,
                            "rejectReason" = :reason
                        WHERE id = :id
                    """),
                    {
                        "status": self.STATUS_REJECTED,
                        "by": responder_member_id,
                        "reason": reject_reason,
                        "id": transaction_id,
                    },
                )
                return {"transactionId": transaction_id, "status": self.STATUS_REJECTED}

            self._assert_trade_deadline(conn, txm["leagueId"])
            week = self._get_week_for_league(txm["leagueId"], txm["weekId"])
            if week["isLocked"]:
                raise ValueError("Week is locked")

            self._validate_trade(
                conn,
                txm["leagueId"],
                week["weekNumber"],
                txm["memberFromId"],
                txm["memberToId"],
                list(txm["fromTeamIds"]),
                list(txm["toTeamIds"]),
            )

            conn.execute(
                text("""
                    UPDATE "Transaction"
                    SET status = :status,
                        "decidedByMemberId" = :by
                    WHERE id = :id
                """),
                {
                    "status": self.STATUS_PENDING,
                    "by": responder_member_id,
                    "id": transaction_id,
                },
            )

        return {"transactionId": transaction_id, "status": self.STATUS_PENDING}
    
    def apply_trade(
        self,
        transaction_id: int,
    ):
        with self.db.begin() as conn:

            tx = conn.execute(
                text("""
                    SELECT *
                    FROM "Transaction"
                    WHERE id = :id
                    FOR UPDATE
                """),
                {"id": transaction_id},
            ).fetchone()

            if not tx:
                raise ValueError("Transaction not found")

            txm = tx._mapping
            self._assert_trade_deadline(conn, txm["leagueId"])

            week = self._get_week_for_league(txm["leagueId"], txm["weekId"])

            # 1) Close out current ownership rows for teams leaving each member
            if txm['fromTeamIds']:
                conn.execute(
                    text("""
                        UPDATE "LeagueTeamSlot"
                        SET "droppedWeek" = :week_number
                        WHERE "leagueId" = :league_id
                        AND "memberId" = :member_id
                        AND "sportTeamId" = ANY(:team_ids)
                        AND "acquiredWeek" <= :week_number
                        AND ("droppedWeek" IS NULL OR "droppedWeek" > :week_number)
                    """),
                    {
                        "league_id": txm['leagueId'],
                        "member_id": txm['memberFromId'],
                        "team_ids": txm['fromTeamIds'],
                        "week_number": week['weekNumber'],
                    },
                )

            if txm['toTeamIds']:
                conn.execute(
                    text("""
                        UPDATE "LeagueTeamSlot"
                        SET "droppedWeek" = :week_number
                        WHERE "leagueId" = :league_id
                        AND "memberId" = :member_id
                        AND "sportTeamId" = ANY(:team_ids)
                        AND "acquiredWeek" <= :week_number
                        AND ("droppedWeek" IS NULL OR "droppedWeek" > :week_number)
                    """),
                    {
                        "league_id": txm['leagueId'],
                        "member_id": txm['memberToId'],
                        "team_ids": txm['toTeamIds'],
                        "week_number": week['weekNumber'],
                    },
                )

            # 2) Insert new ownership rows starting this week (executemany)
            insert_sql = text("""
                INSERT INTO "LeagueTeamSlot"
                    ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia")
                VALUES
                    (:league_id, :member_id, :team_id, :week_number, :acquired_via)
            """)

            if txm['fromTeamIds']:
                rows = [
                    {
                        "league_id": txm['leagueId'],
                        "member_id": txm['memberToId'],
                        "team_id": int(tid),
                        "week_number": week['weekNumber'],
                        "acquired_via": self.TYPE_TRADE,
                    }
                    for tid in txm['fromTeamIds']
                ]
                conn.execute(insert_sql, rows)

            if txm['toTeamIds']:
                rows = [
                    {
                        "league_id": txm['leagueId'],
                        "member_id": txm['memberFromId'],
                        "team_id": int(tid),
                        "week_number": week['weekNumber'],
                        "acquired_via": self.TYPE_TRADE,
                    }
                    for tid in txm['toTeamIds']
                ]
                conn.execute(insert_sql, rows)

            conn.execute(
                text("""
                    UPDATE "Transaction"
                    SET status = :status
                    WHERE id = :id
                """),
                {
                    "status": self.STATUS_COMPLETED,
                    "id": transaction_id,
                },
            )
        
    
    def cancel_trade_proposal(self, transaction_id: int, requester_member_id: int) -> Dict[str, Any]:
        with self.db.begin() as conn:
            tx = conn.execute(
                text("""
                    SELECT id, status, type, "memberFromId"
                    FROM "Transaction"
                    WHERE id = :id
                    FOR UPDATE
                """),
                {"id": transaction_id},
            ).fetchone()

            if not tx:
                raise ValueError("Transaction not found")

            txm = tx._mapping

            if txm["type"] != self.TYPE_TRADE:
                raise ValueError("Not a trade transaction")

            if txm["status"] != self.STATUS_PROPOSED:
                raise ValueError("Only PROPOSED trades can be cancelled")

            if requester_member_id != txm["memberFromId"]:
                raise ValueError("Only the proposing member can cancel this trade")

            conn.execute(
                text("""
                    UPDATE "Transaction"
                    SET status = :status,
                        "decidedByMemberId" = :by
                    WHERE id = :id
                """),
                {"status": self.STATUS_CANCELLED, "by": requester_member_id, "id": transaction_id},
            )

        return {"transactionId": transaction_id, "status": self.STATUS_CANCELLED}
    
    

    # ---------- Free agency helpers ----------

    def _is_team_owned_in_week(
        self,
        conn,
        league_id: int,
        team_id: int,
        week_number: int,
    ) -> bool:
        """
        True if *anyone* owns this team in this league during this week.
        """
        sql = text("""
            SELECT 1
            FROM "LeagueTeamSlot"
            WHERE "leagueId" = :league_id
            AND "sportTeamId" = :team_id
            AND "acquiredWeek" <= :week_number
            AND ("droppedWeek" IS NULL OR "droppedWeek" > :week_number)
            LIMIT 1
        """)
        row = conn.execute(sql, {
            "league_id": league_id,
            "team_id": team_id,
            "week_number": week_number,
        }).fetchone()
        return row is not None


    def _is_team_owned_by_member_in_week(
        self,
        conn,
        league_id: int,
        member_id: int,
        team_id: int,
        week_number: int,
    ) -> bool:
        """
        True if this member owns this team in this league during this week.
        """
        sql = text("""
            SELECT 1
            FROM "LeagueTeamSlot"
            WHERE "leagueId" = :league_id
            AND "memberId" = :member_id
            AND "sportTeamId" = :team_id
            AND "acquiredWeek" <= :week_number
            AND ("droppedWeek" IS NULL OR "droppedWeek" > :week_number)
            LIMIT 1
        """)
        row = conn.execute(sql, {
            "league_id": league_id,
            "member_id": member_id,
            "team_id": team_id,
            "week_number": week_number,
        }).fetchone()
        return row is not None

    
    def _get_team_conference_info(self, conn, team_ids: List[int]) -> Dict[int, Dict[str, int]]:
        """
        For each team_id, returns its sportConferenceId and that conference's maxTeamsPerOwner.

        Assumes:
        ConferenceMembership.sportTeamId -> SportTeam.id
        ConferenceMembership.sportConferenceId -> SportConference.id
        SportConference has maxTeamsPerOwner
        """
        if not team_ids:
            return {}

        rows = conn.execute(
            text("""
                SELECT
                cm."sportTeamId"       AS "sportTeamId",
                cm."sportConferenceId" AS "sportConferenceId",
                sc."maxTeamsPerOwner"  AS "maxTeamsPerOwner"
                FROM "ConferenceMembership" cm
                JOIN "SportConference" sc
                ON sc.id = cm."sportConferenceId"
                WHERE cm."sportTeamId" = ANY(:team_ids)
            """),
            {"team_ids": team_ids},
        ).mappings().all()

        info: Dict[int, Dict[str, int]] = {}
        for r in rows:
            tid = int(r["sportTeamId"])
            # If you ever add seasonYear to ConferenceMembership filtering,
            # this is where you'd apply it.
            info[tid] = {
                "sportConferenceId": int(r["sportConferenceId"]),
                "maxTeamsPerOwner": int(r["maxTeamsPerOwner"]),
            }

        # Safety: if any requested team is missing conference membership data
        missing = [t for t in team_ids if t not in info]
        if missing:
            raise ValueError(f"Missing ConferenceMembership rows for team(s): {missing}")

        return info

    def _get_member_conference_counts(
        self,
        conn,
        league_id: int,
        member_id: int,
        week_number: int,
    ) -> Dict[int, int]:
        """
        Returns: { sportConferenceId: countOwnedInThatConferenceForWeek }
        """
        rows = conn.execute(
            text("""
                SELECT
                cm."sportConferenceId" AS "sportConferenceId",
                COUNT(*)              AS "cnt"
                FROM "LeagueTeamSlot" lts
                JOIN "ConferenceMembership" cm
                ON cm."sportTeamId" = lts."sportTeamId"
                WHERE lts."leagueId" = :league_id
                AND lts."memberId" = :member_id
                AND lts."acquiredWeek" <= :week_number
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week_number)
                GROUP BY cm."sportConferenceId"
            """),
            {"league_id": league_id, "member_id": member_id, "week_number": week_number},
        ).mappings().all()

        return {int(r["sportConferenceId"]): int(r["cnt"]) for r in rows}
    
    def _get_member_roster_team_ids_for_week(self, conn, league_id: int, member_id: int, week_number: int) -> List[int]:
        rows = conn.execute(
            text("""
                SELECT lts."sportTeamId" AS "sportTeamId"
                FROM "LeagueTeamSlot" lts
                WHERE lts."leagueId" = :league_id
                AND lts."memberId" = :member_id
                AND lts."acquiredWeek" <= :week_number
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week_number)
                ORDER BY lts."sportTeamId"
            """),
            {"league_id": league_id, "member_id": member_id, "week_number": week_number},
        ).scalars().all()

        return [int(x) for x in rows]


    # ---------- Free agency add / drop ----------

    def free_agency_add_drop(
        self,
        league_id: int,
        week_id: int,
        week_number: int,
        member_id: int,
        add_team_id: Optional[int],
        drop_team_id: Optional[int],
    ) -> Dict[str, Any]:
        """
        Performs a free-agency add/drop for a single league member…
        """
        week_info = self._get_week_for_league(league_id, week_id)
        week_number = week_info["weekNumber"]
        if week_info["isLocked"]:
            next_week = self._get_next_unlocked_week_for_league(
                league_id,
                after_week_number=int(week_number),
            )
            week_id = int(next_week["id"])
            week_number = int(next_week["weekNumber"])

        # Enforce swap limit first
        self._ensure_member_can_swap(league_id, member_id)

        # Ensure member belongs to league
        self._validate_members_in_league(league_id, [member_id])

        with self.db.begin() as conn:
            self._assert_free_agent_deadline(conn, league_id)
            # Conference info for any teams involved
            involved_team_ids: List[int] = []
            if add_team_id is not None:
                involved_team_ids.append(add_team_id)
            if drop_team_id is not None:
                involved_team_ids.append(drop_team_id)

            team_conf_info = (
                self._get_team_conference_info(conn, involved_team_ids)
                if involved_team_ids
                else {}
            )

            # Current conference counts
            counts = self._get_member_conference_counts(
                conn, league_id, member_id, week_number
            )

            # Build conference limits map
            conf_limits: Dict[int, int] = {}
            for info in team_conf_info.values():
                cid = info["sportConferenceId"]
                limit = info["maxTeamsPerOwner"]
                if cid in conf_limits and conf_limits[cid] != limit:
                    raise ValueError(
                        f"Inconsistent maxTeamsPerOwner for conference {cid}"
                    )
                conf_limits[cid] = limit

            # 1) Validate / simulate drop
            counts_after = dict(counts)

            if drop_team_id is not None:
                # Ensure team is on member's roster this week
                owned = self._is_team_owned_by_member_in_week(
                    conn, league_id, member_id, drop_team_id, week_number
                )
                if not owned:
                    raise ValueError(
                        f"Member {member_id} does not own team {drop_team_id} in week {week_number}"
                    )

                info = team_conf_info.get(drop_team_id)
                if info:
                    cid = info["sportConferenceId"]
                    counts_after[cid] = counts_after.get(cid, 0) - 1
                    if counts_after[cid] < 0:
                        raise ValueError(
                            f"Member {member_id} would have negative count in conference {cid}"
                        )

            # 2) Validate / simulate add
            if add_team_id is not None:
                # Ensure team is a free agent
                if self._is_team_owned_in_week(
                    conn, league_id, add_team_id, week_number
                ):
                    raise ValueError(
                        f"Team {add_team_id} is not a free agent in week {week_number}"
                    )

                info = team_conf_info[add_team_id]
                cid = info["sportConferenceId"]
                max_per = conf_limits.get(cid)
                new_count = counts_after.get(cid, 0) + 1
                if max_per is not None and new_count > max_per:
                    raise ValueError(
                        f"Member {member_id} would exceed maxTeamsPerOwner "
                        f"({new_count}/{max_per}) in conference {cid}"
                    )
                counts_after[cid] = new_count

            # 3) Apply DB changes: drop then add
            if drop_team_id is not None:
                drop_sql = text(
                    """
                    UPDATE "LeagueTeamSlot"
                    SET "droppedWeek" = :week_number
                    WHERE "leagueId"   = :league_id
                      AND "memberId"   = :member_id
                      AND "sportTeamId" = :team_id
                      AND "acquiredWeek" <= :week_number
                      AND ("droppedWeek" IS NULL OR "droppedWeek" > :week_number)
                    """
                )
                conn.execute(
                    drop_sql,
                    {
                        "league_id": league_id,
                        "member_id": member_id,
                        "team_id": drop_team_id,
                        "week_number": week_number,
                    },
                )

            if add_team_id is not None:
                insert_sql = text(
                    """
                    INSERT INTO "LeagueTeamSlot"
                        ("leagueId", "memberId", "sportTeamId", "acquiredWeek", "acquiredVia")
                    VALUES
                        (:league_id, :member_id, :team_id, :week_number, :acquired_via)
                    """
                )
                conn.execute(
                    insert_sql,
                    {
                        "league_id": league_id,
                        "member_id": member_id,
                        "team_id": add_team_id,
                        "week_number": week_number,
                        "acquired_via": self.TYPE_FREE_AGENT,
                    },
                )

            # 4) Log Transaction
            tx_sql = text(
                """
                INSERT INTO "Transaction"
                    ("leagueId", "weekId", type, "memberFromId", "memberToId", status)
                VALUES
                    (:league_id, :week_id, :type, :member_from_id, NULL, :status)
                RETURNING id
                """
            )

            tx_row = conn.execute(
                tx_sql,
                {
                    "league_id": league_id,
                    "week_id": week_id,
                    "type": self.TYPE_FREE_AGENT,
                    "member_from_id": member_id,
                    "status": self.STATUS_COMPLETED,
                },
            ).fetchone()

            transaction_id = int(tx_row._mapping["id"])

            # 5) Updated roster
            member_roster = self._get_member_roster_team_ids_for_week(
                conn, league_id, member_id, week_number
            )

        return {
            "leagueId": league_id,
            "weekId": week_id,
            "weekNumber": week_number,
            "transactionId": transaction_id,
            "type": self.TYPE_FREE_AGENT,
            "memberId": member_id,
            "added": add_team_id,
            "dropped": drop_team_id,
            "memberRosterTeamIds": member_roster,
        }

    def get_week_roster_violations(
        self,
        league_id: int,
        week_id: int,
    ):
        """
        Returns a list of roster violations for the given week.
        A "violation" is: member has more than maxTeamsPerOwner in a conference.

        Result shape:
        [
          {
            "memberId": 123,
            "sportConferenceId": 5,
            "count": 4,
            "maxTeamsPerOwner": 3
          },
          ...
        ]
        """
        week_info = self._get_week_for_league(league_id, week_id)
        week_number = week_info["weekNumber"]

        sql = text(
            """
            SELECT
              lts."memberId"           AS "memberId",
              cm."sportConferenceId"   AS "sportConferenceId",
              sc."maxTeamsPerOwner"    AS "maxTeamsPerOwner",
              COUNT(*)                 AS "count"
            FROM "LeagueTeamSlot" lts
            JOIN "ConferenceMembership" cm
              ON cm."sportTeamId" = lts."sportTeamId"
            JOIN "SportConference" sc
              ON sc.id = cm."sportConferenceId"
            WHERE lts."leagueId" = :league_id
              AND lts."acquiredWeek" <= :week_number
              AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week_number)
            GROUP BY
              lts."memberId",
              cm."sportConferenceId",
              sc."maxTeamsPerOwner"
            HAVING COUNT(*) > sc."maxTeamsPerOwner"
            """
        )

        with self.db.connect() as conn:
            rows = conn.execute(
                sql,
                {
                    "league_id": league_id,
                    "week_number": week_number,
                },
            ).mappings().all()

        violations = []
        for r in rows:
            violations.append(
                {
                    "memberId": int(r["memberId"]),
                    "sportConferenceId": int(r["sportConferenceId"]),
                    "count": int(r["count"]),
                    "maxTeamsPerOwner": int(r["maxTeamsPerOwner"]),
                }
            )

        return violations

    def assert_week_rosters_valid(
        self,
        league_id: int,
        week_id: int,
    ):
        """
        Raises ValueError if any member exceeds maxTeamsPerOwner in any conference
        for this week.
        """
        violations = self.get_week_roster_violations(league_id, week_id)
        if not violations:
            return

        # Build a simple summary string
        parts = []
        for v in violations:
            parts.append(
                f'member {v["memberId"]} has {v["count"]}/'
                f'{v["maxTeamsPerOwner"]} teams in conference {v["sportConferenceId"]}'
            )

        details = "; ".join(parts)
        raise ValueError(f"Roster violations for week {week_id}: {details}")
    
    def get_open_trade_transactions_for_member(
        self,
        league_id: int,
        member_id: int,
    ) -> Dict[str, Any]:
        """
        Returns all non-finalized TRADE transactions involving this member,
        split into incoming/outgoing, plus an 'all' list.
        Excludes FREE_AGENT transactions entirely.
        """
        sql = text("""
            SELECT
            t.id,
            t."leagueId",
            t."weekId",
            t.type,
            t.status,
            t."memberFromId",
            t."memberToId",
            t."createdAt",

            -- member context
            COALESCE(tv_me.veto, false) AS "memberHasVetoed",
            (t."memberFromId" = :member_id OR t."memberToId" = :member_id) AS "isParticipant",

            -- counts for UI
            (
                SELECT COUNT(*)
                FROM "TransactionVote" tvc
                WHERE tvc."transactionId" = t.id
                AND tvc.veto = true
            ) AS "vetoCount",

            -- member display info
            lm_from."teamName" AS "memberFromTeamName",
            u_from."displayName" AS "memberFromDisplayName",
            lm_to."teamName" AS "memberToTeamName",
            u_to."displayName" AS "memberToDisplayName",

            -- FROM teams
            COALESCE(
                jsonb_agg(
                DISTINCT jsonb_build_object(
                    'id', st_from.id,
                    'displayName', st_from."displayName"
                )
                ) FILTER (WHERE st_from.id IS NOT NULL),
                '[]'::jsonb
            ) AS "fromTeams",

            -- TO teams
            COALESCE(
                jsonb_agg(
                DISTINCT jsonb_build_object(
                    'id', st_to.id,
                    'displayName', st_to."displayName"
                )
                ) FILTER (WHERE st_to.id IS NOT NULL),
                '[]'::jsonb
            ) AS "toTeams"

            FROM "Transaction" t

            -- requesting member's veto (at most 1 row due to unique constraint)
            LEFT JOIN "TransactionVote" tv_me
            ON tv_me."transactionId" = t.id
            AND tv_me."leagueMemberId" = :member_id

            LEFT JOIN "LeagueMember" lm_from
            ON lm_from.id = t."memberFromId"
            LEFT JOIN "User" u_from
            ON u_from.id = lm_from."userId"

            LEFT JOIN "LeagueMember" lm_to
            ON lm_to.id = t."memberToId"
            LEFT JOIN "User" u_to
            ON u_to.id = lm_to."userId"

            -- Expand FROM team ids
            LEFT JOIN LATERAL jsonb_array_elements_text(t."fromTeamIds") AS f(team_id)
            ON TRUE
            LEFT JOIN "SportTeam" st_from
            ON st_from.id = f.team_id::bigint

            -- Expand TO team ids
            LEFT JOIN LATERAL jsonb_array_elements_text(t."toTeamIds") AS tt(team_id)
            ON TRUE
            LEFT JOIN "SportTeam" st_to
            ON st_to.id = tt.team_id::bigint

            WHERE t."leagueId" = :league_id
            AND t.type = 'TRADE'
            AND t.status NOT IN ('COMPLETED', 'REJECTED', 'CANCELLED', 'VETOED')

            GROUP BY
            t.id,
            t."leagueId",
            t."weekId",
            t.type,
            t.status,
            t."memberFromId",
            t."memberToId",
            t."createdAt",
            tv_me.veto,
            lm_from."teamName",
            u_from."displayName",
            lm_to."teamName",
            u_to."displayName",
            (t."memberFromId" = :member_id OR t."memberToId" = :member_id)

            ORDER BY t."createdAt" DESC
        """)

        with self.db.connect() as conn:
            rows = conn.execute(
                sql,
                {"league_id": league_id, "member_id": member_id},
            ).mappings().all()

        mine_all: List[Dict[str, Any]] = []
        mine_incoming: List[Dict[str, Any]] = []
        mine_outgoing: List[Dict[str, Any]] = []
        others: List[Dict[str, Any]] = []

        for r in rows:
            item = {
                "transactionId": int(r["id"]),
                "leagueId": int(r["leagueId"]),
                "weekId": int(r["weekId"]),
                "type": r["type"],
                "status": r["status"],
                "memberFromId": int(r["memberFromId"]),
                "memberToId": int(r["memberToId"]) if r["memberToId"] is not None else None,
                "memberFromTeamName": r["memberFromTeamName"],
                "memberFromDisplayName": r["memberFromDisplayName"],
                "memberToTeamName": r["memberToTeamName"],
                "memberToDisplayName": r["memberToDisplayName"],
                "fromTeams": list(r["fromTeams"] or []),
                "toTeams": list(r["toTeams"] or []),
                "memberHasVetoed": bool(r["memberHasVetoed"]),
                "isParticipant": bool(r["isParticipant"]),
                "vetoCount": int(r["vetoCount"] or 0),
                "createdAt": r["createdAt"].isoformat() if r["createdAt"] else None,
            }

            if item["isParticipant"]:
                if item["memberToId"] == member_id:
                    mine_incoming.append(item)
                if item["memberFromId"] == member_id:
                    mine_outgoing.append(item)
            else:
                others.append(item)

        return {
            "memberId": member_id,
            "mine": {
                "incoming": mine_incoming,
                "outgoing": mine_outgoing,
            },
            "others": others,
        }

    def _get_trade_veto_settings(self, league_id: int) -> Dict[str, Any]:
        settings = self._get_league_settings(league_id)
        tx = (settings.get("transactions") or {})
        veto = (tx.get("tradeVeto") or {})
        enabled = bool(veto.get("enabled", False))
        required = veto.get("requiredVetoCount")
        try:
            required_int = int(required) if required is not None else 0
        except (TypeError, ValueError):
            required_int = 0
        return {"enabled": enabled, "requiredVetoCount": required_int}


    def veto_trade(self, transaction_id: int, league_member_id: int) -> Dict[str, Any]:
        """
        Toggles a member's veto vote for a trade.
        If veto_count reaches requiredVetoCount, marks Transaction as VETOED.
        league_member_id is LeagueMember.id (not User.id).
        """
        with self.db.begin() as conn:
            tx = conn.execute(
                text("""
                    SELECT id, "leagueId", type, status, "memberFromId", "memberToId"
                    FROM "Transaction"
                    WHERE id = :id
                    FOR UPDATE
                """),
                {"id": transaction_id},
            ).fetchone()

            if not tx:
                raise ValueError("Transaction not found")

            txm = tx._mapping

            if txm["type"] != self.TYPE_TRADE:
                raise ValueError("Only TRADE transactions can be vetoed")

            if txm["status"] in (
                self.STATUS_COMPLETED,
                self.STATUS_REJECTED,
                self.STATUS_CANCELLED,
                getattr(self, "STATUS_VETOED", "VETOED"),
            ):
                raise ValueError(f"Trade is not vetoable in status {txm['status']}")

            league_id = int(txm["leagueId"])

            # Ensure voter belongs to the league
            self._validate_members_in_league(league_id, [int(league_member_id)])

            # Prevent proposer/receiver from vetoing (optional rule)
            if int(league_member_id) in (int(txm["memberFromId"]), int(txm["memberToId"])):
                raise ValueError("Trade participants cannot veto their own trade")

            veto_settings = self._get_trade_veto_settings(league_id)
            if not veto_settings["enabled"]:
                raise ValueError("Trade veto is not enabled for this league")

            required = int(veto_settings["requiredVetoCount"] or 0)
            if required <= 0:
                raise ValueError("League veto requiredVetoCount is not configured")

            # 1) Toggle if row exists
            toggled = conn.execute(
                text("""
                    UPDATE "TransactionVote"
                    SET veto = NOT veto
                    WHERE "transactionId" = :tx_id
                    AND "leagueMemberId" = :lm_id
                    RETURNING veto
                """),
                {"tx_id": transaction_id, "lm_id": league_member_id},
            ).fetchone()

            if toggled:
                current_veto = bool(toggled._mapping["veto"])
            else:
                # 2) Otherwise insert a new veto = true
                inserted = conn.execute(
                    text("""
                        INSERT INTO "TransactionVote"
                            ("transactionId","leagueMemberId",veto)
                        VALUES
                            (:tx_id, :lm_id, true)
                        RETURNING veto
                    """),
                    {"tx_id": transaction_id, "lm_id": league_member_id},
                ).fetchone()
                current_veto = bool(inserted._mapping["veto"])

            # Count active vetoes
            vote_row = conn.execute(
                text("""
                    SELECT COUNT(*) AS cnt
                    FROM "TransactionVote"
                    WHERE "transactionId" = :tx_id
                    AND veto = true
                """),
                {"tx_id": transaction_id},
            ).fetchone()

            veto_count = int(vote_row._mapping["cnt"])

            # If threshold reached, mark transaction as VETOED
            new_status = txm["status"]
            if veto_count >= required:
                conn.execute(
                    text("""
                        UPDATE "Transaction"
                        SET status = :status
                        WHERE id = :id
                    """),
                    {"status": getattr(self, "STATUS_VETOED", "VETOED"), "id": transaction_id},
                )
                new_status = getattr(self, "STATUS_VETOED", "VETOED")

        return {
            "transactionId": int(transaction_id),
            "status": str(new_status),
            "memberVetoed": bool(current_veto),
            "vetoCount": int(veto_count),
            "requiredVetoCount": int(required),
        }
