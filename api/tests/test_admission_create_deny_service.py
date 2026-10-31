"""Admission creation/denial orchestration using actual disposable SQL."""
import unittest
from actors import UserActor
from endpoints.league.admission.service import AdmissionService
from endpoints.league.admission.contracts import AdmissionDenied,AdmissionRejected
from endpoints.league.leagueModel import LeagueModel
import test_join_request_authorization as creation
import test_join_request_denial_authorization as denial
from test_transaction_service import ConnectionOwner


class AdmissionCreationServiceTests(unittest.TestCase):
    def setUp(self):
        base=creation.JoinRequestAuthorizationTests();base.setUp()
        self.addCleanup(base.doCleanups)
        self.db,self.rows=base.db,base.requests
        self.engine=ConnectionOwner(self.db);self.service=AdmissionService(self.engine)

    def test_actor_and_name_required_before_io(self):
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError):self.service.create_request(actor,10,team_name='New')
        for name in (None,12,'  '):
            with self.assertRaises(AdmissionRejected):self.service.create_request(UserActor(1,'alice'),10,team_name=name)
        self.assertEqual(self.engine.begins,0)

    def test_normalized_creation_repeat_and_one_transaction_per_call(self):
        first=self.service.create_request(UserActor(1,'alice'),10,'First',' New ')
        repeat=self.service.create_request(UserActor(1,'alice'),10,'Replacement','Other')
        self.assertEqual(first,repeat)
        self.assertEqual(self.engine.begins,2)
        self.assertEqual(len(self.rows()),1)
        self.assertEqual((self.rows()[0]['teamName'],self.rows()[0]['message']),('New','First'))
        with self.assertRaises(AdmissionRejected):self.service.create_request(UserActor(1,'alice'),20,team_name='Member')

    def test_failure_after_insert_rolls_back(self):
        execute=self.db.execute
        def fail(statement,params):
            result=execute(statement,params)
            if 'INSERT INTO "LeagueJoinRequest"' in str(statement):
                result.mappings().first()
                raise RuntimeError('synthetic post-insert failure')
            return result
        self.db.execute=fail
        with self.assertRaises(RuntimeError):self.service.create_request(UserActor(1,'alice'),10,team_name='New')
        self.assertEqual(self.rows(),[])


class AdmissionDenialServiceTests(unittest.TestCase):
    def setUp(self):
        base=denial.JoinRequestDenialAuthorizationTests();base.setUp()
        self.addCleanup(base.doCleanups)
        self.db,self.state=base.db,base.state
        self.engine=ConnectionOwner(self.db);self.service=AdmissionService(self.engine)

    def test_actor_required_and_commissioner_denial_attributed_and_replay_rejected(self):
        with self.assertRaises(TypeError):self.service.deny_request(None,10,101)
        self.assertEqual(self.engine.begins,0)
        row=self.service.deny_request(UserActor(1,'alice'),10,101)
        self.assertEqual((row['status'],row['resolvedByUserId']),('DENIED',1))
        self.assertEqual(self.engine.begins,1)
        after=self.state()
        with self.assertRaises(AdmissionRejected):self.service.deny_request(UserActor(1,'alice'),10,101)
        self.assertEqual(self.state(),after)

    def test_wrong_authority_scope_and_resolved_states_leave_state_unchanged(self):
        before=self.state()
        with self.assertRaises(AdmissionDenied):self.service.deny_request(UserActor(2,'bob'),10,101)
        for request in (201,999,102,103,104):
            with self.assertRaises(AdmissionRejected):self.service.deny_request(UserActor(1,'alice'),10,request)
        self.assertEqual(self.state(),before)

    def test_failure_after_update_rolls_back(self):
        before=self.state();self.db.fail_after_update=True
        with self.assertRaises(RuntimeError):self.service.deny_request(UserActor(1,'alice'),10,101)
        self.assertEqual(self.state(),before)

    def test_explicit_trusted_denial_and_db_only_facade_preserve_bypass(self):
        model=LeagueModel.__new__(LeagueModel);model.db=self.db
        row=model.deny_join_request(10,101,4)
        self.assertEqual((row['status'],row['resolvedByUserId']),('DENIED',4))
