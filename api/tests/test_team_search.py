"""Literal search behavior shared with the browser; no external calls or DB."""
import json
from pathlib import Path
import unittest
from utils.team_search import rank_team_search_match

ROOT = Path(__file__).resolve().parents[2]


class TeamSearchTests(unittest.TestCase):
    def test_shared_alias_and_typo_behavior(self):
        cases = json.loads((ROOT / 'tests/fixtures/team-search-cases.json').read_text())
        for case in cases:
            with self.subTest(candidate=case['candidate'], query=case['query']):
                score = rank_team_search_match(case['candidate'], case['query'], case.get('aliases',()))
                if 'score' in case: self.assertEqual(score, case['score'])
                if 'minimum' in case: self.assertGreaterEqual(score, case['minimum'])
                if 'maximum' in case: self.assertLessEqual(score, case['maximum'])

    def test_overlong_queries_do_not_search(self):
        for query in ('iowa ' * 100, 'i' * 200, 'one two three four five six seven eight nine'):
            self.assertEqual(rank_team_search_match('Iowa State', query), 0)

    def test_aliases_are_supplied_by_database_not_seed_json(self):
        self.assertEqual(rank_team_search_match('Stored Name','brand new alias',['brand new alias']),98)
        self.assertEqual(rank_team_search_match('Northern Iowa','UNI'),0)
