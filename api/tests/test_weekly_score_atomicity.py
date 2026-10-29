"""MOD-007 real replacement SQL and rollback on disposable SQLite data."""
import unittest
from test_scoring_week_zero import WeekZeroScoringModel
from test_league_read_authorization import ReadDatabase


class WeeklyScoreAtomicityTests(unittest.TestCase):
    def setUp(self):
        self.db=ReadDatabase()
        self.addCleanup(self.db.connection.close)
        self.db.connection.executescript('''
            CREATE TABLE WeeklyTeamScore (leagueId INTEGER,weekId INTEGER,memberId INTEGER,
                pointDifferential INTEGER,rank INTEGER,pointsAwarded INTEGER);
            INSERT INTO WeeklyTeamScore VALUES
                (33,100,1,99,1,2),(33,100,2,88,2,1),
                (44,100,1,77,1,1),(33,200,1,66,1,1);
        ''')
        self.model=WeekZeroScoringModel(self.db,None)

    def rows(self):
        return [tuple(row) for row in self.db.connection.execute(
            'SELECT * FROM WeeklyTeamScore ORDER BY leagueId,weekId,memberId')]

    def assert_failed_replacement_preserves_scores(self, fail_at):
        before=self.rows()
        inserts=0
        def fail(sql):
            nonlocal inserts
            if 'INSERT INTO "WeeklyTeamScore"' in sql:
                inserts += 1
                if inserts == fail_at:
                    raise RuntimeError('injected replacement failure')
        self.db.before_query=fail
        with self.assertRaisesRegex(RuntimeError,'injected'):
            self.model.compute_weekly_scores(33,0)
        self.db.before_query=None
        self.assertEqual(self.rows(),before)

    def test_failure_after_delete_preserves_entire_old_set(self):
        self.assert_failed_replacement_preserves_scores(1)

    def test_failure_during_insert_preserves_entire_old_set(self):
        self.assert_failed_replacement_preserves_scores(2)

    def test_success_replaces_exact_scope_and_repeated_run_converges(self):
        expected=[(33,100,1,5,1,2),(33,100,2,-2,2,1),
                  (33,200,1,66,1,1),(44,100,1,77,1,1)]
        for _ in range(2):
            result=self.model.compute_weekly_scores(33,0)
            self.assertEqual(self.rows(),expected)
            self.assertEqual((result['leagueId'],result['weekId'],result['weekNumber']),(33,100,0))
