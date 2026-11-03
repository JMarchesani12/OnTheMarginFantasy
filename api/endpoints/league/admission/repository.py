"""Admission persistence; caller supplies every connection and transaction."""
from typing import Any, Dict, Optional
from sqlalchemy import text


class AdmissionRepository:
    def commissioner(self, conn, league_id):
        row = conn.execute(text('SELECT commissioner FROM "League" WHERE id = :leagueId'),
                           {'leagueId': league_id}).fetchone()
        return row._mapping['commissioner'] if row else None

    def list_requests(
        self, conn, league_id: int, status: Optional[str], commissioner_id: int | None = None,
    ) -> list[Dict[str, Any]]:
        params: Dict[str, Any] = {"leagueId": league_id}
        where_status = ""
        if status:
            where_status = "AND r.status = :status"
            params["status"] = status

        ownership_clause = ''
        if commissioner_id is not None:
            params['actingUserId'] = commissioner_id
            ownership_clause = '''AND EXISTS (
                SELECT 1 FROM "League" l
                WHERE l.id = r."leagueId" AND l.commissioner = :actingUserId
            )'''

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
                {ownership_clause}
                ORDER BY r."createdAt" DESC
            """),
            params,
        ).mappings().all()

        return [dict(r) for r in rows]

    def lock_request(self, conn, league_id, request_id):
        req = conn.execute(
            text("""
                SELECT id, status, "userId"
                FROM "LeagueJoinRequest"
                WHERE id = :requestId AND "leagueId" = :leagueId
                FOR UPDATE
            """),
            {"requestId": request_id, "leagueId": league_id},
        ).mappings().first()
        return dict(req) if req else None

    def cancel_pending(self, conn, league_id, request_id, user_id):
        updated = conn.execute(
            text("""
                UPDATE "LeagueJoinRequest"
                SET status = 'CANCELLED',
                    "resolvedAt" = now()
                WHERE id = :requestId AND "leagueId" = :leagueId
                  AND "userId" = :userId AND status = 'PENDING'
                RETURNING
                    id, "createdAt", "leagueId", "userId", status, "message",
                    "resolvedAt", "resolvedByUserId"
            """),
            {"requestId": request_id, "leagueId": league_id, "userId": user_id},
        ).mappings().first()
        return dict(updated) if updated else None

    def is_member(self, conn, league_id, user_id):
        member = conn.execute(
            text("""
                SELECT 1
                FROM "LeagueMember"
                WHERE "leagueId" = :leagueId AND "userId" = :userId
            """),
            {"leagueId": league_id, "userId": user_id},
        ).fetchone()
        return member is not None

    def pending_request(self, conn, league_id, user_id):
        existing = conn.execute(
            text("""
                SELECT id, "createdAt", "leagueId", "userId", status, "message",
                       "resolvedAt", "resolvedByUserId"
                FROM "LeagueJoinRequest"
                WHERE "leagueId" = :leagueId AND "userId" = :userId AND status = 'PENDING'
            """),
            {"leagueId": league_id, "userId": user_id},
        ).mappings().first()
        return dict(existing) if existing else None

    def insert_request(self, conn, league_id, user_id, message, team_name):
        row = conn.execute(
            text("""
                INSERT INTO "LeagueJoinRequest"
                    ("leagueId", "userId", status, "message", "teamName")
                VALUES
                    (:leagueId, :userId, 'PENDING', :message, :teamName)
                RETURNING
                    id, "createdAt", "leagueId", "userId", status, "message",
                    "resolvedAt", "resolvedByUserId"
            """),
            {"leagueId": league_id, "userId": user_id, "message": message, "teamName": team_name},
        ).mappings().first()
        return dict(row) if row else None

    def lock_league(self, conn, league_id):
        league = conn.execute(text('''
            SELECT commissioner FROM "League" WHERE id = :leagueId FOR UPDATE
        '''), {'leagueId': league_id}).mappings().first()
        return dict(league) if league else None

    def lock_league_for_job(self, conn, league_id):
        conn.execute(text('''
            SELECT id FROM "League" WHERE id = :leagueId FOR UPDATE
        '''), {'leagueId': league_id}).fetchone()

    def lock_request_for_denial(self, conn, league_id, request_id):
        req = conn.execute(
            text("""
                SELECT id, status
                FROM "LeagueJoinRequest"
                WHERE id = :requestId AND "leagueId" = :leagueId
                FOR UPDATE
            """),
            {"requestId": request_id, "leagueId": league_id},
        ).mappings().first()
        return dict(req) if req else None

    def deny_pending(self, conn, league_id, request_id, acting_user_id):
        updated = conn.execute(
            text("""
                UPDATE "LeagueJoinRequest"
                SET status = 'DENIED',
                    "resolvedAt" = now(),
                    "resolvedByUserId" = :actingUserId
                WHERE id = :requestId AND "leagueId" = :leagueId AND status = 'PENDING'
                RETURNING
                    id, "createdAt", "leagueId", "userId", status, "message",
                    "resolvedAt", "resolvedByUserId"
            """),
            {"requestId": request_id, "leagueId": league_id, "actingUserId": acting_user_id},
        ).mappings().first()
        return dict(updated) if updated else None

    def lock_request_for_approval(self, conn, league_id, request_id):
        req = conn.execute(
            text("""
                SELECT id, "leagueId", "userId", status, "teamName"
                FROM "LeagueJoinRequest"
                WHERE id = :requestId AND "leagueId" = :leagueId
                FOR UPDATE
            """),
            {"requestId": request_id, "leagueId": league_id},
        ).mappings().first()
        return dict(req) if req else None

    def insert_member(self, conn, league_id, user_id, team_name):
        conn.execute(
            text("""
                INSERT INTO "LeagueMember"
                    ("leagueId", "userId", "teamName", "draftOrder", "seasonPoints")
                SELECT
                    :leagueId,
                    :userId,
                    :teamName,
                    COALESCE(MAX(lm."draftOrder"), 0) + 1,
                    0
                FROM "LeagueMember" lm
                WHERE lm."leagueId" = :leagueId
            """),
            {
                "leagueId": league_id,
                "userId": user_id,
                "teamName": team_name,
            },
        )

    def update_capacity(self, conn, league_id):
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

    def approve_pending(self, conn, league_id, request_id, acting_user_id):
        updated = conn.execute(
            text("""
                UPDATE "LeagueJoinRequest"
                SET status = 'APPROVED',
                    "resolvedAt" = now(),
                    "resolvedByUserId" = :actingUserId
                WHERE id = :requestId AND "leagueId" = :leagueId
                RETURNING
                    id, "createdAt", "leagueId", "userId", status, "message",
                    "resolvedAt", "resolvedByUserId"
            """),
            {"requestId": request_id, "leagueId": league_id, "actingUserId": acting_user_id},
        ).mappings().first()
        return dict(updated) if updated else None

    def member_for_request(self, conn, league_id, user_id):
        member = conn.execute(
            text("""
                SELECT id, "leagueId", "userId", "teamName", "seasonPoints", "createdAt"
                FROM "LeagueMember"
                WHERE "leagueId" = :leagueId AND "userId" = :userId
            """),
            {"leagueId": league_id, "userId": user_id},
        ).mappings().first()
        return dict(member) if member else None
