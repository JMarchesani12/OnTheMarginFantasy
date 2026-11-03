"""Profile policy and domain failures; no transport status codes."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileSubject:
    """Verified-claims input for bootstrap, before an application user exists.

    Construction alone does not authenticate a caller; HTTP uses JWT claims.
    """
    subject: str
    email: str


ALLOWED_USER_FIELDS = {'displayName': '"displayName"'}


class ProfileAccessDenied(Exception):
    code = 'profile_access_denied'


class ProfileNotFound(Exception):
    code = 'profile_not_found'


class ProfileUpdateRejected(Exception):
    code = 'profile_update_rejected'


class ProfileAlreadyExists(Exception):
    code = 'profile_already_exists'


class ProfileIdentityAmbiguous(Exception):
    code = 'application_identity_ambiguous'


class ProfileCreationRejected(Exception):
    code = 'profile_creation_rejected'
