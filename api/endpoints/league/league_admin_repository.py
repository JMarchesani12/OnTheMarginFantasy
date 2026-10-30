"""League administration persistence; caller supplies transaction connection."""
from sqlalchemy import text


class LeagueAdminRepository:
    def lock_for_delete(self, conn, league_id):
        row = conn.execute(text("""
                    SELECT id, name, commissioner
                    FROM "League"
                    WHERE id = :leagueId
                    FOR UPDATE
                """), {'leagueId': league_id}).mappings().first()
        return dict(row) if row else None

    def delete_if_commissioner(self, conn, league_id, acting_user_id):
        row = conn.execute(text("""
                    DELETE FROM "League"
                    WHERE id = :leagueId AND commissioner = :actingUserId
                    RETURNING id, name
                """), {'leagueId': league_id, 'actingUserId': acting_user_id}).mappings().first()
        return dict(row) if row else None

    def current_for_update(self, conn, league_id):
        row = conn.execute(text("""
                    SELECT id, sport, settings, commissioner
                    FROM "League"
                    WHERE id = :leagueId
                """), {'leagueId': league_id}).fetchone()
        return dict(row._mapping) if row else None

    def update_fields(self, conn, league_id, payload, commissioner_id=None):
        update_data = {'leagueId': league_id, **payload}
        set_clauses = []
        for key in payload:
            if key == 'settings':
                set_clauses.append('settings = cast(:settings as jsonb)')
            elif key in {'numPlayers', 'draftDate', 'tradeDeadline', 'freeAgentDeadline'}:
                set_clauses.append(f'"{key}" = :{key}')
            else:
                set_clauses.append(f'{key} = :{key}')
        set_clauses.append('"updatedAt" = now()')
        ownership_clause = ''
        if commissioner_id is not None:
            update_data['actingUserId'] = commissioner_id
            ownership_clause = 'AND commissioner = :actingUserId'
        sql = text(f"""
            WITH updated AS (
            UPDATE "League"
            SET {", ".join(set_clauses)}
            WHERE id = :leagueId {ownership_clause}
            RETURNING
                id, "createdAt", name, sport, "numPlayers", status, settings, "updatedAt",
                "draftDate", "freeAgentDeadline", "tradeDeadline", commissioner
            )
            SELECT
            u.*,
            to_jsonb(s.*) AS sportInfo
            FROM updated u
            JOIN "Sport" s ON s.id = u.sport;
        """)
        row = conn.execute(sql, update_data).mappings().first()
        return dict(row) if row else None

    def insert_league(self, conn, league):
        row = conn.execute(text("""
            WITH created AS (
            INSERT INTO "League"
                ("name", sport, "numPlayers", status, settings, "updatedAt", "draftDate", "commissioner", "seasonYear", "isDiscoverable")
            VALUES
                (:name, :sport, :numPlayers, :status, cast(:settings as jsonb), now(), :draftDate, :commissioner, :seasonYear, :isDiscoverable)
            RETURNING
                id, "createdAt", name, sport, "numPlayers", status, settings, "updatedAt", "draftDate", commissioner, "seasonYear", "isDiscoverable"
            )
            SELECT
            c.*,
            to_jsonb(s.*) AS sportInfo
            FROM created c
            JOIN "Sport" s ON s.id = c.sport;
        """), league).mappings().first()
        return dict(row) if row else None

    def insert_creator_member(self, conn, league_id, user_id, team_name):
        row = conn.execute(text("""
                INSERT INTO "LeagueMember"
                    ("leagueId", "userId", "teamName", "seasonPoints", "draftOrder")
                VALUES
                    (:leagueId, :userId, :teamName, 0, 1)
                RETURNING id
            """), {
            'leagueId': league_id, 'userId': user_id, 'teamName': team_name,
        }).fetchone()
        return row._mapping['id']
