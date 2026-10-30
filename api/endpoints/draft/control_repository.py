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
