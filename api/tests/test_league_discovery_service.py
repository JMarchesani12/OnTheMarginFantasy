"""Discovery entitlement, names-only previews and bounded anonymous search."""
import unittest
from actors import UserActor
from endpoints.league.reads.service import LeagueReadService
from endpoints.league.leagueModel import LeagueModel
import test_league_read_authorization as reads
import test_public_league_search as searches
from test_transaction_service import ConnectionOwner


class LeagueDiscoveryServiceTests(unittest.TestCase):
    def setUp(self):
        base=reads.LeagueReadAuthorizationTests();base.setUp()
        self.addCleanup(base.doCleanups)
        self.db=base.db;self.engine=ConnectionOwner(self.db);self.service=LeagueReadService(self.engine)

    def test_actor_required_for_access_and_previews_before_io(self):
        for method in ('access','member_previews'):
            self.assertTrue(callable(getattr(self.service,method,None)), method+' operation missing')
            for actor in (None,1,{'user_id':1}):
                with self.assertRaises(TypeError):getattr(self.service,method)(actor,10)
        self.assertEqual(self.engine.begins,0)

    def test_metadata_entitlements_and_internal_projection(self):
        self.assertTrue(hasattr(self.service,'access'),'access operation missing')
        member=self.service.access(UserActor(2,'bob'),10)
        self.assertEqual(member,{'id':10,'name':'Open League','sport':1,'isDiscoverable':1,'commissionerDisplayName':'Alice','fullAccess':1})
        self.assertEqual(self.service.access(UserActor(3,'outsider'),20)['fullAccess'],0)
        self.assertEqual(self.service.access(UserActor(1,'alice'),20)['fullAccess'],1)
        self.assertIsNone(self.service.access(UserActor(1,'alice'),999))
        self.assertEqual(self.engine.begins,4)

    def test_names_only_preview_and_query_time_visibility(self):
        self.assertTrue(hasattr(self.service,'member_previews'),'preview operation missing')
        actor=UserActor(3,'outsider')
        self.assertEqual(self.service.member_previews(actor,10),[
            {'id':11,'teamName':'Alice Open','displayName':'Alice'},{'id':12,'teamName':'Bob Open','displayName':'Bob'}])
        self.assertEqual(self.service.member_previews(actor,20),[])
        self.db.connection.execute('UPDATE "League" SET "isDiscoverable"=0 WHERE id=10');self.db.connection.commit()
        self.assertEqual(self.service.member_previews(actor,10),[])
        self.assertEqual(len(self.service.member_previews(UserActor(2,'bob'),10)),2)
        self.db.connection.execute('DELETE FROM "LeagueMember" WHERE id=12');self.db.connection.commit()
        self.assertEqual(self.service.member_previews(UserActor(2,'bob'),10),[])

    def test_db_only_legacy_metadata_and_preview_methods(self):
        model=LeagueModel.__new__(LeagueModel);model.db=self.engine
        self.assertEqual(model.get_league_read_access(10,2)['fullAccess'],1)
        self.assertEqual(len(model.get_member_previews_for_user(10,3)),2)


class LeaguePublicSearchServiceTests(unittest.TestCase):
    def setUp(self):
        self.db=searches.SearchDatabase();self.addCleanup(self.db.connection.close)
        self.engine=ConnectionOwner(self.db);self.service=LeagueReadService(self.engine)

    def test_short_query_precedes_bad_pagination_and_does_not_open_connection(self):
        self.assertTrue(hasattr(self.service,'search_public'),'public search operation missing')
        self.assertEqual(self.service.search_public(' m ',limit='bad',offset='bad'),[])
        self.assertEqual(self.engine.begins,0)

    def test_normalization_filter_paging_clamps_and_legacy(self):
        self.assertTrue(hasattr(self.service,'search_public'),'public search operation missing')
        rows=self.service.search_public(' Margin ',limit=100,offset=-1)
        self.assertEqual([r['id'] for r in rows],[1,2])
        self.assertEqual(set(rows[0]),{'id','name','sport','numPlayers','status','draftDate','isDiscoverable','commissioner','commissionerDisplayName'})
        self.assertEqual([r['id'] for r in self.service.search_public('Margin',sport_id=2)],[2])
        self.assertEqual([r['id'] for r in self.service.search_public('Margin',limit=0,offset=1)],[2])
        model=LeagueModel.__new__(LeagueModel);model.db=self.engine
        self.assertEqual(model.search_leagues('Margin'),rows)
        with self.assertRaises(ValueError):self.service.search_public('Margin',limit='bad')
