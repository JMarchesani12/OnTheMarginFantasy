"""Actual HTTP/job builder composition without configured engines/providers."""
import ast
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import jwt
from flask import Flask
from authMiddleware import install_auth_middleware
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
from endpoints.schedule.read_service import ScheduleReadService
from endpoints.scoring.service import ScoringService
from rules.leagueRules import resolve_rules, rule_summary


class ScheduleCompositionTests(unittest.TestCase):
    def client(self):
        from endpoints.schedule.routes import setup_routes
        service = Mock()
        service.member_schedule_for_job.return_value = {'rules':{},'ownedTeams':[],'week':None,'games':[]}
        service.conference_games_for_job.return_value = []
        service.team_games_for_job.return_value = []
        service.search_teams_for_job.return_value = []
        app = Flask(__name__);app.config['TESTING'] = True
        install_auth_middleware(app)
        with patch('endpoints.schedule.scheduleEndpoints.ScheduleReadService',return_value=service):
            setup_routes(app,object())
        client = app.test_client()
        token = jwt.encode({'sub':'00000000-0000-4000-8000-000000000001','aud':'authenticated',
            'iss':ISSUER,'exp':int(time.time())+600},SUPABASE_JWT_SECRET,algorithm='HS256')
        client.environ_base['HTTP_AUTHORIZATION'] = 'Bearer '+token
        return client,service

    def test_actual_read_routes_keep_envelopes_integer_inputs_and_raw_echoes(self):
        client,service = self.client()
        cases = [('/api/schedule/all',{'leagueId':'10','memberId':'11','weekNumber':'2'}),
            ('/api/schedule/conferenceGamesByWeek',{'leagueId':'10','weekNumber':'2','seasonYear':'2026','sportConferenceId':'501'}),
            ('/api/schedule/teamGamesBySeason',{'seasonYear':'2026','sportTeamId':'101'}),
            ('/api/schedule/teamSearch',{'leagueId':'10','query':'iowa st','limit':'3'})]
        for path,body in cases:
            response = client.post(path,json=body)
            self.assertEqual(response.status_code,200)
            if path.endswith('teamSearch'):self.assertEqual(response.json,{'leagueId':'10','query':'iowa st','teams':[]})
            elif path.endswith('teamGamesBySeason'):self.assertEqual(response.json,{'seasonYear':'2026','sportTeamId':'101','leagueId':None,'games':[]})
            elif path.endswith('conferenceGamesByWeek'):self.assertEqual(response.json,{**body,'games':[]})
            else:self.assertEqual(response.json,service.member_schedule_for_job.return_value)
        service.member_schedule_for_job.assert_called_once_with(10,11,2)
        service.team_games_for_job.assert_called_once_with(sport_team_id=101,season_year=2026,league_id=None)
        service.search_teams_for_job.assert_called_once_with(league_id=10,query='iowa st',limit=3)

    def test_value_errors_and_generic_failures_preserve_http_mapping(self):
        client,service = self.client()
        with patch('traceback.print_exc'):
            for error,status,message in ((ValueError('synthetic input'),400,'synthetic input'),
                    (RuntimeError('private detail'),500,'Failed to search teams')):
                service.search_teams_for_job.side_effect = error
                response = client.post('/api/schedule/teamSearch',json={'leagueId':10,'query':'iowa'})
                self.assertEqual((response.status_code,response.json),(status,{'message':message}))

    def test_disabled_week_route_never_calls_canonical_service(self):
        client,service = self.client()
        response = client.post('/api/schedule/createWeeks',json={'leagueId':10,'trustedJob':True})
        self.assertEqual((response.status_code,response.json),(410,{'error':'http_week_generation_disabled'}))
        self.assertEqual(service.method_calls,[])

    def test_member_aggregate_resolves_once_and_preserves_callback_order_and_payload(self):
        service = ScheduleReadService(object());calls = []
        service._get_league = lambda league:(calls.append('league') or {'sport':1,'settings':{}})
        captured = []
        def games(*args,**kwargs):
            calls.append('games');captured.append(kwargs['resolved_rules']);return [{'id':1}]
        service.get_member_games_for_week = games
        service.get_week_for_league = lambda *args:(calls.append('week') or None)
        service.get_owned_teams_for_member = lambda *args:(calls.append('owned') or [{'teamId':101}])
        result = service.member_schedule_for_job(10,11,2)
        rules = resolve_rules(1,{})
        self.assertEqual(calls,['league','games','week','owned'])
        self.assertEqual(result,{'rules':{'version':'v1','summary':rule_summary(rules),'tierAdjustment':rules},
            'week':None,'games':[{'id':1}],'ownedTeams':[{'teamId':101}]})
        self.assertIs(result['rules']['tierAdjustment'],captured[0])

    def test_actual_scoring_builders_need_no_provider_configuration(self):
        for filename in ('cronComputeWeeklyScores.py','cronComputeFinalScoreboard.py'):
            path = Path(__file__).resolve().parents[1]/'cronJobs'/filename
            tree = ast.parse(path.read_text())
            builder = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build_scoring')
            schedule = object()
            namespace = {'load_dotenv':lambda:None,'ScheduleReadService':lambda engine:schedule,
                'ScoringService':ScoringService,'os':SimpleNamespace(getenv=lambda name:None)}
            exec(compile(ast.Module(body=[builder],type_ignores=[]),str(path),'exec'),namespace)
            result = namespace['build_scoring'](object())
            self.assertIs(result.schedule_model,schedule)
