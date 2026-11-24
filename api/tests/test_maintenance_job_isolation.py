"""Containment controls run without Docker, a database or network access."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parent / 'integration' / 'maintenance_jobs.py'
spec = importlib.util.spec_from_file_location('maintenance_rehearsal', PATH)
rehearsal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rehearsal)


class DockerContainmentTests(unittest.TestCase):
    def guard(self, env, outputs):
        function = getattr(rehearsal, 'require_local_docker', None)
        self.assertTrue(callable(function), 'Rehearsal needs an explicit local Docker endpoint guard')
        calls = []
        def inspect(*args):
            calls.append(args)
            return outputs[len(calls)-1]
        result = function(environ=env, inspect=inspect)
        return result, calls

    def test_remote_host_refused_without_inspection(self):
        with self.assertRaisesRegex(RuntimeError, 'local Unix'):
            self.guard({'DOCKER_HOST':'tcp://remote.example:2376'}, [])

    def test_ssh_context_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'local Unix'):
            self.guard({'DOCKER_CONTEXT':'remote'}, ['ssh://remote.example'])

    def test_active_remote_context_refused(self):
        with self.assertRaisesRegex(RuntimeError, 'local Unix'):
            self.guard({}, ['remote', 'tcp://remote.example:2376'])

    def test_explicit_unix_host_accepted_without_context_lookup(self):
        endpoint, calls = self.guard({'DOCKER_HOST':'unix:///tmp/fixture.sock'}, [])
        self.assertEqual(endpoint, 'unix:///tmp/fixture.sock')
        self.assertEqual(calls, [])

    def test_context_precedes_host(self):
        endpoint, calls = self.guard({'DOCKER_HOST':'tcp://ignored:2376', 'DOCKER_CONTEXT':'desktop-linux'}, ['unix:///tmp/desktop.sock'])
        self.assertEqual(endpoint, 'unix:///tmp/desktop.sock')
        self.assertEqual(calls[0][0:3], ('context','inspect','desktop-linux'))

    def test_local_active_context_accepted(self):
        endpoint, calls = self.guard({}, ['desktop-linux','unix:///tmp/desktop.sock'])
        self.assertEqual(endpoint, 'unix:///tmp/desktop.sock')
        self.assertEqual(calls[0], ('context','show'))


if __name__ == '__main__':
    unittest.main()
