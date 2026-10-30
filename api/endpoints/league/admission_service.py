"""Commissioner listing and applicant cancellation authority/transaction scope."""
from actors import UserActor
from .admission_repository import AdmissionRepository
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
