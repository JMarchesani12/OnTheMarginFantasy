"""Run real refresh/finalization CLIs on owned synthetic PostgreSQL + HTTP only.

No dotenv, remote DSN, hosted jobs or command-line target overrides are accepted.
"""
import datetime as dt
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import tempfile
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg2

ROOT = Path(__file__).resolve().parents[3]
IMAGE = 'sha256:00bc86618629af00d2937fdc5a5d63db3ff8450acf52f0636ec813c7f4902929'
MIGRATIONS = ['20261030_game_kickoff_tbd.sql', '20261104_user_identity_unique.sql',
              '20261104_week_score_identity.sql', '20261104_ownership_integrity.sql',
              '20261117_seasonal_reference_integrity.sql','20261124_conference_standings.sql']


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, stderr=subprocess.PIPE).strip()


def require_local_docker(*, environ=None, inspect=docker):
    """Resolve Docker's context precedence and refuse nonlocal transports."""
    environ = os.environ if environ is None else environ
    context = environ.get('DOCKER_CONTEXT')
    if context:
        endpoint = inspect('context', 'inspect', context, '--format', '{{.Endpoints.docker.Host}}')
    elif environ.get('DOCKER_HOST'):
        endpoint = environ['DOCKER_HOST']
    else:
        context = inspect('context', 'show')
        endpoint = inspect('context', 'inspect', context, '--format', '{{.Endpoints.docker.Host}}')
    parsed = urlsplit(endpoint)
    if parsed.scheme != 'unix' or parsed.netloc or not parsed.path.startswith('/'):
        raise RuntimeError('Rehearsal requires a local Unix Docker endpoint')
    return endpoint


def main():
    require_local_docker()
    name = 'otm-job-rehearsal-' + uuid4().hex
    label = 'otm.task=maintenance-rehearsal-20261118'
    report = {'result': 'RUNNING', 'started_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'scope': 'Dedicated synthetic PostgreSQL and loopback provider fixture; exact production CLI files, no hosted operations',
              'image': IMAGE, 'checks': [], 'docker_transport': 'local Unix socket', 'python_debug': __debug__}
    files = [Path(__file__), ROOT/'api/tests/test_maintenance_job_isolation.py', ROOT/'db/baselines/20261029/001_schema.sql',
             *[ROOT/'api/migrations'/p for p in MIGRATIONS],
             *[ROOT/'api/cronJobs'/p for p in ('cronRefreshSchedules.py', 'cronComputeFinalScoreboard.py')],
             *[ROOT/'api'/p for p in ('runtime.py', 'db.py', 'operations.py')]]
    for directory in ('api/endpoints/scoring', 'api/endpoints/schedule', 'api/rules', 'api/utils'):
        files.extend((ROOT/directory).rglob('*.py'))
    report['sources'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}
    started = False
    conn = None
    server = None
    today = dt.datetime.now(ZoneInfo('America/Chicago')).date()
    fixture = {'fail': set(), 'announced': False, 'requests': []}

    class Provider(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            date = query.get('dates', [''])[0]
            fixture['requests'].append(date)
            if parsed.path != '/fixture/scoreboard' or query.get('groups') != ['50']:
                self.send_error(404)
                return
            if date in fixture['fail']:
                self.send_error(503)
                return
            day = dt.datetime.strptime(date, '%Y%m%d').date()
            hour = 20 if fixture['announced'] else 19
            event = {'id': 'synthetic-' + date, 'date': day.isoformat() + f'T{hour}:00:00Z',
                     'competitions': [{'timeValid': fixture['announced'], 'broadcast': 'Fixture',
                         'competitors': [{'homeAway': side, 'score': '0', 'team': {'id': external, 'displayName': side}}
                                         for side, external in [('home', '101'), ('away', '102')]]}]}
            body = json.dumps({'events': [event]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    try:
        docker('run', '--detach', '--rm', '--pull=never', '--name', name, '--label', label,
               '--env', 'POSTGRES_HOST_AUTH_METHOD=trust', '--env', 'POSTGRES_DB=' + name,
               '--publish', '127.0.0.1::5432', IMAGE)
        started = True
        port = int(docker('port', name, '5432/tcp').split(':')[-1])
        deadline = time.monotonic() + 30
        while True:
            try:
                conn = psycopg2.connect(host='127.0.0.1', port=port, user='postgres', dbname=name, connect_timeout=3)
                break
            except psycopg2.OperationalError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Owned fixture startup timeout') from None
                time.sleep(.2)
        conn.autocommit = True
        server = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        provider = 'http://127.0.0.1:' + str(server.server_port)
        env = {'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': '.', 'PYTHON_DOTENV_DISABLED': '1',
               'SUPABASE_DB_URL': f'postgresql+psycopg2://postgres@127.0.0.1:{port}/' + name,
               'ESPN_BASE_URL': provider, 'NO_PROXY': '127.0.0.1', 'PYTHONUNBUFFERED': '1'}

        def execute(statement, params=None):
            with conn.cursor() as c:
                c.execute(statement, params)
                return c.fetchall() if c.description else None

        def reset():
            if execute('SELECT current_database()') != [(name,)]:
                raise RuntimeError('Owned database identity mismatch')
            execute('DROP SCHEMA public CASCADE; DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA public; CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY); CREATE EXTENSION pg_trgm WITH SCHEMA public; CREATE EXTENSION btree_gist WITH SCHEMA public')
            execute((ROOT/'db/baselines/20261029/001_schema.sql').read_text())
            # Synthetic roles/column already present in the hosted platform,
            # but absent from the preserved 2026-10-29 schema fixture.
            execute('''DO $$ BEGIN
                IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon; END IF;
                IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated; END IF;
                IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role BYPASSRLS; END IF;
                END $$;
                ALTER TABLE "GameResult" ADD COLUMN "isCompleted" boolean;
                GRANT USAGE ON SCHEMA public TO anon,authenticated;''')
            for migration in MIGRATIONS:
                execute((ROOT/'api/migrations'/migration).read_text())
            execute('''INSERT INTO "User" (id,email) VALUES (1,'one@fixture.test'),(2,'two@fixture.test');
                INSERT INTO "Sport" (id,name,"api-keyword","apiGroupIds","maxDraftRounds") VALUES (1,'First','fixture','[50]',4),(2,'Other','fixture','[50]',4);
                INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") VALUES (1,1,2026,%s,%s),(2,2,2026,%s,%s);
                INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner,"seasonYear") VALUES (10,'One',1,1,'In-Season','{}',1,2026),(20,'Two',1,1,'In-Season','{}',2,2026),(30,'Other',2,1,'In-Season','{}',1,2026);
                INSERT INTO "LeagueMember" (id,"leagueId","userId","teamName","draftOrder") VALUES (11,10,1,'One',1),(21,20,2,'Two',1),(31,30,1,'Other',1);
                INSERT INTO "School" (id,name) VALUES (1,'Fixture');
                INSERT INTO "SportTeam" (id,"schoolId","sportId","displayName","externalId",tier) VALUES (101,1,1,'Home','101',1),(102,1,1,'Away','102',1);
                ''', (today-dt.timedelta(days=30), today+dt.timedelta(days=4), today-dt.timedelta(days=30), today-dt.timedelta(days=1)))
            fixture['requests'].clear()
            fixture['fail'].clear()
            fixture['announced'] = False

        def cli(job, args=(), expected=0):
            result = subprocess.run([sys.executable, 'cronJobs/' + job + '.py', *args], cwd=ROOT/'api', env=env,
                                    capture_output=True, text=True, timeout=45)
            assert result.returncode == expected, job + ' unexpected exit code ' + str(result.returncode)
            assert 'Traceback' not in result.stderr and 'synthetic-private-message' not in result.stdout + result.stderr
            events = [json.loads(line) for line in result.stderr.splitlines() if line.startswith('{')]
            assert events and len({event['runId'] for event in events}) == 1
            payload = json.loads(result.stdout) if result.stdout.strip() else None
            return payload

        refresh = 'cronRefreshSchedules'
        finalize = 'cronComputeFinalScoreboard'
        args = ['--days', '2', '--sport-season-id', '1']
        reset()
        cli(refresh, args)
        assert execute('SELECT count(*),bool_and("timeTBD") FROM "GameResult"') == [(2, True)]
        fixture['announced'] = True
        cli(refresh, args)
        assert execute('SELECT count(*),bool_or("timeTBD"),min(extract(hour from date AT TIME ZONE \'UTC\')) FROM "GameResult"') == [(2, False, 20)]
        assert len(fixture['requests']) == 4, 'Shared leagues caused repeated season fetches'
        report['checks'].append('Refresh: real HTTP/parser/upsert; shared-season dedup; kickoff announcement update; idempotent replay')
        reset()
        fixture['fail'].add(today.strftime('%Y%m%d'))
        cli(refresh, args, expected=1)
        assert len(fixture['requests']) == 2 and execute('SELECT count(*) FROM "GameResult"') == [(1,)]
        fixture['fail'].clear()
        cli(refresh, args)
        assert execute('SELECT count(*) FROM "GameResult"') == [(2,)]
        report['checks'].append('Refresh: provider failure exits 1, later day continues, successful retry converges')
        for job, key in [(refresh, 4), (finalize, 2)]:
            execute('SELECT pg_advisory_lock(1330924874,%s)', (key,))
            count = len(fixture['requests'])
            try:
                payload = cli(job, args if job == refresh else ())
                if job == finalize:
                    assert payload['outcome'] == 'already_running'
                assert len(fixture['requests']) == count
            finally:
                assert execute('SELECT pg_advisory_unlock(1330924874,%s)', (key,)) == [(True,)]
        report['checks'].append('Both real CLIs: a competing session lock skips all domain/provider work and exits 0')

        def final_fixture():
            reset()
            execute('''UPDATE "SportSeason" SET "seasonEnd"=%s;
                INSERT INTO "Week" (id,"leagueId","weekNumber","startDate","endDate","isLocked","scoringComplete") VALUES (100,10,1,%s,%s,true,true),(200,20,1,%s,%s,true,true),(300,30,1,%s,%s,true,true);
                INSERT INTO "WeeklyTeamScore" ("leagueId","weekId","memberId","pointsAwarded","pointDifferential",rank) VALUES (10,100,11,3,0,1),(20,200,21,2,0,1),(30,300,31,1,0,1)''',
                (today-dt.timedelta(days=1), *[x for _ in range(3) for x in (today-dt.timedelta(days=5),today-dt.timedelta(days=2))]))

        final_fixture()
        scores = execute('SELECT * FROM "WeeklyTeamScore" ORDER BY id')
        payload = cli(finalize)
        assert payload == {'finalized':[1,2], 'skipped':[], 'blocked':[], 'failures':[]}
        assert execute('SELECT status FROM "League" ORDER BY id') == [('Completed',)] * 3
        assert execute('SELECT * FROM "WeeklyTeamScore" ORDER BY id') == scores
        assert cli(finalize) == {'finalized':[], 'skipped':[], 'blocked':[], 'failures':[]}
        report['checks'].append('Finalization: real standings, all leagues completed per season, scores preserved, replay no-op')
        final_fixture()
        execute('UPDATE "Week" SET "scoringComplete"=false WHERE id=200')
        payload = cli(finalize, expected=1)
        assert payload['finalized'] == [2] and payload['blocked'] == [{'sportSeasonId':1,'leagueId':20,'reason':'weeks_not_ready'}]
        assert execute('SELECT status FROM "League" WHERE sport=1 ORDER BY id') == [('In-Season',)] * 2
        execute('UPDATE "Week" SET "scoringComplete"=true WHERE id=200')
        assert cli(finalize)['finalized'] == [1]
        report['checks'].append('Finalization: incomplete week blocks entire season, other season continues, repaired fixture retries')
        final_fixture()
        execute('''CREATE FUNCTION public.fixture_commit_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.sport=1 AND NEW.status='Completed' THEN RAISE EXCEPTION 'synthetic-private-message'; END IF; RETURN NEW; END $$;
            CREATE CONSTRAINT TRIGGER fixture_commit_failure AFTER UPDATE ON "League" DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fixture_commit_failure()''')
        payload = cli(finalize, expected=1)
        assert payload['finalized'] == [2] and len(payload['failures']) == 1 and payload['failures'][0]['sportSeasonId'] == 1
        assert execute('SELECT status FROM "League" WHERE sport=1 ORDER BY id') == [('In-Season',)] * 2
        assert execute('SELECT "seasonFinalized" FROM "SportSeason" WHERE id=1') == [(False,)]
        execute('DROP TRIGGER fixture_commit_failure ON "League"; DROP FUNCTION fixture_commit_failure()')
        assert cli(finalize)['finalized'] == [1]
        report['checks'].append('Finalization: deferred COMMIT failure rolls back whole season, other season continues, retry succeeds; logs sanitized')
        # Real PostgreSQL collection -> awards -> completion -> frozen reads.
        final_fixture()
        execute('''UPDATE "Sport" SET "api-keyword"='basketball/mens-college-basketball' WHERE id=1;
            INSERT INTO "Conference" (id,name) VALUES(1,'Fixture Conference'),(2,'Football Fixture');
            INSERT INTO "SportConference" (id,"conferenceId","sportId","maxTeamsPerOwner") VALUES(1,1,1,4),(2,2,2,4);
            INSERT INTO "SportTeam" (id,"schoolId","sportId","displayName","externalId",tier) VALUES(103,1,1,'Third','103',1),(201,1,2,'Football Home','201',1),(202,1,2,'Football Away','202',1);
            INSERT INTO "ConferenceMembership" ("sportTeamId","sportConferenceId","sportId","seasonYear") VALUES(101,1,1,2026),(102,1,1,2026),(103,1,1,2026),(201,2,2,2026),(202,2,2,2026);
            INSERT INTO "SportSeasonSubdivision" ("sportSeasonId",code,name,"regularSeasonStart","regularSeasonEnd") VALUES(1,'D1','Division I',%s,%s);
            INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia") VALUES(10,11,101,1,'DRAFT'),(30,31,201,1,'DRAFT');
            UPDATE "League" SET settings='{"bonuses":{"conferenceChampion":{"first":1.5}}}' WHERE id=10;
            UPDATE "League" SET settings='{"bonuses":{"farthestInPlayoffs":{"farthest":3}}}' WHERE id=30;
            INSERT INTO "TournamentDefinition" (id,"sportId",code,name,scope) VALUES(1,2,'FBS_PLAYOFFS','CFP','National');
            INSERT INTO "SeasonPhase" (id,"sportSeasonId","tournamentId",type,name,"endDate") VALUES(1,2,1,'NationalTournament','CFP',%s);
            INSERT INTO "GameResult" (sport,"sportSeasonId","seasonPhaseId","externalGameId",date,"isCompleted","homeTeamId","awayTeamId","homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName","roundOrder","bonusTournamentCode")
            VALUES(2,2,1,'cfp-final',%s,true,201,202,30,20,201,202,'Home','Away',4,'FBS_PLAYOFFS');''',
            (today-dt.timedelta(days=30),today-dt.timedelta(days=2),today-dt.timedelta(days=1),today-dt.timedelta(days=2)))
        execute('''INSERT INTO "SportTeam" (id,"schoolId","sportId","displayName","externalId",tier)
            SELECT team,1,2,'Football fixture',team::text,1 FROM generate_series(203,212) team;''')
        for index,(rnd,home,away) in enumerate([(1,205,212),(1,206,211),(1,207,210),(1,208,209),
            (2,201,208),(2,204,205),(2,202,207),(2,203,206),(3,201,204),(3,202,203)]):
            execute('''INSERT INTO "GameResult" (sport,"sportSeasonId","seasonPhaseId","externalGameId",date,"isCompleted","homeTeamId","awayTeamId","homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName","roundOrder","bonusTournamentCode")
                VALUES(2,2,1,%s,%s,true,%s,%s,30,20,%s,%s,'Home','Away',%s,'FBS_PLAYOFFS')''',
                ('cfp-'+str(index),today-dt.timedelta(days=3),home,away,home,away,rnd))
        sys.path.insert(0,str(ROOT/'api'))
        from sqlalchemy import create_engine
        from endpoints.scoring.standings_service import ConferenceStandingsService
        from endpoints.scoring.service import ScoringService
        from endpoints.schedule.read_service import ScheduleReadService
        class StandingsFixture:
            def fetch(self,keyword,year,group):
                return {'id':'50','season':{'year':year},'children':[{'id':'7','name':'Fixture Conference','isConference':True,
                    'standings':{'season':year,'seasonType':2,'entries':[
                        {'team':{'id':str(tid)},'stats':[{'type':'vsconf_playoffseed','value':rank},{'type':'vsconf','summary':record}]}
                        for tid,rank,record in [(101,1,'2-0'),(102,2,'1-1'),(103,3,'0-2')]]}}]}
        bonus_engine=create_engine(env['SUPABASE_DB_URL'])
        try:
            collection=ConferenceStandingsService(bonus_engine,StandingsFixture())
            assert collection.collect_for_job(1)['ready']==[1]
            assert execute('SELECT count(*) FROM "ConferenceStandingsSnapshot"')==[(0,)]
            for _ in range(2): assert collection.collect_for_job(1,apply=True)['ready']==[1]
            assert execute('SELECT count(*) FROM "ConferenceStandingsSnapshot"')==[(1,)]
            scoring=ScoringService(bonus_engine,ScheduleReadService(bonus_engine))
            assert scoring.get_season_standings_for_job(10)['members'][0]['totalPoints']==3
            assert scoring.get_season_standings_for_job(30)['members'][0]['bonusPoints']==0
            execute('SET ROLE authenticated')
            try:
                try: execute('SELECT * FROM "ConferenceStandingsSnapshot"')
                except psycopg2.errors.InsufficientPrivilege: pass
                else: raise AssertionError('Browser role can read backend standings')
            finally: execute('RESET ROLE')
            assert cli(finalize)['finalized']==[1,2]
            assert scoring.get_season_standings_for_job(30)['members'][0]['bonusPoints']==3
            assert scoring.get_season_standings_for_job(10)['members'][0]['bonusPoints']==1.5
            execute('UPDATE "WeeklyTeamScore" SET "pointsAwarded"=99 WHERE "memberId"=11')
            execute("""UPDATE "League" SET settings='{}' WHERE id=10""")
            assert scoring.get_season_standings_for_job(10)['members'][0]['totalPoints']==4.5
        finally:
            bonus_engine.dispose()
        report['checks'].append('Bonuses: actual PostgreSQL migration, preview, idempotent automatic collection, per-team conference and national awards, browser denial, finalization and stable frozen totals')
        report['result'] = 'PASS'
    except BaseException as error:
        report.update(result='FAILED', error_type=type(error).__name__)
        raise
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            report['provider_stopped'] = not thread.is_alive()
        if conn is not None:
            conn.close()
        if started:
            info = json.loads(docker('inspect', name))[0]
            assert info['Image'] == IMAGE and info['Config']['Labels']['otm.task'] == 'maintenance-rehearsal-20261118'
            docker('rm', '--force', name)
            report['container_removed'] = True
        report['completed_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        output = Path(tempfile.mkdtemp(prefix='otm-maintenance-test-'))/'result.json'
        output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'result':report['result'], 'checks':len(report['checks']), 'evidence':str(output)}))


if __name__ == '__main__':
    main()
