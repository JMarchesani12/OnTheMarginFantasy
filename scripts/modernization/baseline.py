"""Checksummed observed baseline; callers own the transaction.

CLI is intentionally restricted to the marked local assessment server.
No .env, configured engine, provider client, application startup or jobs imported.
"""
import argparse
import hashlib
import json
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT=Path(__file__).resolve().parents[2]
PACKAGE=ROOT/'db/baselines/20261029'

QUERIES={
 'tables': "SELECT c.relname AS table_name,pg_get_userbyid(c.relowner) AS owner,c.relrowsecurity AS rls_enabled,c.relforcerowsecurity AS rls_forced FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p') ORDER BY c.relname",
 'columns': "SELECT table_name,column_name,data_type,udt_name,is_nullable,column_default,is_identity,identity_generation FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position",
 'constraints': "SELECT c.relname AS table_name,k.conname,k.contype,pg_get_constraintdef(k.oid) AS definition FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname,k.conname",
 'indexes': "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname",
 'policies': "SELECT schemaname,tablename,policyname,permissive,roles,cmd,qual,with_check FROM pg_policies WHERE schemaname='public' ORDER BY tablename,policyname",
 'sequence_grants': "SELECT c.relname,pg_get_userbyid(c.relowner) AS owner,c.relacl::text AS acl FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='S' ORDER BY c.relname",
 'table_acl': "SELECT c.relname,c.relacl::text AS acl FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p') ORDER BY c.relname",
 'precise_columns': "SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod) AS type,coll.collname,a.attgenerated FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_collation coll ON coll.oid=a.attcollation WHERE n.nspname='public' AND c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attname",
 'sequence_options': "SELECT schemaname,sequencename,data_type,start_value,min_value,max_value,increment_by,cycle,cache_size FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename",
 'default_grants': "SELECT pg_get_userbyid(d.defaclrole) AS owner,n.nspname,d.defaclobjtype,d.defaclacl::text AS acl FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace WHERE n.nspname='public' OR d.defaclnamespace=0 ORDER BY 1,2,3",
 'schema_acl': "SELECT nspname,pg_get_userbyid(nspowner) AS owner,nspacl::text AS acl FROM pg_namespace WHERE nspname='public'",
 'role_flags': "SELECT rolname,rolsuper,rolinherit,rolcanlogin,rolbypassrls FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role') ORDER BY rolname",
 'role_membership': "SELECT parent.rolname AS granted_role,child.rolname AS member,m.admin_option FROM pg_auth_members m JOIN pg_roles parent ON parent.oid=m.roleid JOIN pg_roles child ON child.oid=m.member WHERE child.rolname IN ('anon','authenticated','service_role') ORDER BY 1,2",
 'custom_routines': "SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) AS arguments,pg_get_userbyid(p.proowner) AS owner,p.prosecdef AS security_definer,p.proacl::text AS acl FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid='pg_proc'::regclass AND d.objid=p.oid AND d.deptype='e') ORDER BY p.proname,arguments",
 'column_acl': "SELECT c.relname,a.attname,a.attacl::text AS acl FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND a.attacl IS NOT NULL AND NOT a.attisdropped ORDER BY c.relname,a.attname",
 'triggers': "SELECT c.relname AS table_name,t.tgname,t.tgenabled,n2.nspname AS function_schema,p.proname AS function_name FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace n2 ON n2.oid=p.pronamespace WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY c.relname,t.tgname",
 'views': "SELECT c.relname,c.relkind,c.reloptions,pg_get_userbyid(c.relowner) AS owner,c.relacl::text AS acl FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('v','m') ORDER BY c.relname",
 'internal_triggers': "SELECT c.relname AS table_name,k.conname AS constraint_name,owning.relname AS constraint_table,t.tgtype,t.tgenabled,t.tgdeferrable,t.tginitdeferred,n2.nspname AS function_schema,p.proname AS function_name FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace n2 ON n2.oid=p.pronamespace LEFT JOIN pg_constraint k ON k.oid=t.tgconstraint LEFT JOIN pg_class owning ON owning.oid=k.conrelid WHERE n.nspname='public' AND t.tgisinternal ORDER BY c.relname,k.conname,t.tgtype,p.proname",
 'relation_durability': "SELECT c.relname,c.relkind,c.relpersistence FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','S','m') ORDER BY c.relname",
 'event_trigger': "SELECT e.evtname,e.evtevent,e.evtenabled,e.evttags,n.nspname AS function_schema,p.proname AS function_name FROM pg_event_trigger e JOIN pg_proc p ON p.oid=e.evtfoid JOIN pg_namespace n ON n.oid=p.pronamespace WHERE e.evtname='ensure_rls'",
}


def load_package(path=PACKAGE):
    path=Path(path).resolve()
    raw=(path/'manifest.json').read_bytes()
    manifest=json.loads(raw)
    contents={}
    for item in [*manifest['steps'],manifest['expected']]:
        file=(path/item['path']).resolve()
        data=file.read_bytes()
        if file.parent!=path or hashlib.sha256(data).hexdigest()!=item['sha256']:
            raise ValueError('Baseline checksum mismatch')
        contents[item['path']]=data.decode('utf-8')
    return {**manifest,'directory':path,'checksum':hashlib.sha256(raw).hexdigest(),'contents':contents}


def canonical(rows):
    result=[]
    for row in rows:
        row=dict(row)
        if row.get('acl'):
            row['acl']=','.join(sorted(row['acl'].strip('{}').split(',')))
        result.append(row)
    return sorted(result,key=lambda r:json.dumps(r,sort_keys=True,default=str))


def verify_state(conn,package):
    expected=json.loads(package['contents'][package['expected']['path']])
    differences=[]
    for key,sql in QUERIES.items():
        actual=[dict(r) for r in conn.execute(text(sql)).mappings()]
        if canonical(actual)!=canonical(expected[key]):differences.append(key)
    definition=conn.execute(text("SELECT pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname='rls_auto_enable' AND p.pronargs=0")).scalar()
    if definition!=expected['routine']['definition']:differences.append('routine')
    if differences:raise ValueError('Baseline state mismatch: '+', '.join(differences))


def apply_baseline(conn,path=PACKAGE,mode='initialize'):
    if not conn.in_transaction():raise ValueError('Caller must own a transaction')
    # A caught Python validation error must not leave committable partial DDL.
    with conn.begin_nested():
        return _apply_baseline(conn,path,mode)


def _apply_baseline(conn,path,mode):
    if mode not in ('initialize','adopt'):raise ValueError('Unsupported baseline mode')
    package=load_package(path)
    if not conn.in_transaction():raise ValueError('Caller must own a transaction')
    # Serialize init/adoption/ledger decisions across simultaneous callers.
    conn.execute(text('SELECT pg_advisory_xact_lock(681004005)'))
    version=conn.execute(text("SELECT current_setting('server_version_num')::int")).scalar_one()
    if not 170000<=version<180000:raise ValueError('Baseline requires PostgreSQL 17')
    if conn.execute(text("SELECT to_regclass('auth.users') IS NOT NULL AND to_regprocedure('auth.uid()') IS NOT NULL")).scalar_one() is not True:
        raise ValueError('Missing Supabase Auth prerequisites')
    roles=set(conn.execute(text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated','service_role','supabase_admin')")).scalars())
    if len(roles)!=4:raise ValueError('Missing platform roles')
    if conn.execute(text("SELECT EXISTS(SELECT 1 FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='pg_trgm' AND e.extversion='1.6' AND n.nspname='public')")).scalar_one() is not True:
        raise ValueError('Missing pg_trgm 1.6 in public')
    ledger=conn.execute(text("SELECT to_regclass('app_migrations.baseline')")).scalar()
    if ledger:
        rows=conn.execute(text('SELECT version,checksum FROM app_migrations.baseline')).all()
        if rows!=[(package['version'],package['checksum'])]:raise ValueError('Conflicting baseline ledger')
        verify_state(conn,package)
        return 'already_applied'
    tables=conn.execute(text("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S')")).scalar_one()
    if mode=='initialize':
        custom=conn.execute(text(QUERIES['custom_routines'])).first()
        trigger=conn.execute(text(QUERIES['event_trigger'])).first()
        if tables or custom or trigger:
            raise ValueError('Initialize requires empty application schema; use verified adoption')
        for step in package['steps']:
            conn.execute(text(package['contents'][step['path']]))
    verify_state(conn,package)
    conn.exec_driver_sql('CREATE SCHEMA app_migrations AUTHORIZATION postgres')
    conn.exec_driver_sql('REVOKE ALL ON SCHEMA app_migrations FROM PUBLIC, anon, authenticated, service_role')
    conn.exec_driver_sql('''CREATE TABLE app_migrations.baseline(
        version text PRIMARY KEY,checksum text NOT NULL CHECK(length(checksum)=64),
        mode text NOT NULL CHECK(mode IN ('initialize','adopt')),
        recorded_at timestamptz NOT NULL DEFAULT now())''')
    conn.exec_driver_sql('REVOKE ALL ON app_migrations.baseline FROM PUBLIC, anon, authenticated, service_role')
    conn.execute(text('INSERT INTO app_migrations.baseline(version,checksum,mode) VALUES (:version,:checksum,:mode)'),
                 {'version':package['version'],'checksum':package['checksum'],'mode':mode})
    return 'initialized' if mode=='initialize' else 'adopted'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['initialize','adopt'])
    parser.add_argument('--database',required=True,help='Existing synthetic database in the marked local container')
    args=parser.parse_args()
    if not args.database.startswith('otm_baseline_') or not all(c.isalnum() or c=='_' for c in args.database):
        parser.error('Only otm_baseline_* synthetic databases are accepted')
    engine=create_engine('postgresql+psycopg2://postgres@127.0.0.1:55439/'+args.database,connect_args={'connect_timeout':3})
    try:
        with engine.begin() as conn:
            marker=conn.execute(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname='postgres'")).scalar()
            if marker!='otm-modernization-assessment-20261029-synthetic-only':raise ValueError('Refusing unmarked server')
            print(apply_baseline(conn,mode=args.mode))
    finally:engine.dispose()


if __name__=='__main__':main()
