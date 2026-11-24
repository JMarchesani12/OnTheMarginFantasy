# Native integration checks

The main [isolated unit runner](../run_isolated.py) remains the default. These optional checks exercise boundaries that unit fixtures cannot fully establish:

```sh
python3 api/tests/integration/gunicorn_listener.py
python3 api/tests/integration/maintenance_jobs.py
python3 api/tests/integration/browser_privileges.py
```

Run from the repository root using ordinary Python, without -O/PYTHONOPTIMIZE. Gunicorn/eventlet and backend dependencies must be installed. The maintenance/privilege suites require Docker and their pinned PostgreSQL image cached locally. Maintenance rejects nonlocal Docker transports and checks its unique database identity before fixture reset. These scripts accept no remote DSN or target override, do not load dotenv and never invoke hosted jobs. PostgreSQL/Auth fixtures are synthetic, not full platform acceptance.

- Gunicorn: actual worker startup under normal/preloaded loading, readiness, worker replacement and graceful shutdown, with fake database I/O and loopback HTTP.
- Maintenance: actual refresh/finalization CLI subprocesses against owned PostgreSQL and fixture HTTP; upserts, replay, failure/retry, session-lock contention and per-season commit rollback.
- Browser privileges: the exact versioned privilege transition/recovery against a synthetic catalog, including nonsuperuser authority and drift refusal.

Results are written to a unique temporary directory outside the checkout and their paths printed. They are not committed benchmark/evidence files. Capture useful failures in ordinary bug reports.

Known harness limits: assertions require ordinary Python; cleanup-path errors may prevent a result file or later cleanup, so inspect owned resources after an interrupted/failed run. Gunicorn's forced failure cleanup also needs inspection if the master crashes while children survive. Normal successful runs verify cleanup. These scripts do not establish hosted provider parity or authorize production operations.
