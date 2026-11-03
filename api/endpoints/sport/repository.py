"""Public sport catalog SQL on the caller's connection."""
from sqlalchemy import text


class SportRepository:
    def list_sports(self, conn):
        rows = conn.execute(
            text('SELECT id, name, "maxPlayersToHaveMaxRounds", "maxDraftRounds" FROM "Sport"'),
        ).mappings().all()
        return [dict(row) for row in rows]
