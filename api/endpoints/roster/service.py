"""Roster access and week-selection orchestration, independent of Flask."""
from actors import UserActor
from .contracts import RosterAccessDenied, RosterWeekUnavailable
from .repository import RosterRepository


class RosterService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else RosterRepository()

    @staticmethod
    def _require_actor(actor):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')

    @staticmethod
    def _require_legacy_reader(user_id):
        if isinstance(user_id, bool) or not isinstance(user_id, int):
            raise TypeError('A verified integer reader is required')

    def get_member_teams_for_week(self, actor, league_id, member_id, week_number):
        self._require_actor(actor)
        return self.get_member_teams_for_legacy_reader(actor.user_id, league_id, member_id, week_number)

    def get_available_teams_for_week(self, actor, league_id, week_number):
        self._require_actor(actor)
        return self.get_available_teams_for_legacy_reader(actor.user_id, league_id, week_number)

    def get_member_teams_for_legacy_reader(self, user_id, league_id, member_id, week_number):
        self._require_legacy_reader(user_id)
        with self.engine.connect() as conn:
            if not self.repository.member_read_allowed(conn, league_id, member_id, user_id):
                raise RosterAccessDenied('League member not found')
            return self._member_teams(conn, league_id, member_id, week_number, user_id)

    def get_available_teams_for_legacy_reader(self, user_id, league_id, week_number):
        self._require_legacy_reader(user_id)
        with self.engine.connect() as conn:
            return self._available_teams(conn, league_id, week_number, user_id)

    def get_member_teams_for_job(self, league_id, member_id, week_number):
        with self.engine.connect() as conn:
            return self._member_teams(conn, league_id, member_id, week_number)

    def get_available_teams_for_job(self, league_id, week_number):
        with self.engine.connect() as conn:
            return self._available_teams(conn, league_id, week_number)

    def next_unlocked_week_in_transaction(self, conn, league_id, week_number):
        next_week = self.repository.next_unlocked_week_number(conn, league_id, week_number)
        if next_week is None:
            raise RosterWeekUnavailable(f'No unlocked future week found after week {week_number}')
        return next_week

    def _resolve_week(self, conn, league_id, week_number):
        info = self.repository.get_week_by_number(conn, league_id, week_number)
        if info and info.get('isLocked'):
            week_number = self.next_unlocked_week_in_transaction(conn, league_id, week_number)
        return week_number, info

    def _member_teams(self, conn, league_id, member_id, week_number, reader_user_id=None):
        week_number, _ = self._resolve_week(conn, league_id, week_number)
        return self.repository.member_teams(conn, league_id, member_id, week_number, reader_user_id)

    def _available_teams(self, conn, league_id, week_number, reader_user_id=None):
        league = self.repository.get_league(conn, league_id, reader_user_id)
        if reader_user_id is not None and league is None:
            raise RosterAccessDenied('League not found')
        week_number, info = self._resolve_week(conn, league_id, week_number)
        if info and info.get('isLocked'):
            info = self.repository.get_week_by_number(conn, league_id, week_number)
        # Preserve legacy trusted behavior: week resolution precedes missing league.
        if league is None:
            return []
        week_id = int(info['id']) if info else None
        return self.repository.available_teams(conn, league_id, league['sport'],
                                               league['seasonYear'], week_id, week_number,
                                               reader_user_id)
