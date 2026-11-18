import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class GameBaselineTests(unittest.TestCase):
    def setUp(self):self.m=importlib.import_module('measure_mod017_games')
    def test_exact_queries_and_fixture_counts(self):
        c={x['name']:x for x in self.m.capture_queries(100,'2026-11-13T12:00:00+00:00')}
        self.assertEqual(len(c),12)
        self.assertIn('gr."homeTeamId" = :sportTeamId OR gr."awayTeamId" = :sportTeamId',c['team_current_owner']['sql'])
        self.assertIsNone(c['team_current_no_owner']['params']['leagueId'])
        self.assertIn('NOT EXISTS',c['conference_one']['sql'])
        self.assertEqual(c['member_unknown']['expected_rows'],0)
        self.assertEqual(c['team_current_owner']['expected_rows'],2)
        self.assertEqual(c['team_past_season']['params']['seasonYear'],2025)
        self.assertEqual(self.m.game_facts(100)['games'],10000)
        self.assertEqual(self.m.game_facts(5000)['games'],500000)
    def test_count_and_sample_mismatch_refused(self):
        case={'name':'x','expected_rows':2};record={'result':{'rows':1},'client_execute_fetch_ms':{'samples':[1]*5}}
        with self.assertRaises(AssertionError):self.m.validate_result(case,record)
        record['result']['rows']=2;self.m.validate_result(case,record)
    def test_missing_provenance_cannot_retain_pass(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);manifest=path/'current.json';manifest.write_text('{"result":"PASS"}')
            connect=MagicMock()
            with patch.object(self.m.base,'ROOT',path/'missing'):
                with self.assertRaises(FileNotFoundError):self.m.run(path,manifest,[100],connect)
            connect.assert_not_called();current=json.loads(manifest.read_text());self.assertEqual(current['result'],'FAILED')
            artifact=json.loads((path/current['artifact']).read_text());self.assertEqual(artifact['cleanup'],'no database created')
    def test_independent_fixture_arithmetic_has_boundary_and_season_move(self):
        # One complete team-pair cycle: team1 is home once and away once.
        self.assertEqual(self.m.expected_games(512,teams={1}),2)
        self.assertEqual(self.m.expected_games(512,teams=set()),0)
        self.assertGreater(self.m.expected_games(5000,teams={1},window=(-77,13)),0)
        self.assertEqual(self.m.conference_teams(1,2026),set(range(2,17)))
        self.assertEqual(self.m.conference_teams(1,2025),set(range(1,17)))
        self.assertIn(1,self.m.conference_teams(2,2026))
if __name__=='__main__':unittest.main()
