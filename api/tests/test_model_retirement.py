"""Retired Python entry points must not silently reappear."""
import importlib
import unittest


class ModelRetirementTests(unittest.TestCase):
    def test_retired_model_imports_are_unavailable(self):
        for domain in ('user', 'sport', 'transaction', 'schedule', 'scoring', 'roster', 'league', 'draft'):
            name = f'endpoints.{domain}.{domain}Model'
            with self.subTest(module=name):
                with self.assertRaises(ModuleNotFoundError) as raised:
                    importlib.import_module(name)
                self.assertEqual(raised.exception.name, name)

    def test_migrated_harnesses_import_standalone_without_pythonpath(self):
        # Umbrella harnesses initialize api/ before importing these modules;
        # a fresh interpreter exercises the documented standalone entry path.
        import os
        from pathlib import Path
        import subprocess
        import sys
        root = Path(__file__).resolve().parents[2]
        bootstrap = '''
import runpy, socket, sys
from unittest.mock import patch
import dotenv, psycopg2, sqlalchemy

def forbidden(*args, **kwargs):
    raise AssertionError('Standalone import must not perform I/O')

sys.path.insert(0, sys.argv[1])
with patch.object(dotenv, 'load_dotenv', return_value=False), \\
     patch.object(psycopg2, 'connect', forbidden), \\
     patch.object(sqlalchemy, 'create_engine', forbidden), \\
     patch.object(socket.socket, 'connect', forbidden), \\
     patch.object(socket, 'getaddrinfo', forbidden):
    runpy.run_path(sys.argv[2], run_name='standalone_import_check')
'''
        for name in ('verify_admission_slice', 'verify_admission_create_deny', 'verify_league_settings'):
            with self.subTest(harness=name):
                result = subprocess.run(
                    [sys.executable, '-c', bootstrap, str(root / 'scripts/modernization'),
                     str(root / f'scripts/modernization/{name}.py')],
                    cwd=root, env={key: value for key, value in os.environ.items() if key != 'PYTHONPATH'},
                    capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
