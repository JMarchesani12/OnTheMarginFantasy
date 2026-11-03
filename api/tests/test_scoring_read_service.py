"""Weekly-points orchestration against real disposable scoring SQL."""
import unittest
from actors import UserActor
from endpoints.scoring.service import ScoringReadService
from endpoints.scoring.contracts import ScoringReadDenied
import test_scoring_authorization as fixture
from test_transaction_service import ConnectionOwner


class ScoringReadServiceTests(unittest.TestCase):
    def setUp(self):
        base=fixture.ScoringAuthorizationTests()
        base.setUp()
        self.addCleanup(base.doCleanups)
        self.db=base.db
        self.engine=ConnectionOwner(self.db)
        self.service=ScoringReadService(self.engine)

    def test_actor_required_before_io(self):
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError):
                self.service.get_weekly_points(actor,10,[1])
        self.assertEqual(self.engine.connects,0)

    def test_normalization_projection_order_and_one_connection(self):
        self.db.connection.execute('INSERT INTO Week VALUES (90,10,0,false,\'2026-09-01\',\'2026-09-07\')')
        self.db.connection.execute('INSERT INTO WeeklyTeamScore VALUES (10,90,11,4,20,1)')
        self.db.connection.commit()
        rows=self.service.get_weekly_points(UserActor(1,'alice'),10,[-1,'1',0,1])
        self.assertEqual([(r['weekNumber'],r['memberId']) for r in rows],[(0,11),(1,11),(1,12)])
        self.assertEqual(set(rows[0]),{'weekNumber','startDate','endDate','memberId','teamName','pointsAwarded','pointDifferential','rank'})
        self.assertEqual(self.engine.connects,1)
        self.assertEqual(self.engine.begins,0)

    def test_nonmember_denial_precedes_normalization_and_score_sql(self):
        self.db.queries.clear()
        with self.assertRaises(ScoringReadDenied):
            self.service.get_weekly_points(UserActor(3,'nonmember'),10,['invalid'])
        self.assertFalse(any('WeeklyTeamScore' in s for s in self.db.queries))
        self.assertEqual(self.service.get_weekly_points(UserActor(1,'commissioner'),30,[1]),[])

    def test_final_revocation_discards_scores_and_preserves_concealed_denial(self):
        def revoke(sql):
            if 'WeeklyTeamScore' in sql:
                self.db.before_query=None
                self.db.connection.execute('DELETE FROM LeagueMember WHERE id=12')
        self.db.before_query=revoke
        with self.assertRaisesRegex(ScoringReadDenied,'League not found'):
            self.service.get_weekly_points(UserActor(2,'bob'),10,[1])

    def test_empty_and_negative_only_lists_still_authorize(self):
        for weeks in ([],[-2,-1]):
            self.db.queries.clear()
            self.assertEqual(self.service.get_weekly_points(UserActor(1,'alice'),10,weeks),[])
            self.assertEqual(sum('SELECT id FROM "League"' in s for s in self.db.queries),2)
            self.assertFalse(any('WeeklyTeamScore' in s for s in self.db.queries))
            with self.assertRaises(ScoringReadDenied):
                self.service.get_weekly_points(UserActor(3,'nonmember'),10,weeks)

    def test_empty_list_rechecks_access_at_end(self):
        checks=0
        def revoke(sql):
            nonlocal checks
            if 'SELECT id FROM "League"' in sql:
                checks+=1
                if checks==2:
                    self.db.before_query=None
                    self.db.connection.execute('DELETE FROM LeagueMember WHERE id=12')
        self.db.before_query=revoke
        with self.assertRaises(ScoringReadDenied):
            self.service.get_weekly_points(UserActor(2,'bob'),10,[])
        self.assertEqual(checks,2)

    def test_trusted_reads_are_explicit_and_empty_lists_need_no_connection(self):
        self.assertEqual(self.service.get_weekly_points_for_job(999,[]),[])
        self.assertEqual(self.engine.connects,0)
        rows=self.service.get_weekly_points_for_job(20,['1',1])
        self.assertEqual([r['pointsAwarded'] for r in rows],[8])
        self.assertEqual(self.engine.connects,1)
