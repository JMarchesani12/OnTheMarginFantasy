"""Calendar policy with real scoped SQL; no provider/configured engine access."""
import datetime as dt
import json
import sqlite3
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock
from endpoints.schedule.scheduleModel import ScheduleModel


class CalendarDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(':memory:')
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript('''
            CREATE TABLE "League" (id INTEGER,sport INTEGER,"seasonYear" INTEGER,settings TEXT);
            INSERT INTO "League" VALUES (10,1,2026,'{"timezone":"America/New_York"}');
            CREATE TABLE "SportSeason" (id INTEGER,"sportId" INTEGER,"seasonYear" INTEGER,
                "seasonStart" TEXT,"seasonEnd" TEXT,"scheduleBootstrapped" BOOLEAN,"scheduleBootstrappedAt" TEXT);
            INSERT INTO "SportSeason" VALUES (1,1,2026,'2026-11-02','2026-11-22',0,NULL);
            CREATE TABLE "SportSeasonSubdivision" (id INTEGER,"sportSeasonId" INTEGER,code TEXT,name TEXT,
                "regularSeasonStart" TEXT,"regularSeasonEnd" TEXT,"postseasonStart" TEXT,"postseasonEnd" TEXT);
            INSERT INTO "SportSeasonSubdivision" VALUES (11,1,'D1','Division One','2026-11-02','2026-11-22',NULL,NULL);
            CREATE TABLE "Week" (id INTEGER PRIMARY KEY AUTOINCREMENT,"leagueId" INTEGER,"weekNumber" INTEGER,
                "startDate" TEXT,"endDate" TEXT,"isLocked" BOOLEAN,"scoringComplete" BOOLEAN);
            CREATE TABLE "SeasonPhase" (id INTEGER,"sportSeasonId" INTEGER,"tournamentId" INTEGER);
            CREATE TABLE "TournamentDefinition" (id INTEGER,"sportConferenceId" INTEGER);
        ''')
        self.active = False
        self.queries = []
        self.fail_week = None

    @contextmanager
    def begin(self):
        assert not self.active, 'Nested acquisition'
        self.active = True
        try:
            with self.connection:
                yield self
        finally:
            self.active = False

    def execute(self, statement, params):
        assert self.active, 'Query outside owned scope'
        sql = str(statement)
        self.queries.append(sql)
        if 'INSERT INTO "Week"' in sql and params.get('weekNumber') == self.fail_week:
            raise RuntimeError('synthetic numbered week failure')
        params = {key: value.isoformat() if isinstance(value, (dt.datetime, dt.date)) else value
                  for key, value in params.items()}
        cursor = self.connection.execute(sql, params)

        def mapping(row):
            if row is None:
                return None
            values = dict(row)
            for key, value in values.items():
                if value and key in ('seasonStart','seasonEnd','regularSeasonStart','regularSeasonEnd','postseasonStart','postseasonEnd'):
                    values[key] = dt.date.fromisoformat(value)
                elif value and key in ('startDate','endDate'):
                    values[key] = dt.datetime.fromisoformat(value)
            return values

        class Result:
            def mappings(self): return self
            def first(self): return mapping(cursor.fetchone())
            def all(self): return [mapping(row) for row in cursor.fetchall()]
            def fetchone(self):
                row = self.first()
                return SimpleNamespace(_mapping=row) if row is not None else None
            def fetchall(self): return [SimpleNamespace(_mapping=row) for row in self.all()]
        return Result()


class ScheduleCalendarServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = CalendarDatabase()
        self.addCleanup(self.db.connection.close)

    def service(self):
        from endpoints.schedule.calendar_service import ScheduleCalendarService
        return ScheduleCalendarService(self.db)

    def settings(self, value):
        self.db.connection.execute('UPDATE "League" SET settings=?', (json.dumps(value),))
        self.db.connection.commit()

    def football(self):
        self.db.connection.executescript('UPDATE "League" SET sport=2; UPDATE "SportSeason" SET "sportId"=2;')

    def test_basketball_persisted_plan_keeps_opening_and_dst_utc_boundaries(self):
        service = self.service()
        expected = service.boundaries_for_job(10)
        rows = service.ensure_weeks_for_job(10)
        self.assertEqual([(r['weekNumber'],r['startDate'],r['endDate']) for r in rows], expected)
        self.assertEqual([r['weekNumber'] for r in rows], [1,2,3])
        self.assertEqual(rows[0]['startDate'], dt.datetime(2026,10,26,4,tzinfo=dt.timezone.utc))
        self.assertEqual(rows[1]['startDate'], dt.datetime(2026,11,9,5,tzinfo=dt.timezone.utc))

    def test_timezone_precedence_fallback_and_weekday_validation(self):
        service = self.service()
        self.settings({'timeZone':'America/Chicago','schedule':{'timezone':'UTC','weekStartDay':' Friday '}})
        self.assertEqual(str(service.timezone_for_job(10)), 'America/Chicago')
        self.assertEqual(service._get_week_start_weekday(10), 4)
        self.settings({'timezone':'Invalid/Zone','schedule':{'weekStartWeekday':6}})
        self.assertEqual(service.timezone_for_job(10), dt.timezone.utc)
        self.assertEqual(service._get_week_start_weekday(10), 6)
        self.settings({'schedule':{'weekStartDay':True}})
        with self.assertRaisesRegex(ValueError, 'weekday name'):
            service._get_week_start_weekday(10)

    def test_subdivision_auto_all_explicit_and_missing_configuration(self):
        service = self.service()
        self.db.connection.execute('INSERT INTO "SportSeasonSubdivision" VALUES (12,1,\'D2\',\'Division Two\',\'2026-10-20\',\'2026-12-01\',NULL,NULL)')
        self.db.connection.commit()
        season = service._get_sport_season_for_league(10)
        self.assertEqual((season['subdivisionCode'],season['regularSeasonStart'],season['regularSeasonEnd']),
                         ('ALL',dt.date(2026,10,20),dt.date(2026,12,1)))
        self.settings({'subdivision':' d1 '})
        self.assertEqual(service._get_sport_season_for_league(10)['sportSeasonSubdivisionId'],11)
        self.settings({'subdivision':'missing'})
        with self.assertRaisesRegex(ValueError,'not configured'):
            service._get_sport_season_for_league(10)

    def test_existing_weeks_are_returned_without_season_rebuild(self):
        service = self.service()
        service.ensure_weeks_for_job(10)
        self.db.connection.execute('DELETE FROM "SportSeason"');self.db.connection.commit()
        self.db.queries.clear()
        self.assertEqual(len(service.ensure_weeks_for_job(10)),3)
        self.assertEqual(len(self.db.queries),1)

    def test_bulk_failure_preserves_original_separately_committed_football_week_zero(self):
        self.football();self.db.fail_week = 2
        service = self.service()
        self.assertEqual(service._get_week_start_weekday(10),1)
        with self.assertRaisesRegex(RuntimeError,'numbered week failure'):
            service.ensure_weeks_for_job(10)
        rows = self.db.connection.execute('SELECT "weekNumber" FROM "Week"').fetchall()
        self.assertEqual([row[0] for row in rows],[0])
        self.assertFalse(self.db.active)

    def test_missing_league_season_and_subdivision_keep_error_contracts(self):
        service = self.service()
        with self.assertRaisesRegex(ValueError,'League 999 not found'):
            service.timezone_for_job(999)
        self.db.connection.execute('DELETE FROM "SportSeasonSubdivision"');self.db.connection.commit()
        with self.assertRaisesRegex(ValueError,'no subdivision windows'):
            service._get_sport_season_for_league(10)
        self.db.connection.execute('DELETE FROM "SportSeason"');self.db.connection.commit()
        with self.assertRaisesRegex(ValueError,'No SportSeason'):
            service._get_sport_season_for_league(10)

    def test_legacy_inheritance_and_helper_override_preserve_no_io_path(self):
        from endpoints.schedule.calendar_service import ScheduleCalendarService
        self.assertTrue(issubclass(ScheduleModel,ScheduleCalendarService))
        class ExistingWeeks(ScheduleModel):
            def _get_existing_weeks(self,league_id): return [{'weekNumber':7}]
        model = ExistingWeeks.__new__(ExistingWeeks)
        self.assertEqual(model.ensure_weeks_for_league(10),[{'weekNumber':7}])
        self.assertEqual(ScheduleModel(Mock(),'https://example.test///').espn_base_url,'https://example.test')
