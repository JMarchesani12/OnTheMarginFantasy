"""Draft finalization authority and owned/supplied transaction orchestration."""
from actors import UserActor
from .control_repository import DraftControlRepository


class DraftControlService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else DraftControlRepository()

    def assert_commissioner(self, conn, league_id, user_id):
        league = self.repository.commissioner(conn, league_id)
        if not league:
            raise ValueError(f'League {league_id} not found')
        if int(league['commissioner']) != int(user_id):
            raise PermissionError('Only the commissioner can control this draft')

    def finalize(self, actor, league_id):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.force_finalize_for_user_id(league_id, actor.user_id)

    def force_finalize_for_user_id(self, league_id, user_id):
        if user_id is None:
            raise PermissionError('Only the commissioner can control this draft')
        with self.engine.begin() as conn:
            self.assert_commissioner(conn, league_id, user_id)
            result = self.finalize_for_job(league_id, conn=conn)
            self.assert_commissioner(conn, league_id, user_id)
            return result

    def finalize_for_job(self, league_id, conn=None):
        """Existing trusted final-pick path; supplied connection stays caller-owned."""
        if conn is not None:
            return self._finalize(conn, league_id)
        with self.engine.begin() as owned:
            return self._finalize(owned, league_id)

    def _finalize(self, conn, league_id):
        state = self.repository.finalize_state(conn, league_id)
        if not state:
            raise ValueError(f'DraftState not found for league {league_id}')
        league = self.repository.finalize_league(conn, league_id)
        return {'leagueId': league_id, 'draftComplete': True, 'state': state,
                'leagueStatus': league['leagueStatus'] if league else None}
