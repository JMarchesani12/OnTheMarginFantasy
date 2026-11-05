from utils.conference_membership import conference_sql
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
        # Lock reference rows on this connection so their sport/season cannot
        # change between validation and insertion/update.
        season = conn.execute(text('SELECT id FROM "SportSeason" WHERE id=:sportSeasonId AND "sportId"=:sport FOR SHARE'), params).fetchone()
        if season is None:
            raise ValueError('Game sport/season mismatch')
        if params.get('seasonPhaseId') is not None:
            phase = conn.execute(text('SELECT id FROM "SeasonPhase" WHERE id=:seasonPhaseId AND "sportSeasonId"=:sportSeasonId FOR SHARE'), params).fetchone()
            if phase is None:
                raise ValueError('Game phase/season mismatch')
        for field in ('homeTeamId', 'awayTeamId'):
            if params.get(field) is not None:
                team = conn.execute(text('SELECT id FROM "SportTeam" WHERE id=:teamId AND "sportId"=:sport FOR SHARE'), {'teamId': params[field], 'sport': params['sport']}).fetchone()
                if team is None:
                    raise ValueError('Game team/sport mismatch')
        return conn.execute(text("""
            INSERT INTO "GameResult" (
                sport,
                "sportSeasonId",
                "seasonPhaseId",
                "externalGameId",
                date,
                "timeTBD",
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
                :timeTBD,
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
                "timeTBD" = EXCLUDED."timeTBD",
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
        return conn.execute(text(conference_sql('''
            SELECT a."sportConferenceId"
            FROM "ConferenceMembership" a
            JOIN "ConferenceMembership" b ON b."sportConferenceId"=a."sportConferenceId" AND b."sportId"=a."sportId"
            JOIN "SportSeason" ss ON ss.id=:season AND ss."sportId"=a."sportId"
            WHERE a."sportTeamId"=:home AND b."sportTeamId"=:away
        ''', '(SELECT "seasonYear" FROM "SportSeason" WHERE id=:season)')), params)

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
