"""Draft control persistence; caller supplies transaction connection."""
from sqlalchemy import text


class DraftControlRepository:
    def commissioner(self, conn, league_id):
        row = conn.execute(text("""SELECT commissioner FROM "League" WHERE id = :leagueId"""), {"leagueId": league_id}).fetchone()
        return dict(row._mapping) if row else None

    def finalize_state(self, conn, league_id):
        row = conn.execute(text("""
                    UPDATE "DraftState"
                    SET status = 'complete',
                        "currentMemberId" = NULL,
                        "expiresAt" = NULL,
                        "lastPickAt" = COALESCE("lastPickAt", now()),
                        "updatedAt" = now()
                    WHERE "leagueId" = :leagueId
                    RETURNING "leagueId", status, "currentOverallPickNumber",
                              "currentMemberId", "expiresAt", "lastPickAt", "updatedAt"
                """), {"leagueId": league_id}).fetchone()
        return dict(row._mapping) if row else None

    def finalize_league(self, conn, league_id):
        row = conn.execute(text("""
                    UPDATE "League" l
                    SET status = CASE
                            WHEN ss."seasonEnd"::date < now()::date THEN 'Completed'
                            WHEN ss."seasonStart"::date <= now()::date THEN 'In-Season'
                            ELSE 'Post-Draft'
                        END,
                        "updatedAt" = now()
                    FROM "SportSeason" ss
                    WHERE l.id = :leagueId
                      AND ss."sportId" = l.sport
                      AND ss."seasonYear" = l."seasonYear"
                    RETURNING l.id AS "leagueId", l.status AS "leagueStatus"
                """), {"leagueId": league_id}).fetchone()
        return dict(row._mapping) if row else None

    def settings_row(self, conn, league_id):
        row = conn.execute(text("""SELECT settings, "numPlayers" FROM "League" WHERE id = :leagueId"""), {'leagueId': league_id}).fetchone()
        return dict(row._mapping) if row else None

    def missing_orders(self, conn, league_id, num_players):
        rows = conn.execute(text("""
                    SELECT gs AS "missingOrder"
                    FROM generate_series(1, :numPlayers) gs
                    LEFT JOIN "LeagueMember" lm
                      ON lm."leagueId" = :leagueId AND lm."draftOrder" = gs
                    WHERE lm.id IS NULL
                    ORDER BY gs
                """), {'leagueId': league_id, 'numPlayers': num_players}).mappings().all()
        return [dict(row) for row in rows]

    def seed_members(self, conn, league_id):
        rows = conn.execute(text("""
                SELECT id AS "memberId", "draftOrder"
                FROM "LeagueMember"
                WHERE "leagueId" = :leagueId
                ORDER BY "draftOrder" ASC
            """), {'leagueId': league_id}).fetchall()
        return [dict(row._mapping) for row in rows]

    def insert_turns(self, conn, rows):
        conn.execute(text("""
                INSERT INTO "DraftTurn" ("leagueId","overallPickNumber","memberId")
                VALUES (:leagueId, :overallPickNumber, :memberId)
                ON CONFLICT ("leagueId","overallPickNumber") DO NOTHING
                """), rows)

    def expected_member(self, conn, league_id, overall):
        row = conn.execute(text("""
                SELECT "memberId"
                FROM "DraftTurn"
                WHERE "leagueId" = :leagueId
                AND "overallPickNumber" = :overall
            """), {'leagueId': league_id, 'overall': overall}).fetchone()
        return int(row._mapping["memberId"]) if row else None

    def start_state(self, conn, league_id, first_member_id, selection_time):
        conn.execute(text("""
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
                """), {'leagueId': league_id, 'currentMemberId': first_member_id, 'selectionTime': selection_time})

    def mark_drafting(self, conn, league_id):
        conn.execute(text("""
                    UPDATE "League"
                    SET status = 'Drafting',
                        "updatedAt" = now()
                    WHERE id = :leagueId
                """), {'leagueId': league_id})

    def lock_state(self, conn, league_id):
        row = conn.execute(text("""
                    SELECT status FROM "DraftState"
                    WHERE "leagueId" = :leagueId
                    FOR UPDATE
                """), {'leagueId': league_id}).fetchone()
        return dict(row._mapping) if row else None

    def pause_state(self, conn, league_id):
        conn.execute(text("""
                    UPDATE "DraftState"
                    SET status = 'paused',
                        "expiresAt" = NULL,
                        "updatedAt" = now()
                    WHERE "leagueId" = :leagueId
                """), {'leagueId': league_id})

    def resume_state(self, conn, league_id, selection_time):
        conn.execute(text("""
                    UPDATE "DraftState"
                    SET status = 'live',
                        "expiresAt" = now() + (:selectionTime || ' seconds')::interval,
                        "updatedAt" = now()
                    WHERE "leagueId" = :leagueId
                """), {'leagueId': league_id, 'selectionTime': selection_time})
