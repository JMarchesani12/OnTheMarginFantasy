from flask import request
from socketioInstance import socketio
from endpoints.draft.snapshot_service import DraftSnapshotService
from .realtime import DraftSocketAccess, league_id_from, verified_claims


def register_draft_socket_handlers(engine, socket_server=None):
    server = socket_server if socket_server is not None else socketio
    access = DraftSocketAccess(engine, server)
    server.draft_access = access
    snapshots = DraftSnapshotService(engine)

    @server.on('connect')
    def on_connect(auth):
        token = (auth.get('token') or auth.get('access_token')) if isinstance(auth, dict) else None
        if isinstance(token, str) and token.startswith('Bearer '):
            token = token.split(' ', 1)[1]
        try:
            verified_claims(token)
        except Exception:
            return False
        access.tokens[request.sid] = token

    @server.on('disconnect')
    def on_disconnect(reason=None):
        access.tokens.pop(request.sid, None)

    @server.on('draft:join')
    def on_join(payload):
        try:
            league_id = league_id_from(payload)
        except ValueError:
            server.emit('draft:error', {'message': 'Invalid leagueId'}, to=request.sid)
            return
        try:
            user_id = access.reader(request.sid, league_id)
            snapshot = snapshots.snapshot_for_reader_id(league_id, user_id)
            server.server.enter_room(request.sid, f'draft:{league_id}', namespace='/')
            access.deliver(request.sid, league_id, 'draft:snapshot', {'snapshot': snapshot})
        except Exception:
            access.deny(request.sid, league_id)

    @server.on('draft:leave')
    def on_leave(payload):
        try:
            league_id = league_id_from(payload)
        except ValueError:
            server.emit('draft:error', {'message': 'Invalid leagueId'}, to=request.sid)
            return
        server.server.leave_room(request.sid, f'draft:{league_id}', namespace='/')
