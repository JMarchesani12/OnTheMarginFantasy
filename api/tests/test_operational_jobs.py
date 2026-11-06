import io
import json
import unittest
from contextlib import contextmanager,redirect_stderr,redirect_stdout
from unittest.mock import Mock,patch
from operations import GateLost

@contextmanager
def fake_gate(engine,name):
    gate=Mock();gate.__bool__=lambda _:True
    yield gate

class OperationalJobTests(unittest.TestCase):
    def modules(self):
        from cronJobs import cronComputeWeeklyScores,cronComputeFinalScoreboard,cronIngestScoreboard,cronRefreshSchedules
        return [cronComputeWeeklyScores,cronComputeFinalScoreboard,cronIngestScoreboard,cronRefreshSchedules]

    def test_overlap_skips_each_job_before_service_or_provider_work(self):
        for module in self.modules():
            with self.subTest(module=module.__name__):
                @contextmanager
                def busy(*args):yield False
                out=io.StringIO()
                with patch.object(module,'job_gate',busy),redirect_stderr(out):
                    report=module.main(engine=Mock(),**({'argv':[]} if 'Refresh' in module.__name__ else {}))
                self.assertIn('already_running',out.getvalue())
                self.assertIsNotNone(report)

    def test_live_ingestion_partial_failure_continues_and_is_safe(self):
        module=self.modules()[2];out=io.StringIO()
        with patch.object(module,'job_gate',fake_gate),patch.object(module,'ScheduleIngestionService') as service,redirect_stderr(out):
            service.return_value.active_leagues_for_job.return_value=[10,20]
            service.return_value.ingest_league_for_job.side_effect=[RuntimeError('private token SQL'),{'eventsSeen':2}]*2
            report=module.main(engine=Mock())
        self.assertTrue(report['failures']);self.assertTrue(report['processed'])
        self.assertNotIn('private',out.getvalue())
        rows=[json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(len({row['runId'] for row in rows}),1)

    def test_refresh_partial_failure_does_not_print_exception(self):
        module=self.modules()[3];engine=Mock();out=io.StringIO()
        import datetime as dt
        today=dt.datetime.now(module.ZoneInfo('America/Chicago')).date()
        engine.connect.return_value.__enter__=Mock(return_value=engine)
        engine.connect.return_value.__exit__=Mock(return_value=False)
        engine.execute.return_value.mappings.return_value.all.return_value=[{'id':1,'seasonStart':today,'seasonEnd':today}]
        with patch.object(module,'job_gate',fake_gate),patch.object(module,'ScheduleIngestionService') as service,redirect_stderr(out):
            service.return_value.ingest_season_for_job.side_effect=RuntimeError('secret credential SQL')
            with self.assertRaisesRegex(RuntimeError,'Schedule refresh incomplete'):module.main(argv=[],engine=engine)
        self.assertNotIn('secret',out.getvalue())

    def test_worker_stop_wait_and_safe_failure_log(self):
        from worker import draftTimeoutWorker as worker
        stop=Mock();stop.is_set.side_effect=[False,True];stop.wait.return_value=True
        out=io.StringIO()
        with patch.object(worker,'_get_next_expired_or_soonest_deadline',side_effect=RuntimeError('secret token')),redirect_stderr(out):
            engine=Mock();engine.begin.return_value.__enter__=Mock(return_value=engine);engine.begin.return_value.__exit__=Mock(return_value=False)
            worker.run(engine=engine,stop_event=stop)
        self.assertNotIn('secret',out.getvalue());stop.wait.assert_called_once_with(2)

    def test_timeout_stop_during_deadline_read_prevents_new_mutation(self):
        import threading
        from worker import draftTimeoutWorker as worker
        stop=threading.Event();engine=Mock()
        engine.begin.return_value.__enter__=Mock(return_value=engine);engine.begin.return_value.__exit__=Mock(return_value=False)
        def deadline(conn):stop.set();return (10,-1)
        with patch.object(worker,'_get_next_expired_or_soonest_deadline',deadline),patch.object(worker,'DraftPickService') as service:
            worker.run(engine=engine,stop_event=stop)
        service.return_value.process_timeout_for_job.assert_not_called()

    def test_worker_entry_startup_failure_is_safe_and_restores_signal_handlers(self):
        from worker import draftTimeoutWorker as worker
        out=io.StringIO()
        with patch.object(worker.signal,'signal',return_value='prior') as install,patch.object(worker,'run',side_effect=RuntimeError('secret DSN')),redirect_stderr(out):
            with self.assertRaises(SystemExit) as result:worker.main()
        self.assertEqual(result.exception.code,1);self.assertEqual(install.call_count,4)
        self.assertNotIn('secret',out.getvalue())

    def test_nested_provider_parser_error_does_not_print_body_or_traceback(self):
        from endpoints.schedule.helpers.espn.espnClient import ESPNClient
        out,err=io.StringIO(),io.StringIO()
        with redirect_stdout(out),redirect_stderr(err):
            value=ESPNClient('https://synthetic.invalid','football').extract_game_from_event({'id':'secret contact token','date':'private credential'})
        self.assertIsNone(value)
        self.assertNotIn('secret',out.getvalue()+err.getvalue())
        self.assertNotIn('private',out.getvalue()+err.getvalue())
        self.assertNotIn('Traceback',err.getvalue())

    def test_busy_scoring_jobs_preserve_single_json_stdout_report(self):
        for module in self.modules()[:2]:
            @contextmanager
            def busy(*a):yield False
            out=io.StringIO()
            with patch.object(module,'job_gate',busy),redirect_stdout(out):
                report=module.main(engine=Mock())
            self.assertEqual(json.loads(out.getvalue()),report)
            self.assertEqual(report['outcome'],'already_running')
