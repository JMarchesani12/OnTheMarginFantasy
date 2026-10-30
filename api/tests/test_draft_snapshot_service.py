"""Draft snapshot authority, completed repair and supplied-transaction ownership."""
import unittest
from actors import UserActor
from endpoints.draft.draftModel import DraftModel
import test_draft_state_authorization as draft
from test_transaction_service import ConnectionOwner


class DraftSnapshotServiceTests(unittest.TestCase):
    def setUp(self):
        base=draft.DraftStateAuthorizationTests();base.setUp();self.addCleanup(base.doCleanups)
        self.db,self.states=base.db,base.state_rows
        self.engine=ConnectionOwner(self.db)
    def service(self):
        from endpoints.draft.snapshot_service import DraftSnapshotService
        return DraftSnapshotService(self.engine)
    def complete(self):
        self.db.connection.execute('UPDATE "DraftState" SET status=\'complete\' WHERE "leagueId"=10');self.db.connection.commit()
    def test_actor_required_before_io(self):
        service=self.service()
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError):service.snapshot(actor,10)
        self.assertEqual(self.engine.begins,0)
    def test_snapshot_projection_member_order_picks_and_upcoming_turns(self):
        row=self.service().snapshot(UserActor(1,'alice'),10)
        self.assertEqual(set(row),{'leagueId','draftSettings','serverNow','state','members','picks','onDeck','inTheHole'})
        self.assertEqual(row['draftSettings'],{'type':'snake','rounds':2})
        self.assertEqual([r['memberId'] for r in row['members']],[11,12])
        self.assertEqual(row['picks'][0]['conferenceName'],'Synthetic Conference')
        self.assertEqual(row['onDeck'],{'overallPickNumber':3,'memberId':12,'memberTeamName':'Bob Open'})
        self.assertEqual(row['inTheHole'],{'overallPickNumber':4,'memberId':11,'memberTeamName':'Alice Open'})
        self.assertTrue(row['serverNow'].endswith('+00:00'));self.assertEqual(self.engine.begins,1)
    def test_commissioner_without_membership_denied_before_repair(self):
        service=self.service();before=self.states()
        for actor,league in ((UserActor(1,'alice'),30),(UserActor(3,'outsider'),10),(UserActor(1,'alice'),999)):
            with self.assertRaises(PermissionError):service.snapshot(actor,league)
        self.assertEqual(self.states(),before)
        with self.assertRaises(ValueError):service.snapshot_for_job(999)
    def test_repair_rolls_back_if_later_pick_read_fails(self):
        service=self.service();self.complete();before=self.states();execute=self.db.execute
        def fail(statement,params):
            result=execute(statement,params)
            if 'WITH league_info AS' in str(statement):raise RuntimeError('synthetic after-repair failure')
            return result
        self.db.execute=fail
        with self.assertRaises(RuntimeError):service.snapshot(UserActor(1,'alice'),10)
        self.assertEqual(self.states(),before)
    def test_supplied_connection_does_not_nest_and_caller_can_rollback(self):
        service=self.service();self.complete();before=self.states()
        with self.assertRaises(RuntimeError):
            with self.engine.begin() as conn:
                row=service.snapshot(UserActor(1,'alice'),10,conn=conn)
                self.assertIsNone(row['state']['currentMemberId'])
                self.assertEqual(self.engine.begins,1)
                raise RuntimeError('caller abort')
        self.assertEqual(self.states(),before)
    def test_db_only_legacy_and_connection_helpers_remain_compatible(self):
        model=DraftModel.__new__(DraftModel);model.db=self.engine
        self.assertEqual(model.get_draft_state_snapshot(20)['state']['status'],'paused')
        with self.assertRaises(PermissionError):model.get_draft_state_snapshot(20,reader_user_id=1)
        self.assertEqual(model._get_next_unpicked_turn_from(self.db,10,3),(3,12))
