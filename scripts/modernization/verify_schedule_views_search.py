"""Remaining schedule view/search SQL on marked, uniquely owned loopback DB."""
import hashlib
import json
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from sqlalchemy import event, text
from assess_postgres import LOCAL, ROOT, engine_for
from verify_schedule_member_reads import FIXTURE as MEMBER_FIXTURE, tests as member_tests, calendar_tests
from endpoints.schedule.read_service import ScheduleReadService
from endpoints.schedule.read_repository import ScheduleReadRepository
from endpoints.schedule.scheduleModel import ScheduleModel

FIXTURE = MEMBER_FIXTURE + '''
ALTER TABLE "GameResult" ADD COLUMN "roundOrder" integer DEFAULT 1;
UPDATE "GameResult" SET "roundOrder"=2 WHERE id=3;
DELETE FROM "GameResult" WHERE id=10;
CREATE TABLE "User" (id bigint PRIMARY KEY,"displayName" text);
INSERT INTO "User" VALUES (1,'Alice'),(2,'Bob');
CREATE TABLE "LeagueMember" (id bigint PRIMARY KEY,"leagueId" bigint,"userId" bigint,"teamName" text);
INSERT INTO "LeagueMember" VALUES (11,10,1,'Alice Team'),(12,10,2,'Bob Team');
UPDATE "SportTeam" SET "displayName"=CASE id WHEN 101 THEN 'Iowa State'
 WHEN 102 THEN 'Iowa State Cyclones' WHEN 103 THEN 'East Iowa State' WHEN 104 THEN 'Iowa Big State'
 ELSE "displayName" END;
'''


def tests(engine):
    covered=set()
    def observe(name, method):
        def wrapped(self,*args):
            covered.add(name)
            return method(self,*args)
        return wrapped
    observed=type('ObservedViewRepository',(ScheduleReadRepository,),{
        name:observe(name,method) for name,method in vars(ScheduleReadRepository).items()
        if callable(method) and not name.startswith('_')})
    service=ScheduleReadService(engine,observed())
    def query(statement, **params):
        with engine.begin() as conn:
            result=conn.execute(text(statement),params)
            return result.mappings().all() if result.returns_rows else []
    def reset():
        with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    def state():
        return {table:query(f'SELECT * FROM "{table}" ORDER BY 1') for table in
            ('League','Week','LeagueTeamSlot','SportTeam','GameResult')}
    def expect(error,call,contains=None):
        try:call()
        except error as exc:
            if contains:assert contains in str(exc),(contains,str(exc))
        else:raise AssertionError('Expected '+error.__name__)
    reset();before=state();games=service.conference_games_for_job(10,2,2026,501)
    assert [g['id'] for g in games]==[1,2,11,3,4,5,6]
    assert games[0]['homeOwnerMemberId']==11 and games[0]['homeOwnerTeamName']=='Alice Team'
    assert games[0]['homeOwnerDisplayName']=='Alice' and games[0]['awayOwnerDisplayName']=='Bob'
    assert games[0]['homeInConference'] is True and games[0]['awayInConference'] is True
    unowned=next(g for g in games if g['id']==11)
    assert unowned['homeInConference'] is True and unowned['awayInConference'] is False
    assert unowned['homeOwnerMemberId'] is None and unowned['awayOwnerMemberId'] is None
    assert next(g for g in games if g['id']==3)['roundOrder']==2
    assert set(games[0])=={'id','externalGameId','date','sport','sportSeasonId','seasonPhaseId','roundOrder',
        'homeTeamId','awayTeamId','broadcast','homeTeamName','awayTeamName','homeScore','awayScore',
        'homeOwnerMemberId','homeOwnerTeamName','homeOwnerDisplayName','awayOwnerMemberId','awayOwnerTeamName',
        'awayOwnerDisplayName','homeInConference','awayInConference'}
    assert service.conference_games_for_job(10,2,2024,501)==[]
    assert service.conference_games_for_job(10,2,2026,999)==[]
    expect(ValueError,lambda:service.conference_games_for_job(10,99,2026,501),'Week not found')
    assert state()==before
    query('UPDATE "Week" SET "startDate"=NULL')
    assert [g['id'] for g in service.conference_games_for_job(10,2,2026,501)]==[1,2,11,3,4,5,6]
    reset();games=service.team_games_for_job(101,2026)
    assert [g['id'] for g in games]==[8,1,2,3,4,5,6,7]
    assert all(g['ownerMemberId'] is None for g in games)
    assert games[2]['isHome'] is False and games[2]['opponentTeamId']==102 and games[2]['opponentTeamName']=='Beta'
    assert set(games[0])=={'id','externalGameId','date','sport','broadcast','sportSeasonId','seasonPhaseId','roundOrder',
        'homeTeamId','awayTeamId','homeTeamName','awayTeamName','homeScore','awayScore','isHome',
        'opponentTeamId','opponentTeamName','ownerMemberId','ownerTeamName','ownerDisplayName'}
    assert all(g['ownerMemberId'] is None for g in service.team_games_for_job(101,2026,999))
    assert service.team_games_for_job(999,2026)==[] and service.team_games_for_job(101,2024)==[]
    # Force a current week and a later future week: LATERAL must favor current over latest.
    query('UPDATE "Week" SET "startDate"=now()-interval \'1 day\',"endDate"=now()+interval \'1 day\'')
    query('''INSERT INTO "Week" ("leagueId","weekNumber","startDate","endDate")
        VALUES (10,3,now()+interval '10 days',now()+interval '20 days')''')
    assert all(g['ownerMemberId'] is None for g in service.team_games_for_job(104,2026,10))
    assert all(g['ownerMemberId']==11 for g in service.team_games_for_job(101,2026,10))
    results=service.search_teams_for_job(10,'iowa st')
    assert [r['teamId'] for r in results]==[101,102,103,104]
    assert results[0]=={'teamId':101,'teamName':'Iowa State','conferenceName':'Synthetic Conference',
        'ownerMemberId':11,'ownerTeamName':'Alice Team','ownerDisplayName':'Alice'}
    assert results[2]['ownerMemberId'] is None and results[3]['ownerMemberId'] is None
    # With no current week, latest3 applies; with no weeks999 applies.
    query('UPDATE "Week" SET "startDate"=now()-interval \'10 days\',"endDate"=now()-interval \'8 days\' WHERE "weekNumber"=2')
    assert service.team_games_for_job(104,2026,10)[0]['ownerMemberId']==11
    assert next(r for r in service.search_teams_for_job(10,'iowa st') if r['teamId']==104)['ownerMemberId']==11
    query('DELETE FROM "Week"')
    assert service.team_games_for_job(104,2026,10)[0]['ownerMemberId']==11
    assert next(r for r in service.search_teams_for_job(10,'iowa st') if r['teamId']==104)['ownerMemberId']==11
    # Search current-season/NULL joins retain duplicate rows when both memberships exist.
    query('INSERT INTO "SportConference" VALUES (502,1,402)');query('INSERT INTO "Conference" VALUES (402,\'Historic\')')
    query('INSERT INTO "ConferenceMembership" VALUES (101,1,2025,502)')
    assert service.search_teams_for_job(10,'iowa state')[0]['conferenceName']=='Synthetic Conference'
    query('INSERT INTO "ConferenceMembership" VALUES (101,1,NULL,501)')
    assert len([r for r in service.search_teams_for_job(10,'iowa state') if r['teamId']==101])==2
    reset()
    query('''INSERT INTO "SportTeam" SELECT 1000+i,1,'Iowa State Variant '||lpad(i::text,2,'0'),NULL
        FROM generate_series(0,59) AS i''')
    assert len(service.search_teams_for_job(10,'iowa st',100))==50
    assert len(service.search_teams_for_job(10,'iowa st',0))==20
    assert service.search_teams_for_job(10,'iowa st',-1)[0]['teamId']==101
    assert service.search_teams_for_job(999,'x')==[]
    expect(ValueError,lambda:service.search_teams_for_job(999,'iowa'),'League not found')
    expect(ValueError,lambda:service.search_teams_for_job(10,'',limit='invalid'))
    before=state();triggered=[]
    def fail(conn,cursor,statement,params,context,many):
        if 'LEFT JOIN LATERAL' in statement:triggered.append(True);raise RuntimeError('synthetic context read failure')
    event.listen(engine,'after_cursor_execute',fail)
    try:expect(RuntimeError,lambda:service.search_teams_for_job(10,'iowa'))
    finally:event.remove(engine,'after_cursor_execute',fail)
    assert triggered==[True] and state()==before
    legacy=ScheduleModel.__new__(ScheduleModel);legacy.db=engine
    assert legacy.search_teams_for_league(10,'iowa st',1)[0]['teamId']==101
    assert len(legacy.get_team_games_by_season(101,2026))==8
    expected={'week_window','conference_games','team_owner_context','team_season_games','search_league_context','search_teams'}
    assert covered==expected and expected <= vars(ScheduleReadRepository).keys()
    return {'conference_window_season_memberships_owners_flags_defaults_exact_projection':'PASS',
        'team_season_home_away_opponent_optional_missing_league_and_nullable_binds':'PASS',
        'native_lateral_current_before_latest_and_no_week_999_ownership':'PASS',
        'search_abbreviation_rank_limits_owners_sport_season_global_memberships':'PASS',
        'original_duplicate_rows_missing_guards_read_failure_no_writes_and_legacy':'PASS',
        'repository_queries_exercised':sorted(covered),
        'scope_limit':'Read views/search only; original SQL, context, duplicate, coercion and scope policies retained. Ingestion/bootstrap and final caller composition remain.'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_schedule_views_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cursor.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-schedule-views');calendar=calendar_tests(engine);member=member_tests(engine);views=tests(engine)
        declared={name for name,method in vars(ScheduleReadRepository).items() if callable(method) and not name.startswith('_')}
        assert set(member['repository_queries_exercised'])|set(views['repository_queries_exercised'])==declared
        files=['api/endpoints/schedule/'+f for f in ('read_service.py','read_repository.py','calendar_service.py','calendar_repository.py','scheduleModel.py','scheduleEndpoints.py','routes.py','helpers/weekHelper.py')]
        files+=['api/rules/leagueRules.py','api/rules/tournamentRules.py','api/tests/test_schedule_views_search_service.py']
        files+=['scripts/modernization/'+f for f in ('verify_schedule_calendar.py','verify_schedule_member_reads.py','verify_schedule_views_search.py')]
        report={'result':'PASS','scope':'Marked owned synthetic loopback PostgreSQL; no configured app/DB/provider/jobs startup',
            'views_search':views,'member_rerun':member,'calendar_rerun':calendar,'read_repository_coverage':str(len(declared))+'/10',
            'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-schedule-views-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cursor:cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
