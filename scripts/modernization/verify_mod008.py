"""MOD-008 actual schema, bounded migrations and row-lock races; loopback only."""
import hashlib
import json
import threading
import time
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL, ROOT, engine_for
from endpoints.schedule.calendar_service import ScheduleCalendarService
from endpoints.scoring.service import ScoringService
from verify_schedule_calendar import tests as prior_calendar_tests
from verify_scoring_complete import remaining_tests as prior_scoring_tests

MIGRATION = ROOT / 'api/migrations/20261104_week_score_identity.sql'
PREFLIGHT = ROOT / 'db/preflights/20261104_week_score_identity.sql'


class ScheduleFacts:
    def get_member_games_for_week(self, league_id, member_id, week_number):
        return [{'memberPointDiff': {11: 5, 12: -2}[member_id]}]


def tests(engine, database):
    def query(statement, **params):
        with engine.begin() as conn:
            result = conn.execute(text(statement), params)
            return [dict(row) for row in result.mappings()] if result.returns_rows else []

    def execute_file(path, fetch=False):
        raw = engine.raw_connection()
        try:
            with raw.cursor() as cursor:
                source = path.read_text()
                cursor.execute(source.removesuffix('COMMIT;\n') if fetch else source)
                result = dict(zip([d.name for d in cursor.description], cursor.fetchone())) if fetch else None
            raw.commit()
            return result
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()

    def reset():
        with engine.begin() as conn:
            conn.exec_driver_sql('''DROP SCHEMA public CASCADE; CREATE SCHEMA public;
                DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA auth;
                CREATE TABLE auth.users(id uuid PRIMARY KEY); CREATE EXTENSION pg_trgm WITH SCHEMA public;''')
            conn.exec_driver_sql((ROOT / 'db/baselines/20261029/001_schema.sql').read_text())
            conn.exec_driver_sql((ROOT / 'api/migrations/20261030_game_kickoff_tbd.sql').read_text())
        execute_file(ROOT / 'api/migrations/20261104_user_identity_unique.sql')
        query('''INSERT INTO "User" (id,email) VALUES (1,'first@example.test'),(2,'second@example.test');
            INSERT INTO "Sport" (id,name) VALUES (2,'Football');
            INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd")
                VALUES (1,2,2025,'2025-11-02','2025-11-22');
            INSERT INTO "SportSeasonSubdivision" (id,"sportSeasonId",code,name,"regularSeasonStart","regularSeasonEnd")
                VALUES (1,1,'D1','Synthetic','2025-11-02','2025-11-22');
            INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner,"seasonYear") VALUES
                (10,'First',2,2,'Pre-Draft','{"timezone":"America/New_York"}',1,2025),
                (20,'Other',2,1,'Pre-Draft','{}',2,2025);
            INSERT INTO "LeagueMember" (id,"leagueId","userId","teamName","draftOrder") VALUES
                (11,10,1,'A',1),(12,10,2,'B',2),(21,20,2,'Other',1);''')

    def weeks():
        return query('SELECT * FROM "Week" ORDER BY id')

    def scores():
        return query('SELECT * FROM "WeeklyTeamScore" ORDER BY id')

    def seed_weeks():
        return ScheduleCalendarService(engine).ensure_weeks_for_job(10)

    def score_insert(league, week, member):
        query('''INSERT INTO "WeeklyTeamScore" ("leagueId","weekId","memberId","rank","pointsAwarded")
            VALUES (:league,:week,:member,1,1)''', league=league, week=week, member=member)

    def refuse_migration():
        before = (weeks(), scores())
        try:
            execute_file(MIGRATION)
        except psycopg2.Error as exc:
            assert 'reviewed remediation' in str(exc)
        else:
            raise AssertionError('Dirty historical state accepted')
        assert (weeks(), scores()) == before
        assert query("SELECT conname FROM pg_constraint WHERE conname='Week_league_week_number_key'") == []

    # Prove all preflight categories and migration atomic refusal separately.
    for dirty in ('week', 'score', 'week_league', 'member_league'):
        reset()
        original = seed_weeks()[0]['id']
        if dirty == 'week':
            query('''INSERT INTO "Week" ("leagueId","weekNumber") VALUES (10,0)''')
        elif dirty == 'score':
            score_insert(10, original, 11)
            score_insert(10, original, 11)
        elif dirty == 'week_league':
            score_insert(20, original, 21)
        else:
            score_insert(10, original, 21)
        counts = execute_file(PREFLIGHT, fetch=True)
        expected = {'week': 'duplicate_week_groups', 'score': 'duplicate_score_groups',
                    'week_league': 'wrong_week_league_scores', 'member_league': 'wrong_member_league_scores'}[dirty]
        assert counts[expected] == 1, counts
        refuse_migration()

    reset()
    execute_file(MIGRATION)
    execute_file(MIGRATION)
    assert all(value == 0 for key, value in execute_file(PREFLIGHT, fetch=True).items() if not key.startswith('total_'))
    created = seed_weeks()
    assert [row['weekNumber'] for row in created] == [0, 1, 2, 3]
    week = created[0]['id']
    score_insert(10, week, 11)
    # Verify each constraint family independently by its actual SQLSTATE.
    for statement, params, code in (
        ('INSERT INTO "Week" ("leagueId","weekNumber") VALUES (10,0)', {}, '23505'),
        ('INSERT INTO "WeeklyTeamScore" ("leagueId","weekId","memberId",rank,"pointsAwarded") VALUES (10,:week,11,1,1)', {'week': week}, '23505'),
        ('INSERT INTO "WeeklyTeamScore" ("leagueId","weekId","memberId",rank,"pointsAwarded") VALUES (20,:week,21,1,1)', {'week': week}, '23503'),
        ('INSERT INTO "WeeklyTeamScore" ("leagueId","weekId","memberId",rank,"pointsAwarded") VALUES (10,:week,21,1,1)', {'week': week}, '23503'),
    ):
        before = (weeks(), scores())
        try:
            query(statement, **params)
        except DBAPIError as exc:
            assert exc.orig.pgcode == code
        else:
            raise AssertionError('Direct invalid row accepted')
        assert (weeks(), scores()) == before
    query('DELETE FROM "LeagueMember" WHERE id=11')
    assert scores() == [], 'Same-league FK did not preserve member cascade'

    # Constraint replay must reject a same-named wrong natural key / FK action.
    for drift in ('natural', 'foreign'):
        reset()
        if drift == 'natural':
            query('ALTER TABLE "Week" ADD CONSTRAINT "Week_league_week_number_key" UNIQUE (id)')
        else:
            execute_file(MIGRATION)
            query('''ALTER TABLE "WeeklyTeamScore" DROP CONSTRAINT "WeeklyTeamScore_same_league_week_fkey";
                ALTER TABLE "WeeklyTeamScore" ADD CONSTRAINT "WeeklyTeamScore_same_league_week_fkey"
                FOREIGN KEY ("leagueId","weekId") REFERENCES "Week" ("leagueId",id) ON DELETE NO ACTION;''')
        before = (weeks(), scores())
        try:
            execute_file(MIGRATION)
        except psycopg2.Error as exc:
            assert 'unexpected definition' in str(exc)
        else:
            raise AssertionError('Drifted constraint accepted')
        assert (weeks(), scores()) == before

    # Whole initialization rollback includes week zero, then retry converges.
    for deferred in (False, True):
        reset()
        execute_file(MIGRATION)
        query('''CREATE FUNCTION fail_week() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW."weekNumber"=2 THEN RAISE EXCEPTION 'synthetic initialization failure'; END IF; RETURN NEW; END $$;''')
        query(('CREATE CONSTRAINT TRIGGER fail_week AFTER INSERT ON "Week" DEFERRABLE INITIALLY DEFERRED' if deferred else
               'CREATE TRIGGER fail_week BEFORE INSERT ON "Week"') + ' FOR EACH ROW EXECUTE FUNCTION fail_week()')
        try:
            seed_weeks()
        except DBAPIError:
            pass
        else:
            raise AssertionError('Injected initialization failure missing')
        assert weeks() == []
        query('DROP TRIGGER fail_week ON "Week"')
        assert [row['weekNumber'] for row in seed_weeks()] == [0, 1, 2, 3]

    races = []
    for operation, populated in (('ensure', False), ('score', False), ('score', True)):
        reset()
        execute_file(MIGRATION)
        if operation == 'score':
            seed_weeks()
            if populated:
                ScoringService(engine, ScheduleFacts()).compute_weekly_scores_for_job(10, 0)
        first, second = engine_for(database, 'mod008-first'), engine_for(database, 'mod008-second')
        locked, release = threading.Event(), threading.Event()
        outcomes = {}
        def hold(conn, cursor, statement, params, context, many):
            target = 'SELECT id FROM "League"' if operation == 'ensure' else 'SELECT id FROM "Week"'
            if target in statement and 'FOR UPDATE' in statement:
                locked.set()
                if not release.wait(10):
                    raise RuntimeError('Synthetic lock hold timeout')
        def run(label, owner):
            try:
                if operation == 'ensure':
                    result = ScheduleCalendarService(owner).ensure_weeks_for_job(10)
                    outcomes[label] = [(row['id'], row['weekNumber']) for row in result]
                else:
                    result = ScoringService(owner, ScheduleFacts()).compute_weekly_scores_for_job(10, 0)
                    outcomes[label] = [(row['memberId'], row['pointDifferential'], row['rank'], row['pointsAwarded']) for row in result['scores']]
            except Exception as exc:
                outcomes[label] = type(exc).__name__
        event.listen(first, 'after_cursor_execute', hold)
        a, b = threading.Thread(target=run, args=('first', first), daemon=True), threading.Thread(target=run, args=('second', second), daemon=True)
        a.start()
        try:
            assert locked.wait(5)
            b.start()
            blocked = False
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with engine.connect() as conn:
                    blocked = conn.execute(text('''SELECT EXISTS (SELECT 1 FROM pg_stat_activity
                        WHERE application_name='mod008-second' AND wait_event_type='Lock'
                        AND cardinality(pg_blocking_pids(pid))>0)''')).scalar_one()
                if blocked:
                    break
                time.sleep(.02)
            assert blocked, 'Competing operation did not wait on shared identity lock'
        finally:
            release.set()
            a.join(10)
            if b.ident is not None:
                b.join(10)
            event.remove(first, 'after_cursor_execute', hold)
            first.dispose()
            second.dispose()
        assert not a.is_alive() and not b.is_alive()
        assert isinstance(outcomes['first'], list) and outcomes['first'] == outcomes['second'], outcomes
        if operation == 'ensure':
            assert len(weeks()) == 4
        else:
            assert outcomes['first'] == [(11, 5, 1, 2), (12, -2, 2, 1)]
            assert [(row['memberId'], row['pointDifferential']) for row in scores()] == [(11, 5), (12, -2)]
        races.append({'operation': operation, 'preexisting_scores': populated, 'observed_lock_wait': True, 'converged': True})
    return {'dirty_aggregate_and_atomic_refusal': 'PASS', 'upgrade_replay_and_independent_keys_fks': 'PASS',
            'direct_unique_cross_league_and_cascade': 'PASS', 'whole_plan_statement_commit_rollback_retry': 'PASS', 'races': races}


def main():
    admin = psycopg2.connect(dbname='postgres', **LOCAL)
    admin.autocommit = True
    name = 'otm_mod008_' + uuid4().hex
    created, engine = False, None
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cursor.fetchone()[0] == 'otm-modernization-assessment-20261029-synthetic-only', 'Refusing unmarked server'
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            created = True
        engine = engine_for(name, 'mod008-owner')
        result = tests(engine, name)
        result['prior_calendar'] = prior_calendar_tests(engine)
        result['prior_scoring'] = prior_scoring_tests(engine, name)
        files = ['api/endpoints/schedule/calendar_service.py', 'api/endpoints/schedule/calendar_repository.py',
                 'api/endpoints/scoring/service.py', 'api/endpoints/scoring/repository.py',
                 'api/migrations/20261104_week_score_identity.sql', 'db/preflights/20261104_week_score_identity.sql',
                 'db/baselines/20261029/001_schema.sql', 'db/tables.sql', 'scripts/modernization/verify_mod008.py',
                 'scripts/modernization/verify_schedule_calendar.py', 'scripts/modernization/verify_scoring_complete.py']
        report = {'result': 'PASS', 'scope': 'Marked owned loopback PostgreSQL only; no hosted job/score generation',
                  'tests': result, 'sha256': {file: hashlib.sha256((ROOT / file).read_bytes()).hexdigest() for file in files}}
        (ROOT / 'docs/modernization/evidence/mod-008-postgres-2026-11-04.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()


if __name__ == '__main__':
    main()
