"""Global lifecycle SQL, including main's league-local calendar transitions."""
from sqlalchemy import text

LOCAL_TODAY = """(now() AT TIME ZONE COALESCE(
    NULLIF(l.settings #>> '{schedule,timezone}', ''),
    NULLIF(l.settings #>> '{schedule,timeZone}', ''),
    NULLIF(l.settings ->> 'timezone', ''),
    NULLIF(l.settings ->> 'timeZone', ''), 'UTC'
))::date"""


class LeagueLifecycleRepository:
    def mark_pre_draft(self, conn):
        conn.execute(
            text(f"""
                UPDATE "League" l
                SET status = 'Pre-Draft',
                    "updatedAt" = now()
                WHERE l.status NOT IN ('Pre-Draft', 'Completed')
                  AND NOT EXISTS (
                    SELECT 1
                    FROM "DraftState" ds
                    WHERE ds."leagueId" = l.id
                      AND ds.status IN ('live', 'paused', 'complete')
                  )
            """)
        )

    def mark_drafting(self, conn):
        conn.execute(
            text(f"""
                UPDATE "League" l
                SET status = 'Drafting',
                    "updatedAt" = now()
                FROM "DraftState" ds
                WHERE ds."leagueId" = l.id
                  AND ds.status IN ('live', 'paused')
                  AND l.status <> 'Drafting'
            """)
        )

    def mark_post_draft(self, conn):
        conn.execute(
            text(f"""
                UPDATE "League" l
                SET status = 'Post-Draft',
                    "updatedAt" = now()
                FROM "League" source
                JOIN "SportSeason" ss
                  ON ss."sportId" = source.sport
                 AND ss."seasonYear" = source."seasonYear"
                LEFT JOIN "DraftState" ds ON ds."leagueId" = source.id
                WHERE source.id = l.id
                  AND ds.status = 'complete'
                  AND {LOCAL_TODAY} < ss."seasonStart"::date
                  AND l.status <> 'Completed'
                  AND l.status <> 'Post-Draft'
            """)
        )

    def mark_in_season(self, conn):
        conn.execute(
            text(f"""
                UPDATE "League" l
                SET status = 'In-Season',
                    "updatedAt" = now()
                FROM "SportSeason" ss
                WHERE ss."sportId" = l.sport
                  AND ss."seasonYear" = l."seasonYear"
                  AND {LOCAL_TODAY} >= ss."seasonStart"::date
                  AND {LOCAL_TODAY} <= ss."seasonEnd"::date
                  AND l.status NOT IN ('Drafting', 'In-Season', 'Completed')
                  AND EXISTS (
                    SELECT 1
                    FROM "DraftState" ds
                    WHERE ds."leagueId" = l.id
                      AND ds.status = 'complete'
                  )
            """)
        )

    def mark_completed(self, conn):
        conn.execute(
            text(f"""
                UPDATE "League" l
                SET status = 'Completed',
                    "updatedAt" = now()
                FROM "SportSeason" ss
                WHERE ss."sportId" = l.sport
                  AND ss."seasonYear" = l."seasonYear"
                  AND {LOCAL_TODAY} > ss."seasonEnd"::date
                  AND l.status <> 'Completed'
            """)
        )
