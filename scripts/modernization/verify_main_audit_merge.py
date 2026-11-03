"""Merge checks on an owned, marked loopback DB. Never loads .env or providers."""
import hashlib
import json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import text
from assess_postgres import LOCAL, ROOT, engine_for
from verify_schedule_complete import tests as ingestion_tests, FIXTURE as SCHEDULE_FIXTURE, SyntheticProvider
from verify_schedule_views_search import tests as view_tests, member_tests, calendar_tests
from verify_league_lifecycle import tests as lifecycle_tests
from endpoints.league.lifecycle.service import LeagueLifecycleService
from endpoints.schedule.ingestion_service import ScheduleIngestionService
from endpoints.schedule.read_service import ScheduleReadService

MIGRATION = ROOT/'api/migrations/20261030_game_kickoff_tbd.sql'


def migration_tests(engine):
    baseline = ROOT/'db/baselines/20261029/001_schema.sql'
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY); CREATE EXTENSION pg_trgm;')
        conn.exec_driver_sql(baseline.read_text())
        conn.exec_driver_sql('''INSERT INTO "Sport" (id,name) VALUES (1,'Synthetic');
            INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd")
            VALUES (1,1,2026,'2026-01-01','2026-12-31');
            INSERT INTO "GameResult" (id,sport,"sportSeasonId","externalGameId",date,
            "homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName")
            VALUES (1,1,1,'synthetic','2026-11-01',0,0,11,12,'Home','Away');''')
        before = conn.execute(text('SELECT * FROM "GameResult"')).mappings().one()
        conn.exec_driver_sql(MIGRATION.read_text())
        after = dict(conn.execute(text('SELECT * FROM "GameResult"')).mappings().one())
        assert after.pop('timeTBD') is False and after == dict(before)
        conn.exec_driver_sql('UPDATE "GameResult" SET "timeTBD"=true WHERE id=1')
        conn.exec_driver_sql('UPDATE "GameResult" SET date=(SELECT date FROM "GameResult" WHERE id=1) WHERE id=2')
        conn.exec_driver_sql(MIGRATION.read_text())
        assert conn.execute(text('SELECT "timeTBD" FROM "GameResult" WHERE id=1')).scalar() is True
        metadata = conn.execute(text('''SELECT data_type,is_nullable,column_default FROM information_schema.columns
            WHERE table_schema='public' AND table_name='GameResult' AND column_name='timeTBD' ''')).one()
        assert tuple(metadata) == ('boolean','NO','false')
    return {'frozen_schema_plus_main_migration':'PASS','existing_rows_preserved_false_default':'PASS',
            'replay_preserves_existing_true':'PASS','column_boolean_not_null_default_false':'PASS'}


def kickoff_tests(engine):
    with engine.begin() as conn:
        conn.exec_driver_sql(SCHEDULE_FIXTURE)
        conn.exec_driver_sql('UPDATE "GameResult" SET "timeTBD"=true WHERE id=1')
        conn.exec_driver_sql('UPDATE "GameResult" SET date=(SELECT date FROM "GameResult" WHERE id=1) WHERE id=2')
    reads = ScheduleReadService(engine)
    projections = [reads.member_games_for_job(10,11,2), reads.head_to_head_for_job(10,11,12,2),
        reads.conference_games_for_job(10,2,2026,501), reads.team_games_for_job(101,2026)]
    for games in projections:
        ids = [game['id'] for game in games]
        assert ids.index(1) < ids.index(2), 'Kickoff flag must not change equal-date ordering'
        assert next(game for game in games if game['id']==1)['timeTBD'] is True
        assert next(game for game in games if game['id']==2)['timeTBD'] is False
    provider = SyntheticProvider('https://synthetic.invalid','basketball')
    event = provider.payload('20261103','kickoff-transition')['events'][0]
    event['competitions'][0]['timeValid'] = False
    ingestion = ScheduleIngestionService(engine,'https://synthetic.invalid')
    game_id = ingestion._insert_or_update_game(1,1,provider.extract_game_from_event(event))
    with engine.connect() as conn:
        assert conn.execute(text('SELECT "timeTBD" FROM "GameResult" WHERE id=:id'),{'id':game_id}).scalar() is True
    event['competitions'][0]['timeValid'] = True
    assert ingestion._insert_or_update_game(1,1,provider.extract_game_from_event(event)) == game_id
    with engine.connect() as conn:
        assert conn.execute(text('SELECT "timeTBD" FROM "GameResult" WHERE id=:id'),{'id':game_id}).scalar() is False
    return {'all_four_read_projections_true_and_false':'PASS','actual_parser_upsert_tbd_to_confirmed_same_id':'PASS'}


def timezone_tests(engine):
    with engine.begin() as conn:
        conn.exec_driver_sql('''DROP SCHEMA public CASCADE; CREATE SCHEMA public;
            CREATE TABLE "League"(id bigint,status text,"updatedAt" timestamptz,"draftDate" timestamptz,
                sport bigint,"seasonYear" integer,settings jsonb);
            CREATE TABLE "DraftState"("leagueId" bigint,status text);
            CREATE TABLE "SportSeason"("sportId" bigint,"seasonYear" integer,"seasonStart" date,"seasonEnd" date);''')
        utc_day, local_day, zone = conn.execute(text('''SELECT
            (now() AT TIME ZONE 'UTC')::date,
            (now() AT TIME ZONE (CASE WHEN extract(hour FROM now() AT TIME ZONE 'UTC')<12
                THEN 'Etc/GMT+12' ELSE 'Pacific/Kiritimati' END))::date,
            CASE WHEN extract(hour FROM now() AT TIME ZONE 'UTC')<12
                THEN 'Etc/GMT+12' ELSE 'Pacific/Kiritimati' END''')).one()
        assert utc_day != local_day
        start = max(utc_day,local_day)
        conn.execute(text('''INSERT INTO "SportSeason" VALUES (1,2026,:start, :start + interval '10 days')'''),{'start':start})
        settings = [{'schedule':{'timezone':zone}},{'schedule':{'timeZone':zone}},
                    {'timezone':zone},{'timeZone':zone},{}]
        for i, config in enumerate(settings,1):
            conn.execute(text('''INSERT INTO "League" VALUES (:id,'Post-Draft',now(),NULL,1,2026,CAST(:settings AS jsonb));'''),
                         {'id':i,'settings':json.dumps(config)})
            conn.execute(text('INSERT INTO "DraftState" VALUES (:id,\'complete\')'),{'id':i})
    LeagueLifecycleService(engine).synchronize_for_job()
    with engine.connect() as conn:
        result = dict(conn.execute(text('SELECT id,status FROM "League" ORDER BY id')).all())
    expected_local = 'Post-Draft' if local_day < start else 'In-Season'
    expected_utc = 'Post-Draft' if utc_day < start else 'In-Season'
    assert expected_local != expected_utc
    assert result == {1:expected_local,2:expected_local,3:expected_local,4:expected_local,5:expected_utc},result
    return {'four_timezone_setting_paths_and_utc_fallback_across_day_boundary':'PASS'}


def main():
    admin = psycopg2.connect(dbname='postgres', **LOCAL)
    admin.autocommit = True
    name = 'otm_main_audit_merge_'+uuid4().hex
    engine = None
    created = False
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0] == 'otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            created = True
        engine = engine_for(name,'otm-main-audit-merge')
        report = {'migration':migration_tests(engine),'calendar':calendar_tests(engine),
            'schedule_members':member_tests(engine),'schedule_views':view_tests(engine),
            'ingestion':ingestion_tests(engine),'kickoff':kickoff_tests(engine),
            'lifecycle':lifecycle_tests(engine,name),
            'timezone_boundary':timezone_tests(engine)}
        files = ['api/endpoints/league/lifecycle/repository.py','api/endpoints/schedule/ingestion_repository.py',
            'api/endpoints/schedule/ingestion_service.py','api/endpoints/schedule/read_repository.py',
            'api/endpoints/schedule/helpers/espn/espnClient.py','api/cronJobs/cronRefreshSchedules.py',
            'api/migrations/20261030_game_kickoff_tbd.sql','db/tables.sql',
            'scripts/modernization/verify_main_audit_merge.py']
        report.update(result='PASS',scope='Owned marked local PostgreSQL; synthetic rows/providers only',
            sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files})
        (ROOT/'docs/modernization/evidence/main-audit-merge-2026-11-02.json').write_text(json.dumps(report,indent=2)+'\n')
        print('PASS: migration, schedule read/ingestion, lifecycle and timezone boundary checks')
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()


if __name__ == '__main__':
    main()
