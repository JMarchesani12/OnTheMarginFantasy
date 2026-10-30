"""Member/current-week SQL and supplied game summaries on marked PostgreSQL."""
import datetime as dt
import hashlib,json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from assess_postgres import LOCAL,ROOT,engine_for
from verify_league_details import listing_tests,creation_tests,approval_tests,profile_tests,removal_tests,deletion_tests,settings_tests,league_creation_tests,rules_tests,conference_tests,discovery_tests,tests as detail_tests
from actors import UserActor
from endpoints.league.league_read_service import LeagueReadService
from endpoints.league.leagueModel import LeagueModel
from endpoints.schedule.scheduleModel import ScheduleModel

FIXTURE='''DROP SCHEMA public CASCADE; CREATE SCHEMA public;
CREATE TABLE "User" (id bigint PRIMARY KEY,"displayName" text); INSERT INTO "User" VALUES (1,'Alice'),(2,'Bob');
CREATE TABLE "League" (id bigint PRIMARY KEY,sport bigint,"seasonYear" integer,settings jsonb,commissioner bigint);
INSERT INTO "League" VALUES (10,1,2026,'{"timezone":"America/Chicago"}',1);
CREATE TABLE "LeagueMember" (id bigint PRIMARY KEY,"createdAt" timestamptz DEFAULT now(),"leagueId" bigint,"userId" bigint,
    "teamName" text,"draftOrder" integer,"seasonPoints" integer);
INSERT INTO "LeagueMember" (id,"leagueId","userId","teamName","draftOrder","seasonPoints") VALUES (11,10,1,'Alice',1,10),(12,10,2,'Bob',2,20);
CREATE TABLE "Week" (id bigint PRIMARY KEY,"leagueId" bigint,"weekNumber" integer,"startDate" timestamptz,"endDate" timestamptz);
INSERT INTO "Week" VALUES (1,10,-1,now()-interval '20 days',now()-interval '19 days'),
    (2,10,0,current_date-interval '1 day'+interval '12 hours',current_date+interval '1 day'+interval '23 hours');
CREATE TABLE "WeeklyTeamScore" ("leagueId" bigint,"memberId" bigint,"weekId" bigint,"pointsAwarded" integer);
INSERT INTO "WeeklyTeamScore" VALUES (10,12,1,999),(10,12,2,6);'''


def tests(engine,database):
    with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    with engine.connect() as conn:today=conn.execute(text('SELECT current_date')).scalar_one()
    service=LeagueReadService(engine);schedule=ScheduleModel.__new__(ScheduleModel);schedule.db=engine;calls=[]
    def games(**kwargs):
        calls.append(kwargs);assert kwargs['week_number']==0
        if kwargs['member_id']!=12:return []
        return [{'memberPointDiff':5,'date':dt.datetime.combine(today,dt.time(2),dt.timezone.utc)},
                {'memberPointDiff':-3,'date':dt.datetime.combine(today,dt.time(12)).isoformat()},
                {'memberPointDiff':4,'date':dt.datetime.combine(today,dt.time(15),dt.timezone.utc)},
                {'memberPointDiff':2,'date':None},
                {'memberPointDiff':7,'date':dt.datetime.combine(today+dt.timedelta(days=5),dt.time(12),dt.timezone.utc)}]
    bob=UserActor(2,'bob')
    rows=service.members(bob,10,schedule.get_league_timezone,games)
    assert [r['id'] for r in rows]==[11,12] and [r['seasonPoints'] for r in rows]==[10,6]
    assert rows[1]['currentWeekPointDifferential']==15
    assert rows[1]['dailyPointDifferentials']==[
        {'date':(today-dt.timedelta(days=1)).isoformat(),'pointDifferential':5},
        {'date':today.isoformat(),'pointDifferential':1},
        {'date':(today+dt.timedelta(days=1)).isoformat(),'pointDifferential':0}]
    assert set(rows[0])=={'id','createdAt','leagueId','userId','teamName','draftOrder','seasonPoints','displayName','currentWeekPointDifferential','dailyPointDifferentials'}
    assert rows[0]['createdAt'] is not None and len(calls)==2
    def fail_games(**kwargs):raise RuntimeError('synthetic game capability failure')
    try:service.members(bob,10,schedule.get_league_timezone,fail_games)
    except RuntimeError:pass
    else:raise AssertionError('Game capability error swallowed')
    with engine.begin() as conn:conn.execute(text('UPDATE "Week" SET "startDate"=NULL WHERE id=2'))
    row=service.members(bob,10,schedule.get_league_timezone,games)[1]
    assert row['currentWeekPointDifferential']==15 and row['dailyPointDifferentials']==[]
    with engine.begin() as conn:conn.execute(text('DELETE FROM "Week"'))
    calls.clear();rows=service.members(bob,10,schedule.get_league_timezone,games)
    assert all(r['currentWeekPointDifferential']==0 and r['dailyPointDifferentials']==[] for r in rows) and calls==[]
    other=engine_for(database,'otm-member-summary-revoke');changed=[]
    def revoke(conn,cursor,statement,params,context,many):
        if 'AS "memberId"' in statement and 'FROM "LeagueMember"' in statement and not changed:
            changed.append(True)
            with other.begin() as separate:separate.execute(text('DELETE FROM "LeagueMember" WHERE id=12'))
    event.listen(engine,'before_cursor_execute',revoke)
    try:assert service.members(bob,10,schedule.get_league_timezone,games)==[]
    finally:event.remove(engine,'before_cursor_execute',revoke);other.dispose()
    assert changed==[True] and calls==[]
    model=LeagueModel.__new__(LeagueModel);model.db=engine;model.scheduleModel=schedule
    assert len(model.get_members_for_league(10))==1
    assert model.get_members_for_league(10,reader_user_id=2)==[]
    return {'native_projection_score_fallback_week_zero':'PASS','local_dates_naive_aware_undated_out_of_range_zero_fill':'PASS',
            'null_start_and_no_week_compatibility':'PASS','game_capability_error_and_public_timezone':'PASS',
            'separate_connection_pre_query_revocation_legacy':'PASS',
            'scope_limit':'Scheduling game algorithm unchanged; supplied game facts verify summary orchestration'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_member_summary_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-member-summary')
        prior={'listing_cancellation':listing_tests(engine,name),'creation_denial':creation_tests(engine,name),
               'approval':approval_tests(engine,name),'member_profile':profile_tests(engine,name),'member_removal':removal_tests(engine,name),'league_deletion':deletion_tests(engine,name),'league_settings':settings_tests(engine,name),'league_creation':league_creation_tests(engine,name),'league_rules':rules_tests(engine,name),'league_conferences':conference_tests(engine,name),'league_discovery':discovery_tests(engine,name),'league_details':detail_tests(engine,name)}
        summary=tests(engine,name)
        files=['api/endpoints/league/'+f for f in ('league_read_service.py','league_read_repository.py','league_admin_service.py','league_admin_repository.py','member_service.py','member_repository.py','admission_service.py','admission_repository.py','contracts.py','leagueModel.py','leagueEndpoints.py')]
        files+=['api/endpoints/schedule/scheduleModel.py','api/actors.py','api/rules/leagueRules.py','api/utils/authorization.py']+['scripts/modernization/'+f for f in ('verify_admission_slice.py','verify_admission_create_deny.py','verify_admission_approval.py','verify_member_profile.py','verify_member_removal.py','verify_league_delete.py','verify_league_settings.py','verify_league_creation.py','verify_league_rules_read.py','verify_league_conferences.py','verify_league_discovery.py','verify_league_details.py','verify_member_summary.py')]
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database','prior_slices_rerun':prior,
                'member_summary':summary,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-member-summary-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
