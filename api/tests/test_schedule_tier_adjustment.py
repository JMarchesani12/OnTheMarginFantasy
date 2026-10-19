import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from endpoints.schedule.scheduleModel import ScheduleModel


class TierAdjustedPointDiffTests(unittest.TestCase):
    def test_basketball_same_and_adjacent_tiers_keep_full_margin(self):
        for owned_tier, opponent_tier in [(1, 1), (1, 2), (2, 1), (6, 7), (7, 6)]:
            for margin in [21, -21, 0]:
                with self.subTest(owned=owned_tier, opponent=opponent_tier, margin=margin):
                    self.assertEqual(
                        ScheduleModel._apply_tier_adjustment(
                            margin, owned_tier, opponent_tier, sport_id=1
                        ),
                        margin,
                    )

    def test_basketball_two_or_more_tiers_use_fixed_half_or_double_margin(self):
        for higher_tier, lower_tier in [(1, 3), (1, 4), (3, 5), (2, 10)]:
            for owned, opponent, margin, expected in [
                (higher_tier, lower_tier, 21, 11),
                (higher_tier, lower_tier, -21, -42),
                (lower_tier, higher_tier, 21, 42),
                (lower_tier, higher_tier, -21, -11),
                (higher_tier, lower_tier, 20, 10),
                (lower_tier, higher_tier, -20, -10),
                (higher_tier, lower_tier, 0, 0),
            ]:
                with self.subTest(owned=owned, opponent=opponent, margin=margin):
                    self.assertEqual(
                        ScheduleModel._apply_tier_adjustment(
                            margin, owned, opponent, sport_id=1
                        ),
                        expected,
                    )

    def test_football_still_adjusts_at_one_tier(self):
        self.assertEqual(ScheduleModel._apply_tier_adjustment(21, 1, 2, sport_id=2), 11)
        self.assertEqual(ScheduleModel._apply_tier_adjustment(-21, 1, 2, sport_id=2), -42)
        self.assertEqual(ScheduleModel._apply_tier_adjustment(21, 2, 1, sport_id=2), 42)
        self.assertEqual(ScheduleModel._apply_tier_adjustment(-21, 2, 1, sport_id=2), -11)

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

    def test_doubles_win_margin_for_lower_tier_team_against_higher_tier_opponent(self):
        self.assertEqual(
            ScheduleModel._apply_tier_adjustment(
                raw_point_diff=10,
                owned_team_tier=2,
                opponent_team_tier=1,
            ),
            20,
        )

    def test_halves_loss_margin_for_lower_tier_team_against_higher_tier_opponent(self):
        self.assertEqual(
            ScheduleModel._apply_tier_adjustment(
                raw_point_diff=-10,
                owned_team_tier=2,
                opponent_team_tier=1,
            ),
            -5,
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
