"""Native schedule calendar contracts; uniquely owned marked loopback database only."""
import datetime as dt
import hashlib
import json
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2 import sql
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL, ROOT, engine_for
from endpoints.schedule.calendar_service import ScheduleCalendarService
from endpoints.schedule.calendar_repository import ScheduleCalendarRepository
from endpoints.schedule.scheduleModel import ScheduleModel

FIXTURE = '''
DROP SCHEMA public CASCADE; CREATE SCHEMA public;
CREATE TABLE "League" (id bigint PRIMARY KEY,sport bigint,"seasonYear" integer,settings jsonb);
INSERT INTO "League" VALUES (10,1,2026,'{"timezone":"America/New_York"}');
CREATE TABLE "SportSeason" (id bigint PRIMARY KEY,"sportId" bigint,"seasonYear" integer,
 "seasonStart" date,"seasonEnd" date,"scheduleBootstrapped" boolean,"scheduleBootstrappedAt" timestamptz);
INSERT INTO "SportSeason" VALUES (1,1,2026,'2026-11-02','2026-11-22',false,NULL);
CREATE TABLE "SportSeasonSubdivision" (id bigint PRIMARY KEY,"sportSeasonId" bigint,code text,name text,
 "regularSeasonStart" date,"regularSeasonEnd" date,"postseasonStart" date,"postseasonEnd" date);
INSERT INTO "SportSeasonSubdivision" VALUES (11,1,'D1','Division One','2026-11-02','2026-11-22',NULL,NULL);
CREATE TABLE "Week" (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,"leagueId" bigint,"weekNumber" integer,
 "startDate" timestamptz,"endDate" timestamptz,"isLocked" boolean,"scoringComplete" boolean,
 UNIQUE ("leagueId","weekNumber"));
CREATE TABLE "SeasonPhase" (id bigint PRIMARY KEY,"sportSeasonId" bigint,"tournamentId" bigint,
 "startDate" timestamptz,"endDate" timestamptz,rules jsonb);
CREATE TABLE "TournamentDefinition" (id bigint PRIMARY KEY,"sportConferenceId" bigint);
'''


def tests(engine):
    covered=set()
    def observe(name, method):
        def wrapped(self, *args):
            covered.add(name)
            return method(self, *args)
        return wrapped
    observed=type('ObservedCalendarRepository',(ScheduleCalendarRepository,),{
        name:observe(name,method) for name,method in vars(ScheduleCalendarRepository).items()
        if callable(method) and not name.startswith('_')})
    service=ScheduleCalendarService(engine,observed())
    def query(statement, **params):
        with engine.begin() as conn:
            result=conn.execute(text(statement),params)
            return result.mappings().all() if result.returns_rows else []
    def reset():
        with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    def weeks():return query('SELECT * FROM "Week" ORDER BY "weekNumber"')
    def settings(value):query('UPDATE "League" SET settings=CAST(:settings AS jsonb)',settings=json.dumps(value))
    def football():
        query('UPDATE "League" SET sport=2');query('UPDATE "SportSeason" SET "sportId"=2')
    def expect(error, call, contains=None):
        try:call()
        except error as exc:
            if contains:assert contains in str(exc),(contains,str(exc))
        else:raise AssertionError('Expected '+error.__name__)
    reset();plan=service.boundaries_for_job(10);rows=service.ensure_weeks_for_job(10)
    assert [(r['weekNumber'],r['startDate'],r['endDate']) for r in rows]==plan
    assert [r['weekNumber'] for r in rows]==[1,2,3]
    assert rows[0]['startDate']==dt.datetime(2026,10,26,4,tzinfo=dt.timezone.utc)
    assert rows[1]['startDate']==dt.datetime(2026,11,9,5,tzinfo=dt.timezone.utc)
    assert all(not r['isLocked'] and not r['scoringComplete'] for r in weeks())
    before=weeks();assert len(service.ensure_weeks_for_job(10))==3 and weeks()==before
    query('DELETE FROM "SportSeason"');assert len(service.ensure_weeks_for_job(10))==3
    reset();football();assert service._get_week_start_weekday(10)==1
    rows=service.ensure_weeks_for_job(10);assert rows[0]['weekNumber']==0
    assert {'leagueId','isLocked','scoringComplete'}<=rows[0].keys() and not rows[0]['isLocked']
    reset();settings({'timeZone':'America/Chicago','schedule':{'timezone':'UTC','weekStartDay':' Friday '}})
    assert str(service.timezone_for_job(10))=='America/Chicago' and service._get_week_start_weekday(10)==4
    settings({'timezone':'Invalid/Zone','schedule':{'weekStartWeekday':6}})
    assert service.timezone_for_job(10)==dt.timezone.utc and service._get_week_start_weekday(10)==6
    settings({'schedule':{'weekStartDay':True}});expect(ValueError,lambda:service._get_week_start_weekday(10),'weekday name')
    reset();query('''INSERT INTO "SportSeasonSubdivision" VALUES
        (12,1,'D2','Division Two','2026-10-20','2026-12-01','2026-12-02','2026-12-08')''')
    season=service._get_sport_season_for_league(10)
    assert season['subdivisionCode']=='ALL' and season['regularSeasonStart']==dt.date(2026,10,20)
    assert season['regularSeasonEnd']==dt.date(2026,12,1) and season['postseasonEnd']==dt.date(2026,12,8)
    rows=service.ensure_weeks_for_job(10)
    assert rows[-1]['endDate'].astimezone(ZoneInfo('America/New_York')).date()==dt.date(2026,12,8)
    for previous,following in zip(rows,rows[1:]):assert previous['endDate']+dt.timedelta(microseconds=1)==following['startDate']
    settings({'subdivision':' d1 '});assert service._get_sport_season_for_league(10)['sportSeasonSubdivisionId']==11
    settings({'schedule':{'subdivision':'D2'}});assert service._get_sport_season_for_league(10)['subdivisionCode']=='D2'
    settings({'subdivision':'missing'});expect(ValueError,lambda:service._get_sport_season_for_league(10),'not configured')
    reset();query('INSERT INTO "TournamentDefinition" VALUES (1,9)')
    query('''INSERT INTO "SeasonPhase" VALUES (1,1,1,'2026-11-16T05:00Z','2026-12-01T05:00Z',
        '{"scoringPeriod":"BASKETBALL_FINAL","timezone":"America/New_York"}')''')
    assert service._get_season_phases(1)[0]['sportConferenceId']==9
    rows=service.ensure_weeks_for_job(10)
    assert rows[-1]['startDate']==dt.datetime(2026,11,16,5,tzinfo=dt.timezone.utc)
    assert rows[-1]['endDate']==dt.datetime(2026,12,1,4,59,59,999999,tzinfo=dt.timezone.utc)
    reset();expect(ValueError,lambda:service.timezone_for_job(999),'League 999 not found')
    query('DELETE FROM "SportSeasonSubdivision"');expect(ValueError,lambda:service._get_sport_season_for_league(10),'no subdivision windows')
    query('DELETE FROM "SportSeason"');expect(ValueError,lambda:service._get_sport_season_for_league(10),'No SportSeason')
    # Post-insert failures undo the entire numbered-week helper (not previously committed Week0).
    reset();football();triggered=[]
    def fail_second(conn,cursor,statement,params,context,many):
        if 'INSERT INTO "Week"' in statement and params.get('weekNumber')==2:
            triggered.append(True);raise RuntimeError('synthetic after-second-week failure')
    event.listen(engine,'after_cursor_execute',fail_second)
    try:expect(RuntimeError,lambda:service.ensure_weeks_for_job(10))
    finally:event.remove(engine,'after_cursor_execute',fail_second)
    assert triggered==[True] and [r['weekNumber'] for r in weeks()]==[0]
    for deferred in (False,True):
        reset()
        with engine.begin() as conn:
            conn.exec_driver_sql('''CREATE FUNCTION reject_week() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'synthetic week failure'; END $$;''')
            if deferred:conn.exec_driver_sql('CREATE CONSTRAINT TRIGGER reject_week AFTER INSERT ON "Week" DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reject_week()')
            else:conn.exec_driver_sql('CREATE TRIGGER reject_week BEFORE INSERT ON "Week" FOR EACH ROW EXECUTE FUNCTION reject_week()')
        expect(DBAPIError,lambda:service.ensure_weeks_for_job(10));assert weeks()==[]
    reset();legacy=ScheduleModel.__new__(ScheduleModel);legacy.db=engine
    assert len(legacy.ensure_weeks_for_league(10))==3
    assert str(legacy.get_league_timezone(10))=='America/New_York'
    declared={name for name,method in vars(ScheduleCalendarRepository).items() if callable(method) and not name.startswith('_')}
    assert covered==declared,{'missing_native_queries':sorted(declared-covered)}
    return {'json_dates_timezone_weekday_subdivision_and_missing_guards':'PASS',
        'basketball_opening_dst_persisted_plan_and_existing_week_reuse':'PASS',
        'football_week_zero_original_projection_and_defaults':'PASS',
        'all_subdivisions_continuous_postseason_and_phase_final_calendar_join':'PASS',
        'numbered_batch_rollback_preserves_prior_week_zero_commit':'PASS',
        'native_statement_deferred_commit_rollback':'PASS',
        'legacy_db_only_helpers_and_no_provider_client':'PASS',
        'repository_queries_exercised':sorted(covered),
        'scope_limit':'Calendar only; original helper transaction boundaries preserved. Remaining schedule reads, ingestion/bootstrap and composition are later slices.'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_schedule_calendar_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cursor.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-schedule-calendar');result=tests(engine)
        files=['api/endpoints/schedule/'+f for f in ('calendar_service.py','calendar_repository.py','scheduleModel.py','scheduleEndpoints.py','routes.py','helpers/weekHelper.py')]
        files+=['api/rules/tournamentRules.py','api/tests/test_schedule_calendar_service.py','scripts/modernization/verify_schedule_calendar.py']
        report={'result':'PASS','scope':'Marked owned synthetic loopback PostgreSQL; no configured DB/app/provider/jobs startup',
                'calendar':result,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-schedule-calendar-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cursor:cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
