"""Draft order authority, guards, bump/reorder atomicity and compatibility."""
import unittest
from actors import UserActor
from endpoints.draft.control_service import DraftControlService
from endpoints.draft.pick_service import DraftPickService
import test_draft_control_authorization as controls
from test_transaction_service import ConnectionOwner


class DraftOrderServiceTests(unittest.TestCase):
    def setUp(self):
        base=controls.DraftControlAuthorizationTests();base.setUp();base.prepare('order');self.addCleanup(base.doCleanups)
        self.db,self.state=base.db,base.state;self.engine=ConnectionOwner(self.db);self.service=DraftControlService(self.engine)
        self.actor=UserActor(1,'alice')
    def test_actor_and_empty_input_before_io(self):
        self.assertTrue(hasattr(self.service,'set_order'),'order operation missing')
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError):self.service.set_order(actor,10,[12,11])
        with self.assertRaises(ValueError):self.service.set_order(self.actor,10,[])
        self.assertEqual(self.engine.begins,0)
    def test_swap_projection_and_reject_partial_list(self):
        self.assertTrue(hasattr(self.service,'set_order'),'order operation missing')
        result=self.service.set_order(self.actor,10,[12,11])
        self.assertEqual(result,{'members':[{'memberId':12,'userId':2,'teamName':'Bob Open','draftOrder':1},
                                          {'memberId':11,'userId':1,'teamName':'Alice Open','draftOrder':2}]})
        self.assertEqual(self.engine.begins,1)
        before=self.state()
        with self.assertRaises(ValueError):self.service.set_order(self.actor,10,[11])
        self.assertEqual(self.state(),before)
    def test_authority_duplicate_foreign_and_started_guards(self):
        self.assertTrue(hasattr(self.service,'set_order'),'order operation missing')
        before=self.state()
        with self.assertRaises(PermissionError):self.service.set_order(UserActor(2,'bob'),10,[12,11])
        for ids in ([12,12],[21,11],[999]):
            with self.assertRaises(ValueError):self.service.set_order(self.actor,10,ids)
        self.assertEqual(self.state(),before)
        for status in ('live','paused','complete'):
            self.db.connection.execute('INSERT INTO "DraftState" ("leagueId",status) VALUES (10,?) ON CONFLICT ("leagueId") DO UPDATE SET status=excluded.status',(status,));self.db.connection.commit()
            before=self.state()
            with self.assertRaises(ValueError):self.service.set_order(self.actor,10,[12,11])
            self.assertEqual(self.state(),before)
    def test_post_bump_failure_and_late_authority_restore_entire_state(self):
        self.assertTrue(hasattr(self.service,'set_order'),'order operation missing')
        before=self.state()
        def fail(sql):
            if 'WITH input AS' in sql:raise RuntimeError('synthetic post-bump failure')
        self.db.before_query=fail
        with self.assertRaises(RuntimeError):self.service.set_order(self.actor,10,[12,11])
        self.assertEqual(self.state(),before)
        checks=[]
        def revoke(sql):
            if 'SELECT commissioner FROM "League"' in sql:
                checks.append(True)
                if len(checks)==2:self.db.connection.execute('UPDATE "League" SET commissioner=2 WHERE id=10')
        self.db.before_query=revoke
        with self.assertRaises(PermissionError):self.service.set_order(self.actor,10,[12,11])
        self.assertEqual(self.state(),before)
    def test_canonical_trusted_defaults_and_coercion(self):
        model=DraftPickService(self.engine)
        self.assertEqual(DraftControlService(model.db).set_order_for_job(10, [12, 11])['members'][0]['memberId'],12)
        self.assertEqual(DraftControlService(model.db).set_order_for_legacy_user_id(10, [11, 12], '1')['members'][0]['memberId'],11)

    def test_malformed_member_ids_fail_without_mutation(self):
        before = self.state()
        for ids in ([True, 12], [11.0, 12], ['11', 12], [11, 11], [11], [11, 12, 21], '11,12'):
            with self.subTest(ids=ids):
                with self.assertRaises(ValueError):
                    self.service.set_order(self.actor, 10, ids)
                self.assertEqual(self.state(), before)

    def test_late_lifecycle_and_unknown_state_cannot_reorder(self):
        for status in ('Drafting', 'Post-Draft', 'In-Season', 'Completed'):
            self.db.connection.execute('UPDATE "League" SET status=? WHERE id=10', (status,))
            self.db.connection.commit()
            before = self.state()
            with self.assertRaises(ValueError): self.service.set_order(self.actor, 10, [12, 11])
            self.assertEqual(self.state(), before)
        self.db.connection.execute('UPDATE "League" SET status=? WHERE id=10', ('Pre-Draft',))
        self.db.connection.execute('INSERT INTO "DraftState" ("leagueId",status) VALUES (10,?)', ('unknown',))
        self.db.connection.commit()
        before = self.state()
        with self.assertRaises(ValueError): self.service.set_order(self.actor, 10, [12, 11])
        self.assertEqual(self.state(), before)
