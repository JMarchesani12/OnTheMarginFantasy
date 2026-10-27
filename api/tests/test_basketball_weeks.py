import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from endpoints.schedule.scheduleModel import ScheduleModel


class BasketballWeeksTests(unittest.TestCase):
    def model(self, sport=1, start=dt.date(2026, 11, 2)):
        model = ScheduleModel(Mock(), '')
        model._get_sport_season_for_league = lambda _: dict(
            sportId=sport, sportSeasonId=1, regularSeasonStart=start,
            regularSeasonEnd=dt.date(2026, 11, 22), allSubdivisions=False)
        model._get_league_timezone = lambda _: ZoneInfo('America/New_York')
        model._get_week_start_weekday = lambda _: 0
        model._get_season_phases = lambda _: []
        return model

    def test_early_game_counts_in_week_one_without_shifting_later_weeks(self):
        boundaries = self.model().get_week_boundaries(1)
        self.assertEqual([n for n, _, _ in boundaries], [1, 2, 3])
        early_game = dt.datetime(2026, 11, 1, 18, tzinfo=dt.timezone.utc)
        self.assertTrue(boundaries[0][1] <= early_game <= boundaries[0][2])
        self.assertEqual(boundaries[1][1], dt.datetime(2026, 11, 9, 5, tzinfo=dt.timezone.utc))
        for previous, following in zip(boundaries, boundaries[1:]):
            self.assertEqual(previous[2] + dt.timedelta(microseconds=1), following[1])

    def test_partial_opening_is_merged_into_first_full_week(self):
        boundaries = self.model(start=dt.date(2026, 11, 1)).get_week_boundaries(1)
        self.assertEqual(boundaries[0][0], 1)
        self.assertEqual(boundaries[0][2], dt.datetime(2026, 11, 9, 4, 59, 59, 999999, tzinfo=dt.timezone.utc))

    def test_new_basketball_leagues_do_not_insert_week_zero(self):
        model = self.model()
        model._get_existing_weeks = lambda _: []
        model._insert_week0 = Mock()
        model._insert_weeks = Mock(return_value=[dict(weekNumber=1)])
        model.ensure_weeks_for_league(1)
        model._insert_week0.assert_not_called()

    def test_football_retains_week_zero(self):
        self.assertEqual(self.model(sport=2).get_week_boundaries(1)[0][0], 0)
