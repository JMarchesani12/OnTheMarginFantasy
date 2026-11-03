"""Run unittest suites without dotenv, live credentials, engines or sockets.

From the repository root: python3 api/tests/run_isolated.py [test_file_pattern]
The guard is for this repository's unit tests, not a general security sandbox.
"""
import os
from pathlib import Path
import socket
import sys
import unittest
from contextlib import ExitStack
from unittest.mock import patch


def main():
    api_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(api_root))
    # Import libraries, never the application factory or configured engine.
    import dotenv
    import sqlalchemy
    import sqlalchemy.engine.create
    import psycopg2

    def forbidden(*args, **kwargs):
        raise AssertionError("Isolated tests must not open network/database connections")

    with ExitStack() as guards:
        guards.enter_context(patch.dict(os.environ, {
            "SUPABASE_PROJECT_ID": "regression-test",
            "SUPABASE_JWT_SECRET": "synthetic-test-secret-never-used-outside-tests-2026",
        }, clear=True))
        guards.enter_context(patch.object(dotenv, "load_dotenv", return_value=False))
        guards.enter_context(patch.object(sqlalchemy, "create_engine", side_effect=forbidden))
        guards.enter_context(patch.object(sqlalchemy.engine.create, "create_engine", side_effect=forbidden))
        guards.enter_context(patch.object(sqlalchemy.engine, "create_engine", side_effect=forbidden))
        guards.enter_context(patch.object(psycopg2, "connect", side_effect=forbidden))
        guards.enter_context(patch.object(socket.socket, "connect", forbidden))
        guards.enter_context(patch.object(socket.socket, "connect_ex", forbidden))
        guards.enter_context(patch.object(socket, "create_connection", side_effect=forbidden))
        guards.enter_context(patch.object(socket, "getaddrinfo", side_effect=forbidden))
        guards.enter_context(patch.object(socket.socket, "sendto", forbidden))
        suite = unittest.defaultTestLoader.discover(
            str(api_root / "tests"), pattern=sys.argv[1] if len(sys.argv) > 1 else "test_*.py"
        )
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
