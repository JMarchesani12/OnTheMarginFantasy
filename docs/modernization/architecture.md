# Architecture orientation

Observed 2026-10-28; source inspection only. Paths are relative to the repository root. No repository-specific AGENTS.md or CLAUDE.md was found.

## Entry points and configuration

- Frontend: `front-end/index.html` → `src/main.tsx` → `src/App.tsx`. React 19, TypeScript 5.9, Vite 7, React Router 7; lazy-loaded screens, AuthProvider and CurrentUserProvider. Configuration: `vite.config.ts`, `tsconfig*.json`, `eslint.config.js`.
- Backend: `api/api.py:create_app` builds Flask 3, installs CORS/auth middleware, registers eight route groups, initializes Flask-SocketIO and starts the draft notification listener. Development: `api/dev.py`; production: `api/start.sh` → Gunicorn/eventlet, one worker → `api/wsgi.py:app`. Default API port: 5050.
- Request flow: React `src/api/*` → Flask `endpoints/*/routes.py` → `*Endpoints.py` → `*Model.py` → SQLAlchemy/raw SQL → Supabase Postgres (`api/db.py`).

## Directory map

| Path | Responsibility |
| --- | --- |
| `front-end/src/screens`, `components` | Auth, league, draft, roster, schedule, settings UI and reusable views |
| `front-end/src/api`, `context`, `lib` | HTTP clients, session/current-user state, Supabase client |
| `front-end/src/types`, `utils`, `mock` | Shared types, calculations/display helpers, sample data |
| `front-end/public`, `tests` | Static assets/SEO files; Node test-runner utility tests |
| `api/endpoints` | League, draft, roster, schedule, transaction, scoring, user and sport APIs; schedule provider adapters |
| `api/rules`, `utils`, `tests` | League/tournament rules, serialization helpers, Python unittest suites |
| `api/cronJobs`, `worker` | Score ingestion, weekly/final scoring; persistent draft timeout process |
| `api/startSeasonJobs`, `scripts` | Season manifests/bootstrap and week rebuild/rescore maintenance |
| `api/migrations`, `db` | SQL migrations; schema snapshot and data-model documentation |
| `scripts/basketball-tiers` | Standalone TypeScript ESPN analysis/tier-generation CLI with tests |
| `.cache`, `output` | Local/generated artifacts; bootstrap also uses `api/.cache/season-bootstrap` per setup docs |

## Dependencies and commands

Manifests: `front-end/package.json` and `package-lock.json`; `api/requirements.txt` (pinned Python dependencies); `scripts/basketball-tiers/package.json` (ES-module marker, no dependencies/scripts). No root manifest found.

Commands below are identified, **not executed**. Derived commands are distinguished from package scripts.

| Working directory | Purpose | Command |
| --- | --- | --- |
| `front-end` | Dev / preview | `npm run dev` / `npm run preview` |
| `front-end` | Build, including TypeScript | `npm run build` (`tsc -b && vite build`) |
| `front-end` | Lint | `npm run lint` (`eslint .`) |
| `front-end` | App type-check only, derived | `./node_modules/.bin/tsc -p tsconfig.app.json --noEmit` |
| `front-end` | UI utility tests, derived; no general test script | `node --test --experimental-strip-types tests/*.test.ts` |
| `front-end` | Tier CLI / tests / type-check | `npm run basketball:tiers` / `npm run basketball:tiers:test` / `npm run basketball:tiers:typecheck` |
| `api` | Dev / production-style startup | `python3 dev.py` / `./start.sh` |
| `api` | Python tests, derived from unittest files | `python3 -m unittest discover -s tests -p 'test_*.py'` |

Node must support TypeScript stripping for the test/CLI commands; no explicit runtime pin found. No backend lint/type-check/build command or CI workflow found. Test safety and command success have not been validated.

## Authentication and authorization

- Supabase Auth handles email/password signup/login and password recovery (`screens/Auth/*`); `context/AuthContext.tsx` also exposes email OTP. OAuth code in SignIn is commented out. The Supabase client persists and refreshes sessions; `api/client.ts` sends bearer tokens. Application profiles map Supabase UUIDs to `User` rows through the API.
- `api/authMiddleware.py` validates JWTs into `g.user`. `supabaseAuth.py` uses HS256, configured issuer and `authenticated` audience. Public exceptions in `api.py`: health, sports, league search, user-by-UUID prefix, Socket.IO handshake; OPTIONS bypasses auth.
- Authorization is distributed across endpoint/model logic (e.g. `leagueModel.py:_ensure_commissioner`). Sample REST endpoints accept `userId`/`actingUserId` in request bodies; consistent binding to authenticated claims is **not established** by this orientation.
- `endpoints/draft/draftSocket.py` independently verifies connection tokens and checks JWT-subject league membership before joining draft rooms. No database RLS/policy definitions were found in `db/tables.sql`; deployed policies and DB-role privileges are unknown.

## Supabase and schema

Frontend SDK integration is in `front-end/src/lib/supabaseClient.ts`; backend connects directly to Postgres using SQLAlchemy, with psycopg2 for LISTEN. No Supabase CLI configuration, Edge Functions or Supabase Realtime subscription was found in the inspected paths.

Schema evidence: `db/tables.sql`, `db/README.md`. Main entities: User, Sport/School/SportTeam, SportSeason/SeasonPhase, Conference membership, League/LeagueMember/Week, DraftState/Turn/Pick, LeagueTeamSlot ownership intervals, transactions and game/weekly scores.

Present migrations: `api/migrations/20260803_create_sport_season_subdivision.sql` and `20260803_fix_sport_season_start_column.sql`. Both `db/README.md` and `api/startSeasonJobs/README.md` reference **absent** `20261023_basketball_tournament_rules.sql`; the snapshot already includes `SeasonPhase.rules`. Migration runner/history and live schema alignment are unknown.

## Jobs, realtime and integrations

- `api/worker/draftTimeoutWorker.py` runs separately, checks draft deadlines, processes expired picks and triggers PostgreSQL notifications.
- `endpoints/draft/notifyChannel.py` publishes `draft_updated`; `startDraftNotifyListener.py` starts a background LISTEN loop during app creation, loads snapshots and emits `draft:updated` to league rooms. `draftBroadcast.py` also supports socket broadcasts. Frontend `LeagueDraftPage.tsx` authenticates sockets, consumes snapshots/updates and maintains timed UI refreshes.
- `cronJobs/cronIngestScoreboard.py` ingests active-league games using Central dates, including yesterday before 03:00; weekly scoring and final scoreboard scripts handle period/season processing. Scheduler cadence and production worker supervision are not in the checkout.
- `startSeasonJobs/startSeason.py` bootstraps seasons from JSON manifests with resume checkpoints. `api/scripts/rebuild_weeks_and_rescore.py` is a database-writing maintenance tool, not a verification command.
- ESPN HTTP integrations: `endpoints/schedule/helpers/espn/espnClient.py` and `scripts/basketball-tiers/espn.ts`. The `helpers/ncaa/ncaaClient.py` adapter also describes ESPN-style URLs; actual provider selection is not fully traced. Supabase supplies hosted Auth/Postgres. No other external service was established in this pass.

## Deployment and environment names

`front-end/vercel.json` rewrites SPA routes to index.html, indicating Vercel support; deployed project settings are unknown. Backend launch configuration is `api/start.sh`/`wsgi.py`; no Dockerfile, backend hosting manifest or checked-in CI was found. CORS is configured separately for HTTP and sockets. `dev.py`, `wsgi.py`, `db.py` and job helpers use python-dotenv; production-style `start.sh` sources `.env`.

Names identified **only from source references**, without opening environment files or inspecting process values:

| Area | Names |
| --- | --- |
| Browser build | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL`, `VITE_SOCKET_URL` |
| Backend/database/auth | `SUPABASE_DB_URL`, `DATABASE_URL` (notification listener), `SUPABASE_PROJECT_ID`, `SUPABASE_JWT_SECRET` |
| Runtime/integrations/jobs | `CORS_ORIGINS`, `PORT`, `ESPN_BASE_URL`, `SEASON_CONFIG` (season manifest fallback) |

Environment files exist at `.env`, `api/.env`, `front-end/.env`; contents remain unread. Additional deployment-only variables, runtime versions, actual hosts, auth redirect/email settings, cron schedules, and secret provisioning remain unknown.
