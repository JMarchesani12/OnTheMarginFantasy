import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from endpoints.league.leagueModel import LeagueModel


class LeagueTeamNameTests(unittest.TestCase):
    def setUp(self):
        self.model = LeagueModel.__new__(LeagueModel)
        self.model.db = MagicMock()

    def test_creation_requires_nonblank_string_before_database_access(self):
        for value in [None, '', '   ', 42]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'Team name is required'):
                self.model.create_league({'teamName': value})
        self.model.db.begin.assert_not_called()

    def test_join_requires_nonblank_string_before_database_access(self):
        for value in [None, '', '   ', 42]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'Team name is required'):
                self.model.create_join_request(1, 2, team_name=value)
        self.model.db.begin.assert_not_called()

    def test_join_stores_trimmed_team_name(self):
        conn = self.model.db.begin.return_value.__enter__.return_value
        conn.execute.return_value.fetchone.return_value = None
        conn.execute.return_value.mappings.return_value.first.side_effect = [None, {'id': 3}]
        self.assertEqual(self.model.create_join_request(1, 2, team_name='  Margin Makers  '), {'id': 3})
        sql, params = conn.execute.call_args.args
        self.assertIn(':teamName', str(sql))
        self.assertEqual(params['teamName'], 'Margin Makers')


if __name__ == '__main__':
    unittest.main()
