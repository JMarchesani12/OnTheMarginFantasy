"""Global lifecycle update SQL; caller supplies the transaction connection."""
from sqlalchemy import text


class LeagueLifecycleRepository:
    def mark_pre_draft(self, conn):
        conn.execute(text("""
                    UPDATE "League" l
                    SET status = 'Pre-Draft',
                        "updatedAt" = now()
                    WHERE l."draftDate" IS NOT NULL
                      AND now() < l."draftDate"
                      AND l.status <> 'Pre-Draft'
                      AND NOT EXISTS (
                        SELECT 1
                        FROM "DraftState" ds
                        WHERE ds."leagueId" = l.id
                          AND ds.status IN ('live', 'paused', 'complete')
                      )
                """))

    def mark_drafting(self, conn):
        conn.execute(text("""
                    UPDATE "League" l
                    SET status = 'Drafting',
                        "updatedAt" = now()
                    FROM "DraftState" ds
                    WHERE ds."leagueId" = l.id
                      AND ds.status IN ('live', 'paused')
                      AND l.status <> 'Drafting'
                """))

    def mark_post_draft(self, conn):
        conn.execute(text("""
                    UPDATE "League" l
                    SET status = 'Post-Draft',
                        "updatedAt" = now()
                    FROM "DraftState" ds, "SportSeason" ss
                    WHERE ds."leagueId" = l.id
                      AND ss."sportId" = l.sport
                      AND ss."seasonYear" = l."seasonYear"
                      AND ds.status = 'complete'
                      AND now()::date < ss."seasonStart"::date
                      AND l.status <> 'Post-Draft'
                """))

    def mark_in_season(self, conn):
        conn.execute(text("""
                    UPDATE "League" l
                    SET status = 'In-Season',
                        "updatedAt" = now()
                    FROM "SportSeason" ss
                    WHERE ss."sportId" = l.sport
                      AND ss."seasonYear" = l."seasonYear"
                      AND now()::date >= ss."seasonStart"::date
                      AND now()::date <= ss."seasonEnd"::date
                      AND l.status NOT IN ('Drafting', 'In-Season', 'Completed')
                      AND NOT EXISTS (
                        SELECT 1
                        FROM "DraftState" ds
                        WHERE ds."leagueId" = l.id
                          AND ds.status IN ('live', 'paused')
                      )
                """))

    def mark_completed(self, conn):
        conn.execute(text("""
                    UPDATE "League" l
                    SET status = 'Completed',
                        "updatedAt" = now()
                    FROM "SportSeason" ss
                    WHERE ss."sportId" = l.sport
                      AND ss."seasonYear" = l."seasonYear"
                      AND now()::date > ss."seasonEnd"::date
                      AND l.status <> 'Completed'
                """))
