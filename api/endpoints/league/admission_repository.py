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
