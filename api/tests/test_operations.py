import io
import json
import unittest
from contextlib import redirect_stderr
from unittest.mock import Mock
from operations import safe_event, job_gate, GateLost

class OperationsTests(unittest.TestCase):
    def test_log_allowlist_excludes_secrets_and_correlates(self):
        out=io.StringIO()
        with redirect_stderr(out):
            safe_event('weekly','failed','abc',category=RuntimeError('postgres://secret'),leagueId=10,
                       password='secret',message='raw SQL',payload={'token':'secret'})
        value=json.loads(out.getvalue())
        self.assertEqual(value,{'operation':'weekly','event':'failed','runId':'abc','category':'unexpected','leagueId':10})
        self.assertNotIn('secret',out.getvalue())

    def engine(self, acquired=True):
        engine=Mock();conn=engine.connect.return_value
        conn.execute.return_value.scalar_one.return_value=acquired
        return engine,conn

    def test_acquire_release_and_skip_are_same_session(self):
        for acquired in (True,False):
            engine,conn=self.engine(acquired)
            with job_gate(engine,'weekly') as gate:
                self.assertEqual(bool(gate),acquired)
                if acquired:gate.check()
            self.assertEqual(conn.close.call_count,1)
            sql=[str(c.args[0]) for c in conn.execute.call_args_list]
            self.assertIn('pg_try_advisory_lock',sql[0])
            self.assertEqual(any('pg_advisory_unlock' in s for s in sql),acquired)

    def test_exception_releases_and_unlock_failure_invalidates(self):
        engine,conn=self.engine()
        with self.assertRaises(ValueError):
            with job_gate(engine,'weekly'):raise ValueError('fault')
        self.assertTrue(any('pg_advisory_unlock' in str(c.args[0]) for c in conn.execute.call_args_list))
        engine,conn=self.engine();conn.execute.side_effect=[Mock(scalar_one=lambda:True),Mock(scalar_one=lambda:123),RuntimeError('secret')]
        with self.assertRaises(GateLost):
            with job_gate(engine,'weekly'):pass
        conn.invalidate.assert_called_once();conn.close.assert_called_once()

    def test_lost_connection_never_reconnects_or_claims_success(self):
        engine,conn=self.engine();conn.invalidated=False;conn.closed=False
        with self.assertRaises(GateLost):
            with job_gate(engine,'weekly') as gate:
                conn.invalidated=True;gate.check()
        self.assertEqual(engine.connect.call_count,1)

    def test_setup_failure_after_acquire_discards_session_lock(self):
        engine,conn=self.engine()
        conn.execute.side_effect=[Mock(scalar_one=lambda:True),RuntimeError('secret')]
        with self.assertRaises(GateLost):
            with job_gate(engine,'weekly'):pass
        conn.invalidate.assert_called_once();conn.close.assert_called_once()

    def test_interrupts_during_setup_and_unlock_discard_session(self):
        for stage in ('setup','unlock'):
            engine,conn=self.engine()
            conn.execute.side_effect=([Mock(scalar_one=lambda:True),KeyboardInterrupt()] if stage=='setup' else
                [Mock(scalar_one=lambda:True),Mock(scalar_one=lambda:123),KeyboardInterrupt()])
            with self.assertRaises(KeyboardInterrupt):
                with job_gate(engine,'weekly'):pass
            conn.invalidate.assert_called_once();conn.close.assert_called_once()
