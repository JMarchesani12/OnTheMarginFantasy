"""Disposable MOD-004/005/009 assessment. Never reads .env or accepts a DSN.

Requires the documented task-owned PostgreSQL container on 127.0.0.1:55439.
Creates new uniquely named databases, and drops only databases created by this run.
Supabase Auth is a minimal synthetic SQL fixture, not a full platform deployment.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
from uuid import uuid4

import psycopg2
from sqlalchemy import create_engine, event, text

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'docs/modernization/evidence'
LOCAL = dict(host='127.0.0.1', port=55439, user='postgres', connect_timeout=3)
# Model imports only; never import configured db/app/jobs or load dotenv.
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
sys.path.insert(0, str(ROOT / 'api'))
from endpoints.transaction.transactionModel import TransactionModel


def candidate():
    source = (ROOT / 'db/tables.sql').read_text()
    tables = {}
    for ddl, name in re.findall(r'(create table public\."([^"]+)".*?;)', source, re.S | re.I):
        if name in tables:
            assert tables[name] == ddl, 'Conflicting duplicate table declaration'
        tables[name] = ddl
    pending = dict(tables)
    ordered = []
    while pending:
        ready = [name for name, ddl in pending.items() if not
                 (set(re.findall(r'references "([^"]+)"', ddl, re.I)) & pending.keys())]
        assert ready, 'Unresolved dependency cycle'
        for name in ready:
            ordered.append(pending.pop(name))
    indexes = list(dict.fromkeys(re.findall(r'create (?:unique )?index .*?;', source, re.S | re.I)))
    assert len(tables) == 23
    return '\n\n'.join(ordered + indexes) + '\n'


PLATFORM = """
CREATE SCHEMA auth;
CREATE TABLE auth.users (id uuid PRIMARY KEY);
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
CREATE EXTENSION pg_trgm WITH SCHEMA public;
"""


def engine_for(database, name='otm-assessment'):
    return create_engine('postgresql+psycopg2://postgres@127.0.0.1:55439/' + database,
                         connect_args={'connect_timeout': 3, 'application_name': name},
                         pool_pre_ping=True)


def definitions(conn):
    queries = {
        'columns': "SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default,is_identity,identity_generation FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position",
        'constraints': "SELECT c.relname AS table_name,k.conname,k.contype,pg_get_constraintdef(k.oid) AS definition FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname,k.conname",
        'indexes': "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname",
    }
    return {key: [dict(row) for row in conn.execute(text(sql)).mappings()]
            for key, sql in queries.items()}


def diff(actual, expected):
    result = {}
    for group, keys in [('columns', ('table_name','column_name')),
                        ('constraints', ('table_name','conname')),
                        ('indexes', ('tablename','indexname'))]:
        a = {tuple(row[k] for k in keys): row for row in actual[group]}
        b = {tuple(row[k] for k in keys): row for row in expected[group]}
        result[group] = {
            'candidate_only': [a[k] for k in sorted(a.keys()-b.keys())],
            'deployed_only': [b[k] for k in sorted(b.keys()-a.keys())],
            'different': [{'key': k, 'candidate': a[k], 'deployed': b[k]}
                          for k in sorted(a.keys() & b.keys()) if a[k] != b[k]],
        }
    return result


def access_tests(engine, catalog):
    with engine.begin() as conn:
        routine=json.loads((EVIDENCE/'rls-auto-enable-2026-10-29.json').read_text())['routines'][0]
        assert routine['result_type']=='event_trigger'
        conn.execute(text(routine['definition']))
        conn.exec_driver_sql("CREATE EVENT TRIGGER ensure_rls ON ddl_command_end WHEN TAG IN ('CREATE TABLE','CREATE TABLE AS','SELECT INTO') EXECUTE FUNCTION public.rls_auto_enable()")
        conn.exec_driver_sql('CREATE TABLE public.otm_rls_probe (id bigint)')
        assert conn.execute(text("SELECT relrowsecurity FROM pg_class WHERE oid='public.otm_rls_probe'::regclass")).scalar_one()
        conn.exec_driver_sql('DROP TABLE public.otm_rls_probe')
        # Reproduce observed table-level grants and RLS, never alter deployment.
        for table in catalog['tables']:
            name = table['table_name'].replace('"','""')
            conn.exec_driver_sql(f'ALTER TABLE public."{name}" ENABLE ROW LEVEL SECURITY')
            conn.exec_driver_sql(f'GRANT ALL ON public."{name}" TO otm_anon,otm_authenticated,otm_service')
        conn.exec_driver_sql('GRANT USAGE ON SCHEMA public,auth TO otm_anon,otm_authenticated,otm_service')
        conn.exec_driver_sql('CREATE POLICY "read own user row" ON public."User" FOR SELECT TO PUBLIC USING (uuid=auth.uid())')
        conn.exec_driver_sql("INSERT INTO auth.users VALUES ('00000000-0000-4000-8000-000000000001'),('00000000-0000-4000-8000-000000000002')")
        conn.exec_driver_sql("""INSERT INTO public."User" (id,uuid,email,"displayName") VALUES
            (1,'00000000-0000-4000-8000-000000000001','a@synthetic.test','A'),
            (2,'00000000-0000-4000-8000-000000000002','b@synthetic.test','B')""")
        conn.exec_driver_sql('''INSERT INTO public."Sport" (id,name) VALUES (1,'synthetic')''')
    results = []
    for role, subject, expected in [
        ('otm_anon','',[]),
        ('otm_authenticated','00000000-0000-4000-8000-000000000001',[1]),
        ('otm_authenticated','00000000-0000-4000-8000-000000000002',[2]),
        ('otm_authenticated','',[]),
        ('otm_authenticated','00000000-0000-4000-8000-000000000003',[]),
        ('otm_service','',[1,2]), ('postgres','',[1,2])]:
        with engine.begin() as conn:
            conn.exec_driver_sql('SET LOCAL ROLE '+role)
            conn.execute(text("SELECT set_config('request.jwt.claim.sub',:subject,true)"),{'subject':subject})
            ids = list(conn.execute(text('SELECT id FROM public."User" ORDER BY id')).scalars())
            assert ids == expected, (role, ids)
            sport_count = conn.execute(text('SELECT count(*) FROM public."Sport"')).scalar_one()
            assert sport_count == (1 if role in ('otm_service','postgres') else 0)
            if role in ('otm_anon','otm_authenticated'):
                assert conn.execute(text('''UPDATE public."User" SET "displayName"='changed' RETURNING id''')).all() == []
                try:
                    with conn.begin_nested():
                        conn.exec_driver_sql('''INSERT INTO public."User" (id,email) VALUES (3,'forbidden@synthetic.test')''')
                except Exception as exc:
                    assert getattr(exc.orig,'pgcode',None) == '42501'
                else:
                    raise AssertionError('Unexpected browser insert success')
            results.append({'role':role,'subject':subject,'visible_profile_ids':ids,'visible_sport_rows':sport_count})
    # TRUNCATE is not filtered by RLS. Roll back the destructive synthetic probe.
    with engine.connect() as conn:
        transaction = conn.begin()
        conn.exec_driver_sql('SET LOCAL ROLE otm_anon')
        conn.exec_driver_sql('TRUNCATE public."School" CASCADE')
        transaction.rollback()
    return {'profile_and_catalog_reads':results,'browser_updates_and_inserts':'denied',
            'anon_truncate_cascade':'succeeds on synthetic tables; probe rolled back',
            'deployed_event_trigger_definition':'replayed; public CREATE TABLE automatically enabled RLS',
            'scope':'SQL role tests; synthetic auth.uid; no HTTP/PostgREST or full Auth-service test'}


def trade_tests(engine, database):
    with engine.begin() as conn:
        conn.exec_driver_sql('DROP SCHEMA public CASCADE')
        conn.exec_driver_sql('CREATE SCHEMA public')
        conn.exec_driver_sql("""
            CREATE TABLE "League" (id bigint PRIMARY KEY,"tradeDeadline" timestamptz);
            CREATE TABLE "Week" (id bigint PRIMARY KEY,"leagueId" bigint,"weekNumber" bigint);
            CREATE TABLE "Transaction" (id bigint PRIMARY KEY,"leagueId" bigint,"weekId" bigint,
                type text,status text,"memberFromId" bigint,"memberToId" bigint,"fromTeamIds" jsonb,"toTeamIds" jsonb);
            CREATE TABLE "LeagueTeamSlot" (id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                "leagueId" bigint,"memberId" bigint,"sportTeamId" bigint,"acquiredWeek" bigint,"droppedWeek" bigint,"acquiredVia" text);
            CREATE TABLE "ConferenceMembership" ("sportTeamId" bigint,"sportConferenceId" bigint);
            CREATE TABLE "SportConference" (id bigint,"maxTeamsPerOwner" bigint);
            INSERT INTO "League" VALUES (10,NULL);
            INSERT INTO "Week" VALUES (100,10,2);
            INSERT INTO "ConferenceMembership" VALUES (101,500),(102,500);
            INSERT INTO "SportConference" VALUES (500,3);
        """)
    results=[]
    for dispatch in (False,True):
        with engine.begin() as conn:
            conn.exec_driver_sql('TRUNCATE "Transaction","LeagueTeamSlot" RESTART IDENTITY')
            conn.exec_driver_sql("""INSERT INTO "Transaction" VALUES (1,10,100,'TRADE','PENDING_APPLY',11,12,'[101]','[102]');
                INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek")
                VALUES (10,11,101,1),(10,12,102,1)""")
        first = engine_for(database,'otm-first')
        second = engine_for(database,'otm-second')
        locked, release = threading.Event(), threading.Event()
        outcomes={}
        def after_lock(conn,cursor,statement,params,context,many):
            if 'FOR UPDATE' in statement:
                locked.set()
                assert release.wait(10), 'First apply was not released'
        event.listen(first,'after_cursor_execute',after_lock)
        def apply(label,db):
            try:
                model=TransactionModel(db)
                value=(model.apply_pending_transaction if dispatch else model.apply_trade)(1)
                outcomes[label]=('success',value)
            except Exception as exc:
                outcomes[label]=(type(exc).__name__,str(exc))
        t1=threading.Thread(target=apply,args=('first',first))
        t2=threading.Thread(target=apply,args=('second',second))
        t1.start()
        try:
            assert locked.wait(5), 'First apply did not acquire transaction lock'
            t2.start()
            blocked=False
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                with engine.connect() as conn:
                    blocked=conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE application_name='otm-second' AND wait_event_type='Lock' AND cardinality(pg_blocking_pids(pid))>0)")).scalar_one()
                if blocked: break
                time.sleep(.02)
            assert blocked, 'Did not observe a competing PostgreSQL lock wait'
        finally:
            release.set()
            t1.join(10)
            if t2.ident is not None: t2.join(10)
            first.dispose()
            second.dispose()
        assert not t1.is_alive() and not t2.is_alive()
        assert outcomes == {'first':('success',None),'second':('ValueError','Transaction is not pending apply')},outcomes
        with engine.connect() as conn:
            slots=[tuple(r) for r in conn.execute(text('SELECT "memberId","sportTeamId","acquiredWeek","droppedWeek" FROM "LeagueTeamSlot" ORDER BY id'))]
            assert slots == [(11,101,1,2),(12,102,1,2),(12,101,2,None),(11,102,2,None)],slots
            assert conn.execute(text('SELECT status FROM "Transaction"')).scalar_one()=='COMPLETED'
        results.append({'path':'dispatcher' if dispatch else 'direct','observed_lock_wait':True,
                        'outcomes':outcomes,'ownership_intervals':slots})
    return results


def main():
    EVIDENCE.mkdir(exist_ok=True)
    ddl=candidate()
    (EVIDENCE/'public-schema-assessment-candidate.sql').write_text(
        '-- Assessment candidate only; not an approved deployment migration.\n'
        '-- Requires Supabase Auth/roles/extensions; see assessment report.\n'+ddl)
    catalog=json.loads((EVIDENCE/'supabase-catalog-2026-10-29.json').read_text())
    admin=psycopg2.connect(dbname='postgres',**LOCAL)
    admin.autocommit=True
    created=[]
    created_roles=[]
    engines=[]
    report={'scope':'Synthetic PostgreSQL 17.6; no deployed changes; auth.users/auth.uid are minimal SQL test fixtures.',
            'sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in [ROOT/'db/tables.sql',ROOT/'api/endpoints/transaction/transactionModel.py',
                                   *sorted((ROOT/'api/migrations').glob('*.sql'))]}}
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0] == 'otm-modernization-assessment-20261029-synthetic-only', 'Refusing unmarked database server'
            for role,attrs in [('otm_anon',''),('otm_authenticated',''),('otm_service','BYPASSRLS')]:
                cur.execute('CREATE ROLE '+role+' NOLOGIN '+attrs)
                created_roles.append(role)
        def new_database():
            name='otm_assessment_'+uuid4().hex
            with admin.cursor() as cur: cur.execute('CREATE DATABASE '+name)
            created.append(name)
            engine=engine_for(name)
            engines.append(engine)
            with engine.begin() as conn: conn.exec_driver_sql(PLATFORM)
            return name,engine
        name,base=new_database()
        with base.begin() as conn: conn.exec_driver_sql(ddl)
        with base.connect() as conn:
            expected=definitions(conn)
            report['source_vs_deployed']=diff(expected,catalog)
            for group, differences in report['source_vs_deployed'].items():
                assert not differences['candidate_only'] and not differences['deployed_only']
                for difference in differences['different']:
                    fields=[key for key in difference['candidate']
                            if difference['candidate'][key]!=difference['deployed'][key]]
                    assert group=='columns' and fields==['ordinal_position'], difference
            report['logical_definition_comparison']={'collected_properties':'match except ordinal positions',
                'ordinal_position_differences':len(report['source_vs_deployed']['columns']['different'])} 
        report['access']=access_tests(base,catalog)
        upgrades=[]
        # Validate both historical files on their explicit synthetic prerequisites.
        for old_name in (False,True):
            _,up=new_database()
            historical=re.sub(r'create table public\."SportSeasonSubdivision".*?;', '', ddl, flags=re.S|re.I)
            if old_name:
                historical=historical.replace('"seasonStart"','"esasonStart"')
            with up.begin() as conn: conn.exec_driver_sql(historical)
            with up.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
                for file in sorted((ROOT/'api/migrations').glob('*.sql')):
                    conn.exec_driver_sql(file.read_text())
            with up.connect() as conn:
                differences=diff(definitions(conn),expected)
                assert all(not rows for group in differences.values() for rows in group.values()),differences
            upgrades.append({'starting_column':'esasonStart' if old_name else 'seasonStart',
                             'subdivision':'initially absent','normalized_comparison':'matches source candidate'})
        report['historical_upgrade_fixtures']=upgrades
        report['trade_concurrency']=trade_tests(base,name)
        report['result']='PASS'
        (EVIDENCE/'postgres-assessment-2026-10-29.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
        print(json.dumps(report,indent=2,default=str))
    finally:
        for engine in engines: engine.dispose()
        with admin.cursor() as cur:
            for name in created:
                cur.execute('DROP DATABASE '+name+' WITH (FORCE)')
            for role in created_roles:
                cur.execute('DROP ROLE '+role)
        admin.close()


if __name__=='__main__':
    main()
