"""Resource authorization predicates for model operations with verified actors.

HTTP adapters resolve principals; trusted callers retain separate model entry
semantics. These checks never derive identity from client data or job flags.
"""
from contextlib import contextmanager
from sqlalchemy import text


def require_owned_league_member(conn, league_id: int, member_id: int, user_id: int):
    """Deny missing/foreign members uniformly; commissioner status grants no ownership.

    Call with a verified actor at the operation's transaction boundaries. This
    query does not establish locks or promise revocation after the final check.
    """
    row = conn.execute(text('''
        SELECT lm.id FROM "LeagueMember" lm
        JOIN "League" l ON l.id = lm."leagueId"
        WHERE lm.id = :member_id AND lm."leagueId" = :league_id
          AND lm."userId" = :user_id
    '''), {'league_id': league_id, 'member_id': member_id, 'user_id': user_id}).fetchone()
    if row is None:
        raise PermissionError('League member not found')


@contextmanager
def league_read_access(db, league_id: int, reader_user_id):
    """Guard multi-query reads before work and before returning their payload.

    Reuse the established full-read policy; None preserves trusted model reads.
    No lock or concurrent-revocation-after-final-check guarantee is established.
    """
    if reader_user_id is None:
        yield
        return
    from endpoints.league.leagueModel import LeagueModel
    scope, params = LeagueModel._league_read_scope(league_id, reader_user_id)

    def require_access():
        with db.connect() as conn:
            row = conn.execute(text(
                'SELECT id FROM "League" WHERE id = :leagueId ' + scope
            ), {'leagueId': league_id, **params}).fetchone()
            if row is None:
                raise PermissionError('League not found')

    require_access()
    yield
    require_access()
