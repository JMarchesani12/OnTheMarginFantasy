"""Own-profile policy and transaction ownership, independent of Flask."""
from actors import UserActor
from sqlalchemy.exc import IntegrityError
from .contracts import ALLOWED_USER_FIELDS, ProfileAccessDenied, ProfileNotFound, ProfileUpdateRejected
from .contracts import (ProfileSubject, ProfileAlreadyExists, ProfileIdentityAmbiguous,
                        ProfileCreationRejected)
from .repository import UserRepository


class UserService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else UserRepository()

    def create_profile(self, actor, display_name=None):
        if not isinstance(actor, ProfileSubject):
            raise TypeError('A verified ProfileSubject is required')
        if not isinstance(actor.subject, str) or not actor.subject.strip():
            raise ProfileCreationRejected('A verified subject is required')
        if not isinstance(actor.email, str) or not actor.email.strip():
            raise ProfileCreationRejected('email is required')
        if display_name is not None and not isinstance(display_name, str):
            raise ProfileCreationRejected('displayName must be a string')
        email, name = self._creation_values(actor.email, display_name)
        try:
            with self.engine.begin() as conn:
                matches = self.repository.profile_ids_for_subject(conn, actor.subject)
                if len(matches) > 1:
                    raise ProfileIdentityAmbiguous('Application identity is ambiguous')
                if matches:
                    raise ProfileAlreadyExists('User already exists')
                return self._insert_profile(conn, email, name, actor.subject)
        except IntegrityError as exc:
            raise ProfileCreationRejected('User creation failed') from exc

    @staticmethod
    def _creation_values(email, display_name):
        # Preserve the legacy direct-call normalization/validation contract.
        if not email or not email.strip():
            raise ProfileCreationRejected('email is required')
        return email.strip(), (display_name or '').strip()

    def _insert_profile(self, conn, email, display_name, uuid):
        row = self.repository.insert(conn, email, display_name, uuid)
        if row is None:
            raise RuntimeError('Failed to insert User')
        return row

    def create_profile_for_job(self, email, display_name=None, uuid=None):
        email, name = self._creation_values(email, display_name)
        try:
            with self.engine.begin() as conn:
                return self._insert_profile(conn, email, name, uuid)
        except IntegrityError as exc:
            raise ProfileCreationRejected('User creation failed') from exc

    def get_profile_by_uuid_for_job(self, uuid):
        with self.engine.begin() as conn:
            row = self.repository.get_by_uuid(conn, uuid)
        if row is None:
            raise ProfileNotFound('User not found')
        return row

    def require_profile_owner(self, actor, user_id):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        if user_id != actor.user_id:
            raise ProfileAccessDenied('User not found')

    def get_profile(self, actor, user_id):
        self.require_profile_owner(actor, user_id)
        return self.get_profile_for_job(user_id)

    def update_profile(self, actor, user_id, updates):
        self.require_profile_owner(actor, user_id)
        return self.update_profile_for_job(user_id, updates)

    def get_profile_for_job(self, user_id):
        with self.engine.begin() as conn:
            row = self.repository.get_by_id(conn, user_id)
        if row is None:
            raise ProfileNotFound('User not found')
        return row

    def update_profile_for_job(self, user_id, updates):
        payload = {key: updates[key] for key in updates.keys() if key in ALLOWED_USER_FIELDS}
        if not payload:
            raise ProfileUpdateRejected('No valid fields provided to update')
        with self.engine.begin() as conn:
            row = self.repository.update(conn, user_id, payload)
        if row is None:
            raise ProfileNotFound('User not found')
        return row
