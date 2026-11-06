"""Per-process socket credentials and fail-closed draft delivery policy.

Tokens stay in server memory, keyed by Socket.IO SID. This uses the existing
single-process manager; it is not a cross-worker session registry.
"""
import math
import time
from sqlalchemy import text
from supabaseAuth import verify_supabase_token
from utils.jsonSafe import jsonSafe
from utils.requestValidation import integer_field


def league_id_from(payload):
    if not isinstance(payload, dict):
        raise ValueError('leagueId is required')
    value = integer_field(payload, 'leagueId')
    if not 0 < value <= 2**63 - 1:
        raise ValueError('leagueId is out of range')
    return value


def verified_claims(token):
    if not isinstance(token, str) or not token:
        raise PermissionError('Draft access denied')
    claims = verify_supabase_token(token)
    expiry = claims.get('exp') if claims else None
    if (not claims or not isinstance(claims.get('sub'), str) or not claims['sub'] or
            type(expiry) not in (int, float) or not math.isfinite(expiry) or expiry <= time.time()):
        raise PermissionError('Draft access denied')
    return claims


class DraftSocketAccess:
    def __init__(self, engine, socket_server):
        self.engine = engine
        self.socket = socket_server
        self.tokens = {}

    def reader(self, sid, league_id):
        token = self.tokens.get(sid)
        claims = verified_claims(token)
        with self.engine.begin() as conn:
            users = conn.execute(text('SELECT id FROM "User" WHERE uuid = :subject LIMIT 2'),
                                 {'subject': claims['sub']}).mappings().fetchmany(2)
            if len(users) != 1:
                raise PermissionError('Draft access denied')
            user_id = int(users[0]['id'])
            member = conn.execute(text('''SELECT 1 FROM "LeagueMember"
                WHERE "leagueId"=:leagueId AND "userId"=:userId LIMIT 1'''),
                {'leagueId': league_id, 'userId': user_id}).fetchone()
            if member is None:
                raise PermissionError('Draft access denied')
        # Database I/O may outlive the credential or disconnect. Recheck after it.
        if self.tokens.get(sid) != token:
            raise PermissionError('Draft access denied')
        verified_claims(token)
        return user_id

    def deny(self, sid, league_id):
        self.socket.server.leave_room(sid, f'draft:{league_id}', namespace='/')
        self.socket.emit('draft:error', {'message': 'Draft access denied'}, to=sid)

    def deliver(self, sid, league_id, event, payload):
        try:
            self.reader(sid, league_id)
        except Exception:
            self.deny(sid, league_id)
            return False
        self.socket.emit(event, jsonSafe(payload), to=sid)
        return True
