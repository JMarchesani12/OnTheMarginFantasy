import io
import json
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace
from unittest.mock import Mock,patch
from sqlalchemy.engine import make_url
from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
from endpoints.draft.listener import DraftNotifyListener, connection_arguments


def engine(url='postgresql+psycopg2://alice:synthetic-secret@db.test/app?sslmode=require'):
    return SimpleNamespace(url=make_url(url),dialect=PGDialect_psycopg2())

class Connection:
    def __init__(self):
        self.notifies=[];self.closed=0;self.statements=[];self.poll_error=False;self.sql_error=None
    def cursor(self): return SimpleNamespace(execute=self.execute,close=lambda:None)
    def execute(self,sql):
        self.statements.append(sql)
        if self.sql_error and self.sql_error in sql:raise RuntimeError('secret SQL password')
    def close(self): self.closed+=1
    def poll(self):
        if self.poll_error:raise RuntimeError('secret DSN')
    def set_isolation_level(self,value):pass

class ListenerTests(unittest.TestCase):
    def make(self,**kwargs):
        self.now=0.;self.connections=[]
        def connect(*a,**kw):
            conn=Connection();self.connections.append(conn);return conn
        self.dispatch=Mock();self.rooms=[]
        options=dict(connect=connect,wait=lambda conn,timeout:True,clock=lambda:self.now,
                     dispatch=self.dispatch,rooms=lambda:iter(self.rooms),legacy_url=None)
        options.update(kwargs)
        return DraftNotifyListener(engine(),Mock(),**options)

    def test_engine_arguments_preserve_ssl_and_legacy_target_only(self):
        args,params=connection_arguments(engine(),'postgres://alice:other@db.test:5432/app')
        self.assertEqual(params['sslmode'],'require');self.assertEqual(params['password'],'synthetic-secret')
        self.assertEqual(params['connect_timeout'],5)
        for value in ('postgresql://alice:secret@elsewhere/app','broken secret', 'postgresql://alice@db.test/other',
                      'postgresql://alice@db.test/app?host=elsewhere'):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError,'Listener database configuration is invalid'):
                    connection_arguments(engine(),value)

    def test_connect_listen_resync_and_stop_close(self):
        listener=self.make();self.rooms=[10,20]
        self.assertEqual(listener.status()['state'],'starting')
        listener.step();self.assertEqual(listener.status()['state'],'connected')
        self.assertEqual([c.args[0] for c in self.dispatch.call_args_list],[10,20])
        self.assertIn('LISTEN draft_updated',self.connections[0].statements)
        listener.stop();listener.stop();listener.step()
        self.assertEqual(self.connections[0].closed,1)
        self.assertEqual(listener.status()['state'],'stopped')

    def test_connection_failure_backoff_caps_and_logs_are_safe(self):
        out=io.StringIO();listener=self.make(connect=Mock(side_effect=RuntimeError('postgresql://password-secret')))
        with redirect_stderr(out):
            delays=[]
            for i in range(8):
                delays.append(listener.step());self.now+=delays[-1]
        self.assertEqual(delays,[1,2,4,8,16,30,30,30])
        self.assertEqual(listener.status()['state'],'retrying')
        self.assertNotIn('password',out.getvalue());self.assertNotIn('postgresql',out.getvalue())

    def test_listen_poll_select_and_probe_failure_reconnect(self):
        for fault in ('listen','poll','select','probe'):
            with self.subTest(fault=fault):
                listener=self.make();listener.step();conn=self.connections[0]
                if fault=='listen':
                    listener.stop();listener=self.make();
                    def fail(*a,**kw):
                        c=Connection();c.sql_error='LISTEN';self.connections.append(c);return c
                    listener.connect=fail
                if fault=='poll':conn.poll_error=True
                if fault=='select':listener.wait=Mock(side_effect=RuntimeError('private select'))
                if fault=='probe':conn.sql_error='SELECT 1';self.now=16
                listener.step();self.assertEqual(listener.status()['state'],'retrying')
                self.assertEqual(self.connections[-1].closed,1)

    def test_snapshot_failure_retries_without_starving_other_leagues(self):
        listener=self.make();listener.step()
        self.dispatch.side_effect=lambda league: (_ for _ in ()).throw(RuntimeError('private snapshot')) if league==10 and self.now<2 else None
        self.connections[0].notifies=[SimpleNamespace(payload=json.dumps({'leagueId':n})) for n in (10,20,10)]
        listener.step();self.assertEqual(listener.status()['state'],'degraded')
        self.assertIn(20,[c.args[0] for c in self.dispatch.call_args_list])
        self.now=3;listener.step();self.assertEqual(listener.status()['state'],'connected')
        self.assertEqual(listener.pending,{})

    def test_malformed_notification_is_safe_and_overflow_is_bounded(self):
        listener=self.make();listener.step();conn=self.connections[0]
        conn.notifies=[SimpleNamespace(payload='secret invalid JSON')]
        listener.step();self.assertEqual(listener.status()['state'],'connected')
        conn.notifies=[SimpleNamespace(payload=json.dumps({'leagueId':n+1})) for n in range(listener.MAX_PENDING+1)]
        listener.step();self.assertLessEqual(len(listener.pending),listener.MAX_PENDING)
        self.assertEqual(listener.status()['state'],'retrying');self.assertEqual(conn.closed,1)

    def test_start_idempotent_and_stop_prevents_task_restart(self):
        server=Mock();listener=self.make();listener.socket=server
        listener.start();listener.start();self.assertEqual(server.start_background_task.call_count,1)
        listener.stop();listener.start();self.assertEqual(server.start_background_task.call_count,1)

    def test_stop_during_delivery_authorization_prevents_emit(self):
        from test_draft_realtime import DraftRealtimeTests
        from endpoints.draft.startDraftNotifyListener import dispatch_draft_notification
        base=DraftRealtimeTests();base.setUp();self.addCleanup(base.doCleanups)
        client=base.client();base.join(client)
        active=[True];access=base.io.draft_access;reader=access.reader
        def stop_after_lookup(sid,league):
            result=reader(sid,league);active[0]=False;return result
        with patch.object(access,'reader',stop_after_lookup):
            dispatch_draft_notification(base.io,base.db,{'leagueId':10},should_deliver=lambda:active[0])
        self.assertEqual(client.get_received(),[])

    def test_hostaddr_and_service_overrides_cannot_hide_target_mismatch(self):
        for field in ('hostaddr','service'):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError,'Listener database configuration is invalid'):
                    connection_arguments(engine(f'postgresql://alice@db.test/app?{field}=127.0.0.1'),
                        f'postgresql://alice@db.test/app?{field}=127.0.0.2')

    def test_overflow_reconnect_makes_progress_past_failing_prefix(self):
        listener=self.make();listener.MAX_PENDING=2;self.rooms=[1,2,3,4]
        def dispatch(league):
            if league!=4:raise RuntimeError('private failed snapshot')
        self.dispatch.side_effect=dispatch
        for attempt in range(4):
            listener.step();self.now+=31
        self.assertIn(4,[c.args[0] for c in self.dispatch.call_args_list])
        self.assertLessEqual(len(listener.pending),2)
        self.assertEqual(listener.status()['state'],'retrying')
