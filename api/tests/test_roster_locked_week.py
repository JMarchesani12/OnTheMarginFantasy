import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from endpoints.roster.rosterModel import RosterModel


class _FakeRow:
    def __init__(self, mapping):
        self._mapping = mapping

    def __getitem__(self, index):
        return tuple(self._mapping.values())[index]


class _FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)


class _FakeConnection:
    def __init__(self):
        self.executions = []

    def execute(self, sql, params=None):
        self.executions.append((str(sql), params))
        query = str(sql)

        if 'FROM "Week"' in query and '"weekNumber" > :week_number' in query:
            return _FakeResult([_FakeRow({"weekNumber": 2})])

        if 'FROM "Week"' in query and params["week_number"] == 1:
            return _FakeResult([
                _FakeRow({"id": 101, "weekNumber": 1, "isLocked": True})
            ])

        if 'FROM "Week"' in query and params["week_number"] == 2:
            return _FakeResult([
                _FakeRow({"id": 102, "weekNumber": 2, "isLocked": False})
            ])

        return _FakeResult([])


class _FakeConnect:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, traceback):
        return False


class _FakeDb:
    def __init__(self):
        self.conn = _FakeConnection()

    def connect(self):
        return _FakeConnect(self.conn)


class RosterLockedWeekTests(unittest.TestCase):
    def test_member_teams_forward_locked_week_to_next_unlocked_week(self):
        model = RosterModel(_FakeDb())

        model.get_member_teams_for_week(
            league_id=7,
            member_id=42,
            week_number=1,
        )

        roster_query_params = [
            params
            for query, params in model.db.conn.executions
            if 'FROM "LeagueTeamSlot" lts' in query
        ]
        self.assertEqual(roster_query_params[0]["weekNumber"], 2)


if __name__ == "__main__":
    unittest.main()
