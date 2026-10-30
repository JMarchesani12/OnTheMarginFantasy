"""Member update ownership, allowlist and rollback against synthetic real SQL."""
import unittest
from actors import UserActor
import test_member_profile_authorization as profile
from test_transaction_service import ConnectionOwner
from endpoints.league.leagueModel import LeagueModel


class MemberServiceTests(unittest.TestCase):
    def setUp(self):
        base = profile.MemberProfileAuthorizationTests(); base.setUp()
        self.addCleanup(base.doCleanups)
        self.db, self.member = base.db, base.member
        self.engine = ConnectionOwner(self.db)

    def service(self):
        from endpoints.league.member_service import MemberService
        return MemberService(self.engine)

    def test_actor_and_name_required_before_io(self):
        service = self.service()
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError): service.rename(actor,11,'New')
        for name in (None,42,'','  '):
            with self.assertRaises(ValueError): service.rename(UserActor(1,'alice'),11,name)
        self.assertEqual(self.engine.begins,0)

    def test_owner_projection_raw_name_and_concealed_foreign_target(self):
        service = self.service(); before = self.member(11)
        row = service.rename(UserActor(1,'alice'),11,' New ')
        self.assertEqual(row,{**before,'teamName':' New '})
        self.assertEqual(self.engine.begins,1)
        for member in (12,21,999):
            with self.assertRaises(LookupError): service.rename(UserActor(1,'alice'),member,'Stolen')
        self.assertEqual(self.member(12)['teamName'],'Bob Team')

    def test_trusted_allowlist_and_bound_values_do_not_change_identity(self):
        service = self.service(); before = self.member(12)
        row = service.update_for_job(12,{'userId':1,'leagueId':20,'teamName':"O'Brien :x",'draftOrder':4,'seasonPoints':99})
        self.assertEqual(row,{**before,'teamName':"O'Brien :x",'draftOrder':4,'seasonPoints':99})
        for payload in ({},{'userId':1}):
            with self.assertRaises(ValueError): service.update_for_job(12,payload)
        with self.assertRaises(ValueError): service.update_for_job(999,{'teamName':'Missing'})

    def test_post_update_failure_rolls_back_both_paths(self):
        service = self.service(); before = self.member(11); execute = self.db.execute
        def fail(statement,params):
            result = execute(statement,params)
            if 'UPDATE "LeagueMember"' in str(statement):
                result.mappings().first()
                raise RuntimeError('synthetic post-update failure')
            return result
        self.db.execute = fail
        for operation in (lambda:service.rename(UserActor(1,'alice'),11,'New'),
                          lambda:service.update_for_job(11,{'seasonPoints':99})):
            with self.assertRaises(RuntimeError): operation()
            self.assertEqual(self.member(11),before)

    def test_db_only_legacy_facade_preserves_permissive_owner_and_trusted_semantics(self):
        model = LeagueModel.__new__(LeagueModel); model.db = self.engine
        self.assertEqual(model.update_owned_league_member(11,1,'')['teamName'],'')
        self.assertEqual(model.update_league_member(12,{'seasonPoints':99})['seasonPoints'],99)
        with self.assertRaises(LookupError): model.update_owned_league_member(12,1,'Stolen')
