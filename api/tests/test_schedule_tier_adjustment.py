import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from endpoints.schedule.scheduleModel import ScheduleModel


class TierAdjustedPointDiffTests(unittest.TestCase):
    def test_halves_win_margin_against_lower_tier_opponent_rounding_up(self):
        self.assertEqual(
            ScheduleModel._apply_tier_adjustment(
                raw_point_diff=21,
                owned_team_tier=1,
                opponent_team_tier=3,
            ),
            11,
        )

    def test_doubles_loss_margin_against_lower_tier_opponent(self):
        self.assertEqual(
            ScheduleModel._apply_tier_adjustment(
                raw_point_diff=-7,
                owned_team_tier=1,
                opponent_team_tier=3,
            ),
            -14,
        )

    def test_keeps_margin_for_same_tier_opponent(self):
        self.assertEqual(
            ScheduleModel._apply_tier_adjustment(
                raw_point_diff=21,
                owned_team_tier=2,
                opponent_team_tier=2,
            ),
            21,
        )

    def test_keeps_margin_when_team_tier_is_unknown(self):
        self.assertEqual(
            ScheduleModel._apply_tier_adjustment(
                raw_point_diff=21,
                owned_team_tier=None,
                opponent_team_tier=3,
            ),
            21,
        )


if __name__ == "__main__":
    unittest.main()
