"""Weekly-points read policy and connection ownership; no calculation/provider I/O."""
from actors import UserActor
from .contracts import ScoringReadDenied
from .repository import ScoringRepository


class ScoringReadService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository if repository is not None else ScoringRepository()

    @staticmethod
    def _normalize_weeks(week_numbers):
        if not week_numbers:
            return []
        return sorted({int(w) for w in week_numbers if int(w) >= 0})

    def get_weekly_points(self, actor, league_id, week_numbers):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.get_weekly_points_for_legacy_reader(actor.user_id, league_id, week_numbers)

    def get_weekly_points_for_legacy_reader(self, user_id, league_id, week_numbers):
        if isinstance(user_id, bool) or not isinstance(user_id, int):
            raise TypeError('A verified integer reader is required')
        rows = []
        with self.engine.connect() as conn:
            allowed = self.repository.league_read_allowed(conn, league_id, user_id)
            if allowed:
                weeks = self._normalize_weeks(week_numbers)
                if weeks:
                    rows = self.repository.weekly_points(conn, league_id, weeks)
                allowed = self.repository.league_read_allowed(conn, league_id, user_id)
        # Match the existing guard's denial after its read connection closes.
        if not allowed:
            raise ScoringReadDenied('League not found')
        return rows

    def get_weekly_points_for_job(self, league_id, week_numbers):
        weeks = self._normalize_weeks(week_numbers)
        if not weeks:
            return []
        with self.engine.connect() as conn:
            return self.repository.weekly_points(conn, league_id, weeks)
