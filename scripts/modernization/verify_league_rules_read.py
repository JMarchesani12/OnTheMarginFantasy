"""Rules read native projection/scope on marked synthetic PostgreSQL."""
import hashlib,json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from assess_postgres import LOCAL,ROOT,engine_for
from verify_league_creation import listing_tests,creation_tests,approval_tests,profile_tests,removal_tests,deletion_tests,settings_tests,tests as league_creation_tests
from actors import UserActor
from endpoints.league.reads.service import LeagueReadService
from endpoints.league.leagueModel import LeagueModel

FIXTURE='''DROP SCHEMA public CASCADE; CREATE SCHEMA public;
CREATE TABLE "League" (id bigint PRIMARY KEY,name text,sport bigint,"seasonYear" integer,settings jsonb,
    "tradeDeadline" timestamptz,"freeAgentDeadline" timestamptz,"draftDate" timestamptz,commissioner bigint,"isDiscoverable" boolean);
INSERT INTO "League" VALUES (10,'Open League',1,2026,'{"ruleSetVersion":"v1","timezone":"UTC"}',
    '2026-12-01T12:00:00Z',NULL,'2026-11-01T10:00:00Z',1,true),
    (20,'Private League',1,2026,'{}',NULL,NULL,NULL,2,false),
    (30,'Null Tier League',3,2026,'{}',NULL,NULL,NULL,1,false);
CREATE TABLE "LeagueMember" (id bigint PRIMARY KEY,"leagueId" bigint,"userId" bigint);
INSERT INTO "LeagueMember" VALUES (11,10,1),(12,10,2),(21,20,2);
CREATE TABLE "SportTeam" (id bigint PRIMARY KEY,"sportId" bigint,"displayName" text,tier integer);
INSERT INTO "SportTeam" VALUES (1,1,'Zulu',2),(2,1,'beta',1),(3,1,'Alpha',1),(4,1,'Untiered',NULL),
    (5,2,'Other Sport',9),(6,3,'Only Null',NULL);'''


def tests(engine,database):
    with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    service=LeagueReadService(engine);bob=UserActor(2,'bob')
    row=service.rules(bob,10)
    assert (row['leagueId'],row['leagueName'],row['seasonYear'],row['version'])==(10,'Open League',2026,'v1')
    assert [g['tier'] for g in row['tiers']]==[1,2,3]
    assert [t['teamName'] for t in row['tiers'][0]['teams']]==['Alpha','beta']
    assert row['tiers'][2]['teams']==[{'teamId':4,'teamName':'Untiered','tier':3}]
    assert row['settings']=={'timezone':'UTC','tradeDeadline':'2026-12-01T12:00:00+00:00',
                             'freeAgentDeadline':None,'draftDate':'2026-11-01T10:00:00+00:00'}
    assert row['tierAdjustment']['minimumTierGap']==2 and row['sportName']=='Basketball'
    assert service.rules(UserActor(1,'alice'),30)['tiers']==[{'tier':1,'teams':[{'teamId':6,'teamName':'Only Null','tier':1}]}]
    assert service.rules_for_job(20)['version']=='v1'
    for actor,league in ((UserActor(3,'outsider'),10),(UserActor(1,'alice'),20),(bob,999)):
        statements=[]
        def record(conn,cursor,statement,params,context,many):statements.append(statement)
        event.listen(engine,'after_cursor_execute',record)
        try:assert service.rules(actor,league) is None
        finally:event.remove(engine,'after_cursor_execute',record)
        assert len(statements)==1 and 'FROM "SportTeam"' not in statements[0]
    model=LeagueModel.__new__(LeagueModel);model.db=engine
    assert model.get_league_rules(20)['leagueId']==20 and model.get_league_rules(20,reader_user_id=1) is None
    assert model.get_league_rules(20,reader_user_id=2)['leagueId']==20
    revoked=[]
    for facade in (False,True):
        with engine.begin() as conn:conn.execute(text('INSERT INTO "LeagueMember" VALUES (12,10,2) ON CONFLICT (id) DO NOTHING'))
        other=engine_for(database,'otm-rules-revoke');changed=[];statements=[]
        def revoke(conn,cursor,statement,params,context,many):
            statements.append(statement)
            if 'SELECT id, name, sport,' in statement and not changed:
                changed.append(True)
                with other.begin() as separate:
                    separate.execute(text('DELETE FROM "LeagueMember" WHERE "leagueId"=10 AND "userId"=2'))
        event.listen(engine,'before_cursor_execute',revoke)
        try:
            result=model.get_league_rules(10,reader_user_id=2) if facade else service.rules(bob,10)
            assert result is None
        finally:event.remove(engine,'before_cursor_execute',revoke);other.dispose()
        assert changed==[True] and len(statements)==1
        revoked.append({'path':'legacy_facade' if facade else 'service','separate_connection_revocation_before_select':True,'result':None,'team_query_skipped':True})
    with engine.begin() as conn:conn.execute(text('UPDATE "League" SET settings=\'{"ruleSetVersion":"v2"}\'::jsonb WHERE id=10'))
    try:service.rules(UserActor(1,'alice'),10)
    except ValueError:pass
    else:raise AssertionError('Unsupported stored rules version accepted')
    return {'native_rules_projection_tiers_sport_isolation_deadlines':'PASS','denied_missing_skip_team_query':'PASS',
            'stored_version_and_trusted_legacy':'PASS','query_time_member_revocation':revoked,
            'scope_limit':'No post-SELECT final access recheck or stronger snapshot guarantee added'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_league_rules_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-league-rules')
        prior={'listing_cancellation':listing_tests(engine,name),'creation_denial':creation_tests(engine,name),
               'approval':approval_tests(engine,name),'member_profile':profile_tests(engine,name),'member_removal':removal_tests(engine,name),'league_deletion':deletion_tests(engine,name),'league_settings':settings_tests(engine,name),'league_creation':league_creation_tests(engine,name)}
        rules=tests(engine,name)
        files=['api/endpoints/league/'+f for f in ('reads/service.py','reads/repository.py','administration/service.py','administration/repository.py','members/service.py','members/repository.py','admission/service.py','admission/repository.py','admission/contracts.py','leagueModel.py','leagueEndpoints.py')]
        files+=['api/actors.py','api/rules/leagueRules.py','api/utils/authorization.py']+['scripts/modernization/'+f for f in ('verify_admission_slice.py','verify_admission_create_deny.py','verify_admission_approval.py','verify_member_profile.py','verify_member_removal.py','verify_league_delete.py','verify_league_settings.py','verify_league_creation.py','verify_league_rules_read.py')]
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database','prior_slices_rerun':prior,
                'league_rules':rules,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-league-rules-read-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
