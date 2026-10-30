"""Admission request policy and transaction ownership, independent of transport."""
from actors import UserActor
from .repository import AdmissionRepository
from .contracts import AdmissionDenied, AdmissionRejected


class AdmissionService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else AdmissionRepository()

    @staticmethod
    def _actor_id(actor):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return actor.user_id

    @staticmethod
    def _require_user_id(user_id):
        if isinstance(user_id, bool) or not isinstance(user_id, int):
            raise TypeError('A verified integer user ID is required')

    def list_requests(self, actor, league_id, status=None):
        return self.list_requests_for_legacy_reader(self._actor_id(actor), league_id, status)

    def list_requests_for_legacy_reader(self, user_id, league_id, status=None):
        self._require_user_id(user_id)
        with self.engine.begin() as conn:
            commissioner = self.repository.commissioner(conn, league_id)
            if commissioner is None:
                raise AdmissionRejected(f'League {league_id} not found')
            if commissioner != user_id:
                raise AdmissionDenied('Only the commissioner can perform this action')
            return self.repository.list_requests(conn, league_id, status, user_id)

    def list_requests_for_job(self, league_id, status=None):
        with self.engine.begin() as conn:
            return self.repository.list_requests(conn, league_id, status)

    def list_requests_for_legacy_scope(self, user_id, league_id, status=None):
        """Preserve the private model helper: scoped query without initial denial."""
        self._require_user_id(user_id)
        with self.engine.begin() as conn:
            return self.repository.list_requests(conn, league_id, status, user_id)

    def get_commissioner_for_job(self, league_id):
        with self.engine.begin() as conn:
            return self.repository.commissioner(conn, league_id)

    def cancel_request(self, actor, league_id, request_id):
        return self.cancel_request_for_owner_id(self._actor_id(actor), league_id, request_id)

    def cancel_request_for_owner_id(self, user_id, league_id, request_id):
        self._require_user_id(user_id)
        with self.engine.begin() as conn:
            req = self.repository.lock_request(conn, league_id, request_id)
            if not req:
                raise AdmissionRejected('Join request not found')
            if req['userId'] != user_id:
                raise AdmissionDenied("Cannot cancel another user's request")
            if req['status'] != 'PENDING':
                raise AdmissionRejected('Only pending requests can be cancelled')
            updated = self.repository.cancel_pending(conn, league_id, request_id, user_id)
        return dict(updated)

    def create_request(self, actor, league_id, message=None, team_name=None):
        return self.create_request_for_user_id(self._actor_id(actor), league_id, message, team_name)

    def create_request_for_user_id(self, user_id, league_id, message=None, team_name=None):
        self._require_user_id(user_id)
        if not isinstance(team_name, str) or not team_name.strip():
            raise AdmissionRejected('Team name is required.')
        team_name = team_name.strip()
        with self.engine.begin() as conn:
            if self.repository.is_member(conn, league_id, user_id):
                raise AdmissionRejected('Already a member of this league')
            existing = self.repository.pending_request(conn, league_id, user_id)
            if existing:
                return existing
            row = self.repository.insert_request(conn, league_id, user_id, message, team_name)
            if not row:
                raise RuntimeError('Failed to create join request')
            return row

    def deny_request(self, actor, league_id, request_id):
        return self.deny_request_for_legacy_commissioner(self._actor_id(actor), league_id, request_id)

    def deny_request_for_legacy_commissioner(self, user_id, league_id, request_id):
        self._require_user_id(user_id)
        with self.engine.begin() as conn:
            league = self.repository.lock_league(conn, league_id)
            if not league:
                raise AdmissionRejected(f'League {league_id} not found')
            if league['commissioner'] != user_id:
                raise AdmissionDenied('Only the commissioner can perform this action')
            return self.deny_request_in_transaction(conn, league_id, request_id, user_id)

    def deny_request_for_job(self, league_id, request_id, acting_user_id):
        """Existing trusted operation; HTTP cannot select this via a job flag."""
        with self.engine.begin() as conn:
            self.repository.lock_league_for_job(conn, league_id)
            return self.deny_request_in_transaction(conn, league_id, request_id, acting_user_id)

    def deny_request_in_transaction(self, conn, league_id, request_id, acting_user_id):
        req = self.repository.lock_request_for_denial(conn, league_id, request_id)
        if not req:
            raise AdmissionRejected('Join request not found')
        if req['status'] != 'PENDING':
            raise AdmissionRejected('Join request is not pending')
        updated = self.repository.deny_pending(conn, league_id, request_id, acting_user_id)
        return dict(updated)

    def approve_request(self, actor, league_id, request_id):
        return self.approve_request_for_legacy_commissioner(self._actor_id(actor), league_id, request_id)

    def approve_request_for_legacy_commissioner(self, user_id, league_id, request_id):
        self._require_user_id(user_id)
        with self.engine.begin() as conn:
            league = self.repository.lock_league(conn, league_id)
            if not league:
                raise AdmissionRejected(f'League {league_id} not found')
            if league['commissioner'] != user_id:
                raise AdmissionDenied('Only the commissioner can perform this action')
            return self.approve_request_in_transaction(conn, league_id, request_id, user_id)

    def approve_request_for_job(self, league_id, request_id, acting_user_id):
        """Trusted legacy approval; HTTP always selects checked actor approval."""
        with self.engine.begin() as conn:
            self.repository.lock_league_for_job(conn, league_id)
            return self.approve_request_in_transaction(conn, league_id, request_id, acting_user_id)

    def approve_request_in_transaction(self, conn, league_id, request_id, acting_user_id):
        req = self.repository.lock_request_for_approval(conn, league_id, request_id)
        if not req:
            raise AdmissionRejected('Join request not found')
        if req['status'] != 'PENDING':
            raise AdmissionRejected('Join request is not pending')
        self.repository.insert_member(conn, league_id, req['userId'], req.get('teamName') or 'My Team')
        self.repository.update_capacity(conn, league_id)
        updated = self.repository.approve_pending(conn, league_id, request_id, acting_user_id)
        member = self.repository.member_for_request(conn, league_id, req['userId'])
        return {'request': dict(updated), 'member': dict(member) if member else None}
