from ..bootstrap import *
import time
from sqlalchemy import text
from endpoints.draft.draftModel import DraftModel

from db import engine

def run():
    model = DraftModel(engine)

    while True:
        try:
            # find leagues with live drafts that are expired past grace
            with engine.begin() as conn:
                rows = conn.execute(text("""
                    SELECT ds."leagueId"
                    FROM "DraftState" ds
                    JOIN "League" l ON l.id = ds."leagueId"
                    WHERE ds.status = 'live'
                      AND ds."expiresAt" IS NOT NULL
                      AND now() > (ds."expiresAt" + ((l.settings->'draft'->>'graceSeconds') || ' seconds')::interval)
                """)).fetchall()

            for r in rows:
                league_id = int(r[0])
                action = model.process_expired_pick_if_needed(league_id)
                # if action is not None, you would broadcast websocket events here

        except Exception:
            pass

        time.sleep(2)

if __name__ == "__main__":
    run()
