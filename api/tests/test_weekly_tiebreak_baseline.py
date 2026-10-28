"""J4/K7 rule slice: real tie resolution with hand-derived stored-game inputs."""
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from endpoints.scoring.scoringModel import ScoringModel


class WeeklyTiebreakBaselineTests(unittest.TestCase):
    def tied_members(self):
        return [{"memberId": 1, "teamName": "Alpha", "pointDifferential": 10},
                {"memberId": 2, "teamName": "Beta", "pointDifferential": 10},
                {"memberId": 3, "teamName": "Gamma", "pointDifferential": -5}]

    def test_head_to_head_winner_precedes_single_margin_without_reordering_non_tied_members(self):
        schedule = Mock()
        schedule.get_head_to_head_games.return_value = [{
            "homeScore": 13, "awayScore": 20,
            "homeOwnedByA": True, "awayOwnedByA": False,
            "homeOwnedByB": False, "awayOwnedByB": True,
        }]
        # Alpha's larger single-game margin must not override Beta's H2H win.
        schedule.get_member_games_for_week.side_effect = lambda **kw: [
            {"memberPointDiff": 100 if kw['member_id'] == 1 else 7}]
        result = ScoringModel(None, schedule).apply_weekly_tiebreakers(7, 2, self.tied_members())
        self.assertEqual([m["memberId"] for m in result], [2, 1, 3])
        self.assertEqual([m["pointDifferential"] for m in result], [10, 10, -5])

    def test_no_head_to_head_result_falls_back_to_largest_absolute_game_margin(self):
        schedule = Mock()
        schedule.get_head_to_head_games.return_value = []
        schedule.get_member_games_for_week.side_effect = lambda **kw: [
            {"memberPointDiff": 5 if kw['member_id'] == 1 else -12}]
        result = ScoringModel(None, schedule).apply_weekly_tiebreakers(7, 2, self.tied_members())
        self.assertEqual([m["memberId"] for m in result], [2, 1, 3])
        self.assertEqual(result[-1], {"memberId": 3, "teamName": "Gamma", "pointDifferential": -5})
