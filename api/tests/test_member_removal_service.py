"""Removal policy and atomicity on synthetic real SQL; native locks separately."""
import unittest
from actors import UserActor
from endpoints.league.members.service import MemberService
from endpoints.league.leagueModel import LeagueModel
import test_member_removal_authorization as removal
from test_transaction_service import ConnectionOwner


class MemberRemovalServiceTests(unittest.TestCase):
    def setUp(self):
        base = removal.MemberRemovalAuthorizationTests(); base.setUp()
        self.addCleanup(base.doCleanups)
        self.db, self.state = base.db, base.state
        self.engine = ConnectionOwner(self.db); self.service = MemberService(self.engine)
        self.actor = UserActor(1,'alice')

    def test_actor_and_boolean_shift_required_before_io(self):
        self.assertTrue(callable(getattr(self.service,'remove',None)), 'actor removal operation missing')
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError): self.service.remove(actor,10,12)
        for shift in (None,0,'false'):
            with self.assertRaises(ValueError): self.service.remove(self.actor,10,12,shift)
        self.assertEqual(self.engine.begins,0)

    def test_commissioner_removal_shifts_only_own_league_and_replay_rejects(self):
        self.assertTrue(hasattr(self.service,'remove'), 'actor removal operation missing')
        before=self.state();result=self.service.remove(self.actor,10,12)
        self.assertEqual(result,{'removedMemberId':12,'removedDraftOrder':2,'members':[
            {'memberId':11,'userId':1,'teamName':'Alice Team','draftOrder':1,'displayName':'Alice'},
            {'memberId':13,'userId':3,'teamName':'Charlie Team','draftOrder':2,'displayName':'Charlie'}]})
        after=self.state();self.assertEqual(self.engine.begins,1)
        self.assertEqual(after['League'][0]['numPlayers'],2)
        self.assertEqual(after['League'][1],before['League'][1])
        self.assertEqual(after['LeagueMember'][-2:],before['LeagueMember'][-2:])
        with self.assertRaises(ValueError):self.service.remove(self.actor,10,12)
        self.assertEqual(self.state(),after)

    def test_wrong_authority_scope_missing_and_commissioner_leave_state_unchanged(self):
        self.assertTrue(hasattr(self.service,'remove'), 'actor removal operation missing')
        before=self.state()
        with self.assertRaises(PermissionError):self.service.remove(UserActor(2,'bob'),10,13)
        for league,member in ((999,12),(10,999),(10,22),(10,11)):
            with self.assertRaises(ValueError):self.service.remove(self.actor,league,member)
        self.assertEqual(self.state(),before)

    def test_shift_disabled_and_count_floor(self):
        self.assertTrue(hasattr(self.service,'remove'), 'actor removal operation missing')
        self.db.connection.execute('UPDATE "League" SET "numPlayers"=0 WHERE id=10');self.db.connection.commit()
        row=self.service.remove(self.actor,10,12,False)
        self.assertEqual([m['draftOrder'] for m in row['members']],[1,3])
        self.assertEqual(self.state()['League'][0]['numPlayers'],0)

    def test_failure_after_delete_rolls_back_all_mutations(self):
        self.assertTrue(hasattr(self.service,'remove'), 'actor removal operation missing')
        before=self.state();self.db.fail_after_delete=True
        with self.assertRaises(RuntimeError):self.service.remove(self.actor,10,12)
        self.assertEqual(self.state(),before)

    def test_db_only_legacy_delegate_preserves_coercion_and_truthiness(self):
        model=LeagueModel.__new__(LeagueModel);model.db=self.engine
        row=model.remove_member_and_shift_draft_order(10,12,'1',0)
        self.assertEqual([m['draftOrder'] for m in row['members']],[1,3])
        self.assertEqual(self.engine.begins,1)
