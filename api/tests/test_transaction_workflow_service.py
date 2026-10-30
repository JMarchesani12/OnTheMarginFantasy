"""Remaining transaction actor/job contracts using existing real scoped SQL fixtures."""
import json
import unittest
from unittest.mock import patch
from flask import Flask
from actors import UserActor
import test_trade_veto_authorization as fixture
from endpoints.transaction.transactionModel import TransactionModel
from endpoints.transaction.transactionEndpoints import TransactionEndpoints


class TransactionWorkflowTests(unittest.TestCase):
    def setUp(self):
        base = fixture.TradeVetoAuthorizationTests();base.setUp();self.addCleanup(base.doCleanups)
        self.db,self.state = base.db,base.state

    def service(self):
        from endpoints.transaction.workflow_service import TransactionWorkflowService
        return TransactionWorkflowService(self.db)

    def test_actor_is_required_before_any_io_for_all_interactive_operations(self):
        from endpoints.transaction.workflow_service import TransactionWorkflowService
        class NoIO:
            def connect(self): raise AssertionError('unexpected I/O')
            def begin(self): raise AssertionError('unexpected I/O')
        service = TransactionWorkflowService(NoIO())
        for actor in (None,1,{'user_id':1}):
            for call in (lambda:service.propose(actor,10,100,11,12,[101],[102]),
                         lambda:service.respond(actor,10,1,'ACCEPT',12),
                         lambda:service.cancel(actor,10,1,11),lambda:service.veto(actor,10,1,13),
                         lambda:service.free_agency(actor,10,100,1,11,103,101),
                         lambda:service.open_trades(actor,10,11)):
                with self.assertRaises(TypeError):call()

    def test_owned_proposal_and_wrong_owner_preserve_slots(self):
        service = self.service();before = self.state()
        with self.assertRaises(PermissionError):service.propose(UserActor(2,'bob'),10,100,11,12,[101],[102])
        self.assertEqual(self.state(),before)
        result = service.propose(UserActor(1,'alice'),10,100,11,12,[101],[102])
        self.assertEqual(result['status'],'PROPOSED')
        self.assertEqual(self.state()['LeagueTeamSlot'],before['LeagueTeamSlot'])

    def test_accept_reject_cancel_and_veto_toggle_use_verified_roles(self):
        service = self.service()
        with self.assertRaises(PermissionError):service.respond(UserActor(1,'alice'),10,1,'ACCEPT',12)
        self.assertEqual(service.respond(UserActor(2,'bob'),10,1,'ACCEPT',12)['status'],'PENDING_APPLY')
        self.db.connection.execute('UPDATE "Transaction" SET status=\'PROPOSED\' WHERE id=1');self.db.connection.commit()
        self.assertEqual(service.veto(UserActor(3,'voter'),10,1,13)['vetoCount'],1)
        self.assertEqual(service.veto(UserActor(3,'voter'),10,1,13)['vetoCount'],0)
        self.assertEqual(service.cancel(UserActor(1,'alice'),10,1,11)['status'],'CANCELLED')

    def test_free_agency_effective_week_roster_pending_and_swap_exception_identity(self):
        service = self.service();before = self.state()['LeagueTeamSlot']
        result = service.free_agency(UserActor(1,'alice'),10,100,999,11,103,101)
        self.assertEqual((result['status'],result['weekNumber'],result['memberRosterTeamIds']),('PENDING_APPLY',1,[103]))
        self.assertEqual(self.state()['LeagueTeamSlot'],before)
        self.db.connection.execute('UPDATE "League" SET settings=? WHERE id=10',(json.dumps({'roster':{'maxSwaps':1}}),));self.db.connection.commit()
        self.assertIs(TransactionModel.SwapLimitExceeded,service.SwapLimitExceeded)
        with self.assertRaises(TransactionModel.SwapLimitExceeded):
            service.free_agency(UserActor(1,'alice'),10,100,1,11,None,101)

    def test_mutation_failure_restores_trade_state(self):
        service = self.service();before = self.state();execute = self.db.execute
        def fail(statement,params=None):
            result = execute(statement,params)
            if 'SET status = :status' in str(statement):raise RuntimeError('synthetic after-action failure')
            return result
        self.db.execute = fail
        with self.assertRaisesRegex(RuntimeError,'after-action'):
            service.cancel(UserActor(1,'alice'),10,1,11)
        self.assertEqual(self.state(),before)

    def test_legacy_helper_override_and_explicit_job_dispatch(self):
        from endpoints.transaction.workflow_service import TransactionWorkflowService
        self.assertTrue(issubclass(TransactionModel,TransactionWorkflowService))
        class Custom(TransactionModel):
            def _get_week_for_league(self,*args):raise ValueError('custom week hook')
        model = Custom.__new__(Custom)
        with self.assertRaisesRegex(ValueError,'custom week hook'):
            model.free_agency_add_drop(10,100,1,11,None,101)
        service = self.service()
        self.db.connection.execute('UPDATE "Transaction" SET status=\'COMPLETED\' WHERE id=1');self.db.connection.commit()
        with self.assertRaisesRegex(ValueError,'not pending'):
            service.apply_pending_for_job(1)

    def test_unregistered_legacy_week_lock_has_a_working_connection_owner(self):
        endpoint = TransactionEndpoints(self.db);app = Flask(__name__)
        with patch.object(TransactionModel,'assert_week_rosters_valid',return_value=None),app.app_context():
            response,status = endpoint.lock_week(10,100)
        self.assertEqual((status,response.get_json()),(200,{'message':'Week locked successfully','leagueId':10,'weekId':100}))
        row = self.db.connection.execute('SELECT "isLocked" FROM "Week" WHERE id=100').fetchone()
        self.assertTrue(row[0])
