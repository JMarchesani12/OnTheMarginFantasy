import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from endpoints.scoring.scoringModel import ScoringModel


class _FakeConnection:
    def __init__(self):
        self.executions = []

    def execute(self, sql, params=None):
        self.executions.append((sql, params))


class _FakeBegin:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, traceback):
        return False


class _FakeDb:
    def __init__(self):
        self.conn = _FakeConnection()

    def begin(self):
        return _FakeBegin(self.conn)


class _ScheduleStub:
    pass


class WeekZeroScoringModel(ScoringModel):
    def _get_week_by_number(self, league_id, week_number):
        return {"id": 100, "weekNumber": week_number}

    def _get_league_members(self, league_id):
        return [
            {"id": 1, "teamName": "A"},
            {"id": 2, "teamName": "B"},
        ]

    def _delete_existing_weekly_scores(self, league_id, week_id):
        self.deleted = (league_id, week_id)

    def compute_member_point_diff_for_week(self, league_id, member_id, week_number):
        return {1: 5, 2: -2}[member_id]

    def apply_weekly_tiebreakers(self, league_id, week_number, members):
        return members


class ScoringWeekZeroTests(unittest.TestCase):
    def test_compute_weekly_scores_accepts_week_zero(self):
        model = WeekZeroScoringModel(_FakeDb(), _ScheduleStub())

        result = model.compute_weekly_scores(league_id=33, week_number=0)

        self.assertEqual(result["weekNumber"], 0)
        self.assertEqual(
            result["scores"],
            [
                {
                    "memberId": 1,
                    "teamName": "A",
                    "pointDifferential": 5,
                    "rank": 1,
                    "pointsAwarded": 2,
                },
                {
                    "memberId": 2,
                    "teamName": "B",
                    "pointDifferential": -2,
                    "rank": 2,
                    "pointsAwarded": 1,
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
