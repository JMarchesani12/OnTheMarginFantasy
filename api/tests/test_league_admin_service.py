"""League deletion policy and atomic cascades on disposable synthetic SQL."""
from endpoints.league.administration.service import LeagueAdminService
import unittest
from actors import UserActor
import test_league_deletion_authorization as deletion
from test_transaction_service import ConnectionOwner


class LeagueAdminServiceTests(unittest.TestCase):
    def setUp(self):
        base=deletion.LeagueDeletionAuthorizationTests();base.setUp()
        self.addCleanup(base.doCleanups)
        self.db,self.state=base.db,base.state
        self.engine=ConnectionOwner(self.db)

    def service(self):
        from endpoints.league.administration.service import LeagueAdminService
        return LeagueAdminService(self.engine)

    def test_actor_required_before_io(self):
        service=self.service()
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError):service.delete(actor,10)
        self.assertEqual(self.engine.begins,0)

    def test_commissioner_projection_cascades_and_replay(self):
        service=self.service();before=self.state()
        result=service.delete(UserActor(1,'alice'),10)
        self.assertEqual(result,{'deletedLeagueId':10,'deletedLeagueName':'Alice League'})
        self.assertEqual(self.engine.begins,1)
        after=self.state()
        self.assertEqual(after['League'],[before['League'][1]])
        for table in ('LeagueMember','LeagueJoinRequest'):
            self.assertEqual(after[table],[r for r in before[table] if r['leagueId']==20])
        with self.assertRaises(ValueError):service.delete(UserActor(1,'alice'),10)
        self.assertEqual(self.state(),after)

    def test_authority_and_missing_league_do_not_mutate(self):
        service=self.service();before=self.state()
        for actor,target in ((UserActor(2,'bob'),10),(UserActor(1,'alice'),20)):
            with self.assertRaises(PermissionError):service.delete(actor,target)
        with self.assertRaises(ValueError):service.delete(UserActor(1,'alice'),999)
        self.assertEqual(self.state(),before)

    def test_post_delete_failure_restores_league_and_dependents(self):
        service=self.service();before=self.state();self.db.fail_after_league_delete=True
        with self.assertRaises(RuntimeError):service.delete(UserActor(1,'alice'),10)
        self.assertEqual(self.state(),before)

    def test_canonical_delegate_checks_authority_and_preserves_coercion(self):
        model=self.engine
        with self.assertRaises(PermissionError):LeagueAdminService(model).delete_for_legacy_commissioner(10, 2)
        self.assertEqual(LeagueAdminService(model).delete_for_legacy_commissioner(10, '1'),{'deletedLeagueId':10,'deletedLeagueName':'Alice League'})
