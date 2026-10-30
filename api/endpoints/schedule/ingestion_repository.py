"""Schedule ingestion persistence queries on caller-supplied connections."""
from sqlalchemy import text


class ScheduleIngestionRepository:

    def api_config(self, conn, params):
        return conn.execute(text('SELECT "api-keyword", "apiGroupIds", "baseUrlName" FROM "Sport" WHERE id = :sportId'), params)

    def team_id(self, conn, params):
        return conn.execute(text("""
            SELECT id
            FROM "SportTeam"
            WHERE "sportId" = :sportId
              AND "externalId" = :externalId
            LIMIT 1
        """), params)

    def upsert_game(self, conn, params):
        return conn.execute(text("""
            INSERT INTO "GameResult" (
                sport,
                "sportSeasonId",
                "seasonPhaseId",
                "externalGameId",
                date,
                "homeTeamId",
                "awayTeamId",
                "homeScore",
                "awayScore",
                "homeTeamExternalId",
                "awayTeamExternalId",
                "homeTeamName",
                "awayTeamName",
                "broadcast"
            )
            VALUES (
                :sport,
                :sportSeasonId,
                :seasonPhaseId,
                :externalGameId,
                :date,
                :homeTeamId,
                :awayTeamId,
                :homeScore,
                :awayScore,
                :homeTeamExternalId,
                :awayTeamExternalId,
                :homeTeamName,
                :awayTeamName,
                :broadcast
            )
            ON CONFLICT (sport, "sportSeasonId", "externalGameId")
            DO UPDATE SET
                "seasonPhaseId" = EXCLUDED."seasonPhaseId",
                date = EXCLUDED.date,
                "homeTeamId" = EXCLUDED."homeTeamId",
                "awayTeamId" = EXCLUDED."awayTeamId",
                "homeScore" = EXCLUDED."homeScore",
                "awayScore" = EXCLUDED."awayScore",
                "homeTeamExternalId" = EXCLUDED."homeTeamExternalId",
                "awayTeamExternalId" = EXCLUDED."awayTeamExternalId",
                "homeTeamName" = EXCLUDED."homeTeamName",
                "awayTeamName" = EXCLUDED."awayTeamName",
                "broadcast" = EXCLUDED."broadcast"
            RETURNING id;
        """), params)

    def sport_teams(self, conn, params):
        base_sql = """
            SELECT id, "sportId", "displayName", "externalId"
            FROM "SportTeam"
            WHERE "sportId" = :sportId
              AND "externalId" IS NOT NULL
            ORDER BY id
        """
        if "maxTeams" in params:
            base_sql += " LIMIT :maxTeams"
        return conn.execute(text(base_sql), params)

    def mark_team_bootstrapped(self, conn, params):
        return conn.execute(text("""
            UPDATE "SportSeason"
            SET "scheduleBootstrapped" = true,
                "scheduleBootstrappedAt" = now()
            WHERE id = :sportSeasonId
        """), params)

    def season_for_ingestion(self, conn, params):
        return conn.execute(text("""
                    SELECT id, "sportId"
                    FROM "SportSeason"
                    WHERE id = :id
                """), params)

    def season_for_bootstrap(self, conn, params):
        return conn.execute(text("""
                    SELECT
                        id,
                        "sportId",
                        COALESCE("scheduleBootstrapped", false) AS "scheduleBootstrapped",
                        "seasonStart"::date AS "seasonStart",
                        "seasonEnd"::date AS "seasonEnd"
                    FROM "SportSeason"
                    WHERE id = :id
                """), params)

    def bootstrap_start(self, conn, params):
        return conn.execute(text('''
                UPDATE "SportSeason" SET "scheduleBootstrapped"=false, "scheduleBootstrappedAt"=NULL
                WHERE id=:id
            '''), params)

    def bootstrap_finish(self, conn, params):
        return conn.execute(text("""
                    UPDATE "SportSeason"
                    SET "scheduleBootstrapped" = :complete,
                        "scheduleBootstrappedAt" = CASE WHEN :complete THEN now() ELSE NULL END
                    WHERE id = :id
                """), params)

    def shared_conferences(self, conn, params):
        return conn.execute(text('''
                        SELECT DISTINCT a."sportConferenceId"
                        FROM "ConferenceMembership" a
                        JOIN "ConferenceMembership" b
                          ON b."sportConferenceId"=a."sportConferenceId" AND b."sportId"=a."sportId"
                        JOIN "SportSeason" ss ON ss.id=:season AND ss."sportId"=a."sportId"
                        WHERE a."sportTeamId"=:home AND b."sportTeamId"=:away
                          AND (a."seasonYear"=ss."seasonYear" OR (a."seasonYear" IS NULL AND NOT EXISTS (
                              SELECT 1 FROM "ConferenceMembership" x WHERE x."sportTeamId"=a."sportTeamId"
                              AND x."sportId"=a."sportId" AND x."seasonYear"=ss."seasonYear")))
                          AND (b."seasonYear"=ss."seasonYear" OR (b."seasonYear" IS NULL AND NOT EXISTS (
                              SELECT 1 FROM "ConferenceMembership" x WHERE x."sportTeamId"=b."sportTeamId"
                              AND x."sportId"=b."sportId" AND x."seasonYear"=ss."seasonYear")))
                    '''), params)

    def fallback_phase(self, conn, params):
        return conn.execute(text("""
            SELECT sp.id
            FROM "SeasonPhase" sp
            WHERE sp."sportSeasonId" = :sportSeasonId
            AND :eventDate >= sp."startDate"
            AND :eventDate <  sp."endDate"
            ORDER BY sp."priority" ASC, sp."startDate" DESC, sp.id DESC
            LIMIT 1;
        """), params)

    def upsert_season(self, conn, params):
        return conn.execute(text("""
                INSERT INTO "SportSeason"
                    ("sportId", "seasonYear", "seasonStart", "seasonEnd")
                VALUES
                    (:sportId, :year, :seasonStart, :seasonEnd)
                ON CONFLICT ("sportId","seasonYear")
                DO UPDATE SET
                    "seasonStart" = EXCLUDED."seasonStart",
                    "seasonEnd" = EXCLUDED."seasonEnd"
                RETURNING id
            """), params)

    def active_leagues(self, conn, params):
        return conn.execute(text("""
        SELECT l.id
        FROM "League" l
        JOIN "SportSeason" ss
          ON ss."sportId" = l."sport"
         AND ss."seasonYear" = l."seasonYear"
        WHERE
          ss."seasonStart"::date <= :d
          AND ss."seasonEnd"::date >= :d
          AND l.status <> 'Completed'
    """), params)
