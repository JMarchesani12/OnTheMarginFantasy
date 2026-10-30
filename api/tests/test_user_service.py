"""Direct own-profile service and compatibility contracts on disposable SQL."""
import unittest
from actors import UserActor
from endpoints.user.service import UserService
from endpoints.user.contracts import ProfileAccessDenied, ProfileNotFound, ProfileUpdateRejected
from endpoints.user.userModel import UserModel
import test_profile_regression as profiles
from test_profile_regression import ALICE, BOB
from test_transaction_service import ConnectionOwner


class UserServiceTests(unittest.TestCase):
    def setUp(self):
        self.db=profiles.ProfileDatabase()
        self.addCleanup(self.db.connection.close)
        self.engine=ConnectionOwner(self.db)
        self.service=UserService(self.engine)

    def test_actor_required_before_io_on_both_operations(self):
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError):
                self.service.get_profile(actor,1)
            with self.assertRaises(TypeError):
                self.service.update_profile(actor,1,{'displayName':'Changed'})
        self.assertEqual(self.engine.begins,0)

    def test_foreign_profile_denied_before_io_even_with_invalid_updates(self):
        actor=UserActor(1,ALICE)
        with self.assertRaises(ProfileAccessDenied):
            self.service.get_profile(actor,2)
        with self.assertRaises(ProfileAccessDenied):
            self.service.update_profile(actor,2,None)
        self.assertEqual(self.engine.begins,0)
        self.assertEqual(self.db.profile(2)['displayName'],'Bob')

    def test_own_read_and_update_preserve_projection_identity_and_one_transaction(self):
        actor=UserActor(1,ALICE)
        original=self.service.get_profile(actor,1)
        self.assertEqual(self.engine.begins,1)
        result=self.service.update_profile(actor,1,{'displayName':'Changed','email':'forged',
                                                  'uuid':BOB,'id':2,'trustedJob':True})
        self.assertEqual(self.engine.begins,2)
        self.assertEqual(result,{**original,'displayName':'Changed'})
        self.assertEqual(set(result),{'id','uuid','email','displayName','createdAt'})
        self.assertEqual(self.db.profile(2)['displayName'],'Bob')

    def test_empty_allowed_update_rejected_without_transaction(self):
        with self.assertRaisesRegex(ProfileUpdateRejected,'No valid fields provided'):
            self.service.update_profile(UserActor(1,ALICE),1,{'uuid':BOB,'email':'forged'})
        self.assertEqual(self.engine.begins,0)

    def test_missing_profile_has_domain_failure_and_legacy_value_error(self):
        with self.assertRaisesRegex(ProfileNotFound,'User not found'):
            self.service.get_profile(UserActor(999,'missing'),999)
        with self.assertRaises(ProfileNotFound):
            self.service.update_profile(UserActor(999,'missing'),999,{'displayName':'New'})
        for operation,args in ((UserModel(self.db).get_user_by_id,(999,)),
                               (UserModel(self.db).update_user,(999,{'displayName':'New'}))):
            with self.assertRaisesRegex(ValueError,'User not found'):
                operation(*args)

    def test_failure_after_update_rolls_back_persisted_name(self):
        execute=self.db.execute
        def fail(statement,params):
            result=execute(statement,params)
            if 'UPDATE "User"' in str(statement):
                # Exhaust RETURNING so SQLite permits rollback after our failure.
                result.mappings().first()
                raise RuntimeError('injected persistence failure')
            return result
        self.db.execute=fail
        with self.assertRaisesRegex(RuntimeError,'injected persistence'):
            self.service.update_profile(UserActor(1,ALICE),1,{'displayName':'Forbidden'})
        self.assertEqual(self.db.profile(1)['displayName'],'Alice')

    def test_trusted_model_reads_and_updates_remain_context_free(self):
        model=UserModel(self.db)
        self.assertEqual(model.get_user_by_id(2)['uuid'],BOB)
        self.assertEqual(model.update_user(2,{'displayName':'Trusted'})['displayName'],'Trusted')
        self.assertEqual(model.get_user_by_uuid(BOB)['id'],2)


class ProfileAdapterOrderingTests(unittest.TestCase):
    def setUp(self):
        base=profiles.ProfileRegressionTests()
        base.setUp()
        self.addCleanup(base.doCleanups)
        self.client,self.db,self.headers=base.client,base.db,base.headers

    def test_foreign_target_denied_before_malformed_json_and_private_fields_remain_hidden(self):
        response=self.client.patch('/api/user/2', headers={**self.headers(),'Content-Type':'application/json'}, data='{broken')
        self.assertEqual(response.status_code,404)
        self.assertEqual(response.json,{'message':'User not found'})
        self.assertEqual(self.db.profile(2)['displayName'],'Bob')
