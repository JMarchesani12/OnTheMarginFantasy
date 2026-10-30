"""Admission policy/transaction contracts against actual synthetic SQL."""
import unittest
from actors import UserActor
from endpoints.league.admission_service import AdmissionService
from endpoints.league.contracts import AdmissionDenied, AdmissionRejected
import test_join_request_listing_authorization as listing
import test_join_request_cancellation_authorization as cancellation
from test_transaction_service import ConnectionOwner


class AdmissionListingServiceTests(unittest.TestCase):
    def setUp(self):
        base=listing.JoinRequestListingAuthorizationTests()
        base.setUp()
        self.addCleanup(base.doCleanups)
        self.db=base.db
        self.engine=ConnectionOwner(self.db)
        self.service=AdmissionService(self.engine)

    def test_actor_is_required_before_io(self):
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError): self.service.list_requests(actor,10)
        self.assertEqual(self.engine.begins,0)

    def test_listing_projection_order_filters_and_one_connection(self):
        rows=self.service.list_requests(UserActor(1,'alice'),10)
        self.assertEqual([r['id'] for r in rows],[102,101])
        self.assertEqual(rows[1]['userEmail'],'bob@example.test')
        self.assertEqual(self.engine.begins,1)
        self.assertEqual([r['id'] for r in self.service.list_requests(UserActor(1,'alice'),10,'PENDING')],[101])
        with self.assertRaises(AdmissionDenied): self.service.list_requests(UserActor(2,'bob'),10)
        with self.assertRaises(AdmissionRejected): self.service.list_requests(UserActor(1,'alice'),999)

    def test_final_query_rechecks_commissioner_and_trusted_listing_stays_explicit(self):
        self.db.before_listing=lambda:self.db.connection.execute('UPDATE "League" SET commissioner=2 WHERE id=10')
        self.assertEqual(self.service.list_requests(UserActor(1,'alice'),10),[])
        self.assertEqual([r['id'] for r in self.service.list_requests_for_job(20)],[201])
        self.assertEqual(self.service.list_requests_for_job(999),[])


class AdmissionCancellationServiceTests(unittest.TestCase):
    def setUp(self):
        base=cancellation.JoinRequestCancellationAuthorizationTests()
        base.setUp()
        self.addCleanup(base.doCleanups)
        self.db,self.state=base.db,base.state
        self.engine=ConnectionOwner(self.db)
        self.service=AdmissionService(self.engine)

    def test_actor_required_and_owner_cancel_one_transaction_rejects_replay(self):
        with self.assertRaises(TypeError): self.service.cancel_request(None,10,101)
        self.assertEqual(self.engine.begins,0)
        row=self.service.cancel_request(UserActor(2,'bob'),10,101)
        self.assertEqual((row['status'],row['userId'],row['resolvedByUserId']),('CANCELLED',2,None))
        self.assertEqual(self.engine.begins,1)
        after=self.state()
        with self.assertRaises(AdmissionRejected): self.service.cancel_request(UserActor(2,'bob'),10,101)
        self.assertEqual(self.state(),after)

    def test_commissioner_cannot_cancel_foreign_request_and_url_scope_is_preserved(self):
        before=self.state()
        with self.assertRaises(AdmissionDenied): self.service.cancel_request(UserActor(1,'commissioner'),10,101)
        with self.assertRaises(AdmissionRejected): self.service.cancel_request(UserActor(2,'bob'),20,101)
        self.assertEqual(self.state(),before)

    def test_failure_after_update_rolls_back(self):
        before=self.state()
        self.db.fail_after_update=True
        with self.assertRaises(RuntimeError): self.service.cancel_request(UserActor(2,'bob'),10,101)
        self.assertEqual(self.state(),before)
