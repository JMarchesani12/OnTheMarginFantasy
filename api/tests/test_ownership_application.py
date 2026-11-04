"""Queued ownership application revalidates actual state before committing."""
import unittest
import test_free_agency_authorization as fixture
from test_operational_trusted_contract import ApplyDatabase


class FreeAgentApplicationIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.base = fixture.FreeAgencyAuthorizationTests()
        self.base.database_type = ApplyDatabase
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.db, self.service = self.base.db, self.base.model

    def pending(self, drops, adds):
        import json
        self.db.connection.execute('''INSERT INTO "Transaction"
            (id,leagueId,weekId,type,memberFromId,memberToId,status,fromTeamIds,toTeamIds)
            VALUES (1,10,101,'FREE_AGENT',11,11,'PENDING_APPLY',?,?)''',
            (json.dumps(drops), json.dumps(adds)))
        self.db.connection.commit()

    def assert_rejected(self):
        before = self.base.state()
        with self.assertRaises(ValueError):
            self.service.apply_free_agent_transaction(1)
        self.assertEqual(self.base.state(), before)

    def test_stale_queued_add_cannot_take_another_members_team(self):
        self.pending([], [102])
        self.assert_rejected()

    def test_stale_queued_drop_cannot_complete_without_owned_team(self):
        self.pending([103], [])
        self.assert_rejected()

    def test_queued_add_rechecks_conference_cap_before_completion(self):
        self.pending([], [103])
        self.db.connection.execute('UPDATE SportConference SET maxTeamsPerOwner=1')
        self.db.connection.commit()
        self.assert_rejected()

    def test_valid_drop_then_add_preserves_end_exclusive_history(self):
        self.pending([101], [103])
        self.service.apply_free_agent_transaction(1)
        state = self.base.state()
        self.assertEqual(state['Transaction'][0]['status'], 'COMPLETED')
        self.assertEqual(state['LeagueTeamSlot'][0]['droppedWeek'], 2)
        self.assertEqual((state['LeagueTeamSlot'][-1]['sportTeamId'], state['LeagueTeamSlot'][-1]['acquiredWeek']), (103, 2))
        before = state
        with self.assertRaises(ValueError): self.service.apply_free_agent_transaction(1)
        self.assertEqual(self.base.state(), before)

    def test_reservation_checks_share_the_owned_transaction(self):
        from endpoints.transaction.workflow_service import TransactionWorkflowService
        from actors import UserActor
        from test_transaction_service import ConnectionOwner
        engine = ConnectionOwner(self.db)
        result = TransactionWorkflowService(engine).free_agency(UserActor(1, 'alice'), 10, 100, 99, 11, 103, 101)
        self.assertEqual(result['status'], 'PENDING_APPLY')
        self.assertEqual(self.base.state()['Transaction'][0]['toTeamIds'], '[103]')
        self.assertEqual((engine.begins, engine.connects), (1, 0))
