"""Finalization orchestration and actual SQL on isolated state; native proves locks."""
import datetime as dt
import unittest
from endpoints.scoring.service import ScoringService
from test_transaction_service import ConnectionOwner
import test_scoring_authorization as scoring_fixture

NOW=dt.datetime(2026,11,5,12,tzinfo=dt.timezone.utc)


class SuppliedSeasonStandingsTests(unittest.TestCase):
    def test_supplied_standings_see_caller_changes_without_acquisition(self):
        fixture=scoring_fixture.ScoringAuthorizationTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        engine=ConnectionOwner(fixture.db);service=ScoringService(engine,None)
        with self.assertRaisesRegex(RuntimeError,'caller failure'):
            with engine.begin() as conn:
                conn.execute('UPDATE WeeklyTeamScore SET pointsAwarded=99 WHERE memberId=11',{})
                result=service.get_season_standings_for_job(10,conn=conn)
                self.assertEqual(result['members'][0]['totalPoints'],99)
                raise RuntimeError('caller failure')
        self.assertEqual(engine.begins,1)
        self.assertEqual(engine.connects,0)
        self.assertEqual(fixture.db.connection.execute('SELECT pointsAwarded FROM WeeklyTeamScore WHERE memberId=11').fetchone()[0],2)

class SeasonFinalizationTests(unittest.TestCase):
    def setUp(self):
        from endpoints.scoring.finalization_service import SeasonFinalizationService
        self.fixture=scoring_fixture.ScoringAuthorizationTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.db=self.fixture.db
        self.db.connection.executescript('''
            ALTER TABLE League ADD COLUMN status TEXT DEFAULT 'In-Season';
            ALTER TABLE League ADD COLUMN updatedAt TEXT;
            UPDATE League SET sport=2 WHERE id=30;
            INSERT INTO LeagueMember (id,leagueId,userId,teamName) VALUES (31,30,1,'Other');
            INSERT INTO Week (id,leagueId,weekNumber,isLocked,startDate,endDate) VALUES (300,30,1,true,'2026-10-01','2026-10-07');
            ALTER TABLE Week ADD COLUMN scoringComplete BOOLEAN DEFAULT true;
            UPDATE Week SET isLocked=true;
            CREATE TABLE SportSeason (id INTEGER PRIMARY KEY,sportId INTEGER,seasonYear INTEGER,seasonEnd TEXT,seasonFinalized BOOLEAN DEFAULT false);
            INSERT INTO SportSeason (id,sportId,seasonYear,seasonEnd) VALUES (1,1,2026,'2026-10-31'),(2,2,2026,'2026-10-31');
        ''')
        self.engine=ConnectionOwner(self.db);self.scoring=ScoringService(self.engine,None)
        self.service=SeasonFinalizationService(self.engine,self.scoring)

    def state(self):
        return [tuple(r) for r in self.db.connection.execute('SELECT id,status,updatedAt FROM League ORDER BY id')],[tuple(r) for r in self.db.connection.execute('SELECT * FROM SportSeason ORDER BY id')]

    def test_success_exact_season_scope_and_replay(self):
        result=self.service.run(NOW)
        self.assertEqual(result,{'finalized':[1,2],'skipped':[],'blocked':[],'failures':[]})
        self.assertEqual([r[1] for r in self.state()[0]],['Completed']*3)
        before=self.state();self.assertEqual(self.service.run(NOW)['finalized'],[]);self.assertEqual(self.state(),before)

    def test_incomplete_week_blocks_whole_season_but_other_season_finishes(self):
        self.db.connection.executescript('UPDATE Week SET scoringComplete=false WHERE id=200;')
        result=self.service.run(NOW)
        self.assertEqual(result['finalized'],[2]);self.assertEqual(result['blocked'][0]['reason'],'weeks_not_ready')
        self.assertEqual([r[1] for r in self.state()[0]],['In-Season','In-Season','Completed'])
        self.db.connection.executescript('UPDATE Week SET scoringComplete=true WHERE id=200;')
        self.assertEqual(self.service.run(NOW)['finalized'],[1])

    def test_completed_lifecycle_status_does_not_bypass_readiness(self):
        self.db.connection.executescript("UPDATE League SET status='Completed' WHERE id=10; UPDATE Week SET scoringComplete=false WHERE id=100;")
        result=self.service.run(NOW)
        self.assertEqual(result['finalized'],[2]);self.assertEqual(result['blocked'][0]['reason'],'weeks_not_ready')

    def test_calendar_missing_null_invalid_or_future_blocks(self):
        for edit in ("DELETE FROM Week WHERE leagueId=10", "UPDATE Week SET endDate=NULL WHERE id=100", "UPDATE Week SET endDate='2026-11-06' WHERE id=100", "UPDATE Week SET startDate='2026-12-01' WHERE id=100"):
            with self.subTest(edit=edit):
                self.db.connection.execute('SAVEPOINT calendar_case')
                self.db.connection.execute(edit)
                # Direct season step lets caller-owned savepoint restore case setup.
                with self.assertRaises(ValueError):self.service.finalize_in_transaction(self.db,1,NOW)
                self.db.connection.execute('ROLLBACK TO calendar_case');self.db.connection.execute('RELEASE calendar_case')

    def test_pending_apply_blocks_and_is_not_modified(self):
        self.db.connection.executescript("INSERT INTO \"Transaction\" VALUES (1,10,101,'FREE_AGENT',11,11,'PENDING_APPLY','[101]','[103]');")
        result=self.service.run(NOW)
        self.assertEqual(result['finalized'],[2]);self.assertEqual(result['blocked'][0]['reason'],'pending_application')
        self.assertEqual(self.db.connection.execute('SELECT status FROM "Transaction"').fetchone()[0],'PENDING_APPLY')

    def test_inclusive_end_day_is_not_finalizable(self):
        self.db.connection.executescript("UPDATE SportSeason SET seasonEnd='2026-11-05' WHERE id=1;")
        self.assertEqual(self.service.run(NOW)['finalized'],[2])

    def test_empty_season_or_membership_blocks_without_completion(self):
        self.db.connection.executescript("INSERT INTO SportSeason VALUES (3,3,2026,'2026-10-31',false); DELETE FROM LeagueMember WHERE leagueId=20;")
        result=self.service.run(NOW)
        self.assertEqual(result['finalized'],[2]);self.assertEqual([r['reason'] for r in result['blocked']],['empty_membership','empty_scope'])

    def test_bad_standings_do_not_finalize(self):
        valid=self.scoring.get_season_standings_for_job(10)
        variants=[None,({'error':'failure'},500),{'error':'failure'},dict(valid,leagueId=999),dict(valid,members=[]),dict(valid,members=valid['members']*2),dict(valid,members=[dict(valid['members'][0],memberId=999),valid['members'][1]]),dict(valid,members=[dict(valid['members'][0],totalPoints=float('nan')),valid['members'][1]]),dict(valid,members=[dict(valid['members'][0],weeklyPoints=True),valid['members'][1]])]
        original=self.scoring.get_season_standings_for_job
        for payload in variants:
            with self.subTest(payload=payload):
                self.scoring.get_season_standings_for_job=lambda league_id,conn=None:payload if league_id==10 else original(league_id,conn=conn)
                result=self.service.run(NOW)
                self.assertFalse(1 in result['finalized']);self.assertEqual(result['failures'][0]['category'],'InvalidStandings')
        self.scoring.get_season_standings_for_job=original
        self.assertEqual(self.service.run(NOW)['finalized'],[1])

    def test_failure_after_first_league_update_rolls_back_whole_season(self):
        before=self.state();execute=self.db.execute
        def fail(sql,params=None):
            result=execute(sql,params)
            if "SET status='Completed'" in str(sql) and params['leagueId']==10:raise RuntimeError('secret SQL payload')
            return result
        self.db.execute=fail;result=self.service.run(NOW)
        self.assertEqual(result['finalized'],[2]);self.assertEqual(self.state()[0][:2],before[0][:2])
        self.assertNotIn('secret',str(result));self.assertEqual(result['failures'],[{'sportSeasonId':1,'category':'RuntimeError'}])
        self.db.execute=execute;self.assertEqual(self.service.run(NOW)['finalized'],[1])

    def test_detected_scope_change_rolls_back(self):
        original=self.scoring.get_season_standings_for_job
        def change_scope(league_id,conn=None):
            result=original(league_id,conn=conn)
            if league_id==20:conn.execute('UPDATE League SET seasonYear=2027 WHERE id=20',{})
            return result
        self.scoring.get_season_standings_for_job=change_scope
        result=self.service.run(NOW)
        self.assertEqual(result['blocked'][0]['reason'],'scope_changed');self.assertEqual(result['finalized'],[2])
        self.assertEqual(self.db.connection.execute('SELECT seasonYear FROM League WHERE id=20').fetchone()[0],2026)

class StandaloneSeasonConnectionTests(unittest.TestCase):
    def test_standalone_standings_do_not_forward_a_closed_read_connection(self):
        fixture=scoring_fixture.ScoringAuthorizationTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        engine=ConnectionOwner(fixture.db);service=ScoringService(engine,None)
        execute=fixture.db.execute
        def only_active(sql,params=None):
            if not engine.active:raise AssertionError('Read after connection scope closed')
            return execute(sql,params)
        fixture.db.execute=only_active
        self.assertEqual(service.get_season_standings_for_job(10)['members'][0]['totalPoints'],2)
        self.assertGreaterEqual(engine.begins,2)

class DiscoveryFailureTests(unittest.TestCase):
    setUp=SeasonFinalizationTests.setUp

    def test_discovery_acquire_query_and_commit_errors_are_safe(self):
        from contextlib import contextmanager
        for stage in ('acquire','query','commit'):
            with self.subTest(stage=stage):
                begin=self.engine.begin;candidates=self.service.repository.candidates
                @contextmanager
                def broken_begin():
                    if stage=='acquire':raise RuntimeError('private SQL row token')
                    with begin() as conn:
                        yield conn
                        if stage=='commit':raise RuntimeError('private SQL row token')
                def broken_candidates(conn,today):raise RuntimeError('private SQL row token')
                self.engine.begin=broken_begin
                if stage=='query':self.service.repository.candidates=broken_candidates
                try:result=self.service.run(NOW)
                finally:self.engine.begin=begin;self.service.repository.candidates=candidates
                self.assertEqual(result,{'finalized':[],'skipped':[],'blocked':[],'failures':[{'sportSeasonId':None,'stage':'discovery','category':'RuntimeError'}]})
                self.assertNotIn('private',str(result))
