from flask_socketio import join_room, emit, leave_room
from socketioInstance import socketio
from endpoints.draft.draftModel import DraftModel
from utils.jsonSafe import jsonSafe

def register_draft_socket_handlers(engine):
    model = DraftModel(engine)

    @socketio.on("draft:join")
    def on_join(payload):
        print("✅ draft:join received payload:", payload)

        try:
            league_id = int(payload.get("leagueId"))
            room = f"draft:{league_id}"
            join_room(room)
            print("✅ joined room:", room)

            snapshot = model.get_draft_state_snapshot(league_id)
            print("✅ snapshot built (has keys):", list(snapshot.keys()))

            emit("draft:snapshot", {"snapshot": jsonSafe(snapshot)})
            print("✅ emitted draft:snapshot")

        except Exception as e:
            print("❌ error in draft:join handler:", repr(e))
            emit("draft:error", {"message": str(e)})

    @socketio.on("draft:leave")
    def on_leave(payload):
        league_id = int(payload.get("leagueId"))
        room = f"draft:{league_id}"
        leave_room(room)