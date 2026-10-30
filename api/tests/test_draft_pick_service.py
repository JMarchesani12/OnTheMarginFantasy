"""Remaining draft allocation behavior and actor/job/facade compatibility."""
import unittest
from actors import UserActor
from endpoints.draft.draftModel import DraftModel
import test_live_pick_authorization as live
from test_transaction_service import ConnectionOwner


class DraftPickServiceTests(unittest.TestCase):
    def setUp(self):
        base=live.LivePickAuthorizationTests();base.setUp();self.addCleanup(base.doCleanups)
        self.db,self.state=base.db,base.state;self.engine=ConnectionOwner(self.db)
    def service(self):
        from endpoints.draft.pick_service import DraftPickService
        return DraftPickService(self.engine)
    def test_actor_required_before_io(self):
        service=self.service()
        for actor in (None,1,{'user_id':2}):
            with self.assertRaises(TypeError):service.pick_live(actor,10,12,102)
        self.assertEqual(self.engine.begins,0)
    def test_live_actor_allocation_and_pointer(self):
        result=self.service().pick_live(UserActor(2,'bob'),10,12,102,acquired_week=3)
        self.assertEqual((result['memberId'],result['overallPickNumber'],result['nextMemberId']),(12,2,12))
        slot=self.state()['LeagueTeamSlot'][0]
        self.assertEqual((slot['sportTeamId'],slot['acquiredWeek'],slot['acquiredVia']),(102,3,'Draft'))
        self.assertEqual(self.engine.begins,1)
    def test_wrong_owner_and_slot_failure_restore_all_state(self):
        service=self.service();before=self.state()
        with self.assertRaises(PermissionError):service.pick_live(UserActor(1,'alice'),10,12,102)
        def fail(sql):
            if 'INSERT INTO "LeagueTeamSlot"' in sql:raise RuntimeError('synthetic slot failure')
        self.db.before_query=fail
        with self.assertRaises(RuntimeError):service.pick_live(UserActor(2,'bob'),10,12,102)
        self.assertEqual(self.state(),before)
    def test_trusted_manual_default_and_notification(self):
        service=self.service();notifications=[]
        self.db.connection.create_function('pg_notify',2,lambda channel,payload:notifications.append((channel,payload)))
        result=service.allocate_manual_for_job(10,12,102)
        self.assertEqual(result['overallPickNumber'],2)
        self.assertEqual(self.state()['LeagueTeamSlot'][0]['acquiredWeek'],1)
        self.assertEqual(notifications[0][0],'draft_updated')
    def test_timeout_paused_and_missing_state_no_ops(self):
        service=self.service()
        self.db.connection.execute('UPDATE "DraftState" SET status=\'paused\' WHERE "leagueId"=10');self.db.connection.commit()
        before=self.state();self.assertIsNone(service.process_timeout_for_job(10));self.assertEqual(self.state(),before)
        self.db.connection.execute('DELETE FROM "DraftState" WHERE "leagueId"=10');self.db.connection.commit()
        self.assertIsNone(service.process_timeout_for_job(10))
    def test_inherited_helpers_keep_override_and_db_only_compatibility(self):
        from endpoints.draft.pick_service import DraftPickService
        self.assertTrue(issubclass(DraftModel,DraftPickService))
        class CustomModel(DraftModel):
            def _get_expected_member_for_overall(self,conn,league_id,overall_pick_number):return 999
        model=CustomModel.__new__(CustomModel);model.db=self.engine
        with self.assertRaisesRegex(ValueError,'Not your turn'):model.create_draft_pick_live(10,12,102)
