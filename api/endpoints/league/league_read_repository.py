"""League read SQL; callers supply connections and explicit reader scope."""
from sqlalchemy import text
from utils.authorization import league_read_scope


class LeagueReadRepository:
    def rules_league(self, conn, league_id, reader_user_id=None):
        scope, reader_params = league_read_scope(league_id, reader_user_id)
        row = conn.execute(text(f'SELECT id, name, sport, "seasonYear", settings, "tradeDeadline", "freeAgentDeadline", "draftDate" FROM "League" WHERE id = :leagueId {scope}'),
                           {'leagueId': league_id, **reader_params}).fetchone()
        return dict(row._mapping) if row else None

    def rules_teams(self, conn, sport_id):
        rows = conn.execute(text("""
                SELECT st.id AS "teamId", st."displayName" AS "teamName",
                    COALESCE(st.tier, (SELECT COALESCE(MAX(t.tier), 0) + 1
                        FROM "SportTeam" t WHERE t."sportId" = :sportId)) AS tier
                FROM "SportTeam" st WHERE st."sportId" = :sportId
                ORDER BY tier, st."displayName"
            """), {'sportId': sport_id}).fetchall()
        return [dict(row._mapping) for row in rows]

    def conference_league(self, conn, league_id, reader_user_id=None):
        scope, reader_params = league_read_scope(league_id, reader_user_id)
        league_sql = text(f"""
            SELECT
              id AS "leagueId",
              sport AS "sportId",
              "seasonYear" AS "seasonYear"
            FROM "League"
            WHERE id = :leagueId
            {scope}
            LIMIT 1
        """)
        row = conn.execute(league_sql, {'leagueId': league_id, **reader_params}).fetchone()
        return dict(row._mapping) if row else None

    def season_conferences(self, conn, sport_id, season_year):
        rows = conn.execute(text("""
                SELECT
                  sc.id AS "sportConferenceId",
                  sc."conferenceId" AS "conferenceId",
                  c.name AS "displayName",
                  sc."maxTeamsPerOwner" AS "maxTeamsPerOwner",
                  COALESCE(t."teamsInConference", 0) AS "teamsInConference"
                FROM "SportConference" sc
                JOIN "Conference" c ON c.id = sc."conferenceId"
                LEFT JOIN (
                  SELECT
                    cm."sportConferenceId",
                    COUNT(*) AS "teamsInConference"
                  FROM "ConferenceMembership" cm
                  WHERE (cm."seasonYear" IS NULL OR cm."seasonYear" = :seasonYear)
                  GROUP BY cm."sportConferenceId"
                ) t ON t."sportConferenceId" = sc.id
                WHERE sc."sportId" = :sportId
                ORDER BY c.name;
            """), {'sportId': sport_id, 'seasonYear': season_year}).fetchall()
        return [dict(row._mapping) for row in rows]

    def access_metadata(self, conn, league_id, user_id):
        row = conn.execute(text("""
                SELECT l.id, l.name, l.sport, l."isDiscoverable",
                       u."displayName" AS "commissionerDisplayName",
                       CASE WHEN l.commissioner = :userId OR EXISTS (
                           SELECT 1 FROM "LeagueMember" lm
                           WHERE lm."leagueId" = l.id AND lm."userId" = :userId
                       ) THEN true ELSE false END AS "fullAccess"
                FROM "League" l LEFT JOIN "User" u ON u.id = l.commissioner
                WHERE l.id = :leagueId
            """), {'leagueId': league_id, 'userId': user_id}).mappings().first()
        return dict(row) if row else None

    def member_previews(self, conn, league_id, user_id):
        rows = conn.execute(text("""
                SELECT lm.id, lm."teamName", u."displayName"
                FROM "LeagueMember" lm
                JOIN "User" u ON u.id = lm."userId"
                JOIN "League" l ON l.id = lm."leagueId"
                WHERE l.id = :leagueId AND (
                    l."isDiscoverable" = true OR l.commissioner = :userId OR EXISTS (
                        SELECT 1 FROM "LeagueMember" reader
                        WHERE reader."leagueId" = l.id AND reader."userId" = :userId
                    )
                )
                ORDER BY lm.id
            """), {'leagueId': league_id, 'userId': user_id}).mappings().all()
        return [dict(row) for row in rows]

    def search_discoverable(self, conn, q, sport_id, limit, offset):
        params = {'pattern': f'%{q}%', 'q': q, 'limit': limit, 'offset': offset}
        sport_clause = ''
        if sport_id is not None:
            sport_clause = 'AND l.sport = :sportId'
            params['sportId'] = sport_id
        sql = text(f"""
            SELECT
            l.id,
            l.name,
            l.sport,
            l."numPlayers",
            l.status,
            l."draftDate",
            l."isDiscoverable",
            l.commissioner,
            u."displayName" AS "commissionerDisplayName"
            FROM "League" l
            JOIN "User" u ON u.id = l.commissioner
            WHERE l."isDiscoverable" = true
            AND l.name ILIKE :pattern
            {sport_clause}
            ORDER BY similarity(l.name, :q) DESC, l.name ASC
            LIMIT :limit OFFSET :offset
        """)
        rows = conn.execute(sql, params).mappings().all()
        return [dict(row) for row in rows]
