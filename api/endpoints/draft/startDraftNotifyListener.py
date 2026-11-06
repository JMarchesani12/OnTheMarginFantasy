import os
import json
import select
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from endpoints.draft.snapshot_service import DraftSnapshotService
from .draftBroadcast import broadcast_draft_update
from .realtime import league_id_from

DRAFT_NOTIFY_CHANNEL = "draft_updated"

def dispatch_draft_notification(socketio, engine, payload):
    league_id = league_id_from(payload)
    snapshot = DraftSnapshotService(engine).snapshot_for_job(league_id)
    broadcast_draft_update(league_id, {"type": "notify", "snapshot": snapshot},
                           engine=engine, socket_server=socketio)

def start_draft_notify_listener(socketio, engine):
    """
    Called explicitly by the web runtime, once per serving process.
    Listens for pg_notify events and broadcasts snapshots to the league room.
    """
    def _listen():
        dsn = os.environ["DATABASE_URL"]
        conn = psycopg2.connect(dsn)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        cur = conn.cursor()
        cur.execute(f"LISTEN {DRAFT_NOTIFY_CHANNEL};")


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
                    dispatch_draft_notification(socketio, engine, {"leagueId": league_id})
                except Exception:
                    # Don't crash listener on snapshot errors
                    pass

    return socketio.start_background_task(_listen)
