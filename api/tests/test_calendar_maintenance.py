"""Actual maintenance SQL/calendar with strict supplied-connection SQLite port."""
import datetime as dt
import unittest
from sqlalchemy import text
from test_schedule_calendar_service import CalendarDatabase
from endpoints.schedule.calendar_service import ScheduleCalendarService
from endpoints.schedule.maintenance_service import CalendarMaintenanceService

NOW=dt.datetime(2026,12,1,tzinfo=dt.timezone.utc)


class MaintenanceDatabase(CalendarDatabase):
    before_sql=None
    after_sql=None
    def __init__(self):
        super().__init__()
        self.connection.create_function('pg_advisory_xact_lock',1,lambda key:None)
    def execute(self,statement,params):
        sql=str(statement).replace('FOR SHARE','')
        if self.before_sql:self.before_sql(sql,params)
        result=super().execute(text(sql),params)
        if self.after_sql:self.after_sql(sql,params)
        return result


class CalendarMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.db=MaintenanceDatabase();self.addCleanup(self.db.connection.close)
        self.db.connection.executescript('''
            ALTER TABLE League ADD COLUMN status TEXT DEFAULT 'Pre-Draft';
            ALTER TABLE SportSeason ADD COLUMN seasonFinalized BOOLEAN DEFAULT false;
            CREATE TABLE DraftState(leagueId INTEGER,status TEXT,currentOverallPickNumber INTEGER DEFAULT 1,currentMemberId INTEGER,expiresAt TEXT,lastPickAt TEXT);
            CREATE TABLE DraftPick(id INTEGER,leagueId INTEGER);
            CREATE TABLE LeagueMember(id INTEGER,leagueId INTEGER,teamName TEXT);
            INSERT INTO LeagueMember VALUES (11,10,'Creator');
            CREATE TABLE LeagueTeamSlot(id INTEGER,leagueId INTEGER,memberId INTEGER,sportTeamId INTEGER,acquiredWeek INTEGER,droppedWeek INTEGER);
            CREATE TABLE "Transaction"(id INTEGER,leagueId INTEGER,weekId INTEGER,status TEXT);
            CREATE TABLE WeeklyTeamScore(id INTEGER PRIMARY KEY,leagueId INTEGER,weekId INTEGER,memberId INTEGER,pointsAwarded INTEGER,pointDifferential INTEGER,rank INTEGER);
        ''')
        self.schedule=ScheduleCalendarService(self.db)
        database=self.db
        class Scoring:
            def compute_weekly_scores_for_job(inner,league_id,week_number,conn=None):
                if conn is not database:raise AssertionError('Detached score connection')
                week=conn.execute(text('SELECT id FROM Week WHERE leagueId=:leagueId AND weekNumber=:weekNumber'),dict(leagueId=league_id,weekNumber=week_number)).fetchone()._mapping
                member=conn.execute(text('SELECT id FROM LeagueMember WHERE leagueId=:leagueId ORDER BY id'),{'leagueId':league_id}).fetchone()._mapping['id']
                conn.execute(text('INSERT INTO WeeklyTeamScore(leagueId,weekId,memberId,pointsAwarded,pointDifferential,rank) VALUES (:leagueId,:weekId,:memberId,1,5,1)'),dict(leagueId=league_id,weekId=week['id'],memberId=member))
                return {'weekId':week['id']}
        self.service=CalendarMaintenanceService(self.db,self.schedule,Scoring())

    def state(self):
        return {t:[tuple(r) for r in self.db.connection.execute(f'SELECT * FROM "{t}" ORDER BY 1')] for t in ('Week','WeeklyTeamScore','LeagueTeamSlot','Transaction','DraftPick','DraftState')}

    def create_weeks(self):self.schedule.ensure_weeks_for_job(10)

    def test_preview_defaults_read_only_and_reports_added_periods(self):
        before=self.state();report=self.service.run(2026,now=NOW)
        self.assertEqual(self.state(),before)
        row=report['leagues'][0]
        self.assertEqual(row['outcome'],'preview');self.assertTrue(row['plan']['eligible'])
        self.assertEqual([p['change'] for p in row['plan']['periods']],['added']*3)
        self.assertEqual(report['failures'],[])

    def test_historical_changed_plan_reports_temporal_impacts_but_apply_preserves_everything(self):
        self.create_weeks()
        self.db.connection.executescript('''
            UPDATE Week SET endDate='2026-11-01T23:59:59+00:00' WHERE weekNumber=1;
            INSERT INTO LeagueTeamSlot VALUES (1,10,11,101,1,3);
            INSERT INTO "Transaction" VALUES (1,10,1,'COMPLETED');
            INSERT INTO WeeklyTeamScore VALUES (1,10,1,11,7,5,1);
        ''')
        before=self.state();preview=self.service.run(2026,now=NOW)['leagues'][0]['plan']
        self.assertFalse(preview['eligible']);self.assertIn('ownership_history',preview['reasons'])
        self.assertEqual(preview['transactions'][0]['impact'],'boundaries_changed')
        self.assertEqual(preview['scoreTotals'],[{'memberId':11,'pointsAwarded':7}])
        report=self.service.run(2026,apply=True,now=NOW)
        self.assertEqual(report['leagues'][0]['outcome'],'blocked');self.assertEqual(self.state(),before)

    def test_every_history_or_lifecycle_indicator_blocks_even_unchanged_plan(self):
        self.create_weeks()
        edits=[('draft_history','INSERT INTO DraftPick VALUES (1,10)'),
          ('ownership_history','INSERT INTO LeagueTeamSlot VALUES (1,10,11,101,1,NULL)'),
          ('transaction_history','INSERT INTO "Transaction" VALUES (1,10,1,\'CANCELLED\')'),
          ('score_history','INSERT INTO WeeklyTeamScore VALUES (1,10,1,11,7,5,1)'),
          ('period_history','UPDATE Week SET isLocked=true WHERE weekNumber=1'),
          ('period_history','UPDATE Week SET scoringComplete=true WHERE weekNumber=1'),
          ('league_not_unused','UPDATE League SET status=\'In-Season\''),
          ('league_not_unused','UPDATE League SET status=\'Completed\''),
          ('draft_not_unused','INSERT INTO DraftState(leagueId,status) VALUES (10,\'live\')'),
          ('draft_not_unused','INSERT INTO DraftState(leagueId,status) VALUES (10,\'unknown\')'),
          ('season_finalized','UPDATE SportSeason SET seasonFinalized=true')]
        for reason,edit in edits:
            with self.subTest(reason=reason,edit=edit):
                self.db.connection.execute('SAVEPOINT guard_case');self.db.connection.execute(edit)
                with self.db.begin() as conn:plan=self.service.preview_in_transaction(conn,10,2026)
                self.assertIn(reason,plan['reasons'])
                # begin() commits SQLite savepoints, restore fixture explicitly.
                self.db.connection.execute('DELETE FROM DraftPick');self.db.connection.execute('DELETE FROM LeagueTeamSlot');self.db.connection.execute('DELETE FROM "Transaction"');self.db.connection.execute('DELETE FROM WeeklyTeamScore');self.db.connection.execute('DELETE FROM DraftState')
                self.db.connection.executescript("UPDATE Week SET isLocked=false,scoringComplete=false; UPDATE League SET status='Pre-Draft'; UPDATE SportSeason SET seasonFinalized=false;")

    def test_foreign_league_reference_prevents_cascade_deletion(self):
        self.create_weeks()
        self.db.connection.executescript('''INSERT INTO Week VALUES (99,10,9,'2027-01-01','2027-01-07',false,false);
            INSERT INTO "Transaction" VALUES (1,20,99,'PENDING_APPLY');''')
        before=self.state();report=self.service.run(2026,apply=True,now=NOW)
        plan=report['leagues'][0]['plan']
        self.assertIn('transaction_history',plan['reasons']);self.assertEqual(plan['transactions'][0]['impact'],'period_removed')
        self.assertEqual(self.state(),before)

    def test_apply_keeps_retained_ids_scores_and_flags_in_one_transaction(self):
        self.create_weeks();before_ids=[r[0] for r in self.state()['Week']]
        self.db.connection.executescript("UPDATE Week SET startDate='2026-01-01' WHERE weekNumber=1; INSERT INTO Week VALUES (99,10,9,'2027-01-01','2027-01-07',false,false);")
        result=self.service.run(2026,apply=True,now=NOW)
        self.assertEqual(result['leagues'][0]['outcome'],'applied',result)
        self.assertEqual([r[0] for r in self.state()['Week']],before_ids)
        self.assertEqual(len(self.state()['WeeklyTeamScore']),3)
        self.assertTrue(all(r[-1] and r[-2] for r in self.state()['Week']))
        after=self.state();self.assertEqual(self.service.run(2026,apply=True,now=NOW)['leagues'][0]['outcome'],'blocked');self.assertEqual(self.state(),after)

    def test_mid_score_failure_restores_calendar_scores_flags_and_retry(self):
        self.create_weeks();self.db.connection.executescript("UPDATE Week SET startDate='2026-01-01' WHERE weekNumber=1;")
        before=self.state();hits=0
        def fail(sql,params):
            nonlocal hits
            if 'INSERT INTO WeeklyTeamScore' in sql:
                hits+=1
                if hits==2:raise RuntimeError('private SQL payload')
        self.db.after_sql=fail
        result=self.service.run(2026,apply=True,now=NOW)
        self.assertEqual(self.state(),before);self.assertEqual(result['leagues'],[])
        self.assertNotIn('private',str(result));self.assertEqual(result['failures'][0]['category'],'RuntimeError')
        self.db.after_sql=None
        self.assertEqual(self.service.run(2026,apply=True,now=NOW)['leagues'][0]['outcome'],'applied')

    def test_requested_year_and_explicit_scope_are_exact(self):
        self.db.connection.executescript("INSERT INTO League VALUES (20,1,2025,'{}','Pre-Draft');")
        result=self.service.run(2026,[10,20,999],now=NOW)
        self.assertEqual([r['leagueId'] for r in result['leagues']],[10])
        self.assertEqual(result['scopeErrors'],[{'leagueId':20,'reason':'wrong_season'},{'leagueId':999,'reason':'not_found'}])
        self.assertEqual([r['leagueId'] for r in self.service.run(2026,now=NOW)['leagues']],[10])

    def test_discovery_failure_is_safe_and_does_not_write(self):
        before=self.state()
        def fail(sql,params):raise RuntimeError('private SQL payload')
        self.db.before_sql=fail
        result=self.service.run(2026,apply=True,now=NOW)
        self.assertEqual(self.state(),before);self.assertEqual(result['failures'],[{'leagueId':None,'stage':'discovery','category':'RuntimeError'}])

    def test_failed_league_does_not_prevent_other_league_repair(self):
        self.db.connection.executescript("INSERT INTO League VALUES (20,1,2026,'{}','Pre-Draft'); INSERT INTO LeagueMember VALUES (21,20,'Other');")
        def fail(sql,params):
            if 'INSERT INTO "Week"' in sql and params.get('leagueId')==10:raise RuntimeError('synthetic')
        self.db.before_sql=fail
        result=self.service.run(2026,apply=True,now=NOW)
        self.assertEqual([r['leagueId'] for r in result['leagues']],[20])
        self.assertEqual(result['leagues'][0]['outcome'],'applied')
        self.assertEqual(result['failures'][0]['leagueId'],10)
        self.assertTrue(all(row[1]==20 for row in self.state()['Week']))

    def test_preconfigured_order_is_not_history_but_changed_state_is_rechecked(self):
        self.db.connection.executescript("INSERT INTO DraftState(leagueId,status) VALUES (10,'pre');")
        self.assertTrue(self.service.run(2026,now=NOW)['leagues'][0]['plan']['eligible'])
        self.db.connection.executescript('INSERT INTO LeagueTeamSlot VALUES (1,10,11,101,1,NULL);')
        before=self.state();result=self.service.run(2026,apply=True,now=NOW)
        self.assertEqual(result['leagues'][0]['outcome'],'blocked');self.assertEqual(self.state(),before)

    def test_invalid_proposed_calendar_never_writes(self):
        original=self.schedule.boundaries_for_job
        boundaries=original(10)
        for plan in ([],[boundaries[0],boundaries[0]],[(1,boundaries[0][2],boundaries[0][1])]):
            with self.subTest(plan=plan):
                self.schedule.boundaries_for_job=lambda *args,**kwargs:plan
                before=self.state();result=self.service.run(2026,apply=True,now=NOW)
                self.assertEqual(result['leagues'],[]);self.assertEqual(result['failures'][0]['category'],'ValueError')
                self.assertEqual(self.state(),before)
        self.schedule.boundaries_for_job=original

    def test_pre_state_with_current_member_is_not_unused(self):
        self.db.connection.executescript("INSERT INTO DraftState(leagueId,status,currentMemberId) VALUES (10,'pre',11);")
        before=self.state();preview=self.service.run(2026,now=NOW)['leagues'][0]['plan']
        self.assertIn('draft_not_unused',preview['reasons'])
        result=self.service.run(2026,apply=True,now=NOW)
        self.assertEqual(result['leagues'][0]['outcome'],'blocked');self.assertEqual(self.state(),before)
