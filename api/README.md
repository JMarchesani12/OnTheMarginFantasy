# Backend startup

The backend is Python/Flask; `npm run dev` starts the separate frontend.
Local isolated checks are verified with Python **3.14.1** and Node **22.22.2**.
CI uses Python **3.14** and Node **22.22.2**. Other runtime versions have not been
validated for this startup change. Production eventlet/Gunicorn operation still
needs a deployment smoke check; isolated tests use fake launch dependencies.

From `api`, create/activate a virtual environment and install dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 dev.py
```

The development server listens on port 5050. Configure `api/.env` or process
environment with `SUPABASE_DB_URL`, `SUPABASE_PROJECT_ID`, and
`SUPABASE_JWT_SECRET`. Process environment takes precedence. Runtime entry points
resolve `.env` relative to the API directory, independent of the current directory.
Never put credentials in checked-in files.

## Notification listener

Web startup retains the in-process PostgreSQL notification listener by default.
It uses `DATABASE_URL`, separately from the application `SUPABASE_DB_URL`.
To run the web server without notification listening:

```sh
DRAFT_NOTIFY_LISTENER_ENABLED=false python3 dev.py
```

The switch accepts `true`/`1` and `false`/`0` (case insensitive); invalid values
fail before startup. Disabling it removes database-driven draft broadcasts from
that web process. It does not suspend or restart a Render service, or disable
the independently invoked draft-timeout worker. Preserve the intentionally
suspended service until its actual command is verified.

`create_app(engine=...)` only constructs the HTTP/socket application; it starts
no listener. `runtime.create_web_app()` explicitly loads configuration, creates
the engine/application and starts the enabled listener. The dev reload supervisor
does not start a listener; its serving child does. Startup is idempotent per app.
Production retains the existing single-worker eventlet topology:

```sh
./start.sh
# Equivalent from api after runtime environment is configured:
gunicorn -k eventlet -w 1 -b 0.0.0.0:5050 wsgi:app
```

`wsgi.py` is an intentional runtime entry point: importing it initializes the web
application and applies eventlet monkey patching. Importing definition modules
(`api`, `db`, `dev`, domain and job modules) does neither. Do not preload the app
in a Gunicorn master or increase worker count without a separate listener and
Socket.IO coordination review.

## Jobs and maintenance commands

Run explicit module entry points from `api` so imports use the established API
module root. These commands perform real work; they are not test commands:

```sh
python3 -m cronJobs.cronComputeWeeklyScores
python3 -m cronJobs.cronComputeFinalScoreboard
python3 -m cronJobs.cronIngestScoreboard
python3 -m worker.draftTimeoutWorker
python3 -m startSeasonJobs.startSeason --config startSeasonJobs/configs/college-football-2026.json
python3 -m scripts.rebuild_weeks_and_rescore --season-year 2026
```

Cron `main(engine=...)` and timeout `run(engine=...)` accept injected engines for
isolated callers. They resolve runtime configuration only when no engine is
supplied. Job schedules, recovery rules and calculations are unchanged.

## Credential-free verification

From the repository root:

```sh
python3 api/tests/run_isolated.py
```

The runner clears runtime environment, disables dotenv, and prohibits engine
creation and network/database connections. Startup tests additionally check
fresh-process imports, fake web/job launches and listener/reloader configuration.
Do not replace this command with app startup or ordinary configured discovery.

Frontend checks, from `front-end` with dependencies installed:

```sh
node --test --experimental-strip-types tests/*.test.ts
npm run build
```

Node 22.22.2 supports the TypeScript stripping used by the tests and tier tools.
Render command/role inspection and hosted startup verification remain separate
read-only/deployment checks. No hosted configuration is changed by this work.
