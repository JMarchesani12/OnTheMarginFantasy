"""Conference scope/season aggregates on marked synthetic PostgreSQL."""
import hashlib,json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from assess_postgres import LOCAL,ROOT,engine_for
from verify_league_rules_read import listing_tests,creation_tests,approval_tests,profile_tests,removal_tests,deletion_tests,settings_tests,league_creation_tests,tests as rules_tests
from actors import UserActor
from endpoints.league.league_read_service import LeagueReadService
from endpoints.league.leagueModel import LeagueModel

FIXTURE='''DROP SCHEMA public CASCADE; CREATE SCHEMA public;
CREATE TABLE "League" (id bigint PRIMARY KEY,sport bigint,"seasonYear" integer,commissioner bigint,"isDiscoverable" boolean);
INSERT INTO "League" VALUES (10,1,2026,1,true),(20,1,2026,2,false),(30,3,2026,2,false),(40,1,NULL,1,false);
CREATE TABLE "LeagueMember" (id bigint PRIMARY KEY,"leagueId" bigint,"userId" bigint);
INSERT INTO "LeagueMember" VALUES (11,10,1),(12,10,2);
CREATE TABLE "Conference" (id bigint PRIMARY KEY,name text);
INSERT INTO "Conference" VALUES (1,'Zulu'),(2,'Alpha'),(3,'Other Sport');
CREATE TABLE "SportConference" (id bigint PRIMARY KEY,"conferenceId" bigint,"sportId" bigint,"maxTeamsPerOwner" integer);
INSERT INTO "SportConference" VALUES (1,1,1,2),(2,2,1,1),(3,3,2,5);
CREATE TABLE "ConferenceMembership" ("sportConferenceId" bigint,"seasonYear" integer);
INSERT INTO "ConferenceMembership" VALUES (1,NULL),(1,2026),(1,2025),(2,2025),(3,NULL);'''


def tests(engine,database):
    with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    service=LeagueReadService(engine);bob=UserActor(2,'bob')
    assert service.conferences(bob,10)=={'leagueId':10,'sportId':1,'seasonYear':2026,'conferences':[
        {'sportConferenceId':2,'conferenceId':2,'displayName':'Alpha','maxTeamsPerOwner':1,'teamsInConference':0},
        {'sportConferenceId':1,'conferenceId':1,'displayName':'Zulu','maxTeamsPerOwner':2,'teamsInConference':2}]}
    for who,league in ((UserActor(3,'outsider'),10),(UserActor(1,'alice'),20),(bob,999),(UserActor(1,'alice'),40)):
        statements=[]
        def record(conn,cursor,statement,params,context,many):statements.append(statement)
        event.listen(engine,'after_cursor_execute',record)
        try:
            try:service.conferences(who,league)
            except ValueError:pass
            else:raise AssertionError('Conference scope/missing-season guard bypass')
        finally:event.remove(engine,'after_cursor_execute',record)
        assert len(statements)==1 and 'FROM "SportConference"' not in statements[0]
    model=LeagueModel.__new__(LeagueModel);model.db=engine
    assert service.conferences_for_job(30)=={'leagueId':30,'sportId':3,'seasonYear':2026,'conferences':[]}
    assert model.get_league_conferences(30)['conferences']==[]
    assert model.get_league_conferences(30,reader_user_id=2)['conferences']==[]
    try:model.get_league_conferences(30,reader_user_id=1)
    except ValueError:pass
    else:raise AssertionError('Legacy scoped conference read bypass')
    revoked=[]
    for facade in (False,True):
        with engine.begin() as conn:conn.execute(text('INSERT INTO "LeagueMember" VALUES (12,10,2) ON CONFLICT (id) DO NOTHING'))
        other=engine_for(database,'otm-conferences-revoke');changed=[];statements=[]
        def revoke(conn,cursor,statement,params,context,many):
            statements.append(statement)
            if 'id AS "leagueId"' in statement and not changed:
                changed.append(True)
                with other.begin() as separate:separate.execute(text('DELETE FROM "LeagueMember" WHERE id=12'))
        event.listen(engine,'before_cursor_execute',revoke)
        try:
            try:
                if facade:model.get_league_conferences(10,reader_user_id=2)
                else:service.conferences(bob,10)
            except ValueError as exc:assert str(exc)=='League 10 not found'
            else:raise AssertionError('Late conference scope loss did not reject')
        finally:event.remove(engine,'before_cursor_execute',revoke);other.dispose()
        assert changed==[True] and len(statements)==1
        revoked.append({'path':'legacy_facade' if facade else 'service','separate_connection_revocation_before_select':True,
                        'result':'ValueError','aggregate_query_skipped':True})
    return {'native_projection_season_null_counts_zero_order_sport_isolation':'PASS',
            'denied_missing_null_season_skip_aggregate':'PASS','empty_trusted_legacy':'PASS','query_time_member_revocation':revoked}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_league_conferences_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-league-conferences')
        prior={'listing_cancellation':listing_tests(engine,name),'creation_denial':creation_tests(engine,name),
               'approval':approval_tests(engine,name),'member_profile':profile_tests(engine,name),'member_removal':removal_tests(engine,name),'league_deletion':deletion_tests(engine,name),'league_settings':settings_tests(engine,name),'league_creation':league_creation_tests(engine,name),'league_rules':rules_tests(engine,name)}
        conferences=tests(engine,name)
        files=['api/endpoints/league/'+f for f in ('league_read_service.py','league_read_repository.py','league_admin_service.py','league_admin_repository.py','member_service.py','member_repository.py','admission_service.py','admission_repository.py','contracts.py','leagueModel.py','leagueEndpoints.py')]
        files+=['api/actors.py','api/rules/leagueRules.py','api/utils/authorization.py']+['scripts/modernization/'+f for f in ('verify_admission_slice.py','verify_admission_create_deny.py','verify_admission_approval.py','verify_member_profile.py','verify_member_removal.py','verify_league_delete.py','verify_league_settings.py','verify_league_creation.py','verify_league_rules_read.py','verify_league_conferences.py')]
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database','prior_slices_rerun':prior,
                'league_conferences':conferences,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-league-conferences-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
