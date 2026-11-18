"""Explicit authorized refresh/read boundary; ordinary readers never synchronize."""
from actors import UserActor
from .repository import LeagueLifecycleRepository
from ..reads.service import LeagueReadService


class LifecycleRefreshConflict(Exception):
    """The bounded first-draft-state race could not settle; caller may retry."""


class _DraftStateAppeared(Exception):
    pass


class LeagueLifecycleQueryService:
    def __init__(self, engine, repository=None, read_service=None):
        self.engine = engine
        self.repository = repository if repository is not None else LeagueLifecycleRepository()
        self.reader = read_service if read_service is not None else LeagueReadService(engine)

    def details(self, actor, league_id):
        return self._query(actor, league_id=league_id)

    def mine(self, actor, stage='all'):
        return self._query(actor, stage=stage)

    def _query(self, actor, league_id=None, stage='all'):
        if not isinstance(actor, UserActor) or isinstance(actor.user_id, bool) or not isinstance(actor.user_id, int):
            raise TypeError('A verified UserActor is required')
        for attempt in range(2):
            try:
                with self.engine.connect() as raw:
                    conn = raw.execution_options(isolation_level='READ COMMITTED')
                    with conn.begin():
                        candidates = sorted(set(self.repository.candidate_ids(conn, actor.user_id, league_id)))
                        eligible = []
                        for target in candidates:
                            had_state = self.repository.lock_state(conn, target)
                            if not self.repository.lock_league(conn, target):
                                continue
                            if not had_state and self.repository.state_exists(conn, target):
                                # Never acquire a newly created state lock while holding League.
                                raise _DraftStateAppeared()
                            if self.repository.authorized(conn, target, actor.user_id, league_id is None):
                                eligible.append(target)
                        if not eligible:
                            result = [] if league_id is None else None
                        else:
                            for phase in ('mark_pre_draft', 'mark_drafting', 'mark_post_draft', 'mark_in_season', 'mark_completed'):
                                getattr(self.repository, phase)(conn, eligible, actor.user_id, league_id is None)
                            if league_id is None:
                                result = self.reader.mine_in_transaction(conn, actor.user_id, stage, eligible)
                            else:
                                result = self.reader.details_in_transaction(conn, league_id, actor.user_id)
                    return result  # The transaction committed before the payload escapes.
            except _DraftStateAppeared:
                if attempt:
                    raise LifecycleRefreshConflict() from None
        raise AssertionError('Unreachable lifecycle retry state')
