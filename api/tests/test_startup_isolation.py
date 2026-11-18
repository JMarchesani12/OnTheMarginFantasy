"""Startup contracts: subprocesses must never read real configuration."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

API = Path(__file__).resolve().parents[1]


class StartupIsolationTests(unittest.TestCase):
    def test_fresh_definition_imports_need_no_secrets_or_runtime(self):
        script = '''
import os, sys, importlib, socket
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
import dotenv, sqlalchemy, psycopg2

def forbidden(*a, **kw):
    raise AssertionError('Unexpected runtime activity during import')
with patch.dict(os.environ, {}, clear=True), patch.object(dotenv, 'load_dotenv', forbidden), patch.object(sqlalchemy, 'create_engine', forbidden), patch.object(psycopg2, 'connect', forbidden), patch.object(socket.socket, 'connect', forbidden):
    for name in ('db', 'supabaseAuth', 'bootstrap', 'api', 'dev', 'endpoints.draft.startDraftNotifyListener', 'worker.draftTimeoutWorker', 'cronJobs.cronComputeWeeklyScores', 'cronJobs.cronComputeFinalScoreboard', 'cronJobs.cronIngestScoreboard', 'cronJobs.cronRefreshSchedules', 'startSeasonJobs.startSeason', 'scripts.rebuild_weeks_and_rescore'):
        importlib.import_module(name)
'''
        result = subprocess.run([sys.executable, '-c', script, str(API)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_app_factory_does_not_start_listener(self):
        from api import create_app
        engine = Mock()
        with patch('flask_socketio.SocketIO.start_background_task', side_effect=AssertionError('listener started')):
            app = create_app(engine=engine)
        self.assertEqual(app.test_client().get('/health').json, {'ok': True})

    def test_missing_auth_configuration_fails_clearly(self):
        import supabaseAuth
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'SUPABASE_PROJECT_ID'):
                supabaseAuth.verify_supabase_token('synthetic')

    def test_listener_switch_and_duplicate_start(self):
        from runtime import start_web_listener
        for value in (None, 'true', '1', 'false', '0'):
            with self.subTest(value=value):
                app = Mock()
                app.extensions = {}
                env = {} if value is None else {'DRAFT_NOTIFY_LISTENER_ENABLED': value}
                start = Mock()
                with patch.dict(os.environ, env, clear=True):
                    start_web_listener(app, 'socket', 'engine', starter=start)
                    start_web_listener(app, 'socket', 'engine', starter=start)
                self.assertEqual(start.call_count, 0 if value in ('false', '0') else 1)
                if start.called:
                    start.assert_called_once_with('socket', 'engine')

    def test_invalid_switch_and_reload_supervisor_do_not_start(self):
        from runtime import start_web_listener
        app = Mock()
        app.extensions = {}
        start = Mock()
        with patch.dict(os.environ, {'DRAFT_NOTIFY_LISTENER_ENABLED': 'typo'}, clear=True):
            with self.assertRaisesRegex(ValueError, 'DRAFT_NOTIFY_LISTENER_ENABLED'):
                start_web_listener(app, 'socket', 'engine', starter=start)
        with patch.dict(os.environ, {}, clear=True):
            start_web_listener(app, 'socket', 'engine', starter=start, use_reloader=True)
        start.assert_not_called()
        with patch.dict(os.environ, {'WERKZEUG_RUN_MAIN': 'true'}, clear=True):
            start_web_listener(app, 'socket', 'engine', starter=start, use_reloader=True)
        start.assert_called_once()

    def test_engine_is_resolved_only_on_demand(self):
        import db
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'SUPABASE_DB_URL'):
                db.get_engine()
        with patch.dict(os.environ, {'SUPABASE_DB_URL': 'synthetic'}, clear=True), patch.object(db, 'create_engine') as create:
            self.assertIs(db.get_engine(), create.return_value)
            create.assert_called_once_with('synthetic', pool_pre_ping=True)

    def test_web_composition_passes_engine_to_factory_and_listener(self):
        from runtime import create_web_app
        engine, app = Mock(), Mock()
        with patch('runtime.load_runtime_environment') as load, patch('api.create_app', return_value=app) as factory, patch('runtime.start_web_listener') as start:
            self.assertIs(create_web_app(engine=engine, use_reloader=True), app)
        load.assert_called_once()
        factory.assert_called_once_with(engine=engine)
        start.assert_called_once()
        self.assertIs(start.call_args.args[0], app)
        self.assertIs(start.call_args.args[2], engine)
        self.assertEqual(start.call_args.kwargs, {'use_reloader': True})

    def test_job_entry_points_accept_fake_engine_without_loading_configuration(self):
        from cronJobs import cronComputeWeeklyScores as weekly
        from cronJobs import cronComputeFinalScoreboard as final
        from cronJobs import cronIngestScoreboard as ingest
        engine = Mock()
        engine.begin.return_value.__enter__ = Mock(return_value=engine)
        engine.begin.return_value.__exit__ = Mock(return_value=False)
        engine.execute.return_value.fetchall.return_value = []
        with patch('runtime.configured_engine', side_effect=AssertionError('configuration loaded')):
            weekly.main(engine=engine)
            final.main(engine=engine)
            with patch.object(ingest, 'ScheduleIngestionService') as service:
                service.return_value.active_leagues_for_job.return_value = []
                with patch.dict(os.environ, {'ESPN_BASE_URL': 'https://synthetic.invalid'}, clear=True):
                    ingest.main(engine=engine)
                self.assertIs(service.call_args.args[0], engine)

    def test_worker_accepts_fake_engine_without_loading_configuration(self):
        from worker import draftTimeoutWorker as worker
        engine = Mock()
        engine.begin.return_value.__enter__ = Mock(return_value=engine)
        engine.begin.return_value.__exit__ = Mock(return_value=False)
        with patch('runtime.configured_engine', side_effect=AssertionError('configuration loaded')), patch.object(worker, '_get_next_expired_or_soonest_deadline', return_value=None), patch.object(worker.threading.Event, 'wait', side_effect=KeyboardInterrupt('stop fake worker')):
            with self.assertRaises(KeyboardInterrupt):
                worker.run(engine=engine)

    def test_environment_path_does_not_depend_on_working_directory(self):
        import runtime
        with patch.object(runtime, 'load_dotenv') as load:
            runtime.load_runtime_environment()
        load.assert_called_once_with(API / '.env')

    def test_wsgi_composes_after_eventlet_patch_with_fakes(self):
        import runpy
        import types
        eventlet = types.ModuleType('eventlet')
        calls = []
        eventlet.monkey_patch = lambda: calls.append('patch')
        sentinel = object()
        with patch.dict(sys.modules, {'eventlet': eventlet}), patch('runtime.create_web_app', side_effect=lambda: calls.append('compose') or sentinel):
            namespace = runpy.run_path(str(API / 'wsgi.py'))
        self.assertIs(namespace['app'], sentinel)
        self.assertEqual(calls, ['patch', 'compose'])

    def test_dev_launch_composes_before_running_server(self):
        import dev
        from socketioInstance import socketio
        sentinel = object()
        with patch('runtime.create_web_app', return_value=sentinel) as compose, patch.object(socketio, 'run') as run, patch('runtime.stop_web_listener') as stop, patch('eventlet.monkey_patch'):
            dev.main()
        compose.assert_called_once_with(use_reloader=True)
        run.assert_called_once_with(sentinel, host='0.0.0.0', port=5050, debug=True)
        stop.assert_called_once_with(sentinel)

    def test_injected_factory_never_loads_dotenv(self):
        from api import create_app
        with patch('dotenv.load_dotenv', side_effect=AssertionError('factory loaded local secrets')), patch('flask_socketio.SocketIO.start_background_task', side_effect=AssertionError('listener started')):
            app = create_app(engine=Mock())
        self.assertEqual(app.test_client().get('/health').status_code, 200)

    def test_socket_cors_uses_composition_environment_after_preimport(self):
        from api import create_app
        from socketioInstance import socketio
        with patch.dict(os.environ, {'CORS_ORIGINS': 'https://synthetic.invalid'}, clear=True):
            create_app(engine=Mock())
        self.assertEqual(socketio.server.eio.cors_allowed_origins, ['https://synthetic.invalid'])
