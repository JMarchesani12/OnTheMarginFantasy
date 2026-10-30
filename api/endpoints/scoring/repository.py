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
