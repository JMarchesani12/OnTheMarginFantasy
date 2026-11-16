"""Actual group service/tie resolution; native harness establishes SQL parity."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from endpoints.schedule.read_service import ScheduleReadService
from endpoints.scoring.service import ScoringService

class GroupReadTests(unittest.TestCase):
    def test_group_method_uses_supplied_connection_once(self):
        engine=MagicMock();repo=MagicMock();conn=object();row=dict(id=9,homeScore=13,awayScore=20,homeMemberIds=[1],awayMemberIds=[2])
        repo.head_to_head_games_for_members.return_value.fetchall.return_value=[SimpleNamespace(_mapping=row)]
        service=ScheduleReadService(engine,repo)
        self.assertEqual(service.get_head_to_head_games_for_members(7,[2,1,2],3,conn),[row])
        repo.head_to_head_games_for_members.assert_called_once_with(conn,dict(leagueId=7,weekNumber=3,memberIds=[1,2]))
        engine.begin.assert_not_called();engine.connect.assert_not_called()

    def test_small_group_and_missing_connection_never_query(self):
        repo=MagicMock();service=ScheduleReadService(None,repo)
        for ids in ([],[1],[1,1]):self.assertEqual(service.get_head_to_head_games_for_members(7,ids,3,object()),[])
        with self.assertRaises(ValueError):service.get_head_to_head_games_for_members(7,[1,2],3,None)
        repo.head_to_head_games_for_members.assert_not_called()

    def test_pair_api_contract_unchanged(self):
        repo=MagicMock();conn=object();repo.head_to_head_games.return_value.fetchall.return_value=[]
        self.assertEqual(ScheduleReadService(None,repo).get_head_to_head_games(7,1,2,3,conn=conn),[])
        repo.head_to_head_games.assert_called_once_with(conn,dict(leagueId=7,weekNumber=3,memberA=1,memberB=2))

def members(ids, pd=5):return [dict(memberId=i,teamName=str(i),pointDifferential=pd) for i in ids]
def game(home,away,hs=13,aws=20):return dict(homeMemberIds=home,awayMemberIds=away,homeScore=hs,awayScore=aws)

class GroupScoringTests(unittest.TestCase):
    def fixture(self,rows):
        schedule=MagicMock();schedule.get_head_to_head_games_for_members.return_value=rows
        schedule.get_head_to_head_games.side_effect=AssertionError('Supplied scoring must not fetch pairs')
        schedule.get_member_games_for_week.side_effect=lambda **kw:[dict(memberPointDiff={1:100,2:7,3:4,4:-12}[kw['member_id']])]
        return ScoringService(None,schedule),schedule

    def test_supplied_tie_fetches_once_raw_h2h_beats_adjusted_margin(self):
        scoring,schedule=self.fixture([game([1],[2])]);conn=object()
        result=scoring.apply_weekly_tiebreakers(7,2,members([1,2]),conn=conn)
        self.assertEqual([m['memberId'] for m in result],[2,1]);schedule.get_member_games_for_week.assert_not_called()
        schedule.get_head_to_head_games_for_members.assert_called_once_with(league_id=7,member_ids=[1,2],week_number=2,conn=conn)

    def test_empty_or_equal_totals_fall_back_without_parsing_ineligible_scores(self):
        for rows in ([],[game([1],[],None,None)],[game([1,1,2],[1,2])]):
            scoring,schedule=self.fixture(rows)
            result=scoring.apply_weekly_tiebreakers(7,2,members([3,4]),conn=object())
            self.assertEqual([m['memberId'] for m in result],[4,3])
        scoring,schedule=self.fixture([game([1],[2],None,4)])
        with self.assertRaises(TypeError):scoring._tb_weekly_head_to_head(7,2,members([1,2]),conn=object())

    def test_dual_and_duplicate_owner_facts_keep_boolean_semantics(self):
        scoring,schedule=self.fixture([game([1,1,2],[1,2]),game([2,2],[3],14,10)])
        result=scoring._tb_weekly_head_to_head(7,2,members([1,2,3]),conn=object())
        self.assertEqual([m['memberId'] for m in result],[2,1,3])

    def test_partial_h2h_subtie_does_not_run_recursive_fallback(self):
        scoring,schedule=self.fixture([game([1],[3],17,10),game([2],[3],17,10)])
        result=scoring.apply_weekly_tiebreakers(7,2,members([1,2,3]),conn=object())
        self.assertEqual([m['memberId'] for m in result],[1,2,3]);schedule.get_member_games_for_week.assert_not_called()

    def test_two_groups_h2h_then_fallback_are_isolated_and_fresh(self):
        scoring,schedule=self.fixture([])
        schedule.get_head_to_head_games_for_members.side_effect=[[game([1],[2],17,10),game([1],[3],1000,0)],[],[]]
        group=members([1,2],5)+members([3,4],1)
        result=scoring.apply_weekly_tiebreakers(7,2,group,conn=object())
        self.assertEqual([m['memberId'] for m in result],[1,2,4,3]);self.assertEqual([m['pointDifferential'] for m in result],[5,5,1,1])
        self.assertEqual(schedule.get_head_to_head_games_for_members.call_count,2)
        result=scoring.apply_weekly_tiebreakers(8,3,members([1,2]),conn=object())
        self.assertEqual([m['memberId'] for m in result],[1,2]);self.assertEqual(schedule.get_head_to_head_games_for_members.call_count,3)

    def test_no_conn_keeps_pair_api(self):
        schedule=MagicMock();schedule.get_head_to_head_games.return_value=[]
        schedule.get_member_games_for_week.return_value=[]
        ScoringService(None,schedule).apply_weekly_tiebreakers(7,2,members([1,2,3]))
        self.assertEqual(schedule.get_head_to_head_games.call_count,3);schedule.get_head_to_head_games_for_members.assert_not_called()
