"""Approval policy, transaction atomicity and compatibility on synthetic SQL."""
import json
import sqlite3
import unittest
from actors import UserActor
from endpoints.league.admission.service import AdmissionService
from endpoints.league.admission.contracts import AdmissionDenied, AdmissionRejected
from endpoints.league.leagueModel import LeagueModel
import test_join_request_approval_authorization as approval
from test_transaction_service import ConnectionOwner


class AdmissionApprovalServiceTests(unittest.TestCase):
    def setUp(self):
        base = approval.JoinRequestApprovalAuthorizationTests(); base.setUp()
        self.addCleanup(base.doCleanups)
        self.db, self.state = base.db, base.state
        self.engine = ConnectionOwner(self.db)
        self.service = AdmissionService(self.engine)
        self.actor = UserActor(1, 'alice')

    def test_verified_actor_required_before_io(self):
        self.assertTrue(callable(getattr(self.service, 'approve_request', None)), 'actor approval operation missing')
        for actor in (None, 1, {'user_id': 1}):
            with self.assertRaises(TypeError): self.service.approve_request(actor, 10, 101)
        self.assertEqual(self.engine.begins, 0)

    def test_approval_allocates_member_updates_count_and_preserves_settings(self):
        self.assertTrue(hasattr(self.service, 'approve_request'), 'actor approval operation missing')
        self.db.connection.execute('UPDATE "Sport" SET "maxPlayersToHaveMaxRounds"=2')
        self.db.connection.commit()
        result = self.service.approve_request(self.actor, 10, 101)
        self.assertEqual(self.engine.begins, 1)
        self.assertEqual(set(result), {'request', 'member'})
        self.assertEqual((result['request']['status'], result['request']['resolvedByUserId']), ('APPROVED', 1))
        member = next(r for r in self.state()['LeagueMember'] if r['userId'] == 3)
        self.assertEqual((member['teamName'], member['draftOrder'], member['seasonPoints']), ('Applicant Team', 3, 0))
        league = self.state()['League'][0]
        self.assertEqual(league['numPlayers'], 3)
        self.assertEqual(json.loads(league['settings']), {'draft': {'numberOfRounds': 7}, 'timezone': 'UTC'})
        after = self.state()
        with self.assertRaises(AdmissionRejected): self.service.approve_request(self.actor, 10, 101)
        self.assertEqual(self.state(), after)

    def test_authority_scope_and_pending_guards_do_not_mutate(self):
        self.assertTrue(hasattr(self.service, 'approve_request'), 'actor approval operation missing')
        before = self.state()
        with self.assertRaises(AdmissionDenied): self.service.approve_request(UserActor(2, 'bob'), 10, 101)
        for league, request in ((999, 101), (10, 201), (10, 999), (10, 102)):
            with self.assertRaises(AdmissionRejected): self.service.approve_request(self.actor, league, request)
        self.assertEqual(self.state(), before)

    def test_empty_team_falls_back_and_rounds_floor_at_one(self):
        self.assertTrue(hasattr(self.service, 'approve_request'), 'actor approval operation missing')
        self.db.connection.execute('UPDATE "LeagueJoinRequest" SET "teamName"=NULL WHERE id=101')
        self.db.connection.execute('UPDATE "League" SET "numPlayers"=20 WHERE id=10')
        self.db.connection.commit()
        result = self.service.approve_request(self.actor, 10, 101)
        self.assertEqual(result['member']['teamName'], 'My Team')
        self.assertEqual(json.loads(self.state()['League'][0]['settings'])['draft']['numberOfRounds'], 1)

    def test_existing_member_constraint_is_operational_failure_and_atomic(self):
        self.assertTrue(hasattr(self.service, 'approve_request'), 'actor approval operation missing')
        self.db.connection.execute('UPDATE "LeagueJoinRequest" SET "userId"=2 WHERE id=101')
        self.db.connection.commit(); before = self.state()
        with self.assertRaises(sqlite3.IntegrityError): self.service.approve_request(self.actor, 10, 101)
        self.assertEqual(self.state(), before)

    def test_failure_after_member_insert_rolls_back_every_table(self):
        self.assertTrue(hasattr(self.service, 'approve_request'), 'actor approval operation missing')
        before = self.state(); self.db.fail_league_update = True
        with self.assertRaises(RuntimeError): self.service.approve_request(self.actor, 10, 101)
        self.assertEqual(self.state(), before)

    def test_trusted_and_supplied_connection_facades_remain_context_free(self):
        model = LeagueModel.__new__(LeagueModel); model.db = self.engine
        result = model.approve_join_request(10, 101, 4)
        self.assertEqual(result['request']['resolvedByUserId'], 4)
        self.assertEqual(self.engine.begins, 1)
        with self.engine.begin() as conn:
            result = model._approve_join_request(conn, 20, 201, 4)
        self.assertEqual(result['request']['resolvedByUserId'], 4)
        self.assertEqual(self.engine.begins, 2)
