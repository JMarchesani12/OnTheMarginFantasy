"""Member update SQL; callers supply connection and transaction."""
from sqlalchemy import text

ALLOWED_LEAGUE_MEMBER_FIELDS = {
    "teamName": '"teamName"',
    "draftOrder": '"draftOrder"',
    "seasonPoints": '"seasonPoints"',
}


class MemberRepository:
    def rename_owned(self, conn, member_id, user_id, team_name):
        row = conn.execute(text("""
                UPDATE "LeagueMember"
                SET "teamName" = :teamName
                WHERE id = :memberId AND "userId" = :userId
                RETURNING id, "leagueId", "userId", "teamName", "draftOrder",
                          "seasonPoints", "createdAt"
            """), {
            'memberId': member_id, 'userId': user_id, 'teamName': team_name,
        }).mappings().first()
        return dict(row) if row else None

    def update_member(self, conn, member_id, payload):
        set_clauses = []
        params = {'memberId': member_id}
        for i, (key, val) in enumerate(payload.items()):
            param_name = f'v{i}'
            set_clauses.append(f'{ALLOWED_LEAGUE_MEMBER_FIELDS[key]} = :{param_name}')
            params[param_name] = val
        row = conn.execute(text(f"""
            UPDATE "LeagueMember"
            SET {", ".join(set_clauses)}
            WHERE id = :memberId
            RETURNING id, "leagueId", "userId", "teamName", "draftOrder", "seasonPoints", "createdAt"
        """), params).mappings().first()
        return dict(row) if row else None

    def lock_league_for_removal(self, conn, league_id):
        row = conn.execute(text("""
                    SELECT id, status, "commissioner", "numPlayers"
                    FROM "League"
                    WHERE id = :leagueId
                    FOR UPDATE
                """), {'leagueId': league_id}).mappings().first()
        return dict(row) if row else None

    def lock_member_for_removal(self, conn, league_id, member_id):
        row = conn.execute(text("""
                    SELECT id, "userId", "draftOrder"
                    FROM "LeagueMember"
                    WHERE id = :memberId AND "leagueId" = :leagueId
                    FOR UPDATE
                """), {'memberId': member_id, 'leagueId': league_id}).mappings().first()
        return dict(row) if row else None

    def delete_member(self, conn, league_id, member_id):
        conn.execute(text("""
                    DELETE FROM "LeagueMember"
                    WHERE id = :memberId AND "leagueId" = :leagueId
                """), {'memberId': member_id, 'leagueId': league_id})

    def shift_after_removal(self, conn, league_id, removed_order):
        conn.execute(text("""
                        UPDATE "LeagueMember"
                        SET "draftOrder" = "draftOrder" - 1
                        WHERE "leagueId" = :leagueId
                          AND "draftOrder" > :removedOrder
                    """), {'leagueId': league_id, 'removedOrder': removed_order})

    def decrement_count(self, conn, league_id):
        conn.execute(text("""
                    UPDATE "League"
                    SET "numPlayers" = GREATEST("numPlayers" - 1, 0),
                        "updatedAt" = now()
                    WHERE id = :leagueId
                """), {'leagueId': league_id})

    def remaining_members(self, conn, league_id):
        rows = conn.execute(text("""
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
                """), {'leagueId': league_id}).mappings().all()
        return [dict(row) for row in rows]
