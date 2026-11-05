"""Actual weekly SQL/progress and ownership commands; native tests prove locks."""
import datetime as dt
import unittest
from endpoints.scoring.weekly_service import WeeklyCompletionService
from endpoints.transaction.workflow_service import TransactionWorkflowService
from test_operational_trusted_contract import ApplyDatabase
import test_free_agency_authorization as fixture_module
from test_transaction_service import ConnectionOwner

NOW=dt.datetime(2026,11,5,tzinfo=dt.timezone.utc)


class WeeklyCompletionTests(unittest.TestCase):
    def setUp(self):
        fixture=fixture_module.FreeAgencyAuthorizationTests();fixture.database_type=ApplyDatabase
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.db=fixture.db
        self.db.connection.executescript('''
            ALTER TABLE Week ADD COLUMN scoringComplete BOOLEAN DEFAULT false;
            ALTER TABLE Week ADD COLUMN endDate TEXT DEFAULT '2026-11-04 00:00:00+00:00';
            CREATE TABLE Scores (leagueId INTEGER,weekNumber INTEGER,ownedTeam INTEGER);
            UPDATE Week SET endDate='2026-11-12 00:00:00+00:00' WHERE id=101;
        ''')
        self.engine=ConnectionOwner(self.db)
        engine=self.engine
        class Scoring:
            def compute_weekly_scores_for_job(inner,league_id,week_number,conn=None):
                if conn is not self.db:raise AssertionError('Detached scoring')
                conn.execute('INSERT INTO Scores SELECT :leagueId,:weekNumber,sportTeamId FROM LeagueTeamSlot WHERE leagueId=:leagueId AND memberId=11 AND acquiredWeek<=:weekNumber AND (droppedWeek IS NULL OR droppedWeek>:weekNumber)',dict(leagueId=league_id,weekNumber=week_number))
        self.service=WeeklyCompletionService(engine,Scoring(),TransactionWorkflowService(engine))

    def rows(self,table):
        return [tuple(r) for r in self.db.connection.execute(f'SELECT * FROM "{table}"')]

    def pending(self,week_id=101,transaction_id=1):
        self.db.connection.execute('''INSERT INTO "Transaction" VALUES (?,10,?,'FREE_AGENT',11,11,'PENDING_APPLY','[101]','[103]')''',(transaction_id,week_id));self.db.connection.commit()

    def test_close_and_apply_scope_then_replay_is_noop(self):
        self.pending();result=self.service.run(NOW)
        self.assertEqual(result['closed'],[100,200]);self.assertEqual(result['applied'],[1])
        self.assertEqual(self.db.connection.execute('SELECT isLocked FROM Week WHERE id=101').fetchone()[0],1)
        before=self.rows('Scores'),self.rows('LeagueTeamSlot')
        result=self.service.run(NOW)
        self.assertEqual((result['closed'],result['applied']),([],[]))
        self.assertEqual((self.rows('Scores'),self.rows('LeagueTeamSlot')),before)

    def test_retry_pending_without_new_scoring(self):
        self.pending();self.db.connection.execute('UPDATE Week SET scoringComplete=true WHERE id IN (100,200)');self.db.connection.commit()
        result=self.service.run(NOW)
        self.assertEqual((result['closed'],result['applied']),([],[1]))

    def test_catchup_applies_before_target_scores(self):
        self.pending();self.db.connection.execute("UPDATE Week SET endDate='2026-11-04 00:00:00+00:00' WHERE id=101");self.db.connection.commit()
        self.service.run(NOW)
        self.assertEqual(self.rows('Scores'),[(10,1,101),(10,2,103)])

    def test_completion_failure_rolls_back_scores_and_flags_and_other_league_runs(self):
        before=self.rows('Week');execute=self.db.execute
        def fail(sql,params=None):
            result=execute(sql,params)
            if 'SET "scoringComplete"' in str(sql) and params['weekId']==100:raise RuntimeError('synthetic')
            return result
        self.db.execute=fail
        result=self.service.run(NOW)
        self.assertEqual(result['closed'],[200]);self.assertEqual(self.rows('Scores'),[])
        self.assertEqual(self.rows('Week')[:2],before[:2]);self.assertEqual(result['failures'][0]['leagueId'],10)
        self.db.execute=execute
        self.assertEqual(self.service.run(NOW)['closed'],[100])

    def test_pending_failure_stops_target_close_but_other_league_runs_and_retry_succeeds(self):
        self.pending();self.db.connection.execute("UPDATE Week SET endDate='2026-11-04 00:00:00+00:00' WHERE id=101");self.db.connection.execute('UPDATE SportConference SET maxTeamsPerOwner=0');self.db.connection.commit()
        result=self.service.run(NOW)
        self.assertEqual(result['closed'],[100,200]);self.assertEqual(result['applied'],[])
        self.assertEqual(self.db.connection.execute('SELECT status FROM "Transaction"').fetchone()[0],'PENDING_APPLY')
        self.assertEqual(self.rows('Scores'),[(10,1,101)])
        self.db.connection.execute('UPDATE SportConference SET maxTeamsPerOwner=3');self.db.connection.commit()
        result=self.service.run(NOW)
        self.assertEqual((result['closed'],result['applied']),([101],[1]))
        self.assertEqual(self.rows('Scores'),[(10,1,101),(10,2,103)])

    def test_first_period_pending_is_reported_without_closing_it(self):
        self.pending(100);result=self.service.run(NOW)
        self.assertEqual(result['closed'],[200]);self.assertEqual(result['blocked'][0]['reason'],'missing_predecessor')
        self.assertEqual(self.rows('Scores'),[])

    def test_scored_target_pending_is_retained_and_reported(self):
        self.pending();self.db.connection.execute('UPDATE Week SET scoringComplete=true WHERE leagueId=10');self.db.connection.commit()
        result=self.service.run(NOW)
        self.assertEqual(result['applied'],[]);self.assertEqual(result['blocked'][0]['reason'],'target_already_scored')

    def test_future_unclosed_predecessor_does_not_allow_application(self):
        self.pending();self.db.connection.execute("UPDATE Week SET endDate='2026-11-12 00:00:00+00:00' WHERE id=100");self.db.connection.commit()
        result=self.service.run(NOW)
        self.assertEqual(result['applied'],[]);self.assertEqual(result['closed'],[200])

    def test_week_zero_is_a_valid_predecessor(self):
        self.pending(100);self.db.connection.execute("INSERT INTO Week VALUES (99,10,0,false,false,'2026-11-01 00:00:00+00:00')");self.db.connection.commit()
        result=self.service.run(NOW)
        self.assertEqual(result['closed'],[99,100,200]);self.assertEqual(result['applied'],[1])
        self.assertEqual(self.rows('Scores'),[(10,1,103)])

    def test_closed_period_is_locked_even_if_legacy_flag_was_false(self):
        self.service.run(NOW)
        self.assertEqual(self.db.connection.execute('SELECT isLocked FROM Week WHERE id=100').fetchone()[0],1)

    def test_missing_middle_period_blocks_later_close(self):
        self.db.connection.executescript("UPDATE Week SET scoringComplete=true WHERE id=100; UPDATE Week SET weekNumber=3,endDate='2026-11-04' WHERE id=101;")
        result=self.service.run(NOW)
        self.assertEqual(result['blocked'][0]['reason'],'missing_predecessor')
        self.assertEqual(result['closed'],[200])

    def test_missing_initial_period_does_not_make_week_three_a_new_first_week(self):
        self.db.connection.executescript("DELETE FROM Week WHERE id=100; UPDATE Week SET weekNumber=3,endDate='2026-11-04' WHERE id=101;")
        result=self.service.run(NOW)
        self.assertEqual(result['closed'],[200])
        self.assertEqual(result['blocked'][0]['reason'],'missing_predecessor')

    def test_future_target_applies_only_after_its_own_predecessor(self):
        self.pending(101)
        self.db.connection.executescript("UPDATE Week SET scoringComplete=true WHERE id=200; UPDATE Week SET endDate='2026-11-12' WHERE id=100;")
        self.assertEqual(self.service.run(NOW)['applied'],[])

    def test_failure_report_does_not_include_exception_payload(self):
        execute=self.db.execute
        def fail(sql,params=None):
            if 'INSERT INTO Scores' in str(sql):raise RuntimeError('secret row SQL token payload')
            return execute(sql,params)
        self.db.execute=fail
        result=self.service.run(NOW)
        self.assertEqual(result['failures'][0],{'leagueId':10,'category':'RuntimeError'})
        self.assertNotIn('secret',str(result))
