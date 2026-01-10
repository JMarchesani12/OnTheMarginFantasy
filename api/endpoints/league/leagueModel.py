import json
import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from endpoints.schedule.scheduleModel import ScheduleModel

ALLOWED_LEAGUE_MEMBER_FIELDS = {
    "teamName": '"teamName"',
    "draftOrder": '"draftOrder"',
    "seasonPoints": '"seasonPoints"',
}

class LeagueModel:
    def __init__(self, db: Engine):
        self.db = db
        self.scheduleModel = ScheduleModel(db, os.getenv("ESPN_BASE_URL"))

    def get_league(self, leagueId):
        with self.db.begin() as conn:
            league = conn.execute(
                text('SELECT * FROM "League" WHERE id = :leagueId'),
                {"leagueId": leagueId}
            ).fetchone()

        return dict(league._mapping)

    def create_league(self, league: Dict[str, Any]) -> Dict[str, Any]:
        # Make a copy so we don't mutate the original dict
        league = dict(league)

        print(league)

        # JSON-encode the settings dict so Postgres can cast it to jsonb
        if isinstance(league.get("settings"), (dict, list)):
            league["settings"] = json.dumps(league["settings"])

        sql = text("""
            WITH created AS (
            INSERT INTO "League"
                ("name", sport, "numPlayers", status, settings, "updatedAt", "draftDate", "commissioner", "seasonYear", "isDiscoverable")
            VALUES
                (:name, :sport, :numPlayers, :status, cast(:settings as jsonb), now(), :draftDate, :commissioner, :seasonYear, :isDiscoverable)
            RETURNING
                id, "createdAt", name, sport, "numPlayers", status, settings, "updatedAt", "draftDate", commissioner, "seasonYear", "isDiscoverable"
            )
            SELECT
            c.*,
            to_jsonb(s.*) AS sportInfo
            FROM created c
            JOIN "Sport" s ON s.id = c.sport;
        """)

        with self.db.begin() as conn:
            created_row = conn.execute(sql, league).mappings().first()

            if not created_row:
                raise RuntimeError("Failed to create League")

            created = dict(created_row)

            # Create LeagueMember for commissioner
            lm_sql = text("""
                INSERT INTO "LeagueMember"
                    ("leagueId", "userId", "teamName", "seasonPoints", "draftOrder")
                VALUES
                    (:leagueId, :userId, :teamName, 0, 1)
                RETURNING id
            """)

            lm_row = conn.execute(
                lm_sql,
                {
                    "leagueId": created["id"],
                    "userId": created["commissioner"],
                    "teamName": "My Team",
                },
            ).fetchone()

            created["creatorMemberId"] = lm_row._mapping["id"]

        self.scheduleModel.ensure_weeks_for_league(created['id'])

        return created
    
    def update_league(self, league_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
        """
        Partially updates a League row.

        - Only updates fields present in `patch`.
        - JSON-encodes settings if dict/list.
        - Always updates "updatedAt" = now().
        """

        # 1) Fetch current league (and optionally enforce commissioner)
        with self.db.begin() as conn:
            league_row = conn.execute(
                text("""
                    SELECT id
                    FROM "League"
                    WHERE id = :leagueId
                """),
                {"leagueId": league_id},
            ).fetchone()

        if not league_row:
            raise ValueError(f"League {league_id} not found")

        # 2) Allowlist fields you actually want to update
        allowed_fields = {
            "name",
            "numPlayers",
            "status",
            "settings",
            "draftDate",
            "tradeDeadline",
            "freeAgentDeadline"
        }

        update_data: Dict[str, Any] = {"leagueId": league_id}
        set_clauses = []

        for key, value in patch.items():
            if key not in allowed_fields:
                continue  # silently ignore unknown fields (or raise)

            if key == "settings" and isinstance(value, (dict, list)):
                value = json.dumps(value)

            update_data[key] = value

            if key == "settings":
                set_clauses.append('settings = cast(:settings as jsonb)')
            else:
                # quote any mixed-case columns
                if key in {"numPlayers", "draftDate", "tradeDeadline", "freeAgentDeadline"}:
                    set_clauses.append(f'"{key}" = :{key}')
                else:
                    set_clauses.append(f'{key} = :{key}')

        # Always update updatedAt
        set_clauses.append('"updatedAt" = now()')

        if len(set_clauses) == 1:
            # Only updatedAt, nothing meaningful to update
            # You can choose to return the current league instead.
            raise ValueError("No valid fields to update")

        sql = text(f"""
            WITH updated AS (
            UPDATE "League"
            SET {", ".join(set_clauses)}
            WHERE id = :leagueId
            RETURNING
                id, "createdAt", name, sport, "numPlayers", status, settings, "updatedAt",
                "draftDate", "freeAgentDeadline", "tradeDeadline", commissioner
            )
            SELECT
            u.*,
            to_jsonb(s.*) AS sportInfo
            FROM updated u
            JOIN "Sport" s ON s.id = u.sport;
        """)

        with self.db.begin() as conn:
            updated_row = conn.execute(sql, update_data).mappings().first()

        if not updated_row:
            raise RuntimeError("Failed to update League")

        return dict(updated_row)

    
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
            l."settings"        AS "settings",

            -- Commissioner info
            cu."displayName"    AS "commissionerDisplayName",
            cu."id"             AS "commissionerId",

            -- Sport info
            s.name              AS "sport",
            s."maxPlayersToHaveMaxRounds" AS "maxPlayersToHaveMaxRounds",

            -- Member-specific fields for this user
            lm.id               AS "memberId",
            lm."teamName"       AS "teamName",
            lm."draftOrder"     AS "draftOrder",
            COALESCE(sp."seasonPoints", lm."seasonPoints", 0) AS "seasonPoints",

            -- Current week info (nullable if no matching week)
            w.id                AS "currentWeekId",
            w."weekNumber"      AS "currentWeekNumber",
            w."startDate"       AS "currentWeekStartDate",
            w."endDate"         AS "currentWeekEndDate"

            FROM "LeagueMember" lm
            JOIN "League"      l  ON l.id = lm."leagueId"
            JOIN "Sport"       s  ON s.id = l."sport"
            JOIN "User"        cu ON cu.id = l.commissioner
            LEFT JOIN (
                SELECT
                    "leagueId",
                    "memberId",
                    SUM("pointsAwarded") AS "seasonPoints"
                FROM "WeeklyTeamScore"
                GROUP BY "leagueId", "memberId"
            ) sp
            ON sp."leagueId" = lm."leagueId"
            AND sp."memberId" = lm.id

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
              lm."seasonPoints"   AS "seasonPoints",
              u."displayName"     AS "displayName"
            FROM "LeagueMember" lm
            JOIN "User" u on u.id = lm."userId"
            WHERE lm."leagueId" = :league_id
            ORDER BY lm."draftOrder", lm.id
            """
        )

        current_week_sql = text("""
            SELECT w."weekNumber"
            FROM "Week" w
            WHERE w."leagueId" = :league_id
              AND now() >= w."startDate"
              AND now() <= w."endDate"
            ORDER BY w."weekNumber" DESC
            LIMIT 1
        """)

        with self.db.connect() as conn:
            result = conn.execute(sql, {"league_id": league_id})
            rows = [dict(r._mapping) for r in result]
            current_week_row = conn.execute(
                current_week_sql,
                {"league_id": league_id},
            ).fetchone()

        current_week_number = None
        if current_week_row:
            current_week_number = int(current_week_row[0])

        members: List[Dict[str, Any]] = []
        for r in rows:
            member_id = r["memberId"]
            current_week_point_differential = 0
            if current_week_number is not None:
                games = self.scheduleModel.get_member_games_for_week(
                    league_id=league_id,
                    member_id=member_id,
                    week_number=current_week_number,
                )
                for g in games:
                    current_week_point_differential += int(g["memberPointDiff"])

            members.append(
                {
                    "id": r["memberId"],
                    "createdAt": r["memberCreatedAt"],
                    "leagueId": r["leagueId"],
                    "userId": r["userId"],
                    "teamName": r["teamName"],
                    "draftOrder": r["draftOrder"],
                    "seasonPoints": r["seasonPoints"],
                    "displayName": r['displayName'],
                    "currentWeekPointDifferential": current_week_point_differential,
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
    
    def _get_league_commissioner(self, league_id: int) -> Optional[int]:
        with self.db.begin() as conn:
            row = conn.execute(
                text('SELECT commissioner FROM "League" WHERE id = :leagueId'),
                {"leagueId": league_id},
            ).fetchone()
        return row._mapping["commissioner"] if row else None

    def _ensure_commissioner(self, league_id: int, acting_user_id: int) -> None:
        commissioner = self._get_league_commissioner(league_id)
        if commissioner is None:
            raise ValueError(f"League {league_id} not found")
        if commissioner != acting_user_id:
            raise PermissionError("Only the commissioner can perform this action")
        

    def create_join_request(self, league_id: int, user_id: int, message: Optional[str] = None) -> Dict[str, Any]:
        with self.db.begin() as conn:
            # Already a member?
            member = conn.execute(
                text("""
                    SELECT 1
                    FROM "LeagueMember"
                    WHERE "leagueId" = :leagueId AND "userId" = :userId
                """),
                {"leagueId": league_id, "userId": user_id},
            ).fetchone()
            if member:
                raise ValueError("Already a member of this league")

            # If a pending request exists, return it (idempotent UX)
            existing = conn.execute(
                text("""
                    SELECT id, "createdAt", "leagueId", "userId", status, "message",
                           "resolvedAt", "resolvedByUserId"
                    FROM "LeagueJoinRequest"
                    WHERE "leagueId" = :leagueId AND "userId" = :userId AND status = 'PENDING'
                """),
                {"leagueId": league_id, "userId": user_id},
            ).mappings().first()

            if existing:
                return dict(existing)

            row = conn.execute(
                text("""
                    INSERT INTO "LeagueJoinRequest"
                        ("leagueId", "userId", status, "message")
                    VALUES
                        (:leagueId, :userId, 'PENDING', :message)
                    RETURNING
                        id, "createdAt", "leagueId", "userId", status, "message",
                        "resolvedAt", "resolvedByUserId"
                """),
                {"leagueId": league_id, "userId": user_id, "message": message},
            ).mappings().first()

            if not row:
                raise RuntimeError("Failed to create join request")

            return dict(row)

    def list_join_requests(self, league_id: int, status: Optional[str] = None) -> list[Dict[str, Any]]:
        params: Dict[str, Any] = {"leagueId": league_id}
        where_status = ""
        if status:
            where_status = "AND r.status = :status"
            params["status"] = status

        with self.db.begin() as conn:
            rows = conn.execute(
                text(f"""
                    SELECT
                      r.id, r."createdAt", r."leagueId", r."userId",
                      r.status, r."message", r."resolvedAt", r."resolvedByUserId",
                      u.email AS "userEmail",
                      u."displayName" AS "userDisplayName"
                    FROM "LeagueJoinRequest" r
                    JOIN "User" u ON u.id = r."userId"
                    WHERE r."leagueId" = :leagueId
                    {where_status}
                    ORDER BY r."createdAt" DESC
                """),
                params,
            ).mappings().all()

        return [dict(r) for r in rows]

    def approve_join_request(self, league_id: int, request_id: int, acting_user_id: int) -> Dict[str, Any]:
        with self.db.begin() as conn:
            # lock the request row to prevent double-approval races
            req = conn.execute(
                text("""
                    SELECT id, "leagueId", "userId", status
                    FROM "LeagueJoinRequest"
                    WHERE id = :requestId AND "leagueId" = :leagueId
                    FOR UPDATE
                """),
                {"requestId": request_id, "leagueId": league_id},
            ).mappings().first()

            if not req:
                raise ValueError("Join request not found")
            if req["status"] != "PENDING":
                raise ValueError("Join request is not pending")

            # create membership (unique index should prevent duplicates)
            conn.execute(
                text("""
                    INSERT INTO "LeagueMember"
                        ("leagueId", "userId", "teamName", "draftOrder", "seasonPoints")
                    SELECT
                        :leagueId,
                        :userId,
                        'My Team',
                        COALESCE(MAX(lm."draftOrder"), 0) + 1,
                        0
                    FROM "LeagueMember" lm
                    WHERE lm."leagueId" = :leagueId
                """),
                {
                    "leagueId": league_id,
                    "userId": req["userId"],
                },
            )

            conn.execute(
                text("""
                    WITH locked_league AS (
                        SELECT l.id,
                            l."sport",
                            l."numPlayers" AS cur_players,
                            l.settings AS cur_settings
                        FROM "League" l
                        WHERE l.id = :leagueId
                        FOR UPDATE
                    ),
                    sport_cfg AS (
                        SELECT s.id,
                            s."maxDraftRounds" AS max_rounds,
                            s."maxPlayersToHaveMaxRounds" AS max_players_full
                        FROM "Sport" s
                        JOIN locked_league ll ON ll."sport" = s.id
                    ),
                    computed AS (
                        SELECT
                            ll.id AS league_id,
                            (ll.cur_players + 1) AS new_players,
                            GREATEST(
                                1,
                                CASE
                                    WHEN (ll.cur_players + 1) <= sc.max_players_full
                                        THEN sc.max_rounds
                                    ELSE sc.max_rounds - ((ll.cur_players + 1) - sc.max_players_full)
                                END
                            ) AS new_num_rounds
                        FROM locked_league ll
                        JOIN sport_cfg sc ON true
                    )
                    UPDATE "League" l
                    SET
                        "numPlayers" = c.new_players,
                        settings = jsonb_set(
                            COALESCE(l.settings, '{}'::jsonb),
                            '{draft,numberOfRounds}',
                            to_jsonb(c.new_num_rounds),
                            true
                        ),
                        "updatedAt" = now()
                    FROM computed c
                    WHERE l.id = c.league_id
                    RETURNING l.id, l."numPlayers", l.settings
                """),
                {"leagueId": league_id},
            ).mappings().first()

            updated = conn.execute(
                text("""
                    UPDATE "LeagueJoinRequest"
                    SET status = 'APPROVED',
                        "resolvedAt" = now(),
                        "resolvedByUserId" = :actingUserId
                    WHERE id = :requestId
                    RETURNING
                        id, "createdAt", "leagueId", "userId", status, "message",
                        "resolvedAt", "resolvedByUserId"
                """),
                {"requestId": request_id, "actingUserId": acting_user_id},
            ).mappings().first()

            # Return the new member too (handy for UI)
            member = conn.execute(
                text("""
                    SELECT id, "leagueId", "userId", "teamName", "seasonPoints", "createdAt"
                    FROM "LeagueMember"
                    WHERE "leagueId" = :leagueId AND "userId" = :userId
                """),
                {"leagueId": league_id, "userId": req["userId"]},
            ).mappings().first()

        return {"request": dict(updated), "member": dict(member) if member else None}

    def deny_join_request(self, league_id: int, request_id: int, acting_user_id: int) -> Dict[str, Any]:
        with self.db.begin() as conn:
            req = conn.execute(
                text("""
                    SELECT id, status
                    FROM "LeagueJoinRequest"
                    WHERE id = :requestId AND "leagueId" = :leagueId
                    FOR UPDATE
                """),
                {"requestId": request_id, "leagueId": league_id},
            ).mappings().first()

            if not req:
                raise ValueError("Join request not found")
            if req["status"] != "pending":
                raise ValueError("Join request is not pending")

            updated = conn.execute(
                text("""
                    UPDATE "LeagueJoinRequest"
                    SET status = 'DENIED',
                        "resolvedAt" = now(),
                        "resolvedByUserId" = :actingUserId,
                    WHERE id = :requestId
                    RETURNING
                        id, "createdAt", "leagueId", "userId", status, "message",
                        "resolvedAt", "resolvedByUserId"
                """),
                {"requestId": request_id, "actingUserId": acting_user_id},
            ).mappings().first()

        return dict(updated)

    def cancel_join_request(self, league_id: int, request_id: int, user_id: int) -> Dict[str, Any]:
        with self.db.begin() as conn:
            req = conn.execute(
                text("""
                    SELECT id, status, "userId"
                    FROM "LeagueJoinRequest"
                    WHERE id = :requestId AND "leagueId" = :leagueId
                    FOR UPDATE
                """),
                {"requestId": request_id, "leagueId": league_id},
            ).mappings().first()

            if not req:
                raise ValueError("Join request not found")
            if req["userId"] != user_id:
                raise PermissionError("Cannot cancel another user's request")
            if req["status"] != "pending":
                raise ValueError("Only pending requests can be cancelled")

            updated = conn.execute(
                text("""
                    UPDATE "LeagueJoinRequest"
                    SET status = 'CANCELLED',
                        "resolvedAt" = now()
                    WHERE id = :requestId
                    RETURNING
                        id, "createdAt", "leagueId", "userId", status, "message",
                        "resolvedAt", "resolvedByUserId"
                """),
                {"requestId": request_id},
            ).mappings().first()

        return dict(updated)
    
    def remove_member_and_shift_draft_order(
        self,
        league_id: int,
        member_id: int,
        acting_user_id: int,
        shift_draft_order: bool = True,
    ) -> Dict[str, Any]:
        """
        Removes a LeagueMember and (optionally) shifts down draftOrder
        for all members behind them so orders remain contiguous.

        This is transactional: if anything fails, nothing is committed.
        """

        with self.db.begin() as conn:
            # Lock league row to avoid concurrent join/removal races
            league = conn.execute(
                text("""
                    SELECT id, status, "commissioner", "numPlayers"
                    FROM "League"
                    WHERE id = :leagueId
                    FOR UPDATE
                """),
                {"leagueId": league_id},
            ).mappings().first()

            if not league:
                raise ValueError("League not found")

            # Basic permission (adjust to your rules)
            if int(league["commissioner"]) != int(acting_user_id):
                raise ValueError("Only the commissioner can remove members")

            # Find member + their draft order (lock the member row)
            member = conn.execute(
                text("""
                    SELECT id, "userId", "draftOrder"
                    FROM "LeagueMember"
                    WHERE id = :memberId AND "leagueId" = :leagueId
                    FOR UPDATE
                """),
                {"memberId": member_id, "leagueId": league_id},
            ).mappings().first()

            if not member:
                raise ValueError("Member not found in this league")

            # (Optional) prevent removing commissioner
            if int(member["userId"]) == int(league["commissioner"]):
                raise ValueError("Cannot remove the commissioner")

            removed_order = int(member["draftOrder"])

            # Delete the member
            conn.execute(
                text("""
                    DELETE FROM "LeagueMember"
                    WHERE id = :memberId AND "leagueId" = :leagueId
                """),
                {"memberId": member_id, "leagueId": league_id},
            )

            # Shift draft order (only if you want this behavior)
            if shift_draft_order:
                conn.execute(
                    text("""
                        UPDATE "LeagueMember"
                        SET "draftOrder" = "draftOrder" - 1
                        WHERE "leagueId" = :leagueId
                          AND "draftOrder" > :removedOrder
                    """),
                    {"leagueId": league_id, "removedOrder": removed_order},
                )

            # Keep numPlayers in sync
            conn.execute(
                text("""
                    UPDATE "League"
                    SET "numPlayers" = GREATEST("numPlayers" - 1, 0),
                        "updatedAt" = now()
                    WHERE id = :leagueId
                """),
                {"leagueId": league_id},
            )

            # Return updated member list (handy for UI)
            members = conn.execute(
                text("""
                    SELECT
                      lm.id AS "memberId",
                      lm."userId" AS "userId",
                      lm."teamName" AS "teamName",
                      lm."draftOrder" AS "draftOrder",
                      u."displayName" AS "displayName"
                    FROM "LeagueMember" lm
                    JOIN "User" u ON u.id = lm."userId"
                    WHERE lm."leagueId" = :leagueId
                    ORDER BY lm."draftOrder", lm.id
                """),
                {"leagueId": league_id},
            ).mappings().all()

        return {
            "removedMemberId": member_id,
            "removedDraftOrder": removed_order,
            "members": [dict(m) for m in members],
        }
    
    def search_leagues(
        self,
        q: str,
        sport_id: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ):
        q = (q or "").strip()
        if len(q) < 2:
            return []

        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))

        pattern = f"%{q}%"

        params = {
            "pattern": pattern,
            "q": q,
            "limit": limit,
            "offset": offset,
        }

        sport_clause = ""
        if sport_id is not None:
            sport_clause = "AND l.sport = :sportId"
            params["sportId"] = sport_id

        sql = text(f"""
            SELECT
            l.id,
            l.name,
            l.sport,
            l."numPlayers",
            l.status,
            l."draftDate",
            l."isDiscoverable",
            l.commissioner,
            u.email AS "commissionerEmail",
            u."displayName" AS "commissionerDisplayName"
            FROM "League" l
            JOIN "User" u ON u.id = l.commissioner
            WHERE l."isDiscoverable" = true
            AND l.name ILIKE :pattern
            {sport_clause}
            ORDER BY similarity(l.name, :q) DESC, l.name ASC
            LIMIT :limit OFFSET :offset
        """)

        with self.db.begin() as conn:
            rows = conn.execute(sql, params).mappings().all()

        return [dict(r) for r in rows]

    def delete_league(self, league_id: int, acting_user_id: int) -> Dict[str, Any]:
        """
        Deletes a league and all dependent data (via ON DELETE CASCADE).

        Only the commissioner is allowed to delete a league.
        This operation is atomic.
        """

        with self.db.begin() as conn:
            # Lock league row
            league = conn.execute(
                text("""
                    SELECT id, name, commissioner
                    FROM "League"
                    WHERE id = :leagueId
                    FOR UPDATE
                """),
                {"leagueId": league_id},
            ).mappings().first()

            if not league:
                raise ValueError("League not found")

            if int(league["commissioner"]) != int(acting_user_id):
                raise ValueError("Only the commissioner can delete this league")

            # Delete league (cascades to members, join requests, weeks, etc.)
            deleted = conn.execute(
                text("""
                    DELETE FROM "League"
                    WHERE id = :leagueId
                    RETURNING id, name
                """),
                {"leagueId": league_id},
            ).mappings().first()

            if not deleted:
                raise RuntimeError("Failed to delete league")

        return {
            "deletedLeagueId": deleted["id"],
            "deletedLeagueName": deleted["name"],
        }
    
    def update_league_member(self, member_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        # keep only allowed keys that are actually present
        payload = {k: updates[k] for k in updates.keys() if k in ALLOWED_LEAGUE_MEMBER_FIELDS}

        if not payload:
            raise ValueError("No valid fields provided to update")

        set_clauses = []
        params: Dict[str, Any] = {"memberId": member_id}

        for i, (key, val) in enumerate(payload.items()):
            param_name = f"v{i}"
            set_clauses.append(f'{ALLOWED_LEAGUE_MEMBER_FIELDS[key]} = :{param_name}')
            params[param_name] = val

        sql = text(f"""
            UPDATE "LeagueMember"
            SET {", ".join(set_clauses)}
            WHERE id = :memberId
            RETURNING id, "leagueId", "userId", "teamName", "draftOrder", "seasonPoints", "createdAt"
        """)

        with self.db.begin() as conn:
            row = conn.execute(sql, params).mappings().first()

        if not row:
            raise ValueError("LeagueMember not found")

        return dict(row)
