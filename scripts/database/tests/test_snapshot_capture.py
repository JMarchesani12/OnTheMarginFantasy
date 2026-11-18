import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class SnapshotCaptureTests(unittest.TestCase):
    def setUp(self):self.m=importlib.import_module('capture_snapshot')
    def test_existing_output_refused_without_changes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'snapshot';p.mkdir();(p/'sentinel').write_text('keep')
            connect=Mock()
            with self.assertRaises(FileExistsError):self.m.capture(p,connect=connect)
            self.assertEqual((p/'sentinel').read_text(),'keep');connect.assert_not_called()
    def test_secret_screening_refuses_connection_strings_and_known_secrets(self):
        for text in ['postgresql://user:pw@host/db','password=abc123','eyJabcdefghijk.abcdefghijklmnop.abcdefghijk','SELECT very-private-secret;']:
            with self.assertRaises(self.m.SnapshotError):self.m.screen(text.encode(),['very-private-secret'])
        self.m.screen(b'CREATE TABLE public."User" (id bigint);',[])
    def test_session_params_force_tls_and_readonly_without_changing_target_project(self):
        values={'SUPABASE_DB_URL':'postgresql://postgres.project:secret@aws.pooler.supabase.com:6543/postgres?sslmode=disable','SUPABASE_PROJECT_ID':'project'}
        p=self.m.connection_parameters(values)
        self.assertEqual(p['port'],5432);self.assertEqual(p['sslmode'],'require')
        self.assertIn('default_transaction_read_only=on',p['options'])
        self.assertEqual(p['host'],'aws.pooler.supabase.com');self.assertEqual(p['password'],'secret')
        with self.assertRaises(self.m.SnapshotError):self.m.connection_parameters(dict(values,SUPABASE_PROJECT_ID='wrong'))
    def test_failed_collection_leaves_failed_manifest_without_private_error(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'snapshot'
            with self.assertRaises(self.m.SnapshotError):self.m.capture(p,connect=Mock(side_effect=ValueError('postgresql://secret')))
            manifest=json.loads((p/'manifest.json').read_text())
            self.assertEqual(manifest['result'],'FAILED');self.assertNotIn('postgresql',json.dumps(manifest))
            self.assertFalse((p/'schema.sql').exists())
    def test_publish_checksums_cover_every_output_and_refuse_secret(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);manifest={'result':'RUNNING'}
            self.m.publish(p,{'schema.sql':b'CREATE TABLE public.safe(id int);','catalog.json':b'{}'},manifest,[])
            self.assertEqual(manifest['result'],'PASS')
            self.assertEqual(set(manifest['files']),{'schema.sql','catalog.json'})
            import hashlib
            for name,metadata in manifest['files'].items():self.assertEqual(hashlib.sha256((p/name).read_bytes()).hexdigest(),metadata['sha256'])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            with self.assertRaises(self.m.SnapshotError):self.m.publish(p,{'schema.sql':b'postgresql://user:pw@host/db'},{'result':'RUNNING'},[])
            self.assertFalse((p/'schema.sql').exists())
    def test_dump_failure_cannot_publish_pass_or_private_stderr(self):
        from unittest.mock import patch
        import subprocess
        values={'SUPABASE_DB_URL':'postgresql://postgres.project:secret@aws.pooler.supabase.com:6543/postgres','SUPABASE_PROJECT_ID':'project'}
        def fail_export(params,ignored):
            return self.m.export_schema(params,'synthetic-snapshot')
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'capture'
            responses=[subprocess.CompletedProcess([],1,b'',b'postgresql://private-password@host/db'),subprocess.CompletedProcess([],0,'','')]
            with patch.object(self.m,'dotenv_values',return_value=values),patch.object(self.m,'collect',side_effect=fail_export),patch.object(self.m.subprocess,'run',side_effect=responses):
                with self.assertRaises(self.m.SnapshotError):self.m.capture(output)
            manifest=(output/'manifest.json').read_text()
            self.assertEqual(json.loads(manifest)['result'],'FAILED')
            self.assertNotIn('private-password',manifest)
            self.assertFalse((output/'schema.sql').exists())
    def test_embedded_database_password_is_screened_even_without_dsn_or_assignment(self):
        from unittest.mock import patch
        values={'SUPABASE_DB_URL':'postgresql://postgres.project:super-private-password@aws.pooler.supabase.com:6543/postgres','SUPABASE_PROJECT_ID':'project'}
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'snapshot'
            returned=(b"CREATE TABLE public.safe(value text DEFAULT 'super-private-password');",{}, {}, {})
            with patch.object(self.m,'dotenv_values',return_value=values),patch.object(self.m,'collect',return_value=returned):
                with self.assertRaises(self.m.SnapshotError):self.m.capture(output)
            self.assertFalse((output/'schema.sql').exists())
            self.assertEqual(json.loads((output/'manifest.json').read_text())['result'],'FAILED')
    def test_known_short_password_is_never_published(self):
        with self.assertRaises(self.m.SnapshotError):self.m.screen(b"CREATE TABLE public.safe(value text DEFAULT 's3cr3t!');",['s3cr3t!'])
