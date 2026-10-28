"""Interactive HTTP identity boundary for adapters opting into authorization.

Only authMiddleware's verified g.user supplies identity. This module does not
import a configured engine or provision profiles. Trusted jobs should call
transport-independent domain/model functions, never synthesize an HTTP principal.
"""
from dataclasses import dataclass

from flask import g, has_request_context
from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    subject: str
    user_id: int


class PrincipalResolutionError(Exception):
    """Explicit denial for adopting HTTP adapters to translate into JSON."""

    def __init__(self, code: str, status_code: int):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def verified_request_subject() -> str:
    """Read a verified HTTP subject even before an application profile exists.

    This is the bootstrap primitive, not an application principal or job bypass.
    Call only after authMiddleware has populated g.user from a verified JWT.
    """
    if not has_request_context():
        raise PrincipalResolutionError('interactive_request_required', 401)

    claims = getattr(g, 'user', None)
    subject = claims.get('sub') if isinstance(claims, dict) else None
    if not isinstance(subject, str) or not subject.strip():
        raise PrincipalResolutionError('missing_authenticated_subject', 401)

    return subject


def resolve_authenticated_principal(db: Engine) -> AuthenticatedPrincipal:
    """Map a middleware-verified subject to exactly one application User.

    Call after install_auth_middleware has authenticated the request. Public
    routes and OPTIONS do not acquire identity automatically. No caller-supplied
    actor, UUID, email or job flag is accepted. Database failures propagate as
    operational errors; they never select a fallback identity. No result is
    cached across requests, so missing/ambiguous mappings fail on each lookup.
    """
    subject = verified_request_subject()

    with db.begin() as conn:
        rows = conn.execute(text('''
            SELECT id FROM "User" WHERE uuid = :subject LIMIT 2
        '''), {'subject': subject}).mappings().fetchmany(2)

    if not rows:
        raise PrincipalResolutionError('application_identity_not_found', 403)
    if len(rows) != 1:
        raise PrincipalResolutionError('application_identity_ambiguous', 403)
    return AuthenticatedPrincipal(subject=subject, user_id=rows[0]['id'])
