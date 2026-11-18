"""Explicit listener adapter; imports perform no runtime work."""
import os
from endpoints.draft.snapshot_service import DraftSnapshotService
from .draftBroadcast import broadcast_draft_update
from .realtime import league_id_from

DRAFT_NOTIFY_CHANNEL = "draft_updated"


def dispatch_draft_notification(socketio, engine, payload, *, should_deliver=None):
    league_id = league_id_from(payload)
    snapshot = DraftSnapshotService(engine).snapshot_for_job(league_id)
    if should_deliver is not None and not should_deliver(): return
    broadcast_draft_update(league_id, {"type": "notify", "snapshot": snapshot},
                           engine=engine, socket_server=socketio, should_deliver=should_deliver)


def start_draft_notify_listener(socketio, engine):
    from .listener import DraftNotifyListener
    return DraftNotifyListener(engine, socketio, legacy_url=os.environ.get('DATABASE_URL')).start()
