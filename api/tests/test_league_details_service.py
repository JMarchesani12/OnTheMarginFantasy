"""Details/listing scopes, normalization and read-only supplied-connection boundary."""
import unittest
from actors import UserActor
from endpoints.league.reads.service import LeagueReadService
import test_league_read_authorization as reads
import test_own_league_listing as listings
from test_transaction_service import ConnectionOwner


class LeagueDetailsServiceTests(unittest.TestCase):
    def setUp(self):
        base=reads.LeagueReadAuthorizationTests();base.setUp();self.addCleanup(base.doCleanups)
        self.db=base.db;self.engine=ConnectionOwner(self.db);self.service=LeagueReadService(self.engine);self.calls=[]
    def sync(self):
        self.assertEqual(self.engine.active,0);self.calls.append('sync')
    def test_actor_and_scoped_details_are_read_only(self):
        self.assertTrue(hasattr(self.service,'details'),'details operation missing')
        with self.assertRaises(TypeError):self.service.details(None,10)
        self.assertEqual(self.calls,[]);self.assertEqual(self.engine.begins,0)
        row=self.service.details(UserActor(2,'bob'),10)
        self.assertEqual((row['id'],row['name'],row['currentWeekId']),(10,'Open League',None))
        self.assertIsNone(self.service.details(UserActor(3,'outsider'),10))
        self.assertIsNone(self.service.details(UserActor(1,'alice'),999))
        self.assertEqual(self.calls,[])
    def test_old_callback_signature_is_rejected_instead_of_ignored(self):
        with self.assertRaises(TypeError):self.service.details(UserActor(1,'alice'),10,self.sync)
        self.assertEqual(self.engine.begins,0)
    def test_trusted_and_scoped_read_only_model(self):
        model=self.engine
        self.assertEqual(LeagueReadService(model).details_for_job(30)['id'],30)
        self.assertIsNone(LeagueReadService(model).details_for_reader_id(30, 1))
        self.assertEqual(self.calls,[])


class OwnLeagueReadServiceTests(unittest.TestCase):
    def setUp(self):
        base=listings.OwnLeagueListingTests();base.setUp();self.addCleanup(base.doCleanups)
        self.engine=ConnectionOwner(base.db);self.service=LeagueReadService(self.engine);self.calls=[]
    def sync(self):
        self.assertEqual(self.engine.active,0);self.calls.append('sync')
    def test_actor_membership_stage_filters_and_normalization(self):
        self.assertTrue(hasattr(self.service,'mine'),'own listing operation missing')
        with self.assertRaises(TypeError):self.service.mine(None)
        self.assertEqual(self.calls,[])
        bob=UserActor(2,'bob')
        rows=self.service.mine(bob)
        self.assertEqual([r['leagueId'] for r in rows],[10,20])
        self.assertEqual([r['teamName'] for r in rows],['Bob Team','Bob Completed'])
        self.assertEqual([r['leagueId'] for r in self.service.mine(bob,'ACTIVE')],[10])
        self.assertEqual([r['leagueId'] for r in self.service.mine(bob,'completed')],[20])
        self.assertEqual(self.service.mine(bob,'unknown'),rows)
        self.assertEqual(self.service.mine(UserActor(3,'outsider')),[])
        self.assertEqual(self.engine.connects,5)
    def test_invalid_stage_and_read_only_listing(self):
        model=self.engine
        with self.assertRaises(AttributeError):LeagueReadService(model).mine_for_user_id(2, 42)
        self.assertEqual(self.calls,[])
        self.assertEqual([r['leagueId'] for r in LeagueReadService(model).mine_for_user_id(2, None)],[10,20])
