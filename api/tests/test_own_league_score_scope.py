"""Actual own-list SQL: scope before aggregation, preserve projection and totals."""
import unittest
from sqlalchemy.dialects.sqlite import dialect
import test_own_league_listing as listing
from endpoints.league.reads.repository import LeagueReadRepository

class OwnScoreScopeTests(unittest.TestCase):
    def setUp(self):
        fixture=listing.OwnLeagueListingTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.db=fixture.db;self.repo=LeagueReadRepository();self.executions=[]
        self.db.connection.executescript('''INSERT INTO "Week" VALUES (100,10,0,NULL,'2025-01-01'),(101,10,-1,NULL,'2025-01-01'),(102,10,1,NULL,'2025-01-01');
        INSERT INTO "WeeklyTeamScore" VALUES (10,12,100,5),(10,12,102,-5),(10,12,101,999),(10,11,100,NULL);''')
        parent=self.db.execute
        def execute(statement,params):
            self.executions.append((str(statement),dict(params)))
            compiled=statement.params(**params).compile(dialect=dialect(paramstyle='named'),compile_kwargs={'render_postcompile':True})
            return parent(str(compiled),compiled.params)
        self.db.execute=execute

    def read(self,user=2,stage='all',scope=None):return self.repo.own_leagues(self.db,user,stage,scope)

    def test_zero_sum_week_zero_negative_week_and_fallback(self):
        rows=self.read();self.assertEqual([(r['memberId'],r['seasonPoints']) for r in rows],[(12,0),(21,30)])
        self.assertEqual(self.read(1)[0]['seasonPoints'],10)
        self.db.connection.execute('UPDATE "LeagueMember" SET "seasonPoints"=NULL WHERE id=21')
        self.assertEqual(self.read()[1]['seasonPoints'],0)
        self.db.connection.execute('DELETE FROM "WeeklyTeamScore" WHERE "memberId"=12')
        self.assertEqual(self.read()[0]['seasonPoints'],20)

    def test_stages_scope_membership_and_empty_no_query(self):
        for stage,want in [('active',[10]),('completed',[20]),('unknown',[10,20])]:self.assertEqual([r['leagueId'] for r in self.read(stage=stage)],want)
        self.assertEqual([r['leagueId'] for r in self.read(scope=[20])],[20]);self.assertEqual(self.read(scope=[999]),[])
        self.executions.clear();self.assertEqual(self.read(scope=[]),[]);self.assertEqual(self.executions,[])
        self.assertEqual(self.read(3),[])
        self.db.connection.execute('DELETE FROM "LeagueMember" WHERE "userId"=1')
        self.assertEqual(self.read(1),[]) # Commissioner alone does not create a row.

    def test_filter_is_inside_score_aggregate_and_values_are_bound(self):
        self.read(stage='completed',scope=[20]);sql,params=self.executions[-1]
        inner=sql[sql.index('FROM "WeeklyTeamScore"'):sql.index('GROUP BY wts.')]
        self.assertIn('EXISTS',inner);self.assertIn(':user_id',inner)
        self.assertIn('score_member.id = wts."memberId"',inner)
        self.assertIn('score_member."leagueId" = wts."leagueId"',inner)
        self.assertIn("score_league.status = 'Completed'",inner);self.assertIn('score_league.id IN',inner)
        self.assertEqual(params,dict(user_id=2,scope_ids=[20]))

    def test_duplicate_legacy_eligibility_does_not_multiply_sum(self):
        self.db.connection.executescript('''DELETE FROM "WeeklyTeamScore" WHERE "memberId"=12;
        INSERT INTO "WeeklyTeamScore" VALUES (10,12,100,5);
        INSERT INTO "LeagueMember" SELECT id,"leagueId","userId",'Duplicate',3,"seasonPoints" FROM "LeagueMember" WHERE id=12;''')
        rows=self.read();self.assertEqual([r['seasonPoints'] for r in rows if r['leagueId']==10],[5,5])
