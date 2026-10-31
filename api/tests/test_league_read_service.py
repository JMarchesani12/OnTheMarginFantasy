"""Rules read scopes and projection on synthetic SQL; native types separately."""
import unittest
from actors import UserActor
from endpoints.league.leagueModel import LeagueModel
import test_league_read_authorization as reads
from test_transaction_service import ConnectionOwner


class LeagueRulesReadServiceTests(unittest.TestCase):
    def setUp(self):
        base=reads.LeagueReadAuthorizationTests();base.setUp()
        self.addCleanup(base.doCleanups)
        self.db=base.db;self.engine=ConnectionOwner(self.db)
        self.db.connection.executescript('''DELETE FROM "SportTeam";
            INSERT INTO "SportTeam" VALUES (1,1,'Zulu',2),(2,1,'beta',1),(3,1,'Alpha',1),
                (4,1,'Untiered',NULL),(5,2,'Other Sport',9);
            UPDATE "League" SET "tradeDeadline"='2026-12-01T00:00:00Z' WHERE id=10;''')

    def service(self):
        from endpoints.league.reads.service import LeagueReadService
        return LeagueReadService(self.engine)

    def test_actor_required_before_io(self):
        service=self.service()
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError):service.rules(actor,10)
        self.assertEqual(self.engine.connects,0)

    def test_member_rules_tiers_deadlines_and_one_connection(self):
        row=self.service().rules(UserActor(2,'bob'),10)
        self.assertEqual(self.engine.connects,1);self.assertEqual(self.engine.begins,0)
        self.assertEqual((row['leagueId'],row['leagueName'],row['seasonYear'],row['version']),(10,'Open League',2026,'v1'))
        self.assertEqual([g['tier'] for g in row['tiers']],[1,2,3])
        self.assertEqual([t['teamName'] for t in row['tiers'][0]['teams']],['Alpha','beta'])
        self.assertEqual(row['tiers'][2]['teams'],[{'teamId':4,'teamName':'Untiered','tier':3}])
        self.assertEqual(row['settings']['tradeDeadline'],'2026-12-01T00:00:00Z')
        self.assertIsNone(row['settings']['draftDate'])

    def test_denied_and_missing_skip_team_query(self):
        service=self.service();execute=self.db.execute
        def no_teams(statement,params):
            if 'FROM "SportTeam"' in str(statement):raise AssertionError('Denied read queried teams')
            return execute(statement,params)
        self.db.execute=no_teams
        self.assertIsNone(service.rules(UserActor(3,'outsider'),10))
        self.assertIsNone(service.rules(UserActor(1,'alice'),30))
        self.assertIsNone(service.rules(UserActor(1,'alice'),999))

    def test_member_revocation_at_scoped_query_returns_none(self):
        service=self.service()
        def revoke(sql):
            if 'SELECT id, name, sport,' in sql:
                self.db.connection.execute('DELETE FROM "LeagueMember" WHERE "leagueId"=10 AND "userId"=2')
        self.db.before_query=revoke
        self.assertIsNone(service.rules(UserActor(2,'bob'),10))

    def test_named_trusted_and_db_only_legacy_methods_preserve_optional_scope(self):
        service=self.service()
        self.assertEqual(service.rules_for_job(30)['leagueId'],30)
        model=LeagueModel.__new__(LeagueModel);model.db=self.engine
        self.assertEqual(model.get_league_rules(30)['leagueId'],30)
        self.assertIsNone(model.get_league_rules(30,reader_user_id=1))
        self.assertEqual(model.get_league_rules(30,reader_user_id=2)['leagueId'],30)
