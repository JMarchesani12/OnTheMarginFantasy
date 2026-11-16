"""Rules-only context: actual schedule resolver and scorer, no configured services."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from endpoints.schedule.read_service import ScheduleReadService

EXPECTED={'version':'v1','minimumTierGap':2,'favoredWinMultiplier':0.5,'favoredLossMultiplier':2,'rounding':'away_from_zero','doubleOwnedMargin':0}

class WeeklyRulesCapabilityTests(unittest.TestCase):
    def test_schedule_resolver_reuses_supplied_connection_and_current_rules(self):
        engine=MagicMock();conn=object();repo=MagicMock()
        repo.league.return_value.fetchone.return_value._mapping={'sport':1,'settings':{'ruleSetVersion':'v1'}}
        service=ScheduleReadService(engine,calendar_repository=repo)
        self.assertEqual(service.resolve_member_game_rules_for_scoring(7,conn),EXPECTED)
        repo.league.assert_called_once_with(conn,{'leagueId':7});engine.begin.assert_not_called();engine.connect.assert_not_called()
        with self.assertRaises(ValueError):service.resolve_member_game_rules_for_scoring(7,None)

    def test_context_defensive_copy_and_mutation_rejection(self):
        from endpoints.scoring.weekly_context import _WeeklyRulesContext
        rules=dict(EXPECTED);context=_WeeklyRulesContext(7,2,object(),rules);rules['minimumTierGap']=99
        self.assertEqual(context.rules,EXPECTED)
        with self.assertRaises(TypeError):context.rules['minimumTierGap']=99
        with self.assertRaises(AttributeError):context.week_number=3

    def test_context_mismatch_rejected_before_io(self):
        from endpoints.scoring.weekly_context import _WeeklyRulesContext
        conn=object();context=_WeeklyRulesContext(7,2,conn,EXPECTED);context.require_match(7,2,conn)
        for league,week,connection in [(8,2,conn),(7,3,conn),(7,2,object())]:
            with self.assertRaises(ValueError):context.require_match(league,week,connection)

    def test_resolver_missing_league_or_invalid_version_propagates(self):
        repo=MagicMock();service=ScheduleReadService(None,calendar_repository=repo)
        repo.league.return_value.fetchone.return_value=None
        with self.assertRaisesRegex(ValueError,'not found'):service.resolve_member_game_rules_for_scoring(7,object())
        repo.league.return_value.fetchone.return_value=SimpleNamespace(_mapping={'sport':1,'settings':{'ruleSetVersion':'invalid'}})
        with self.assertRaisesRegex(ValueError,'Unsupported'):service.resolve_member_game_rules_for_scoring(7,object())

class WeeklyRulesFlowTests(unittest.TestCase):
    def fixture(self, head=False):
        from endpoints.scoring.service import ScoringService
        conn=object();calendar=MagicMock();counts={'rules':0};game_calls=[]
        def league(*args):
            self.assertIs(args[0],conn);counts['rules']+=1
            # A repeated resolution sees a changed definition (sport threshold).
            return SimpleNamespace(fetchone=lambda:SimpleNamespace(_mapping={'sport':1 if counts['rules']==1 else 2,'settings':{}}))
        calendar.league.side_effect=league;reads=MagicMock()
        def games(connection,params):
            self.assertIs(connection,conn);game_calls.append(params['memberId']);diffs={1:[6,-1],2:[8,-3]}[params['memberId']]
            return SimpleNamespace(fetchall=lambda:[SimpleNamespace(_mapping=dict(rawMemberPointDiff=d,ownsHome=True,ownsAway=False,homeTeamTier=1,awayTeamTier=2,awayTeamUnranked=False,sportId=1,phaseRules={})) for d in diffs])
        reads.member_games.side_effect=games
        reads.head_to_head_games.return_value.fetchall.return_value=[SimpleNamespace(_mapping=dict(homeScore=9,awayScore=2,homeOwnedByA=True,awayOwnedByA=False,homeOwnedByB=False,awayOwnedByB=True))] if head else []
        schedule=ScheduleReadService(None,reads,calendar);repo=MagicMock();scorer=ScoringService(None,schedule,repo)
        scorer._get_week_by_number=MagicMock(return_value={'id':10,'weekNumber':1})
        scorer._get_league_members=MagicMock(return_value=[dict(id=1,teamName='A'),dict(id=2,teamName='B')])
        return scorer,conn,counts,game_calls,repo

    def test_supplied_week_uses_one_rules_resolution_for_all_members_and_fallback(self):
        scorer,conn,counts,calls,repo=self.fixture();result=scorer.compute_weekly_scores_for_job(7,1,conn=conn)
        self.assertEqual(counts['rules'],1)
        self.assertEqual(result['scores'],[dict(memberId=2,teamName='B',pointDifferential=5,rank=1,pointsAwarded=2),dict(memberId=1,teamName='A',pointDifferential=5,rank=2,pointsAwarded=1)])
        self.assertEqual(calls,[1,2,1,2]);repo.lock_scoring_week.assert_called_once_with(conn,7,10)

    def test_h2h_retains_raw_precedence_without_extra_rules_reads(self):
        scorer,conn,counts,calls,repo=self.fixture(head=True);result=scorer.compute_weekly_scores_for_job(7,1,conn=conn)
        self.assertEqual([r['memberId'] for r in result['scores']],[1,2]);self.assertEqual(counts['rules'],1);self.assertEqual(calls,[1,2])

    def test_same_service_connection_new_week_league_and_retry_get_fresh_context(self):
        scorer,conn,counts,calls,repo=self.fixture()
        for league,week in [(7,1),(7,2),(8,1)]:scorer.compute_weekly_scores_for_job(league,week,conn=conn)
        self.assertEqual(counts['rules'],3)
        repo.insert_weekly_score.side_effect=RuntimeError('insert')
        with self.assertRaises(RuntimeError):scorer.compute_weekly_scores_for_job(7,1,conn=conn)
        repo.insert_weekly_score.side_effect=None;scorer.compute_weekly_scores_for_job(7,1,conn=conn)
        self.assertEqual(counts['rules'],5)
        self.assertNotIn('scoring_context',vars(scorer));self.assertNotIn('scoring_context',vars(scorer.schedule_model))

    def test_guards_and_empty_roster_precede_context_creation(self):
        import datetime as dt
        for patch in [dict(isFinalPeriod=True,finalPeriodEnd=dt.datetime(2020,2,1,tzinfo=dt.timezone.utc),startDate=dt.datetime(2020,1,1,tzinfo=dt.timezone.utc),endDate=dt.datetime(2020,1,2,tzinfo=dt.timezone.utc)),dict(isFinalPeriod=True,startDate=dt.datetime(2099,1,1,tzinfo=dt.timezone.utc),endDate=dt.datetime(2099,2,1,tzinfo=dt.timezone.utc)),None]:
            scorer,conn,counts,calls,repo=self.fixture()
            if patch:scorer._get_week_by_number.return_value.update(patch)
            else:scorer._get_league_members.return_value=[]
            with self.assertRaises(ValueError):scorer.compute_weekly_scores_for_job(7,1,conn=conn)
            self.assertEqual(counts['rules'],0);self.assertEqual(calls,[]);repo.delete_weekly_scores.assert_not_called()

    def test_mismatched_context_does_not_reach_schedule(self):
        from endpoints.scoring.weekly_context import _WeeklyRulesContext
        scorer,conn,counts,calls,repo=self.fixture();context=_WeeklyRulesContext(99,1,conn,EXPECTED)
        with self.assertRaises(ValueError):scorer.compute_member_point_diff_for_week(7,1,1,conn=conn,scoring_context=context)
        self.assertEqual(calls,[]);self.assertEqual(counts['rules'],0)
