# Backend

Python/Flask API with SQLAlchemy/PostgreSQL and Flask-SocketIO. CI uses Python 3.14.

## Local setup

From api:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 dev.py
```

Development listens on 5050. Set SUPABASE_DB_URL, SUPABASE_PROJECT_ID and SUPABASE_JWT_SECRET in api/.env or process environment. Set CORS_ORIGINS for the frontend origin. Runtime loads environment relative to api; process values take precedence. Never commit credentials.

SUPABASE_DB_URL must use a direct/session-preserving endpoint for LISTEN and job locks. DATABASE_URL is optional legacy consistency validation; if present its effective target must match. Production uses `./start.sh` from api, one Gunicorn/eventlet worker and the worker-local startup/shutdown hooks. See [operations](../docs/operations.md) for listener readiness, scheduled jobs and manual maintenance.

## Application structure

`api.py:create_app(engine=...)` constructs routes/sockets without background startup. `runtime.create_web_app()` composes the web runtime; `wsgi.py` defers it until Gunicorn worker initialization. Services own authorization/transactions, repositories own SQL on caller-supplied connections. Canonical layers do not construct a configured engine.

| Area | Location |
| --- | --- |
| HTTP authentication/principals | authMiddleware.py, supabaseAuth.py, utils/authorization.py |
| Domain routes/services/repositories | endpoints/ |
| League/tournament rules | rules/ |
| Scheduled jobs / timeout polling | cronJobs/ / worker/ |
| Season manifests/bootstrap | [startSeasonJobs](startSeasonJobs/README.md) |
| Calendar maintenance | scripts/rebuild_weeks_and_rescore.py |
| Schema upgrades | migrations/ and [db](../db/README.md) |

The browser uses Supabase Auth; application profile reads/provisioning go through authenticated backend endpoints. Public catalog/search routes are explicit exceptions. Draft sockets validate tokens and current membership before joining/delivery.

## Testing

From the repository root:

```sh
python3 api/tests/run_isolated.py
```

The runner clears configuration, disables dotenv and prevents engine/network/database access. Do not replace it with ordinary discovery that might load local credentials. Optional [native integration checks](tests/integration/README.md) use fake I/O or owned local fixtures only. CI also runs frontend tests/build and [snapshot-tool unit tests](../scripts/database/README.md).

Current domain contracts are documented in [domain rules](../docs/domain-rules.md). Operational follow-ups are tracked in [follow-ups](../docs/follow-ups.md).
