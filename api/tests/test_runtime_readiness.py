import unittest
from unittest.mock import Mock,patch
from api import create_app
from runtime import start_web_listener,stop_web_listener

class RuntimeReadinessTests(unittest.TestCase):
    def test_public_cached_readiness_and_unchanged_liveness(self):
        engine=Mock()
        with patch.dict('os.environ',{'DRAFT_NOTIFY_LISTENER_ENABLED':'true'}):app=create_app(engine)
        client=app.test_client()
        self.assertEqual(client.get('/health').json,{'ok':True})
        self.assertEqual(client.get('/ready').status_code,503)
        engine.reset_mock()
        controller=Mock();app.extensions['draft_notify_listener']=controller
        for state,code in (('connected',200),('starting',503),('retrying',503),('degraded',503),('stopped',503)):
            controller.status.return_value={'enabled':True,'state':state,'category':None}
            response=client.get('/ready');self.assertEqual(response.status_code,code)
            self.assertEqual(response.json['listener']['state'],state)
        engine.begin.assert_not_called();engine.connect.assert_not_called()

    def test_disabled_readiness_idempotent_start_and_stop(self):
        with patch.dict('os.environ',{'DRAFT_NOTIFY_LISTENER_ENABLED':'false'}):app=create_app(Mock())
        self.assertEqual(app.test_client().get('/ready').status_code,200)
        app.extensions={};controller=Mock();starter=Mock(return_value=controller)
        with patch.dict('os.environ',{'DRAFT_NOTIFY_LISTENER_ENABLED':'true'}):
            start_web_listener(app,Mock(),Mock(),starter=starter)
            start_web_listener(app,Mock(),Mock(),starter=starter)
        starter.assert_called_once();stop_web_listener(app);stop_web_listener(app)
        self.assertEqual(controller.stop.call_count,2) # underlying stop is idempotent

    def test_gunicorn_exit_hook_and_dev_finally_use_explicit_stop(self):
        import runpy
        from pathlib import Path
        namespace=runpy.run_path(str(Path(__file__).parents[1]/'gunicorn_conf.py'))
        with patch('runtime.stop_web_listener') as stop:
            app=object();namespace['worker_exit'](Mock(),Mock(wsgi=app));stop.assert_called_once_with(app)
        import dev
        app=Mock()
        with patch('runtime.create_web_app',return_value=app),patch('eventlet.monkey_patch'),patch('runtime.stop_web_listener') as stop,patch('socketioInstance.socketio.run',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):dev.main()
            stop.assert_called_once_with(app)

    def test_deferred_composition_and_worker_hook_start_only_in_worker(self):
        import runtime,runpy
        from pathlib import Path
        app=Mock();app.extensions={};engine=Mock();server=Mock()
        with patch('runtime.load_runtime_environment'),patch('supabaseAuth.auth_configuration'),patch('api.create_app',return_value=app),patch('socketioInstance.socketio',server),patch('runtime.start_web_listener') as start:
            runtime.create_web_app(engine=engine,start_listener=False)
            start.assert_not_called()
            hooks=runpy.run_path(str(Path(__file__).parents[1]/'gunicorn_conf.py'))
            wrapped=Mock();wrapped.initialize.return_value=app
            hooks['post_worker_init'](Mock(wsgi=wrapped))
            wrapped.initialize.assert_called_once_with()
            start.assert_called_once_with(app,server,engine)
