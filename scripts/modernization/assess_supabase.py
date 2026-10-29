"""Real local Supabase provider acceptance. No .env or remote targets accepted.

Requires the dedicated CLI project/runbook and private local status JSON.
Uses actual Auth/PostgREST with synthetic users, never the production app factory.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import psycopg2
import requests
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

import baseline

ROOT=Path(__file__).resolve().parents[2]
WORKDIR=Path('/private/tmp/otm-mod004005-supabase-20261029')
CONTAINER='supabase_db_otm-mod004005-supabase-20261029'
MARKER='otm-supabase-provider-assessment-20261029'
API='http://127.0.0.1:55441'
EVIDENCE=ROOT/'docs/modernization/evidence/supabase-provider-verification-2026-10-29.json'


def require(condition,message):
    if not condition:raise AssertionError(message)


def request(session,method,path,key,token=None,**kwargs):
    headers={'apikey':key,'Authorization':'Bearer '+(token or key)}
    headers.update(kwargs.pop('headers',{}))
    return session.request(method,API+path,headers=headers,timeout=10,allow_redirects=False,**kwargs)


def expect(response,statuses,message):
    require(response.status_code in statuses,message+' (HTTP '+str(response.status_code)+')')
    return response


def reload_rest(engine,session,key):
    with engine.begin() as conn:conn.exec_driver_sql("NOTIFY pgrst, 'reload schema'")
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        response=request(session,'GET','/rest/v1/User?select=id',key)
        if response.status_code==200:return
        time.sleep(.1)
    raise AssertionError('PostgREST did not load application schema')


def checks(session,status,users,hardened=False):
    anon=status['ANON_KEY'];service=status['SERVICE_ROLE_KEY']
    for index,user in enumerate(users):
        response=expect(request(session,'GET','/rest/v1/User?select=id,email,displayName',anon,user['token']),{200},'Own-profile read failed')
        require([r['id'] for r in response.json()]==[user['profile']],'Unfiltered profile read crossed user boundary')
        foreign=users[1-index]['profile']
        response=expect(request(session,'GET',f'/rest/v1/User?select=id&id=eq.{foreign}',anon,user['token']),{200},'Foreign-profile read failed')
        require(response.json()==[],'Foreign profile exposed')
        response=request(session,'PATCH',f'/rest/v1/User?id=eq.{user["profile"]}',anon,user['token'],
                         headers={'Prefer':'return=representation'},json={'displayName':'forbidden'})
        if hardened:expect(response,{403},'Browser update was not rejected')
        else:
            expect(response,{200},'Observed browser update contract changed')
            require(response.json()==[],'Browser updated profile without a write policy')
        response=request(session,'GET','/rest/v1/School?select=id',anon,user['token'])
        if hardened:expect(response,{403},'Other table grant remains')
        else:
            expect(response,{200},'Observed catalog deny contract changed')
            require(response.json()==[],'Policy-free catalog row exposed')
    response=request(session,'GET','/rest/v1/User?select=id',anon)
    if hardened:expect(response,{401},'Anonymous grant remains')
    else:
        expect(response,{200},'Observed anonymous contract changed')
        require(response.json()==[],'Anonymous profile exposed')
    response=expect(request(session,'GET','/rest/v1/User?select=id&order=id',service),{200},'Service read failed')
    require([r['id'] for r in response.json()]==sorted(u['profile'] for u in users),'Service role lost profile access')
    response=expect(request(session,'GET','/rest/v1/School?select=id',service),{200},'Service catalog read failed')
    require(len(response.json())==1,'Service role lost catalog access')
    return {'real_auth_users':2,'own_and_cross_user_reads':'PASS','browser_writes':'denied',
            'anonymous_profiles':'denied','other_browser_table':'denied','service_reads':'preserved',
            'stage':'proposal' if hardened else 'observed baseline'}


def upgrade_checks(engine):
    # Schema-only export from this disposable provider, no Auth/application rows.
    command=['docker','exec',CONTAINER,'pg_dump','-U','postgres','-d','postgres',
             '--no-password','--schema-only','--schema=auth','--schema=public','--no-comments','--no-security-labels']
    dumped=subprocess.run(command,capture_output=True,check=True).stdout
    require(dumped.count(b'CREATE SCHEMA public;')==1,'Unexpected schema export format')
    # Schema-selected pg_dump excludes extension installation and database event
    # triggers. Supply these explicit platform prerequisites, not application DDL.
    prepared=b'DROP SCHEMA public;\n'+dumped.replace(b'CREATE SCHEMA public;',
        b'CREATE SCHEMA public;\nCREATE EXTENSION pg_trgm WITH SCHEMA public;',1)
    prepared+=b"\nSET ROLE postgres;\nGRANT USAGE ON SCHEMA public TO PUBLIC;\nCREATE EVENT TRIGGER ensure_rls ON ddl_command_end WHEN TAG IN ('CREATE TABLE','CREATE TABLE AS','SELECT INTO') EXECUTE FUNCTION public.rls_auto_enable();\nRESET ROLE;\n"
    result={'schema_only_export_sha256':hashlib.sha256(dumped).hexdigest(),
            'restore_prerequisites':['empty target public schema','initial public schema PUBLIC USAGE grant','pg_trgm 1.6','ensure_rls database event-trigger registration'],
            'fixtures':[]}
    admin=psycopg2.connect(host='127.0.0.1',port=55442,user='postgres',password='postgres',dbname='postgres',connect_timeout=3)
    admin.autocommit=True
    created=[]
    try:
        for old in (False,True):
            database='otm_provider_upgrade_'+uuid4().hex
            with admin.cursor() as cur:cur.execute('CREATE DATABASE '+database)
            created.append(database)
            # pg_dump restrict commands are handled by psql, never reinterpreted as Python/shell.
            restore=subprocess.run(['docker','exec','-i','-e','PGPASSWORD=postgres',CONTAINER,'psql','--no-password','-U','supabase_admin','-d',database,
                            '--set','ON_ERROR_STOP=1','--quiet'],input=prepared,capture_output=True)
            if restore.returncode:
                raise RuntimeError('Local schema-only restore failed: '+restore.stderr.decode(errors='replace')[-1500:])
            target=create_engine('postgresql+psycopg2://postgres:postgres@127.0.0.1:55442/'+database)
            try:
                with target.begin() as conn:
                    conn.exec_driver_sql('DROP TABLE public."SportSeasonSubdivision"')
                    if old:conn.exec_driver_sql('ALTER TABLE public."SportSeason" RENAME COLUMN "seasonStart" TO "esasonStart"')
                with target.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
                    for file in sorted((ROOT/'api/migrations').glob('*.sql')):
                        conn.execute(text(file.read_text()))
                with target.begin() as conn:
                    preserved=conn.execute(text("""INSERT INTO public."School"(name) VALUES ('provider upgrade fixture') RETURNING id""")).scalar_one()
                    try:
                        baseline.verify_state(conn,baseline.load_package())
                    except ValueError:
                        print('fixture_schema_acl',[dict(r) for r in conn.execute(text(baseline.QUERIES['schema_acl'])).mappings()])
                        raise
                    require(baseline.apply_baseline(conn,mode='adopt')=='adopted','Historical state adoption failed')
                with target.begin() as conn:
                    require(baseline.apply_baseline(conn,mode='adopt')=='already_applied','Historical adoption replay failed')
                    require(conn.execute(text('SELECT count(*) FROM public."School" WHERE id=:id'),{'id':preserved}).scalar_one()==1,'Adoption lost an existing application row')
                result['fixtures'].append({'starting_column':'esasonStart' if old else 'seasonStart',
                                           'subdivision':'absent before historical files','adoption_and_replay':'PASS','existing_application_row':'preserved'})
            finally:target.dispose()
    finally:
        with admin.cursor() as cur:
            for database in created:cur.execute('DROP DATABASE '+database+' WITH (FORCE)')
        admin.close()
    return result


def main():
    status=json.loads((WORKDIR/'status.json').read_text())
    url=make_url(status['DB_URL'])
    require(url.host=='127.0.0.1' and url.port==55442 and url.database=='postgres','Refusing nonlocal provider database')
    require(status['API_URL'].rstrip('/')==API,'Refusing nonlocal provider API')
    engine=create_engine(url,connect_args={'connect_timeout':3})
    maintenance=create_engine(url.set(username='supabase_admin',password='postgres'),connect_args={'connect_timeout':3})
    session=requests.Session();session.trust_env=False
    users=[];school=None
    package=baseline.load_package()
    report={'scope':'Dedicated real local Supabase Auth/PostgREST project; synthetic users only; no deployed changes.',
            'baseline_version':package['version'],'baseline_checksum':package['checksum'],
            'sha256':{str(file.relative_to(ROOT)):hashlib.sha256(file.read_bytes()).hexdigest()
                      for file in [Path(__file__).resolve(),ROOT/'db/proposals/mod004_browser_privileges.sql',
                                   ROOT/'db/proposals/mod004_browser_privileges_recovery.sql',
                                   *sorted((ROOT/'api/migrations').glob('*.sql'))]}}
    report['cli_version']=subprocess.run(['supabase','--version'],capture_output=True,text=True,check=True).stdout.strip()
    images=subprocess.run(['docker','inspect','--format','{{.Config.Image}}',CONTAINER,
        'supabase_auth_otm-mod004005-supabase-20261029','supabase_rest_otm-mod004005-supabase-20261029'],
        capture_output=True,text=True,check=True).stdout.splitlines()
    report['provider_images']=images
    try:
        with engine.begin() as conn:
            require(conn.execute(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")).scalar_one()==MARKER,'Refusing unmarked provider database')
            # Documented prerequisite, not a fabricated Auth schema or role.
            conn.exec_driver_sql('CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public')
            report['initialize_or_replay']=baseline.apply_baseline(conn)
            role=dict(conn.execute(text("SELECT current_user,r.rolsuper,r.rolbypassrls FROM pg_roles r WHERE r.rolname=current_user")).mappings().one())
            report['real_provider_actor']=role
        for label in ('a','b'):
            email='otm-'+uuid4().hex+'-'+label+'@synthetic.test'
            response=expect(request(session,'POST','/auth/v1/signup',status['ANON_KEY'],json={'email':email,'password':'Synthetic-local-only-2026!'}),{200},'Synthetic signup failed')
            payload=response.json()
            require(bool(payload.get('access_token')) and bool(payload.get('user',{}).get('id')),'Auth did not issue a real user token')
            user={'id':payload['user']['id'],'token':payload['access_token']}
            users.append(user)
            with engine.begin() as conn:
                user['profile']=conn.execute(text('INSERT INTO public."User"(uuid,email,"displayName") VALUES (:uuid,:email,:name) RETURNING id'),
                    {'uuid':user['id'],'email':email,'name':label.upper()}).scalar_one()
        with engine.begin() as conn:
            school=conn.execute(text('INSERT INTO public."School"(name) VALUES (:name) RETURNING id'),{'name':'Synthetic provider school'}).scalar_one()
        with engine.begin() as conn:
            require(baseline.apply_baseline(conn)=='already_applied','Provider baseline replay failed')
        report['baseline_replay']='already_applied with existing Auth/application rows preserved'
        reload_rest(engine,session,status['ANON_KEY'])
        report['http_before']=checks(session,status,users)
        report['historical_upgrade']=upgrade_checks(engine)
        proposal=(ROOT/'db/proposals/mod004_browser_privileges.sql').read_text()
        recovery=(ROOT/'db/proposals/mod004_browser_privileges_recovery.sql').read_text()
        # Prove the ordinary provider actor cannot half-apply the full proposal.
        rejected=False
        with engine.connect() as conn:
            attempt=conn.begin()
            try:
                conn.execute(text(proposal))
            except Exception as exc:
                require(getattr(getattr(exc,'orig',None),'pgcode',None)=='42501','Unexpected ordinary actor proposal failure')
                rejected=True
            finally:
                # Even an unexpected success must never leave proposal changes.
                attempt.rollback()
        require(rejected,'Provider actor capability changed; reassess documented rollout boundary')
        with engine.connect() as conn:baseline.verify_state(conn,package)
        report['ordinary_postgres_proposal']={'result':'rejected with SQLSTATE42501','partial_changes':'none; observed reference preserved'}
        with maintenance.connect() as conn:
            require(conn.execute(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")).scalar_one()==MARKER,'Refusing unmarked maintenance target')
            require(conn.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")).scalar_one(),'Missing local maintenance capability')
        applied=False
        try:
            with maintenance.begin() as conn:conn.execute(text(proposal))
            applied=True
            report['http_proposal']=checks(session,status,users,hardened=True)
            # Existing browser mutation probes must not alter either persisted profile.
            with engine.connect() as conn:
                names=list(conn.execute(text('SELECT "displayName" FROM public."User" ORDER BY id')).scalars())
                require(names==['A','B'],'Denied HTTP write changed a profile')
        finally:
            if applied:
                with maintenance.begin() as conn:conn.execute(text(recovery))
        with engine.connect() as conn:baseline.verify_state(conn,package)
        report['http_recovery']=checks(session,status,users)
        report['data_preserved_after_recovery']=True
        report['result']='PASS'
        EVIDENCE.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        try:
            with engine.begin() as conn:
                for user in users:
                    if 'profile' in user:
                        conn.execute(text('DELETE FROM public."User" WHERE id=:id'),{'id':user['profile']})
                    conn.execute(text('DELETE FROM auth.users WHERE id=:id'),{'id':user['id']})
                if school is not None:conn.execute(text('DELETE FROM public."School" WHERE id=:id'),{'id':school})
        finally:
            session.close();engine.dispose();maintenance.dispose()


if __name__=='__main__':main()
