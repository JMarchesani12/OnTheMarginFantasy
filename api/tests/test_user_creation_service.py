"""Bootstrap service contracts with real synthetic profile SQL, no HTTP context."""
import unittest
from contextlib import contextmanager
from sqlalchemy.exc import IntegrityError
from endpoints.user.service import UserService
from endpoints.user.contracts import (ProfileSubject, ProfileAlreadyExists,
    ProfileIdentityAmbiguous, ProfileCreationRejected, ProfileNotFound)
from endpoints.user.userModel import UserModel
import test_profile_regression as profiles
from test_transaction_service import ConnectionOwner

NEW='00000000-0000-4000-8000-000000000003'


class UserCreationServiceTests(unittest.TestCase):
    def setUp(self):
        self.db=profiles.ProfileDatabase()
        self.addCleanup(self.db.connection.close)
        self.engine=ConnectionOwner(self.db)
        self.service=UserService(self.engine)

    def count(self):
        return self.db.connection.execute('SELECT count(*) FROM "User"').fetchone()[0]

    def test_creation_requires_subject_actor_and_valid_identity_before_io(self):
        for actor in (None,1,{'subject':NEW,'email':'new@example.test'}):
            with self.assertRaises(TypeError):
                self.service.create_profile(actor,'New')
        for subject,email in (('', 'new@example.test'),(NEW,''),(NEW,None)):
            with self.assertRaises(ProfileCreationRejected):
                self.service.create_profile(ProfileSubject(subject,email),'New')
        self.assertEqual(self.engine.begins,0)
        self.assertEqual(self.count(),2)

    def test_new_profile_uses_one_transaction_normalizes_claims_and_reloads(self):
        row=self.service.create_profile(ProfileSubject(NEW,' new@example.test '),' New ')
        self.assertEqual(self.engine.begins,1)
        self.assertEqual((row['uuid'],row['email'],row['displayName']),(NEW,'new@example.test','New'))
        self.assertEqual(self.service.get_profile_by_uuid_for_job(NEW),row)
        self.assertEqual(self.count(),3)

    def test_existing_profile_conflicts_without_overwrite(self):
        with self.assertRaises(ProfileAlreadyExists):
            self.service.create_profile(ProfileSubject(profiles.ALICE,'alice@example.test'),'Tampered')
        self.assertEqual(self.db.profile(1)['displayName'],'Alice')
        self.assertEqual(self.count(),2)

    def test_ambiguous_subject_denies_creation_but_legacy_lookup_remains_first_row(self):
        self.db.connection.executescript('''ALTER TABLE "User" RENAME TO original_user;
            CREATE TABLE "User" AS SELECT * FROM original_user;
            INSERT INTO "User" (id,uuid,email) SELECT 3,uuid,'duplicate@example.test' FROM original_user WHERE id=1;''')
        with self.assertRaises(ProfileIdentityAmbiguous):
            self.service.create_profile(ProfileSubject(profiles.ALICE,'alice@example.test'),'Tampered')
        self.assertEqual(self.count(),3)
        self.assertEqual(UserModel(self.db).get_user_by_uuid(profiles.ALICE)['uuid'],profiles.ALICE)

    def test_constraint_failure_is_domain_error_and_legacy_value_error(self):
        execute=self.db.execute
        def fail(statement,params):
            if 'INSERT INTO' in str(statement):
                raise IntegrityError(str(statement),params,Exception('private collision'))
            return execute(statement,params)
        self.db.execute=fail
        with self.assertRaisesRegex(ProfileCreationRejected,'User creation failed'):
            self.service.create_profile(ProfileSubject(NEW,'new@example.test'),'New')
        with self.assertRaisesRegex(ValueError,'User creation failed'):
            UserModel(self.db).create_user('new@example.test','New',NEW)
        self.assertEqual(self.count(),2)

    def test_unexpected_failure_after_insert_rolls_back_and_propagates(self):
        execute=self.db.execute
        def fail(statement,params):
            result=execute(statement,params)
            if 'INSERT INTO' in str(statement):
                result.fetchone()
                raise RuntimeError('synthetic failure after insert')
            return result
        self.db.execute=fail
        with self.assertRaisesRegex(RuntimeError,'after insert'):
            self.service.create_profile(ProfileSubject(NEW,'new@example.test'),'New')
        self.assertEqual(self.count(),2)

    def test_integrity_failure_on_transaction_exit_is_translated_and_rolled_back(self):
        db=self.db
        class CommitFailure:
            @contextmanager
            def begin(self):
                with db:
                    yield db
                    raise IntegrityError('COMMIT',{},Exception('synthetic deferred failure'))
        with self.assertRaisesRegex(ProfileCreationRejected,'User creation failed'):
            UserService(CommitFailure()).create_profile(ProfileSubject(NEW,'new@example.test'),'New')
        self.assertEqual(self.count(),2)

    def test_legacy_create_validation_and_uuid_missing_contracts_remain(self):
        model=UserModel(self.db)
        with self.assertRaisesRegex(ValueError,'email is required'):
            model.create_user('   ','New',NEW)
        row=model.create_user(' new@example.test ',None,NEW)
        self.assertEqual(row['displayName'],'')
        self.assertEqual(model.get_user_by_uuid(NEW),row)
        with self.assertRaisesRegex(ValueError,'User not found'):
            model.get_user_by_uuid('missing')
        with self.assertRaises(ProfileNotFound):
            self.service.get_profile_by_uuid_for_job('missing')
