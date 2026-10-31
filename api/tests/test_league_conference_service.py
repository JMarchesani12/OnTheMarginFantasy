"""Conference scope and season aggregate behavior on synthetic SQL."""
import unittest
from actors import UserActor
from endpoints.league.reads.service import LeagueReadService
from endpoints.league.leagueModel import LeagueModel
import test_league_read_authorization as reads
from test_transaction_service import ConnectionOwner


class LeagueConferenceServiceTests(unittest.TestCase):
    def setUp(self):
        base=reads.LeagueReadAuthorizationTests();base.setUp()
        self.addCleanup(base.doCleanups)
        self.db=base.db;self.engine=ConnectionOwner(self.db);self.service=LeagueReadService(self.engine)
        self.db.connection.executescript('''DELETE FROM "ConferenceMembership"; DELETE FROM "SportConference"; DELETE FROM "Conference";
            INSERT INTO "Conference" VALUES (1,'Zulu'),(2,'Alpha'),(3,'Other');
            INSERT INTO "SportConference" VALUES (1,1,1,2),(2,2,1,1),(3,3,2,5);
            INSERT INTO "ConferenceMembership" VALUES (1,NULL),(1,2026),(1,2025),(2,2025),(3,NULL);''')

    def test_actor_required_before_io(self):
        self.assertTrue(callable(getattr(self.service,'conferences',None)), 'actor conference operation missing')
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError):self.service.conferences(actor,10)
        self.assertEqual(self.engine.begins,0)

    def test_season_null_memberships_zero_fallback_sport_and_order(self):
        self.assertTrue(hasattr(self.service,'conferences'), 'actor conference operation missing')
        row=self.service.conferences(UserActor(2,'bob'),10)
        self.assertEqual(row,{'leagueId':10,'sportId':1,'seasonYear':2026,'conferences':[
            {'sportConferenceId':2,'conferenceId':2,'displayName':'Alpha','maxTeamsPerOwner':1,'teamsInConference':0},
            {'sportConferenceId':1,'conferenceId':1,'displayName':'Zulu','maxTeamsPerOwner':2,'teamsInConference':2}]})
        self.assertEqual((self.engine.begins,self.engine.connects),(1,0))

    def test_missing_denied_and_null_season_skip_aggregate(self):
        self.assertTrue(hasattr(self.service,'conferences'), 'actor conference operation missing')
        self.db.connection.execute('UPDATE "League" SET "seasonYear"=NULL WHERE id=20');self.db.connection.commit()
        execute=self.db.execute
        def no_aggregate(statement,params):
            if 'FROM "SportConference"' in str(statement):raise AssertionError('Rejected read queried aggregate')
            return execute(statement,params)
        self.db.execute=no_aggregate
        for actor,league in ((UserActor(3,'outsider'),10),(UserActor(1,'alice'),999),(UserActor(2,'bob'),20)):
            with self.assertRaises(ValueError):self.service.conferences(actor,league)

    def test_revocation_at_scoped_read_rejects(self):
        self.assertTrue(hasattr(self.service,'conferences'), 'actor conference operation missing')
        def revoke(sql):
            if 'id AS "leagueId"' in sql:
                self.db.connection.execute('DELETE FROM "LeagueMember" WHERE id=12')
        self.db.before_query=revoke
        with self.assertRaises(ValueError):self.service.conferences(UserActor(2,'bob'),10)

    def test_named_trusted_legacy_and_empty_conferences(self):
        self.assertTrue(hasattr(self.service,'conferences_for_job'), 'trusted conference operation missing')
        self.db.connection.execute('UPDATE "League" SET sport=3 WHERE id=30');self.db.connection.commit()
        self.assertEqual(self.service.conferences_for_job(30),{'leagueId':30,'sportId':3,'seasonYear':2026,'conferences':[]})
        model=LeagueModel.__new__(LeagueModel);model.db=self.engine
        self.assertEqual(model.get_league_conferences(30)['conferences'],[])
        with self.assertRaises(ValueError):model.get_league_conferences(30,reader_user_id=1)
        self.assertEqual(model.get_league_conferences(30,reader_user_id=2)['conferences'],[])
