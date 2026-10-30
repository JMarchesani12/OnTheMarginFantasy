"""Details/current-week and own-league SQL on marked synthetic PostgreSQL."""
import hashlib,json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from assess_postgres import LOCAL,ROOT,engine_for
from verify_league_discovery import listing_tests,creation_tests,approval_tests,profile_tests,removal_tests,deletion_tests,settings_tests,league_creation_tests,rules_tests,conference_tests,tests as discovery_tests
from actors import UserActor
from endpoints.league.league_read_service import LeagueReadService
from endpoints.league.leagueModel import LeagueModel

FIXTURE='''DROP SCHEMA public CASCADE; CREATE SCHEMA public;
CREATE TABLE "User" (id bigint PRIMARY KEY,"displayName" text); INSERT INTO "User" VALUES (1,'Alice'),(2,'Bob');
CREATE TABLE "Sport" (id bigint PRIMARY KEY,name text,"maxPlayersToHaveMaxRounds" integer); INSERT INTO "Sport" VALUES (1,'Basketball',8);
CREATE TABLE "League" (id bigint PRIMARY KEY,"createdAt" timestamptz DEFAULT now(),name text,"numPlayers" integer,
 status text,"updatedAt" timestamptz,"draftDate" timestamptz,"tradeDeadline" timestamptz,"freeAgentDeadline" timestamptz,
 "seasonYear" integer,settings jsonb,commissioner bigint,sport bigint);
INSERT INTO "League" (id,name,"numPlayers",status,"seasonYear",settings,commissioner,sport)
 VALUES (10,'Active',8,'In-Season',2026,'{}',1,1),(20,'Done',8,'Completed',2026,'{}',2,1),(30,'Commissioner only',8,'In-Season',2026,'{}',1,1);
CREATE TABLE "LeagueMember" (id bigint PRIMARY KEY,"leagueId" bigint,"userId" bigint,"teamName" text,"draftOrder" integer,"seasonPoints" integer);
INSERT INTO "LeagueMember" VALUES (11,10,1,'Alice Team',1,10),(12,10,2,'Bob Team',2,20),(21,20,2,'Bob Done',1,30);
CREATE TABLE "Week" (id bigint PRIMARY KEY,"leagueId" bigint,"weekNumber" integer,"startDate" timestamptz,"endDate" timestamptz);
INSERT INTO "Week" VALUES (100,10,-1,now()-interval '20 days',now()-interval '19 days'),
 (101,10,0,now()-interval '10 days',now()-interval '9 days'),
 (102,10,1,NULL,now()+interval '1 day'),(103,10,2,now()-interval '1 day',now()+interval '1 day'),
 (104,10,3,now()+interval '2 days',now()+interval '3 days');
CREATE TABLE "WeeklyTeamScore" ("leagueId" bigint,"memberId" bigint,"weekId" bigint,"pointsAwarded" integer);
INSERT INTO "WeeklyTeamScore" VALUES (10,12,100,999),(10,12,101,4),(10,12,102,6);'''


def tests(engine,database):
    with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    service=LeagueReadService(engine);bob=UserActor(2,'bob');calls=[]
    def sync():calls.append('sync')
    detail=service.details(bob,10,sync)
    assert detail['id']==10 and detail['currentWeekId']==103 and detail['currentWeekNumber']==2
    assert detail['currentWeekStartDate'] is not None and detail['settings']=={}
    assert service.details(UserActor(3,'outsider'),10,sync) is None
    assert service.details(bob,999,sync) is None
    assert service.details(UserActor(1,'alice'),30,sync)['currentWeekId'] is None
    rows=service.mine(bob,sync)
    assert len(rows)==3  # Original overlapping current-week rows remain duplicated.
    active=[r for r in rows if r['leagueId']==10]
    assert {r['currentWeekNumber'] for r in active}=={1,2} and all(r['seasonPoints']==10 for r in active)
    assert rows[-1]['leagueId']==20 and rows[-1]['seasonPoints']==30 and rows[-1]['currentWeekId'] is None
    assert set(rows[0])=={'leagueId','leagueCreatedAt','leagueName','numPlayers','status','updatedAt','draftDate',
        'tradeDeadline','freeAgentDeadline','seasonYear','settings','commissionerDisplayName','commissionerId','sport',
        'maxPlayersToHaveMaxRounds','memberId','teamName','draftOrder','seasonPoints','currentWeekId','currentWeekNumber','currentWeekStartDate','currentWeekEndDate'}
    assert len(service.mine(bob,sync,'ACTIVE'))==2
    assert [r['leagueId'] for r in service.mine(bob,sync,'completed')]==[20]
    assert service.mine(bob,sync,'unknown')==rows
    assert {r['leagueId'] for r in service.mine(UserActor(1,'alice'),sync)}=={10}
    assert service.mine(UserActor(3,'outsider'),sync)==[]
    other=engine_for(database,'otm-details-sync')
    try:
        def committed_sync():
            with other.begin() as conn:conn.execute(text('UPDATE "League" SET status=\'Post-Draft\' WHERE id=10'))
            calls.append('committed sync')
        assert service.details(bob,10,committed_sync)['status']=='Post-Draft'
        def revoke():
            with other.begin() as conn:conn.execute(text('DELETE FROM "LeagueMember" WHERE id=12'))
        assert service.details(bob,10,revoke) is None
        assert [r['leagueId'] for r in service.mine(bob,sync)]==[20]
        statements=[]
        def record(conn,cursor,statement,params,context,many):statements.append(statement)
        def fail():raise RuntimeError('synthetic sync failure')
        event.listen(engine,'before_cursor_execute',record)
        try:
            try:service.details(UserActor(1,'alice'),10,fail)
            except RuntimeError:pass
            else:raise AssertionError('Sync failure swallowed')
        finally:event.remove(engine,'before_cursor_execute',record)
        assert statements==[]
    finally:other.dispose()
    model=LeagueModel.__new__(LeagueModel);model.db=engine;model.sync_due_league_statuses=sync
    assert model.get_league(20)['id']==20 and model.get_league(20,reader_user_id=1) is None
    assert [r['leagueId'] for r in model.get_leagues_for_user(2)]==[20]
    return {'native_details_current_week_intervals_scope':'PASS','own_projection_stage_scores_overlap_compatibility':'PASS',
            'separate_committed_sync_and_membership_revocation':'PASS','sync_failure_before_read':'PASS','legacy_compatibility':'PASS',
            'scope_limit':'Existing lifecycle callback boundary verified; lifecycle algorithm unchanged'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_league_details_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-league-details')
        prior={'listing_cancellation':listing_tests(engine,name),'creation_denial':creation_tests(engine,name),
               'approval':approval_tests(engine,name),'member_profile':profile_tests(engine,name),'member_removal':removal_tests(engine,name),'league_deletion':deletion_tests(engine,name),'league_settings':settings_tests(engine,name),'league_creation':league_creation_tests(engine,name),'league_rules':rules_tests(engine,name),'league_conferences':conference_tests(engine,name),'league_discovery':discovery_tests(engine,name)}
        details=tests(engine,name)
        files=['api/endpoints/league/'+f for f in ('league_read_service.py','league_read_repository.py','league_admin_service.py','league_admin_repository.py','member_service.py','member_repository.py','admission_service.py','admission_repository.py','contracts.py','leagueModel.py','leagueEndpoints.py')]
        files+=['api/actors.py','api/rules/leagueRules.py','api/utils/authorization.py']+['scripts/modernization/'+f for f in ('verify_admission_slice.py','verify_admission_create_deny.py','verify_admission_approval.py','verify_member_profile.py','verify_member_removal.py','verify_league_delete.py','verify_league_settings.py','verify_league_creation.py','verify_league_rules_read.py','verify_league_conferences.py','verify_league_discovery.py','verify_league_details.py')]
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database','prior_slices_rerun':prior,
                'league_details':details,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-league-details-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
