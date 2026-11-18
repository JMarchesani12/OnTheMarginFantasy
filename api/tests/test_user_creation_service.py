"""Bootstrap service contracts with real synthetic profile SQL, no HTTP context."""
import unittest
import sqlite3
from contextlib import contextmanager
from sqlalchemy.exc import IntegrityError
from endpoints.user.service import UserService
from endpoints.user.contracts import (ProfileSubject, ProfileAlreadyExists,
    ProfileIdentityAmbiguous, ProfileCreationRejected, ProfileNotFound)
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
        self.assertEqual(UserService(self.db).get_profile_by_uuid_for_job(profiles.ALICE)['uuid'],profiles.ALICE)

    def test_constraint_failure_is_domain_error_for_actor_and_job(self):
        execute=self.db.execute
        def fail(statement,params):
            if 'INSERT INTO' in str(statement):
                raise IntegrityError(str(statement),params,Exception('private collision'))
            return execute(statement,params)
        self.db.execute=fail
        with self.assertRaisesRegex(ProfileCreationRejected,'User creation failed'):
            self.service.create_profile(ProfileSubject(NEW,'new@example.test'),'New')
        with self.assertRaisesRegex(ProfileCreationRejected,'User creation failed'):
            UserService(self.db).create_profile_for_job('new@example.test','New',NEW)
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

    def test_job_creation_validation_and_missing_uuid_contracts(self):
        model=UserService(self.db)
        with self.assertRaisesRegex(ProfileCreationRejected,'email is required'):
            model.create_profile_for_job('   ','New',NEW)
        row=model.create_profile_for_job(' new@example.test ',None,NEW)
        self.assertEqual(row['displayName'],'')
        self.assertEqual(model.get_profile_by_uuid_for_job(NEW),row)
        with self.assertRaisesRegex(ProfileNotFound,'User not found'):
            model.get_profile_by_uuid_for_job('missing')
        with self.assertRaises(ProfileNotFound):
            self.service.get_profile_by_uuid_for_job('missing')

    def test_unique_race_rechecks_subject_after_rollback_and_returns_existing_conflict(self):
        # A peer's committed row is hidden only from the first (stale) read.
        self.db.connection.execute('INSERT INTO "User" (id,uuid,email,"displayName") VALUES (3,?,?,?)',
                                   (NEW, 'new@example.test', 'Peer'))
        self.db.connection.commit()
        execute = self.db.execute
        reads = []
        class UniqueViolation(Exception):
            pgcode = '23505'
        def race(statement, params):
            if 'SELECT id FROM "User"' in str(statement):
                reads.append(True)
                if len(reads) == 1:
                    return execute(statement, dict(params, subject='missing'))
            try:
                return execute(statement, params)
            except sqlite3.IntegrityError as exc:
                raise IntegrityError(str(statement), params, UniqueViolation('private constraint details')) from exc
        self.db.execute = race
        with self.assertRaises(ProfileAlreadyExists):
            self.service.create_profile(ProfileSubject(NEW, 'new@example.test'), 'Overwrite')
        self.assertEqual(self.engine.begins, 2)
        self.assertEqual(self.db.profile(3)['displayName'], 'Peer')
        self.assertEqual(self.count(), 3)

    def test_other_subject_email_collision_stays_rejected_after_unique_recheck(self):
        execute = self.db.execute
        class UniqueViolation(Exception):
            pgcode = '23505'
        def conflict(statement, params):
            try:
                return execute(statement, params)
            except sqlite3.IntegrityError as exc:
                raise IntegrityError(str(statement), params, UniqueViolation('private email collision')) from exc
        self.db.execute = conflict
        with self.assertRaises(ProfileCreationRejected):
            self.service.create_profile(ProfileSubject(NEW, 'alice@example.test'), 'Overwrite')
        self.assertEqual(self.engine.begins, 2)
        self.assertEqual(self.db.profile(1)['displayName'], 'Alice')
        self.assertEqual(self.count(), 2)
