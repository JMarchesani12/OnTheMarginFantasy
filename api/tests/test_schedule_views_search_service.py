"""Views/search policies on supplied query facts; PostgreSQL SQL checked separately."""
import datetime as dt
import unittest
from test_schedule_read_service import ReadEngine
from endpoints.schedule.read_service import ScheduleReadService
from endpoints.schedule.scheduleModel import ScheduleModel


class SequenceEngine(ReadEngine):
    def __init__(self, results):
        super().__init__([])
        self.results = list(results)

    def execute(self, statement, params):
        self.rows = self.results.pop(0)
        return super().execute(statement, params)


class ScheduleViewsSearchTests(unittest.TestCase):
    def service(self, results):
        engine = SequenceEngine(results)
        return ScheduleReadService(engine), engine

    def context(self):
        return {'sport':1,'seasonYear':2026,'weekNumber':2}

    def test_search_normalization_and_rank_precedence(self):
        service, _ = self.service([])
        self.assertEqual(service._normalize_team_search_text(' A&M Univ. St. '),'a and m university state')
        self.assertEqual([service._team_search_rank({'teamName':name},'iowa st') for name in
            ('Iowa State','Iowa State Cyclones','East Iowa State','Iowa Big State','Other')],
            [100,90,75,50,0])

    def test_search_short_guard_invalid_limit_and_missing_league(self):
        service, engine = self.service([])
        self.assertEqual(service.search_teams_for_job(999,'x'),[])
        self.assertEqual(engine.calls,[])
        with self.assertRaises(ValueError):
            service.search_teams_for_job(10,'',limit='invalid')
        missing, engine = self.service([[]])
        with self.assertRaisesRegex(ValueError,'League not found: 999'):
            missing.search_teams_for_job(999,'iowa')
        self.assertEqual((len(engine.calls),engine.outcomes),(1,['rollback']))

    def test_search_sort_projection_limits_and_shared_context_scope(self):
        rows = [{'teamId':number,'teamName':name,'ownerMemberId':None} for number,name in enumerate(
            ('Iowa Big State','East Iowa State','Iowa State Cyclones','Iowa State'))]
        service, engine = self.service([[self.context()],rows])
        result = service.search_teams_for_job(10,'iowa st',3)
        self.assertEqual([r['teamName'] for r in result],['Iowa State','Iowa State Cyclones','East Iowa State'])
        self.assertTrue(all(set(row)=={'teamId','teamName','ownerMemberId'} for row in result))
        self.assertEqual((len(engine.calls),engine.outcomes),(2,['commit']))
        for limit, expected in ((0,20),(-1,1),(100,50)):
            with self.subTest(limit=limit):
                candidates = [{'teamName':f'Iowa State {i:02}'} for i in range(60)]
                service, _ = self.service([[self.context()],candidates])
                self.assertEqual(len(service.search_teams_for_job(10,'iowa st',limit)),expected)

    def test_conference_window_parameters_projection_and_missing_window(self):
        start = dt.datetime(2026,11,2,tzinfo=dt.timezone.utc)
        end = start+dt.timedelta(days=7)
        rows = [{'id':7,'homeInConference':True,'homeOwnerDisplayName':None}]
        service, engine = self.service([[{'startDate':start,'endDate':end}],rows])
        self.assertEqual(service.conference_games_for_job(10,2,2026,501),rows)
        self.assertEqual((engine.calls[1][1]['weekStart'],engine.calls[1][1]['weekEnd']),(start,end))
        self.assertEqual(engine.outcomes,['commit','commit'])
        missing, engine = self.service([[]])
        with self.assertRaisesRegex(ValueError,'Week not found'):
            missing.conference_games_for_job(10,99,2026,501)
        self.assertEqual(len(engine.calls),1)

    def test_optional_team_context_and_fallback_projection(self):
        rows = [{'id':1,'isHome':False,'opponentTeamId':102,'ownerMemberId':None}]
        for league, context, expected_calls in ((None,None,1),(10,[{'weekNumber':3}],2),(999,[],2)):
            with self.subTest(league=league):
                results = [rows] if league is None else [context,rows]
                service, engine = self.service(results)
                self.assertEqual(service.team_games_for_job(101,2026,league),rows)
                self.assertEqual(len(engine.calls),expected_calls)
                self.assertEqual(engine.calls[-1][1]['weekNumber'],3 if league==10 else 999)
                self.assertEqual(engine.outcomes,['commit'])

    def test_read_failure_propagates_and_scope_unwinds(self):
        service, engine = self.service([[self.context()]])
        engine.failure = RuntimeError('synthetic context failure')
        with self.assertRaisesRegex(RuntimeError,'synthetic context'):
            service.search_teams_for_job(10,'iowa')
        self.assertEqual(engine.outcomes,['rollback'])

    def test_legacy_db_only_classmethod_and_window_overrides(self):
        class CustomRank(ScheduleModel):
            @classmethod
            def _team_search_rank(cls,row,query): return 100
        model = CustomRank.__new__(CustomRank)
        model.db = SequenceEngine([[self.context()],[{'teamName':'Unrelated Team'}]])
        self.assertEqual(model.search_teams_for_league(10,'iowa'),[{'teamName':'Unrelated Team'}])
        class CustomWindow(ScheduleModel):
            def _get_week_window(self,league_id,week_number): return ('start','end')
        model = CustomWindow.__new__(CustomWindow)
        model.db = SequenceEngine([[{'id':1}]])
        self.assertEqual(model.get_conference_games_by_week(10,2,2026,501),[{'id':1}])
        self.assertEqual(len(model.db.calls),1)
