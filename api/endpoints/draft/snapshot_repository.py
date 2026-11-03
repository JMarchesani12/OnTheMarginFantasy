"""Draft snapshot SQL; caller supplies every connection and transaction."""
from sqlalchemy import text


class DraftSnapshotRepository:
    def snapshot_league(self, conn, league_id, reader_user_id=None):
        scope = ''
        params = {'leagueId': league_id}
        if reader_user_id is not None:
            scope = '''AND EXISTS (
                SELECT 1 FROM "LeagueMember" reader_member
                WHERE reader_member."leagueId" = :leagueId
                  AND reader_member."userId" = :readerUserId
            )'''
            params['readerUserId'] = reader_user_id
        row = conn.execute(text(f'SELECT id, "numPlayers", settings FROM "League" WHERE id = :leagueId {scope}'), params).fetchone()
        return dict(row._mapping) if row else None

    def snapshot_state(self, conn, league_id):
        row = conn.execute(text("""
                    SELECT "leagueId", status, "currentOverallPickNumber", "currentMemberId", "expiresAt", "lastPickAt", "updatedAt"
                    FROM "DraftState"
                    WHERE "leagueId" = :leagueId
                """), {'leagueId': league_id}).mappings().fetchone()
        return (dict(row._mapping) if hasattr(row, "_mapping") else dict(row)) if row else None

    def snapshot_members(self, conn, league_id):
        rows = conn.execute(text("""
                    SELECT id AS "memberId", "userId", "teamName", "draftOrder"
                    FROM "LeagueMember"
                    WHERE "leagueId" = :leagueId
                    ORDER BY "draftOrder", id
                """), {'leagueId': league_id}).mappings().all()
        return [dict(row) for row in rows]

    def snapshot_picks(self, conn, league_id):
        rows = conn.execute(text("""
                    WITH league_info AS (
                      SELECT "seasonYear"
                      FROM "League"
                      WHERE id = :leagueId
                    )
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
                    CROSS JOIN league_info li
                    JOIN "LeagueMember" lm ON lm.id = dp."memberId"
                    JOIN "SportTeam" st ON st.id = dp."sportTeamId"
                    LEFT JOIN "ConferenceMembership" cm
                      ON cm."sportTeamId" = st.id
                     AND cm."sportId" = st."sportId"
                     AND (cm."seasonYear" IS NULL OR cm."seasonYear" = li."seasonYear")
                    LEFT JOIN "SportConference" sc
                      ON sc.id = cm."sportConferenceId"
                     AND sc."sportId" = st."sportId"
                    LEFT JOIN "Conference" conf
                      ON conf.id = sc."conferenceId"
                    WHERE dp."leagueId" = :leagueId
                    ORDER BY dp."overallPickNumber"
                """), {'leagueId': league_id}).mappings().all()
        return [dict(row) for row in rows]

    def repair_completed(self, conn, league_id):
        row = conn.execute(text("""
                UPDATE "DraftState"
                SET "currentMemberId" = NULL,
                    "expiresAt" = NULL,
                    "updatedAt" = now()
                WHERE "leagueId" = :leagueId
                  AND status = 'complete'
                RETURNING "leagueId", status, "currentOverallPickNumber",
                          "currentMemberId", "expiresAt", "lastPickAt", "updatedAt"
            """), {'leagueId': league_id}).mappings().fetchone()
        return (dict(row._mapping) if hasattr(row, "_mapping") else dict(row)) if row else None

    def next_unpicked_turn(self, conn, league_id, start_overall):
        row = conn.execute(text("""
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
            """), {'leagueId': league_id , 'startOverall': start_overall}).fetchone()
        return (int(row._mapping["overall"]), int(row._mapping["memberId"])) if row else None
