"""Start/pause/resume policy, seeding and atomic control transactions."""
import json
import unittest
from actors import UserActor
from endpoints.draft.control_service import DraftControlService
from endpoints.draft.draftModel import DraftModel
import test_draft_control_authorization as controls
from test_transaction_service import ConnectionOwner


class DraftControlsServiceTests(unittest.TestCase):
    def setUp(self):
        base=controls.DraftControlAuthorizationTests();base.setUp();base.prepare('start');self.addCleanup(base.doCleanups)
        self.db,self.state=base.db,base.state;self.engine=ConnectionOwner(self.db);self.service=DraftControlService(self.engine)
        self.actor=UserActor(1,'alice')
    def turns(self):
        return [r[0] for r in self.db.connection.execute('SELECT "memberId" FROM "DraftTurn" WHERE "leagueId"=10 ORDER BY "overallPickNumber"')]
    def test_actor_required_before_io_for_each_control(self):
        for name in ('start','pause','resume'):
            self.assertTrue(callable(getattr(self.service,name,None)),name+' operation missing')
            for actor in (None,1,{'user_id':1}):
                with self.assertRaises(TypeError):getattr(self.service,name)(actor,10)
        self.assertEqual(self.engine.begins,0)
    def test_start_snake_turns_snapshot_and_existing_restart_behavior(self):
        self.assertTrue(hasattr(self.service,'start'),'start operation missing')
        row=self.service.start(self.actor,10)
        self.assertEqual(row['state']['status'],'live');self.assertEqual(row['state']['currentOverallPickNumber'],1)
        self.assertEqual(row['state']['currentMemberId'],11);self.assertIsNotNone(row['state']['expiresAt'])
        self.assertEqual(self.turns(),[11,12,12,11]);self.assertEqual(self.engine.begins,1)
        self.service.start(self.actor,10);self.assertEqual(self.turns(),[11,12,12,11])
    def test_straight_seeding(self):
        self.assertTrue(hasattr(self.service,'start'),'start operation missing')
        raw=self.db.connection.execute('SELECT settings FROM "League" WHERE id=10').fetchone()[0];cfg=json.loads(raw)
        cfg['draft']['draftType']='STRAIGHT'
        self.db.connection.execute('UPDATE "League" SET settings=? WHERE id=10',(json.dumps(cfg),));self.db.connection.commit()
        self.service.start(self.actor,10);self.assertEqual(self.turns(),[11,12,11,12])
    def test_pause_resume_preserve_turn_and_complete_guards(self):
        self.assertTrue(hasattr(self.service,'start'),'start operation missing')
        first=self.service.start(self.actor,10)
        paused=self.service.pause(self.actor,10)
        self.assertEqual(paused['state']['status'],'paused');self.assertIsNone(paused['state']['expiresAt'])
        resumed=self.service.resume(self.actor,10)
        self.assertEqual(resumed['state']['status'],'live');self.assertIsNotNone(resumed['state']['expiresAt'])
        self.assertEqual(resumed['state']['currentMemberId'],first['state']['currentMemberId'])
        self.db.connection.execute('UPDATE "DraftState" SET status=\'complete\' WHERE "leagueId"=10');self.db.connection.commit()
        before=self.state()
        for method in (self.service.pause,self.service.resume):
            with self.assertRaises(ValueError):method(self.actor,10)
        self.assertEqual(self.state(),before)
    def test_authority_and_failure_after_seed_or_late_check_roll_back(self):
        self.assertTrue(hasattr(self.service,'start'),'start operation missing')
        before=self.state()
        with self.assertRaises(PermissionError):self.service.start(UserActor(2,'bob'),10)
        def fail(sql):
            if "SET status = 'Drafting'" in sql:raise RuntimeError('synthetic control failure')
        self.db.before_query=fail
        with self.assertRaises(RuntimeError):self.service.start(self.actor,10)
        self.assertEqual(self.state(),before)
        checks=[]
        def revoke(sql):
            if 'SELECT commissioner FROM "League"' in sql:
                checks.append(True)
                if len(checks)==2:self.db.connection.execute('UPDATE "League" SET commissioner=2 WHERE id=10')
        self.db.before_query=revoke
        with self.assertRaises(PermissionError):self.service.start(self.actor,10)
        self.assertEqual(self.state(),before)
    def test_legacy_helpers_keep_supplied_connection_and_trusted_defaults(self):
        model=DraftModel.__new__(DraftModel);model.db=self.engine
        with self.engine.begin() as conn:
            model.seed_draft_turns(conn,10)
            self.assertEqual(model._get_expected_member_for_overall(conn,10,1),11)
            self.assertEqual(model._compute_round_and_pos(3,2),(2,1))
        self.assertEqual(model.start_draft(10)['state']['status'],'live')
        self.assertEqual(model.pause_draft(10,acting_user_id='1')['state']['status'],'paused')
