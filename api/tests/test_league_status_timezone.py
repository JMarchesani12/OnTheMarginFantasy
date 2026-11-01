import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from endpoints.league.leagueModel import LeagueModel


class LeagueStatusTimezoneTests(unittest.TestCase):
    def statements(self):
        model = LeagueModel.__new__(LeagueModel)
        model.db = MagicMock()
        model.sync_due_league_statuses()
        conn = model.db.begin.return_value.__enter__.return_value
        return [str(call.args[0]) for call in conn.execute.call_args_list]

    def test_season_transitions_do_not_use_database_calendar_date(self):
        statements = self.statements()
        transitions = [sql for sql in statements if 'ss."seasonStart"' in sql or 'ss."seasonEnd"' in sql]
        self.assertEqual(len(transitions), 3)
        for sql in transitions:
            self.assertNotIn('now()::date', sql)
            self.assertIn('AT TIME ZONE', sql)
            self.assertIn("l.settings", sql)

    def test_post_draft_requires_a_completed_draft(self):
        sql = next(sql for sql in self.statements() if "SET status = 'Post-Draft'" in sql)
        self.assertIn("AND ds.status = 'complete'", sql)
        self.assertNotIn("OR l.status = 'In-Season'", sql)
        self.assertIn("l.status <> 'Completed'", sql)

    def test_undrafted_league_is_pre_draft_even_without_a_draft_date(self):
        sql = next(sql for sql in self.statements() if "SET status = 'Pre-Draft'" in sql)
        self.assertNotIn('l."draftDate" IS NOT NULL', sql)
        self.assertIn("'Completed'", sql)
        self.assertIn("NOT EXISTS", sql)
        self.assertIn("('live', 'paused', 'complete')", sql)

    def test_season_start_does_not_override_an_unfinished_draft(self):
        sql = next(sql for sql in self.statements() if "SET status = 'In-Season'" in sql)
        self.assertIn("AND EXISTS", sql)
        self.assertIn("ds.status = 'complete'", sql)
