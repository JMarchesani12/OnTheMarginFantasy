from sqlalchemy import text
from sqlalchemy.engine import Engine

class SportModel:
    def __init__(self, db: Engine):
        self.db = db


    def get_sports(self):
        with self.db.begin() as conn:
            sports = conn.execute(
                text('SELECT id, name, "maxPlayersToHaveMaxRounds", "maxDraftRounds" FROM "Sport"'),
            ).mappings().all()

        return [dict(s) for s in sports]