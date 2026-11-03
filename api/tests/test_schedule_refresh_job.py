"""Main's refresh cron uses canonical services and explicit runtime startup."""
import datetime as dt
import unittest
from unittest.mock import MagicMock, patch


class ScheduleRefreshTests(unittest.TestCase):
    def test_import_and_fake_engine_execution_cover_each_day_once_per_season(self):
        from cronJobs import cronRefreshSchedules as refresh
        engine = MagicMock()
        conn = engine.connect.return_value.__enter__.return_value
        today = dt.datetime.now(refresh.ZoneInfo('America/Chicago')).date()
        conn.execute.return_value.mappings.return_value.all.return_value = [
            dict(id=7,seasonStart=today-dt.timedelta(days=1),seasonEnd=today+dt.timedelta(days=4))]
        with patch('runtime.configured_engine', side_effect=AssertionError('unexpected runtime')), patch.object(refresh,'ScheduleIngestionService') as service:
            refresh.main(argv=['--days','2','--sport-season-id','7'],engine=engine)
        self.assertIs(service.call_args.args[0], engine)
        self.assertEqual(service.return_value.ingest_season_for_job.call_args_list, [
            unittest.mock.call(7,today),unittest.mock.call(7,today+dt.timedelta(days=1))])
        self.assertEqual(conn.execute.call_args.args[1]['id'],7)

    def test_invalid_window_never_constructs_runtime(self):
        from cronJobs import cronRefreshSchedules as refresh
        with patch('runtime.configured_engine', side_effect=AssertionError('unexpected runtime')):
            with self.assertRaises(SystemExit) as raised:
                refresh.main(argv=['--days','0'])
        self.assertEqual(raised.exception.code,2)

    def test_refresh_failure_is_reported_after_other_days_are_attempted(self):
        from cronJobs import cronRefreshSchedules as refresh
        engine = MagicMock()
        today = dt.datetime.now(refresh.ZoneInfo('America/Chicago')).date()
        engine.connect.return_value.__enter__.return_value.execute.return_value.mappings.return_value.all.return_value = [
            dict(id=7,seasonStart=today,seasonEnd=today+dt.timedelta(days=1))]
        with patch.object(refresh,'ScheduleIngestionService') as service:
            service.return_value.ingest_season_for_job.side_effect = [RuntimeError('synthetic'),{}]
            with self.assertRaisesRegex(RuntimeError,'Schedule refresh incomplete'):
                refresh.main(argv=['--days','2'],engine=engine)
            self.assertEqual(service.return_value.ingest_season_for_job.call_count,2)
