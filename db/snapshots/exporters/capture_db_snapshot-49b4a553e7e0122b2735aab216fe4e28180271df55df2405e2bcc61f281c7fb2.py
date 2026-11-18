"""Explicitly authorized, metadata-only hosted capture; never imports app/jobs.

Only --configured-read-only opts into api/.env. Credentials stay in memory and
child environment, never argv/artifacts. No DDL, role changes or application rows.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from uuid import uuid4

from dotenv import dotenv_values
import psycopg2
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
import baseline
from mod017_index_support import snapshot_catalog

ROOT=Path(__file__).resolve().parents[2]
IMAGE='sha256:00bc86618629af00d2937fdc5a5d63db3ff8450acf52f0636ec813c7f4902929'
PUBLIC_EXCLUSIONS=['No application/Auth rows or sequence current values','Public schema only; Auth/storage/provider schemas are prerequisites, not exported','Cluster roles/passwords, full platform configuration and data backups excluded','Owner statements/comments/security labels omitted from SQL; public object owners retained in catalog','No claim of browser/runtime deployment acceptance; no grants/DDL/index mutations']

class SnapshotError(RuntimeError):pass


def connection_parameters(values):
    try:
        u=make_url(values['SUPABASE_DB_URL']);project=values['SUPABASE_PROJECT_ID']
    except Exception:raise SnapshotError('Missing/invalid configured database identity') from None
    if not project or not (project in (u.host or '') or (u.username or '').endswith('.'+project)):
        raise SnapshotError('Configured project identity does not match database endpoint')
    if any(k in u.query for k in ('service','hostaddr','host','port','user','password','dbname')):
        raise SnapshotError('Ambiguous transport overrides require review')
    p=dict(u.query)
    p.update(host=u.host,port=u.port or 5432,user=u.username,password=u.password,dbname=u.database,
             sslmode='require',connect_timeout=8,options='-c default_transaction_read_only=on -c statement_timeout=45000 -c lock_timeout=3000',application_name='otm_audit_snapshot')
    if 'pooler' in (u.host or '') and p['port']==6543:p['port']=5432
    return p


def screen(raw,secrets):
    content=raw.decode('utf-8')
    patterns=[r'postgres(?:ql)?://',r'\bpassword\s*=\s*\S+',r'\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}',r'\bAKIA[0-9A-Z]{16}\b']
    if any(re.search(p,content,re.I) for p in patterns) or any(s and len(s)>=8 and s in content for s in secrets):
        raise SnapshotError('Sensitive definition/configuration detected; nothing published')


def atomic_json(path,value):
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2,default=str)+'\n');temporary.replace(path)


def publish(output,files,manifest,secrets):
    if any(Path(name).name!=name for name in files):raise SnapshotError('Invalid output name')
    for raw in files.values():screen(raw,secrets)
    for name,raw in files.items():
        path=output/name
        if path.exists():raise SnapshotError('Refusing existing snapshot artifact')
        with path.open('xb') as f:f.write(raw)
    manifest['files']={name:dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)) for name,raw in files.items()}
    if any(hashlib.sha256((output/name).read_bytes()).hexdigest()!=metadata['sha256'] for name,metadata in manifest['files'].items()):raise SnapshotError('Snapshot checksum verification failed')
    manifest['result']='PASS';manifest['completed_at']=datetime.now(timezone.utc).isoformat();atomic_json(output/'manifest.json',manifest)


def export_schema(params,snapshot):
    env=dict(os.environ)
    variables=dict(PGHOST=params['host'],PGPORT=str(params['port']),PGUSER=params['user'],PGPASSWORD=params['password'],PGDATABASE=params['dbname'],PGSSLMODE='require',PGCONNECT_TIMEOUT='8',PGOPTIONS=params['options'],PGAPPNAME='otm_schema_export')
    env.update(variables)
    name='otm-schema-export-'+uuid4().hex
    command=['docker','run','--rm','--pull=never','--name',name,'--label','otm.task=audit-snapshot-20261117']
    for key in variables:command+=['--env',key]
    command+=['--entrypoint','pg_dump',IMAGE,'--no-password','--schema-only','--schema=public','--no-owner','--no-comments','--no-security-labels','--snapshot='+snapshot]
    try:
        result=subprocess.run(command,env=env,capture_output=True,timeout=90)
        if result.returncode:raise SnapshotError('Schema-only client export failed; private stderr suppressed')
        if b'CREATE TABLE' not in result.stdout:raise SnapshotError('Schema export has no table definitions')
        return result.stdout
    finally:
        # A timed-out Docker client can leave its container running. Remove only
        # this invocation's exact name/ID after verifying image and task label.
        listed=subprocess.run(['docker','ps','-a','--filter','name=^/'+name+'$','--format','{{.ID}}'],capture_output=True,text=True,timeout=10,check=True)
        for identifier in listed.stdout.split():
            inspect=subprocess.run(['docker','inspect',identifier],capture_output=True,text=True,timeout=10,check=True)
            row=json.loads(inspect.stdout)[0]
            if row['Image']!=IMAGE or row['Name']!='/'+name or row['Config']['Labels'].get('otm.task')!='audit-snapshot-20261117':raise SnapshotError('Client container ownership check failed')
            subprocess.run(['docker','rm','-f',row['Id']],capture_output=True,timeout=10,check=True)


def collect(params,values):
    engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(**params))
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            info=conn.execute(text("SELECT current_setting('server_version') AS version,current_setting('transaction_read_only') AS readonly,current_database() AS database,current_user AS actor")).mappings().one()
            client=conn.connection.driver_connection
            if info['readonly']!='on' or not client.info.ssl_in_use:raise SnapshotError('Read-only/client TLS guard failed')
            snapshot=conn.exec_driver_sql('SELECT pg_export_snapshot()').scalar_one()
            catalog={key:[dict(r) for r in conn.execute(text(sql)).mappings()] for key,sql in baseline.QUERIES.items()}
            catalog['index_catalog']=snapshot_catalog(conn)
            extra={
             'constraint_validation':'''SELECT t.relname AS table_name,c.conname,c.contype,c.convalidated,c.condeferrable,c.condeferred,c.confdeltype,c.confupdtype,pg_get_constraintdef(c.oid) AS definition FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public' ORDER BY t.relname,c.conname''',
             'extensions':'''SELECT e.extname,e.extversion,n.nspname AS schema FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace ORDER BY e.extname''',
             'actor':'''SELECT rolname,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,pg_has_role(current_user,'supabase_admin','MEMBER') AS supabase_admin_member FROM pg_roles WHERE rolname=current_user''',
             'custom_routine_definitions':'''SELECT p.proname,pg_get_function_identity_arguments(p.oid) AS arguments,pg_get_functiondef(p.oid) AS definition FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.prokind IN ('f','p') AND NOT EXISTS(SELECT 1 FROM pg_depend d WHERE d.classid='pg_proc'::regclass AND d.objid=p.oid AND d.deptype='e') ORDER BY p.proname,arguments''',
             'all_event_triggers':'''SELECT e.evtname,e.evtevent,e.evtenabled,e.evttags,n.nspname AS function_schema,p.proname AS function_name FROM pg_event_trigger e JOIN pg_proc p ON p.oid=e.evtfoid JOIN pg_namespace n ON n.oid=p.pronamespace ORDER BY e.evtname''',
            }
            for key,sql in extra.items():catalog[key]=[dict(r) for r in conn.execute(text(sql)).mappings()]
            preflight=ROOT/'db/preflights/20261105_seasonal_consistency.sql'
            assessment=dict(mod015_aggregate_preflight=dict(conn.execute(text(preflight.read_text())).mappings().one()),no_application_rows_exported=True)
            source=(ROOT/'docs/modernization/proposals/mod-017-indexes/preflight.sql').read_text()
            sql=source[source.index('WITH relation AS ('):source.index('\\gset mod017_member_')]
            result=dict(conn.execute(text(sql)).mappings().one())
            assessment['mod017_readonly_preflight']=dict(ok=result['ok'],create=result['create'],catalog=result['catalog'],executed='SELECT-only extraction of reviewed preflight; no psql CREATE/DROP/recovery file executed')
            raw=export_schema(params,snapshot)
            context=dict(postgres_version=info['version'],actor=info['actor'],readonly=True,client_tls=True,tls_protocol=client.info.ssl_attribute('protocol'),connection='same configured project/actor via session-preserving pooler port' if 'pooler' in params['host'] else 'configured direct endpoint',target_fingerprint=hashlib.sha256(json.dumps([values['SUPABASE_PROJECT_ID'],info['database'],info['actor']]).encode()).hexdigest(),target_fingerprint_method='SHA256(project reference,database,actor); no credential or endpoint persisted',consistency='Catalog, aggregate preflights and pg_dump share pg_export_snapshot from one open REPEATABLE READ READ ONLY transaction',export_client='cached PostgreSQL17.6 image '+IMAGE)
            conn.rollback()
            return raw,catalog,assessment,context
    finally:engine.dispose()


def capture(output,connect=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    manifest=dict(result='RUNNING',started_at=datetime.now(timezone.utc).isoformat(),scope='Observed public-schema/catalog metadata only',exclusions=PUBLIC_EXCLUSIONS,phase='configuration')
    atomic_json(output/'manifest.json',manifest)
    try:
        if connect is not None:connect() # Failure injection; real access only through explicit CLI/configuration path.
        values=dotenv_values(ROOT/'api/.env');params=connection_parameters(values)
        manifest['phase']='read-only collection and same-snapshot export'
        schema,catalog,assessment,context=collect(params,values)
        manifest['context']=context
        manifest['git_revision']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        sources=['scripts/modernization/capture_db_snapshot.py','scripts/modernization/baseline.py','scripts/modernization/mod017_index_support.py','db/preflights/20261105_seasonal_consistency.sql','docs/modernization/proposals/mod-017-indexes/preflight.sql']
        manifest['sources']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}
        secrets=[str(v) for k,v in values.items() if v and any(s in k for s in ('SECRET','PASSWORD','KEY','DB_URL'))]
        files={'schema.sql':schema,'catalog.json':(json.dumps(catalog,indent=2,default=str)+'\n').encode(),'assessment.json':(json.dumps(assessment,indent=2,default=str)+'\n').encode()}
        manifest['phase']='screened/checksummed publication';publish(output,files,manifest,secrets)
        return manifest
    except BaseException as error:
        manifest.update(result='FAILED',error_type=type(error).__name__,details='Private driver/client/definition details suppressed; never treat this directory as a verified snapshot')
        atomic_json(output/'manifest.json',manifest)
        raise SnapshotError('Snapshot capture failed; see sanitized manifest') from None

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--configured-read-only',action='store_true',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    try:
        result=capture(args.output);print(json.dumps(dict(result=result['result'],output=args.output,files=list(result['files']))))
    except (SnapshotError,FileExistsError) as error:
        print(json.dumps(dict(result='FAILED',error_type=type(error).__name__,details='See sanitized manifest if created; existing snapshot paths are never reused')));raise SystemExit(1)
