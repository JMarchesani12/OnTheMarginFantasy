from flask_socketio import disconnect, join_room, emit, leave_room
from requests import request, session
from socketioInstance import socketio
from endpoints.draft.draftModel import DraftModel
from supabaseAuth import verify_supabase_token
from utils.jsonSafe import jsonSafe

def register_draft_socket_handlers(engine):
    model = DraftModel(engine)

    @socketio.on("connect")
    def on_connect(auth):
        token = None
        if isinstance(auth, dict):
            token = auth.get("token") or auth.get("access_token")
        if token and token.startswith("Bearer "):
            token = token.split(" ", 1)[1]

        if not token:
            return False  # tells Socket.IO to reject the connection

        claims = verify_supabase_token(token)
        if not claims:
            return False

        socketio.server.save_session(request.sid, {"user": claims})

    @socketio.on("draft:join")
    def on_join(payload):
        sess = socketio.server.get_session(request.sid)
        user = sess.get("user")
        if not user:
            emit("draft:error", {"message": "Unauthorized"})
            return

        try:
            league_id_raw = payload.get("leagueId") if isinstance(payload, dict) else None
            if league_id_raw is None:
                emit("draft:error", {"message": "leagueId is required"})
                return
            league_id = int(league_id_raw)

            # ✅ Authorization: user must be a league member
            supabase_sub = user["sub"]
            if not model.is_supabase_user_in_league(league_id, supabase_sub):
                emit("draft:error", {"message": "Forbidden: not a member of this league"})
                return

            room = f"draft:{league_id}"
            join_room(room)

            snapshot = model.get_draft_state_snapshot(league_id)
            emit("draft:snapshot", {"snapshot": jsonSafe(snapshot)})

        except Exception as e:
            emit("draft:error", {"message": str(e)})


    @socketio.on("draft:leave")
    def on_leave(payload):
        sess = socketio.server.get_session(request.sid)
        user = sess.get("user")
        if not user:
            emit("draft:error", {"message": "Unauthorized"})
            return

        league_id_raw = payload.get("leagueId") if isinstance(payload, dict) else None
        if league_id_raw is None:
            emit("draft:error", {"message": "leagueId is required"})
            return
        league_id = int(league_id_raw)
        supabase_sub = user["sub"]
        if not model.is_supabase_user_in_league(league_id, supabase_sub):
            emit("draft:error", {"message": "Forbidden"})
            return

        room = f"draft:{league_id}"
        leave_room(room)