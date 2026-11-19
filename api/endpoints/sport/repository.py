"""Public sport catalog SQL on the caller's connection."""
from sqlalchemy import text


class SportRepository:
    def list_sports(self, conn):
        rows = conn.execute(
            text('SELECT id, name, "maxPlayersToHaveMaxRounds", "maxDraftRounds" FROM "Sport"'),
        ).mappings().all()
        return [dict(row) for row in rows]

    def team_search_catalog(self, conn):
        return conn.execute(text('''
            SELECT st.id AS "teamId",st."schoolId",school.name AS "teamName",sa.alias
            FROM "SportTeam" st JOIN "School" school ON school.id=st."schoolId" LEFT JOIN "SchoolAlias" sa ON sa."schoolId"=st."schoolId"
            ORDER BY st.id,sa."normalizedAlias"
        '''),{}).mappings().all()
