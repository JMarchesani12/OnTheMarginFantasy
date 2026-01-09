import os
import json
import select
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from endpoints.draft.draftModel import DraftModel
from db import engine
from utils.jsonSafe import jsonSafe

DRAFT_NOTIFY_CHANNEL = "draft_updated"

def start_draft_notify_listener(socketio):
    """
    Call once when your Flask app starts.
    Listens for pg_notify events and broadcasts snapshots to the league room.
    """
    def _listen():
        dsn = os.environ["DATABASE_URL"]
        conn = psycopg2.connect(dsn)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        cur = conn.cursor()
        cur.execute(f"LISTEN {DRAFT_NOTIFY_CHANNEL};")

        model = DraftModel(engine)

        while True:
            # Wait up to 10s for a notify (keeps CPU low)
            if select.select([conn], [], [], 10) == ([], [], []):
                continue

            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                try:
                    payload = json.loads(notify.payload)
                    league_id = int(payload["leagueId"])
                except Exception:
                    continue

                # Build the latest snapshot and emit it
                try:
                    snapshot = model.get_draft_state_snapshot(league_id)
                    socketio.emit(
                        "draft:updated",
                        {"type": "notify", "snapshot": jsonSafe(snapshot)},
                        room=f"draft:{league_id}",
                    )
                except Exception:
                    # Don't crash listener on snapshot errors
                    pass

    socketio.start_background_task(_listen)
