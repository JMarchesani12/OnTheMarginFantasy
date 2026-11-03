"""Scoring read persistence on caller-supplied connections."""
from sqlalchemy import bindparam, text
from utils.authorization import league_read_scope


class ScoringRepository:
    def league_read_allowed(self, conn, league_id, user_id):
        scope, params = league_read_scope(league_id, user_id)
        return conn.execute(text('SELECT id FROM "League" WHERE id = :leagueId ' + scope),
                            {'leagueId': league_id, **params}).fetchone() is not None

    def weekly_points(self, conn, league_id, week_numbers):
        sql = text("""
            SELECT
            w."weekNumber",
            w."startDate",
            w."endDate",
            wts."memberId",
            lm."teamName",
            wts."pointsAwarded",
            wts."pointDifferential",
            wts.rank
            FROM "WeeklyTeamScore" wts
            JOIN "Week" w
            ON w.id = wts."weekId"
            JOIN "LeagueMember" lm
            ON lm.id = wts."memberId"
            WHERE wts."leagueId" = :leagueId
            AND w."weekNumber" IN :weekNumbers
            ORDER BY w."weekNumber" ASC, wts.rank ASC;
        """).bindparams(bindparam("weekNumbers", expanding=True))
        rows = conn.execute(sql, {'leagueId': league_id, 'weekNumbers': week_numbers}).fetchall()
        return [dict(r._mapping) for r in rows]

    def league_settings(self, conn, league_id):
        sql = text("""
            SELECT settings
            FROM "League"
            WHERE id = :leagueId
        """)
        return conn.execute(sql, {'leagueId': league_id}).fetchone()

    def week_metadata(self, conn, league_id, week_number):
        sql = text("""
            SELECT w.id, w."weekNumber", w."startDate", w."endDate",
                EXISTS (
                    SELECT 1 FROM "League" l
                    JOIN "SportSeason" ss ON ss."sportId"=l.sport AND ss."seasonYear"=l."seasonYear"
                    JOIN "SeasonPhase" sp ON sp."sportSeasonId"=ss.id
                    WHERE l.id=w."leagueId" AND sp.rules->>'scoringPeriod'='BASKETBALL_FINAL'
                      AND sp."startDate" <= w."endDate" AND sp."endDate" > w."startDate"
                ) AS "isFinalPeriod",
                (SELECT MAX(sp."endDate") FROM "League" l
                 JOIN "SportSeason" ss ON ss."sportId"=l.sport AND ss."seasonYear"=l."seasonYear"
                 JOIN "SeasonPhase" sp ON sp."sportSeasonId"=ss.id
                 WHERE l.id=w."leagueId" AND sp.rules->>'scoringPeriod'='BASKETBALL_FINAL'
                ) AS "finalPeriodEnd",
                (SELECT MIN(sp."startDate") FROM "League" l
                 JOIN "SportSeason" ss ON ss."sportId"=l.sport AND ss."seasonYear"=l."seasonYear"
                 JOIN "SeasonPhase" sp ON sp."sportSeasonId"=ss.id
                 WHERE l.id=w."leagueId" AND sp.rules->>'scoringPeriod'='BASKETBALL_FINAL'
                ) AS "finalPeriodStart"
            FROM "Week" w
            WHERE "leagueId" = :leagueId
              AND "weekNumber" = :weekNumber
        """)
        return conn.execute(sql, {'leagueId': league_id, 'weekNumber': week_number}).fetchone()

    def league_members(self, conn, league_id):
        sql = text("""
            SELECT id, "teamName"
            FROM "LeagueMember"
            WHERE "leagueId" = :leagueId
            ORDER BY id
        """)
        return conn.execute(sql, {'leagueId': league_id}).fetchall()

    def delete_weekly_scores(self, conn, league_id, week_id):
        sql = text("""
            DELETE FROM "WeeklyTeamScore"
            WHERE "leagueId" = :leagueId
              AND "weekId" = :weekId
        """)
        conn.execute(sql, {'leagueId': league_id, 'weekId': week_id})

    def sport_season(self, conn, league_id):
        sql = text("""
            SELECT
              ss.id          AS "sportSeasonId",
              ss."sportId"   AS "sportId",
              ss."seasonYear" AS "seasonYear"
            FROM "League" l
            JOIN "SportSeason" ss
              ON ss."sportId"    = l."sport"
             AND ss."seasonYear" = l."seasonYear"
            WHERE l.id = :leagueId
            LIMIT 1
        """)
        return conn.execute(sql, {'leagueId': league_id}).fetchone()

    def owned_teams(self, conn, league_id, member_id):
        sql = text("""
            SELECT DISTINCT lts."sportTeamId"
            FROM "LeagueTeamSlot" lts
            WHERE lts."leagueId" = :leagueId
              AND lts."memberId" = :memberId
        """)
        return conn.execute(sql, {'leagueId': league_id, 'memberId': member_id}).fetchall()

    def insert_weekly_score(self, conn, league_id, week_id, member_id, point_differential, rank, points_awarded):
        insert_sql = text("""
            INSERT INTO "WeeklyTeamScore"
                ("leagueId", "weekId", "memberId",
                 "pointDifferential", rank, "pointsAwarded")
            VALUES
                (:leagueId, :weekId, :memberId,
                 :pointDifferential, :rank, :pointsAwarded)
        """)
        conn.execute(insert_sql, {'leagueId': league_id, 'weekId': week_id, 'memberId': member_id, 'pointDifferential': point_differential, 'rank': rank, 'pointsAwarded': points_awarded})

    def season_points(self, conn, league_id):
        sql = text("""
            SELECT
            lm.id         AS "memberId",
            lm."teamName" AS "teamName",
            COALESCE(SUM(wts."pointsAwarded"), 0) AS "weeklyPoints"
            FROM "LeagueMember" lm
            LEFT JOIN "WeeklyTeamScore" wts
            ON wts."memberId" = lm.id
            AND wts."leagueId" = lm."leagueId"
            WHERE lm."leagueId" = :leagueId
            GROUP BY lm.id, lm."teamName"
        """)
        return conn.execute(sql, {'leagueId': league_id}).fetchall()

    def primary_phases(self, conn, sport_season_id, primary_types):
        sql_phase = text("""
            SELECT id
            FROM "SeasonPhase"
            WHERE "sportSeasonId" = :sportSeasonId
              AND type = ANY(:primaryTypes)
              AND COALESCE((rules->>'primaryPostseason')::boolean, true)
        """)
        return conn.execute(sql_phase, {'sportSeasonId': sport_season_id, 'primaryTypes': primary_types}).fetchall()

    def playoff_depth(self, conn, sport_season_id, phase_ids, team_ids):
        sql_depth = text("""
            SELECT COALESCE(MAX("roundOrder"), 0) AS max_round
            FROM "GameResult"
            WHERE "sportSeasonId" = :sportSeasonId
              AND "seasonPhaseId" = ANY(:phaseIds)
              AND "roundOrder" IS NOT NULL
              AND (
                "homeTeamId" = ANY(:teamIds)
                OR "awayTeamId" = ANY(:teamIds)
              )
        """)
        return conn.execute(sql_depth, {'sportSeasonId': sport_season_id, 'phaseIds': phase_ids, 'teamIds': team_ids}).fetchone()

    def segment_phases(self, conn, sport_season_id, segment_types):
        sql_phases = text("""
            SELECT id
            FROM "SeasonPhase"
            WHERE "sportSeasonId" = :sportSeasonId
              AND type = ANY(:segmentTypes)
        """)
        return conn.execute(sql_phases, {'sportSeasonId': sport_season_id, 'segmentTypes': segment_types}).fetchall()

    def segment_final(self, conn, sport_season_id, phase_id):
        sql_final = text("""
            SELECT "homeTeamId", "awayTeamId", "homeScore", "awayScore"
            FROM "GameResult"
            WHERE "sportSeasonId" = :sportSeasonId
              AND "seasonPhaseId" = :phaseId
              AND "roundOrder" = (
                SELECT MAX("roundOrder")
                FROM "GameResult"
                WHERE "sportSeasonId" = :sportSeasonId
                  AND "seasonPhaseId" = :phaseId
              )
            LIMIT 1
        """)
        return conn.execute(sql_final, {'sportSeasonId': sport_season_id, 'phaseId': phase_id}).fetchone()

    def head_to_head_phases(self, conn, sport_season_id, types, primary_only):
        sql_phases = text("""
            SELECT id
            FROM "SeasonPhase"
            WHERE "sportSeasonId" = :sportSeasonId
              AND type = ANY(:types)
              AND (:primaryOnly = false OR COALESCE((rules->>'primaryPostseason')::boolean, true))
        """)
        return conn.execute(sql_phases, {'sportSeasonId': sport_season_id, 'types': types, 'primaryOnly': primary_only}).fetchall()

    def head_to_head_games(self, conn, sport_season_id, phase_ids, all_team_ids):
        sql_games = text("""
            SELECT
              gr."homeTeamId",
              gr."awayTeamId",
              gr."homeScore",
              gr."awayScore"
            FROM "GameResult" gr
            WHERE gr."sportSeasonId" = :sportSeasonId
              AND gr."seasonPhaseId" = ANY(:phaseIds)
              AND gr."homeTeamId" IS NOT NULL
              AND gr."awayTeamId" IS NOT NULL
              AND (
                gr."homeTeamId" = ANY(:allTeamIds)
                OR gr."awayTeamId" = ANY(:allTeamIds)
              )
        """)
        return conn.execute(sql_games, {'sportSeasonId': sport_season_id, 'phaseIds': phase_ids, 'allTeamIds': all_team_ids}).fetchall()

    def weeks_descending(self, conn, league_id):
        sql_weeks = text("""
            SELECT id, "weekNumber"
            FROM "Week"
            WHERE "leagueId" = :leagueId
            ORDER BY "weekNumber" DESC
        """)
        return conn.execute(sql_weeks, {'leagueId': league_id}).fetchall()

    def weekly_ranks(self, conn, league_id, week_id, member_ids):
        sql_scores = text("""
            SELECT "memberId", rank
            FROM "WeeklyTeamScore"
            WHERE "leagueId" = :leagueId
              AND "weekId" = :weekId
              AND "memberId" = ANY(:memberIds)
        """)
        return conn.execute(sql_scores, {'leagueId': league_id, 'weekId': week_id, 'memberIds': member_ids}).fetchall()

    def segment_games(self, conn, sport_season_id, phase_ids):
        sql_games = text("""
            SELECT
              gr."homeTeamId",
              gr."awayTeamId",
              gr."homeScore",
              gr."awayScore"
            FROM "GameResult" gr
            WHERE gr."sportSeasonId" = :sportSeasonId
              AND gr."seasonPhaseId" = ANY(:phaseIds)
              AND gr."homeTeamId" IS NOT NULL
              AND gr."awayTeamId" IS NOT NULL
        """)
        return conn.execute(sql_games, {'sportSeasonId': sport_season_id, 'phaseIds': phase_ids}).fetchall()
