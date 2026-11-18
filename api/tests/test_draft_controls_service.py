"""Start/pause/resume policy, seeding and atomic control transactions."""
import json
import unittest
from actors import UserActor
from endpoints.draft.control_service import DraftControlService
from endpoints.draft.pick_service import DraftPickService
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
    def test_start_snake_turns_snapshot_and_reject_restart(self):
        self.assertTrue(hasattr(self.service,'start'),'start operation missing')
        row=self.service.start(self.actor,10)
        self.assertEqual(row['state']['status'],'live');self.assertEqual(row['state']['currentOverallPickNumber'],1)
        self.assertEqual(row['state']['currentMemberId'],11);self.assertIsNotNone(row['state']['expiresAt'])
        self.assertEqual(self.turns(),[11,12,12,11]);self.assertEqual(self.engine.begins,1)
        before=self.state()
        with self.assertRaises(ValueError):self.service.start(self.actor,10)
        self.assertEqual(self.state(),before)
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
    def test_service_helpers_keep_supplied_connection_and_trusted_defaults(self):
        model=DraftPickService(self.engine)
        with self.engine.begin() as conn:
            DraftControlService(model.db).seed_turns(conn, 10)
            self.assertEqual(model._get_expected_member_for_overall(conn,10,1),11)
            self.assertEqual(model._compute_round_and_pos(3,2),(2,1))
        self.db.connection.execute('DELETE FROM "DraftTurn" WHERE "leagueId"=10')
        self.db.connection.commit()
        self.assertEqual(DraftControlService(model.db).start_for_job(10)['state']['status'],'live')
        self.assertEqual(DraftControlService(model.db).pause_for_legacy_user_id(10, '1')['state']['status'],'paused')

    def test_start_conflicts_preserve_all_lifecycle_state(self):
        for status in ('live', 'paused', 'complete', 'unknown'):
            with self.subTest(status=status):
                self.db.connection.execute('INSERT INTO "DraftState" ("leagueId",status,"currentOverallPickNumber","currentMemberId","expiresAt") VALUES (10,?,3,12,NULL) ON CONFLICT ("leagueId") DO UPDATE SET status=excluded.status', (status,))
                self.db.connection.commit()
                before = self.state()
                with self.assertRaises(ValueError): self.service.start_for_job(10)
                self.assertEqual(self.state(), before)

    def test_start_requires_pre_draft_league(self):
        for status in ('Drafting', 'Post-Draft', 'In-Season', 'Completed'):
            self.db.connection.execute('UPDATE "League" SET status=? WHERE id=10', (status,))
            self.db.connection.commit()
            before = self.state()
            with self.assertRaises(ValueError): self.service.start(self.actor, 10)
            self.assertEqual(self.state(), before)

    def test_start_rejects_stale_turns(self):
        self.db.connection.execute('INSERT INTO "DraftTurn" ("leagueId","overallPickNumber","memberId") VALUES (10,1,12)')
        self.db.connection.commit()
        before = self.state()
        with self.assertRaises(ValueError): self.service.start(self.actor, 10)
        self.assertEqual(self.state(), before)

    def test_start_rejects_extra_members(self):
        self.db.connection.execute('INSERT INTO "LeagueMember" (id,"leagueId","userId","draftOrder") VALUES (13,10,3,3)')
        self.db.connection.commit()
        before = self.state()
        with self.assertRaises(ValueError): self.service.start(self.actor, 10)
        self.assertEqual(self.state(), before)

    def test_pristine_pre_state_can_start(self):
        self.db.connection.execute('INSERT INTO "DraftState" ("leagueId",status,"currentOverallPickNumber") VALUES (10,?,1)', ('pre',))
        self.db.connection.commit()
        self.assertEqual(self.service.start(self.actor,10)['state']['status'], 'live')

    def test_pre_state_with_progress_cannot_start(self):
        self.db.connection.execute('INSERT INTO "DraftState" ("leagueId",status,"currentOverallPickNumber") VALUES (10,?,3)', ('pre',))
        self.db.connection.commit()
        before = self.state()
        with self.assertRaises(ValueError): self.service.start(self.actor,10)
        self.assertEqual(self.state(), before)
