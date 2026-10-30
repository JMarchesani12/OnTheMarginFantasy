"""Draft finalization authority and atomic state/league transition tests."""
import unittest
from actors import UserActor
from endpoints.draft.draftModel import DraftModel
import test_draft_control_authorization as controls
from test_transaction_service import ConnectionOwner


class DraftFinalizationServiceTests(unittest.TestCase):
    def setUp(self):
        base=controls.DraftControlAuthorizationTests();base.setUp();base.prepare('finalize');self.addCleanup(base.doCleanups)
        self.db,self.state=base.db,base.state;self.engine=ConnectionOwner(self.db)
    def service(self):
        from endpoints.draft.control_service import DraftControlService
        return DraftControlService(self.engine)
    def test_actor_and_legacy_none_rejected_before_io(self):
        service=self.service()
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError):service.finalize(actor,10)
        with self.assertRaises(PermissionError):service.force_finalize_for_user_id(10,None)
        self.assertEqual(self.engine.begins,0)
    def test_checked_finalization_state_and_season_status_one_transaction(self):
        row=self.service().finalize(UserActor(1,'alice'),10)
        self.assertEqual(set(row),{'leagueId','draftComplete','state','leagueStatus'})
        self.assertTrue(row['draftComplete']);self.assertEqual(row['leagueStatus'],'Post-Draft')
        self.assertEqual(row['state']['status'],'complete');self.assertIsNone(row['state']['currentMemberId']);self.assertIsNone(row['state']['expiresAt'])
        self.assertEqual(self.engine.begins,1)
    def test_wrong_authority_missing_league_and_state_leave_data_unchanged(self):
        service=self.service();before=self.state()
        with self.assertRaises(PermissionError):service.finalize(UserActor(2,'bob'),10)
        with self.assertRaises(ValueError):service.finalize(UserActor(1,'alice'),999)
        with self.assertRaises(ValueError):service.finalize_for_job(999)
        self.assertEqual(self.state(),before)
    def test_post_state_write_failure_rolls_back(self):
        service=self.service();before=self.state();execute=self.db.execute
        def fail(statement,params):
            if 'UPDATE "League" l' in str(statement):raise RuntimeError('synthetic after-state failure')
            return execute(statement,params)
        self.db.execute=fail
        with self.assertRaises(RuntimeError):service.finalize(UserActor(1,'alice'),10)
        self.assertEqual(self.state(),before)
    def test_post_authority_change_rolls_back_all_in_transaction_writes(self):
        service=self.service();before=self.state();checks=[]
        def revoke(sql):
            if 'SELECT commissioner FROM "League"' in sql:
                checks.append(True)
                if len(checks)==2:self.db.connection.execute('UPDATE "League" SET commissioner=2 WHERE id=10')
        self.db.before_query=revoke
        with self.assertRaises(PermissionError):service.finalize(UserActor(1,'alice'),10)
        self.assertEqual(self.state(),before)
    def test_supplied_transaction_legacy_and_assert_helpers(self):
        model=DraftModel.__new__(DraftModel);model.db=self.engine;before=self.state()
        with self.assertRaises(RuntimeError):
            with self.engine.begin() as conn:
                self.assertTrue(model.finalize_draft(10,conn=conn)['draftComplete'])
                self.assertEqual(self.engine.begins,1)
                raise RuntimeError('caller abort')
        self.assertEqual(self.state(),before)
        self.assertTrue(model.force_finalize_draft(10,'1')['draftComplete'])
