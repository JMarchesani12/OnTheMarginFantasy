# endpoints/draft/draftBroadcast.py
from socketioInstance import socketio
from utils.jsonSafe import jsonSafe

def broadcast_draft_update(league_id: int, payload: dict):
    socketio.emit("draft:updated", jsonSafe(payload), room=f"draft:{league_id}")
