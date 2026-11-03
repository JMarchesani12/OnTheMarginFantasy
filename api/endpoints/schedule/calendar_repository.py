"""Calendar SQL executed on a supplied connection; no transaction acquisition."""
from sqlalchemy import text


class ScheduleCalendarRepository:

    def league(self, conn, params):
        return conn.execute(text("""
            SELECT id, "sport", "seasonYear", settings
            FROM "League"
            WHERE id = :leagueId
        """), params)

    def season_for_league(self, conn, params):
        return conn.execute(text("""
            SELECT
                ss.id AS "sportSeasonId",
                ss."sportId",
                ss."seasonYear",
                ss."seasonStart",
                ss."seasonEnd",
                ss."scheduleBootstrapped",
                ss."scheduleBootstrappedAt",
                l.settings
            FROM "League" l
            JOIN "SportSeason" ss
              ON ss."sportId" = l."sport"
             AND ss."seasonYear" = l."seasonYear"
            WHERE l.id = :leagueId
            LIMIT 1
        """), params)

    def subdivisions(self, conn, params):
        return conn.execute(text("""
                    SELECT
                        id AS "sportSeasonSubdivisionId",
                        code AS "subdivisionCode",
                        name AS "subdivisionName",
                        "regularSeasonStart",
                        "regularSeasonEnd",
                        "postseasonStart",
                        "postseasonEnd"
                    FROM "SportSeasonSubdivision"
                    WHERE "sportSeasonId" = :sportSeasonId
                    ORDER BY code
                """), params)

    def weeks_for_league(self, conn, params):
        return conn.execute(text("""
            SELECT id, "weekNumber", "startDate", "endDate"
            FROM "Week"
            WHERE "leagueId" = :leagueId
            ORDER BY "weekNumber" ASC
        """), params)

    def insert_week_zero(self, conn, params):
        return conn.execute(text("""
                    insert into "Week" ("leagueId","weekNumber","startDate","endDate","isLocked","scoringComplete")
                    values (:leagueId, 0, :startDate, :endDate, false, false)
                    returning id, "leagueId", "weekNumber", "startDate", "endDate", "isLocked", "scoringComplete"
                """), params)

    def insert_week(self, conn, params):
        return conn.execute(text("""
            INSERT INTO "Week"
                ("leagueId", "weekNumber", "startDate", "endDate", "isLocked", "scoringComplete")
            VALUES
                (:leagueId, :weekNumber, :startDate, :endDate, false, false)
            RETURNING id, "weekNumber", "startDate", "endDate"
        """), params)

    def season_phases(self, conn, params):
        return conn.execute(text('''
                SELECT sp.*, td."sportConferenceId"
                FROM "SeasonPhase" sp
                LEFT JOIN "TournamentDefinition" td ON td.id=sp."tournamentId"
                WHERE sp."sportSeasonId"=:season
            '''), params)
