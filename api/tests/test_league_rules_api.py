import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
from flask import Flask
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from endpoints.league.leagueEndpoints import LeagueEndpoints
from endpoints.schedule.scheduleModel import ScheduleModel

class Row:
    def __init__(self, **values): self._mapping=values

class Result:
    def __init__(self, rows): self.rows=rows
    def fetchall(self): return self.rows

class Connection:
    def __init__(self, rows): self.rows=rows
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def execute(self,*args,**kwargs): return Result(self.rows)

class LeagueRulesApiTests(unittest.TestCase):
    def setUp(self):
        self.endpoint=LeagueEndpoints.__new__(LeagueEndpoints)
        self.endpoint.leagueModel=Mock()
        app=Flask(__name__)
        app.add_url_rule('/rules/<int:league_id>',view_func=self.endpoint.get_league_rules)
        self.client=app.test_client()

    def test_missing_league(self):
        self.endpoint.leagueModel.get_league_rules.return_value=None
        self.assertEqual(self.client.get('/rules/1').status_code,404)

    def test_invalid_version_is_visible(self):
        self.endpoint.leagueModel.get_league_rules.side_effect=ValueError('Unsupported league rules version')
        response=self.client.get('/rules/1')
        self.assertEqual(response.status_code,400)
        self.assertIn('Unsupported',response.json['message'])

    def test_payload_serializes(self):
        self.endpoint.leagueModel.get_league_rules.return_value={'version':'v1','tiers':[{'tier':1,'teams':[]}]}
        self.assertEqual(self.client.get('/rules/1').json['version'],'v1')

class ScheduleRulesIntegrationTests(unittest.TestCase):
    def test_home_away_and_double_ownership_use_resolved_rules(self):
        for home,away,expected,applied in [(True,False,11,True),(False,True,42,True),(True,True,0,False)]:
            with self.subTest(home=home,away=away):
                row=Row(rawMemberPointDiff=21,ownsHome=home,ownsAway=away,homeTeamTier=1,awayTeamTier=3,sportId=1)
                db=Mock()
                db.begin.return_value=Connection([row])
                model=ScheduleModel(db,'https://example.test')
                model._get_league=Mock(return_value={'sport':1,'settings':{}})
                game=model.get_member_games_for_week(1,2,3)[0]
                self.assertEqual(game['memberPointDiff'],expected)
                self.assertEqual(game['tierAdjustment']['applied'],applied)
                self.assertNotIn('ruleSettings',game)

class EmptyScheduleRulesTests(unittest.TestCase):
    def test_unknown_version_is_rejected_even_without_games(self):
        db=Mock()
        db.begin.return_value=Connection([])
        model=ScheduleModel(db,'https://example.test')
        model._get_league=Mock(return_value={'sport':1,'settings':{'ruleSetVersion':'unknown'}})
        with self.assertRaises(ValueError):
            model.get_member_games_for_week(1,2,3)

class LeagueRulesModelTests(unittest.TestCase):
    def model(self, responses):
        from endpoints.league.leagueModel import LeagueModel
        model=LeagueModel.__new__(LeagueModel)
        conn=Mock()
        conn.execute.side_effect=responses
        context=Mock()
        context.__enter__=Mock(return_value=conn)
        context.__exit__=Mock(return_value=False)
        model.db=Mock()
        model.db.connect.return_value=context
        model.db.begin.return_value=context
        return model,conn

    def test_rules_model_sorts_tiers_and_teams(self):
        league=Row(id=7,name='Test league',sport=1,seasonYear=2026,settings={},tradeDeadline='2026-12-01T00:00:00Z',freeAgentDeadline=None,draftDate=None)
        first=Mock(); first.fetchone.return_value=league
        teams=Mock(); teams.fetchall.return_value=[Row(teamId=1,teamName='Zulu',tier=2),Row(teamId=2,teamName='Beta',tier=1),Row(teamId=3,teamName='Alpha',tier=1)]
        model,conn=self.model([first,teams])
        payload=model.get_league_rules(7)
        self.assertEqual(payload['version'],'v1')
        self.assertEqual(payload['settings']['tradeDeadline'], '2026-12-01T00:00:00Z')
        self.assertIn('blocked after', ' '.join(p for section in payload['sections'] for p in section['paragraphs']))
        self.assertEqual([g['tier'] for g in payload['tiers']],[1,2])
        self.assertEqual([t['teamName'] for t in payload['tiers'][0]['teams']],['Alpha','Beta'])
        self.assertEqual(conn.execute.call_count,2)

    def test_missing_rules_league_does_not_query_teams(self):
        result=Mock(); result.fetchone.return_value=None
        model,conn=self.model([result])
        self.assertIsNone(model.get_league_rules(5))
        self.assertEqual(conn.execute.call_count,1)

    def test_settings_update_preserves_version_in_database_write(self):
        import json
        first=Mock(); first.fetchone.return_value=Row(id=1,sport=1,settings={'ruleSetVersion':'v1'})
        second=Mock(); second.mappings.return_value.first.return_value={'id':1}
        model,conn=self.model([first,second])
        model.update_league(1,{'settings':{'bonuses':{}}})
        self.assertEqual(json.loads(conn.execute.call_args.args[1]['settings'])['ruleSetVersion'],'v1')

    def test_version_change_rejected_before_database_write(self):
        first=Mock(); first.fetchone.return_value=Row(id=1,sport=1,settings={})
        model,conn=self.model([first])
        with self.assertRaises(ValueError):
            model.update_league(1,{'settings':{'ruleSetVersion':'v2'}})
        self.assertEqual(conn.execute.call_count,1)
