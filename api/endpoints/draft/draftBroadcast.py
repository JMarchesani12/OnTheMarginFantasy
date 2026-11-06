"""The sole outbound draft update boundary, for HTTP and database wakeups."""
from socketioInstance import socketio


def broadcast_draft_update(league_id: int, payload: dict, engine=None, socket_server=None):
    server = socket_server if socket_server is not None else socketio
    access = getattr(server, 'draft_access', None)
    if access is None or (engine is not None and access.engine is not engine):
        return  # No registered authorization boundary; never fall back to a room emit.
    participants = list(server.server.manager.get_participants('/', f'draft:{league_id}'))
    for sid, _ in participants:
        access.deliver(sid, league_id, 'draft:updated', payload)
