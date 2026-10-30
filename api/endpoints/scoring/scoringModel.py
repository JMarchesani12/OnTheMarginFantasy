"""Legacy scoring facade. Inheritance preserves established helper override hooks."""
from typing import Any, Dict, List, Optional
from .service import ScoringService
from .contracts import ScoringReadDenied


class ScoringModel(ScoringService):
    def compute_weekly_scores(self, league_id: int, week_number: int) -> Dict[str, Any]:
        return self.compute_weekly_scores_for_job(league_id, week_number)

    def compute_end_of_year_season_standings(self, league_id: int, *, reader_user_id: Optional[int] = None):
        try:
            if reader_user_id is None:
                return self.get_season_standings_for_job(league_id)
            return self.get_season_standings_for_legacy_reader(reader_user_id, league_id)
        except ScoringReadDenied as exc:
            raise PermissionError(str(exc)) from exc

    def get_weekly_points_awarded_for_league(self, league_id: int, week_numbers: List[int], *, reader_user_id: Optional[int] = None):
        try:
            if reader_user_id is None:
                return self._scoring_read_service.get_weekly_points_for_job(league_id, week_numbers)
            return self._scoring_read_service.get_weekly_points_for_legacy_reader(reader_user_id, league_id, week_numbers)
        except ScoringReadDenied as exc:
            raise PermissionError(str(exc)) from exc
