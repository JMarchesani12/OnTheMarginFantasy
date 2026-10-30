"""Details/listing scopes, normalization and pre-read lifecycle capability."""
import unittest
from actors import UserActor
from endpoints.league.league_read_service import LeagueReadService
from endpoints.league.leagueModel import LeagueModel
import test_league_read_authorization as reads
import test_own_league_listing as listings
from test_transaction_service import ConnectionOwner


class LeagueDetailsServiceTests(unittest.TestCase):
    def setUp(self):
        base=reads.LeagueReadAuthorizationTests();base.setUp();self.addCleanup(base.doCleanups)
        self.db=base.db;self.engine=ConnectionOwner(self.db);self.service=LeagueReadService(self.engine);self.calls=[]
    def sync(self):
        self.assertEqual(self.engine.active,0);self.calls.append('sync')
    def test_actor_and_scoped_details_sync_before_read(self):
        self.assertTrue(hasattr(self.service,'details'),'details operation missing')
        with self.assertRaises(TypeError):self.service.details(None,10,self.sync)
        self.assertEqual(self.calls,[]);self.assertEqual(self.engine.begins,0)
        row=self.service.details(UserActor(2,'bob'),10,self.sync)
        self.assertEqual((row['id'],row['name'],row['currentWeekId']),(10,'Open League',None))
        self.assertIsNone(self.service.details(UserActor(3,'outsider'),10,self.sync))
        self.assertIsNone(self.service.details(UserActor(1,'alice'),999,self.sync))
        self.assertEqual(self.calls,['sync']*3)
    def test_sync_failure_prevents_read(self):
        self.assertTrue(hasattr(self.service,'details'),'details operation missing')
        def fail():raise RuntimeError('synthetic sync failure')
        with self.assertRaises(RuntimeError):self.service.details(UserActor(1,'alice'),10,fail)
        self.assertEqual(self.engine.begins,0)
    def test_trusted_and_scoped_model_with_deferred_callback(self):
        model=LeagueModel.__new__(LeagueModel);model.db=self.engine;model.sync_due_league_statuses=self.sync
        self.assertEqual(model.get_league(30)['id'],30)
        self.assertIsNone(model.get_league(30,reader_user_id=1))
        self.assertEqual(self.calls,['sync','sync'])


class OwnLeagueReadServiceTests(unittest.TestCase):
    def setUp(self):
        base=listings.OwnLeagueListingTests();base.setUp();self.addCleanup(base.doCleanups)
        self.engine=ConnectionOwner(base.db);self.service=LeagueReadService(self.engine);self.calls=[]
    def sync(self):
        self.assertEqual(self.engine.active,0);self.calls.append('sync')
    def test_actor_membership_stage_filters_and_normalization(self):
        self.assertTrue(hasattr(self.service,'mine'),'own listing operation missing')
        with self.assertRaises(TypeError):self.service.mine(None,self.sync)
        self.assertEqual(self.calls,[])
        bob=UserActor(2,'bob')
        rows=self.service.mine(bob,self.sync)
        self.assertEqual([r['leagueId'] for r in rows],[10,20])
        self.assertEqual([r['teamName'] for r in rows],['Bob Team','Bob Completed'])
        self.assertEqual([r['leagueId'] for r in self.service.mine(bob,self.sync,'ACTIVE')],[10])
        self.assertEqual([r['leagueId'] for r in self.service.mine(bob,self.sync,'completed')],[20])
        self.assertEqual(self.service.mine(bob,self.sync,'unknown'),rows)
        self.assertEqual(self.service.mine(UserActor(3,'outsider'),self.sync),[])
        self.assertEqual(self.engine.connects,5)
    def test_invalid_legacy_stage_before_sync_and_legacy_listing(self):
        model=LeagueModel.__new__(LeagueModel);model.db=self.engine;model.sync_due_league_statuses=self.sync
        with self.assertRaises(AttributeError):model.get_leagues_for_user(2,stage=42)
        self.assertEqual(self.calls,[])
        self.assertEqual([r['leagueId'] for r in model.get_leagues_for_user(2,None)],[10,20])
