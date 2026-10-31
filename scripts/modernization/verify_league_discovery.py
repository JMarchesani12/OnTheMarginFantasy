"""Discovery visibility and real pg_trgm search on marked synthetic PostgreSQL."""
import hashlib,json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from assess_postgres import LOCAL,ROOT,engine_for
from verify_league_conferences import listing_tests,creation_tests,approval_tests,profile_tests,removal_tests,deletion_tests,settings_tests,league_creation_tests,rules_tests,tests as conference_tests
from actors import UserActor
from endpoints.league.reads.service import LeagueReadService
from endpoints.league.leagueModel import LeagueModel

FIXTURE='''DROP SCHEMA public CASCADE; CREATE SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE "User" (id bigint PRIMARY KEY,"displayName" text,email text);
INSERT INTO "User" VALUES (1,'Alice','private-alice@example.test'),(2,'Bob','private-bob@example.test'),(3,'Outsider','private-other@example.test');
CREATE TABLE "League" (id bigint PRIMARY KEY,name text,sport bigint,"numPlayers" integer,status text,"draftDate" timestamptz,
    "isDiscoverable" boolean,commissioner bigint);
INSERT INTO "League" VALUES (10,'Margin',1,8,'Pre-Draft',NULL,true,1),(11,'Margin AA',1,8,'Pre-Draft',NULL,true,1),
    (12,'Margin BB',1,8,'Pre-Draft',NULL,true,1),(13,'Margin Hidden',1,8,'Pre-Draft',NULL,false,1),
    (14,'Margin Football',2,10,'Pre-Draft',NULL,true,1),(15,'O''Brien',1,8,'Pre-Draft',NULL,true,1);
CREATE TABLE "LeagueMember" (id bigint PRIMARY KEY,"leagueId" bigint,"userId" bigint,"teamName" text,"seasonPoints" integer);
INSERT INTO "LeagueMember" VALUES (101,10,1,'Alice Team',10),(102,10,2,'Bob Team',20),(131,13,2,'Private Team',30);'''


def tests(engine,database):
    with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    service=LeagueReadService(engine);outsider=UserActor(3,'outsider');bob=UserActor(2,'bob')
    assert service.access(bob,10)=={'id':10,'name':'Margin','sport':1,'isDiscoverable':True,'commissionerDisplayName':'Alice','fullAccess':True}
    assert service.access(outsider,13)=={'id':13,'name':'Margin Hidden','sport':1,'isDiscoverable':False,'commissionerDisplayName':'Alice','fullAccess':False}
    assert service.access(UserActor(1,'alice'),13)['fullAccess'] is True
    assert service.access(bob,13)['fullAccess'] is True and service.access(bob,999) is None
    assert service.member_previews(outsider,10)==[{'id':101,'teamName':'Alice Team','displayName':'Alice'},
                                                {'id':102,'teamName':'Bob Team','displayName':'Bob'}]
    assert service.member_previews(outsider,13)==[]
    assert service.member_previews(bob,13)==[{'id':131,'teamName':'Private Team','displayName':'Bob'}]
    rows=service.search_public(' margin ')
    assert rows[0]['id']==10 and {r['id'] for r in rows}=={10,11,12,14}
    assert set(rows[0])=={'id','name','sport','numPlayers','status','draftDate','isDiscoverable','commissioner','commissionerDisplayName'}
    assert 'email' not in json.dumps(rows) and 'example.test' not in json.dumps(rows)
    assert [r['id'] for r in service.search_public('Margin',sport_id=1)]==[10,11,12]
    assert service.search_public('Margin',limit=1,offset=1)==rows[1:2]
    assert [r['id'] for r in service.search_public('Margin',sport_id=2)]==[14]
    assert [r['id'] for r in service.search_public("O'")]==[15]
    statements=[]
    def record(conn,cursor,statement,params,context,many):statements.append(statement)
    event.listen(engine,'before_cursor_execute',record)
    try:assert service.search_public(' x ',limit='bad',offset='bad')==[]
    finally:event.remove(engine,'before_cursor_execute',record)
    assert statements==[]
    with engine.begin() as conn:
        conn.execute(text('''INSERT INTO "League" SELECT n,'Margin Bulk '||n,3,8,'Pre-Draft',NULL,true,1 FROM generate_series(100,154) n'''))
    assert len(service.search_public('Margin',sport_id=3,limit=999,offset=-1))==50
    assert len(service.search_public('Margin',sport_id=3,limit=0))==1
    assert len(service.search_public('Margin',sport_id=3,limit=50,offset=50))==5
    model=LeagueModel.__new__(LeagueModel);model.db=engine
    assert model.get_league_read_access(10,2)['fullAccess'] is True
    assert model.get_member_previews_for_user(13,3)==[]
    assert model.search_leagues('Margin',sport_id=1)==service.search_public('Margin',sport_id=1)
    other=engine_for(database,'otm-discovery-revoke')
    try:
        assert service.access(outsider,10)['isDiscoverable'] is True
        with other.begin() as conn:conn.execute(text('UPDATE "League" SET "isDiscoverable"=false WHERE id=10'))
        assert service.access(outsider,10)['isDiscoverable'] is False
        assert service.member_previews(outsider,10)==[]
        assert len(service.member_previews(bob,10))==2
        with other.begin() as conn:conn.execute(text('DELETE FROM "LeagueMember" WHERE id=102'))
        assert service.access(bob,10)['fullAccess'] is False and service.member_previews(bob,10)==[]
        assert 10 not in [r['id'] for r in service.search_public('Margin')]
        # Revoke immediately before preview SQL, simulating the HTTP precheck/query gap.
        with other.begin() as conn:conn.execute(text('UPDATE "League" SET "isDiscoverable"=true WHERE id=10'))
        changed=[]
        def revoke(conn,cursor,statement,params,context,many):
            if 'SELECT lm.id, lm."teamName", u."displayName"' in statement and not changed:
                changed.append(True)
                with other.begin() as separate:separate.execute(text('UPDATE "League" SET "isDiscoverable"=false WHERE id=10'))
        event.listen(engine,'before_cursor_execute',revoke)
        try:assert service.member_previews(outsider,10)==[]
        finally:event.remove(engine,'before_cursor_execute',revoke)
        assert changed==[True]
    finally:other.dispose()
    return {'native_metadata_full_access_private_missing':'PASS','names_only_preview_entitlements':'PASS',
            'pg_trgm_ranking_tie_order_sport_page_clamps_bound_values':'PASS','short_query_no_io':'PASS',
            'separate_connection_visibility_membership_and_query_gap_revocation':'PASS','legacy_model_compatibility':'PASS'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_league_discovery_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-league-discovery')
        prior={'listing_cancellation':listing_tests(engine,name),'creation_denial':creation_tests(engine,name),
               'approval':approval_tests(engine,name),'member_profile':profile_tests(engine,name),'member_removal':removal_tests(engine,name),'league_deletion':deletion_tests(engine,name),'league_settings':settings_tests(engine,name),'league_creation':league_creation_tests(engine,name),'league_rules':rules_tests(engine,name),'league_conferences':conference_tests(engine,name)}
        discovery=tests(engine,name)
        files=['api/endpoints/league/'+f for f in ('reads/service.py','reads/repository.py','administration/service.py','administration/repository.py','members/service.py','members/repository.py','admission/service.py','admission/repository.py','admission/contracts.py','leagueModel.py','leagueEndpoints.py')]
        files+=['api/actors.py','api/rules/leagueRules.py','api/utils/authorization.py']+['scripts/modernization/'+f for f in ('verify_admission_slice.py','verify_admission_create_deny.py','verify_admission_approval.py','verify_member_profile.py','verify_member_removal.py','verify_league_delete.py','verify_league_settings.py','verify_league_creation.py','verify_league_rules_read.py','verify_league_conferences.py','verify_league_discovery.py')]
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database','prior_slices_rerun':prior,
                'league_discovery':discovery,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-league-discovery-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
