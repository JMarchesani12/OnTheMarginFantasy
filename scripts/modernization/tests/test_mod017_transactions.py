import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class TransactionBaselineTests(unittest.TestCase):
    def setUp(self):self.m=importlib.import_module('measure_mod017_transactions')

    def test_capture_actual_auth_and_pending_queries(self):
        cases={c['name']:c for c in self.m.capture_queries(100,'2026-11-13T12:00:00+00:00')}
        self.assertEqual(len(cases),11)
        self.assertIn('reader_member."userId" = :reader_user_id',cases['open_participant']['sql'])
        self.assertEqual(cases['list_pending']['params']['status'],'PENDING_APPLY')
        self.assertEqual(cases['open_denied']['params']['reader_user_id'],-1)
        self.assertIn('UNION',cases['weekly_candidates']['sql'])
        self.assertNotIn('FOR UPDATE',cases['weekly_candidates']['sql'])
        self.assertEqual(cases['open_participant']['expected_rows'],10)
        self.assertEqual(cases['weekly_candidates']['expected_rows'],10)

    def test_expected_counts_are_enforced(self):
        case=dict(name='pending',expected_rows=1)
        record=dict(result=dict(rows=1),client_execute_fetch_ms=dict(samples=[1]*5))
        self.m.validate_result(case,record)
        record['result']['rows']=0
        with self.assertRaises(AssertionError):self.m.validate_result(case,record)
        record['result']['rows']=1;record['client_execute_fetch_ms']['samples']=[1]
        with self.assertRaises(AssertionError):self.m.validate_result(case,record)

    def test_connection_failure_replaces_current_manifest_not_prior_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);prior=path/'prior.json';prior.write_text('{"result":"PASS"}')
            manifest=path/'current.json';manifest.write_text('{"result":"PASS","artifact":"prior.json"}')
            with self.assertRaisesRegex(RuntimeError,'injected'):
                self.m.run(path,manifest,[100],connect=lambda:(_ for _ in ()).throw(RuntimeError('injected')))
            current=json.loads(manifest.read_text());self.assertEqual(current['result'],'FAILED')
            artifact=json.loads((path/current['artifact']).read_text());self.assertEqual(artifact['result'],'FAILED')
            self.assertEqual(artifact['error_type'],'RuntimeError');self.assertEqual(artifact['cleanup'],'no database created')
            self.assertEqual(json.loads(prior.read_text())['result'],'PASS')

    def test_provenance_failure_replaces_current_pass_before_connect(self):
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);manifest=path/'current.json'
            manifest.write_text('{"result":"PASS","artifact":"previous.json"}')
            (path/'previous.json').write_text('{"result":"PASS"}')
            connect=MagicMock()
            with patch.object(self.m.base,'ROOT',path/'missing-source-root'):
                with self.assertRaises(FileNotFoundError):self.m.run(path,manifest,[100],connect=connect)
            connect.assert_not_called()
            current=json.loads(manifest.read_text());self.assertEqual(current['result'],'FAILED')
            artifact=json.loads((path/current['artifact']).read_text())
            self.assertEqual(artifact['error_type'],'FileNotFoundError')
            self.assertEqual(artifact['cleanup'],'no database created')
            self.assertEqual(json.loads((path/'previous.json').read_text())['result'],'PASS')

    def test_tier_failure_records_cleanup_attempt_and_never_pass(self):
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);admin=MagicMock()
            with patch.object(self.m,'run_tier',side_effect=ValueError('synthetic fixture failed')):
                with self.assertRaises(ValueError):self.m.run(path,path/'current.json',[100],connect=lambda:admin)
            artifact=json.loads((path/json.loads((path/'current.json').read_text())['artifact']).read_text())
            self.assertEqual(artifact['result'],'FAILED');self.assertNotEqual(artifact['cleanup'],'verified')
            admin.close.assert_called_once()

if __name__=='__main__':unittest.main()
