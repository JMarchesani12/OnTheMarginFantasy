"""Exact owner-only SQL acceptance; dedicated loopback Docker DB, no dotenv."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import tempfile
from uuid import uuid4

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / 'db/changes/20261118_browser_privileges'
IMAGE = 'sha256:00bc86618629af00d2937fdc5a5d63db3ff8450acf52f0636ec813c7f4902929'


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, stderr=subprocess.PIPE).strip()


def verify():
    assert (PACKAGE / 'apply.sql').is_file(), 'Owner-scoped SQL package is not prepared'
    before = json.loads((PACKAGE / 'before.json').read_text())
    after = json.loads((PACKAGE / 'after.json').read_text())
    manifest = json.loads((PACKAGE / 'manifest.json').read_text())
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest() == digest
    query = (PACKAGE / 'state-query.sql').read_text()
    apply = (PACKAGE / 'apply.sql').read_text()
    recovery = (PACKAGE / 'recovery.sql').read_text()
    name = 'otm-mod004-owner-' + uuid4().hex
    label = 'otm.task=mod004-owner-20261118'
    started = False
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'result': 'RUNNING',
              'scope': 'Synthetic dedicated PostgreSQL container only; no configured credentials or hosted operations',
              'image': IMAGE, 'cases': [], 'sources': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in [Path(__file__), *sorted(PACKAGE.glob('*'))] if p.is_file()}}
    try:
        docker('run', '--detach', '--rm', '--pull=never', '--name', name, '--label', label,
               '--env', 'POSTGRES_USER=otm_fixture_admin', '--env', 'POSTGRES_HOST_AUTH_METHOD=trust',
               '--publish', '127.0.0.1::5432', IMAGE)
        started = True
        port = int(docker('port', name, '5432/tcp').split(':')[-1])
        params = dict(host='127.0.0.1', port=port, user='otm_fixture_admin', connect_timeout=3)
        deadline = time.monotonic() + 30
        while True:
            try:
                admin = psycopg2.connect(dbname='postgres', **params)
                break
            except psycopg2.OperationalError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Disposable PostgreSQL startup timeout') from None
                time.sleep(.2)
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute('CREATE ROLE postgres LOGIN NOSUPERUSER BYPASSRLS; CREATE ROLE anon NOLOGIN; '
                        'CREATE ROLE authenticated NOLOGIN; CREATE ROLE service_role NOLOGIN BYPASSRLS; '
                        'CREATE ROLE supabase_admin NOLOGIN; CREATE ROLE fixture_parent NOLOGIN')

        def fixture():
            db = 'fixture_' + uuid4().hex
            with admin.cursor() as cur:
                cur.execute(sql.SQL('CREATE DATABASE {} OWNER postgres').format(sql.Identifier(db)))
            fixture_admin = psycopg2.connect(dbname=db, **params)
            fixture_admin.autocommit = True
            with fixture_admin.cursor() as c:
                for creator in ('postgres', 'supabase_admin'):
                    for kind in ('TABLES', 'SEQUENCES', 'FUNCTIONS'):
                        c.execute(f'ALTER DEFAULT PRIVILEGES FOR ROLE {creator} IN SCHEMA public GRANT ALL ON {kind} TO postgres,anon,authenticated,service_role')
            owner_params = {**params, 'user': 'postgres', 'dbname': db}
            owner = psycopg2.connect(**owner_params)
            owner.autocommit = True
            with owner.cursor() as c:
                c.execute('SET ROLE pg_database_owner; GRANT USAGE ON SCHEMA public TO postgres,anon,authenticated,service_role; RESET ROLE')
                c.execute("CREATE SCHEMA auth; CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT NULLIF(current_setting('request.jwt.claim.sub',true),'')::uuid $$; GRANT USAGE ON SCHEMA auth TO anon,authenticated,service_role")
                for relation in before['relations']:
                    ident = sql.Identifier('public', relation['name'])
                    if relation['kind'] == 'S':
                        c.execute(sql.SQL('CREATE SEQUENCE {}').format(ident))
                    else:
                        c.execute(sql.SQL('CREATE TABLE {} (id integer, uuid uuid)').format(ident))
                        if relation['rls']:
                            c.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(ident))
                c.execute('CREATE POLICY "read own user row" ON public."User" FOR SELECT TO PUBLIC USING (uuid = auth.uid())')
                c.execute('INSERT INTO public."User" VALUES (1,\'00000000-0000-0000-0000-000000000001\')')
                c.execute("SELECT rolsuper,pg_has_role(current_user,'supabase_admin','MEMBER') FROM pg_roles WHERE rolname=current_user")
                assert c.fetchone() == (False, False), 'Fixture owner must lack platform authority'
            return db, owner, fixture_admin

        def state(conn):
            with conn.cursor() as c:
                c.execute(query)
                return c.fetchone()[0]

        def execute(conn, statement):
            try:
                with conn.cursor() as c:
                    c.execute(statement)
            except Exception:
                with conn.cursor() as c:
                    c.execute('ROLLBACK')
                raise

        def refused(conn, statement):
            try:
                execute(conn, statement)
            except psycopg2.Error:
                return
            raise AssertionError('Unsafe transition was accepted')

        dirty = {
            'extra_table': 'CREATE TABLE public.unreviewed(id integer)',
            'column_grant': 'GRANT SELECT(id) ON public."User" TO anon',
            'global_defaults': 'ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT SELECT ON TABLES TO anon',
            'unexpected_acl': 'REVOKE SELECT ON public."User" FROM authenticated',
            'unexpected_policy': 'CREATE POLICY extra ON public."User" FOR SELECT TO anon USING (true)',
            'extra_view': 'CREATE VIEW public.unreviewed AS SELECT 1 AS id',
        }
        for case in ['clean', *dirty, 'postcondition_failure', 'recovery_drift', 'recovery_new_object', 'browser_inheritance', 'browser_bypassrls']:
            db, owner, fixture_admin = fixture()
            try:
                initial = state(owner)
                assert initial == before, 'Synthetic initial catalog mismatch: ' + json.dumps({k: {'actual': initial[k], 'expected': before[k]} for k in before if initial[k] != before[k]})
                if case in ('browser_inheritance', 'browser_bypassrls'):
                    alteration = ('GRANT fixture_parent TO anon' if case == 'browser_inheritance' else 'ALTER ROLE anon BYPASSRLS')
                    restoration = ('REVOKE fixture_parent FROM anon' if case == 'browser_inheritance' else 'ALTER ROLE anon NOBYPASSRLS')
                    with fixture_admin.cursor() as c:
                        c.execute(alteration)
                    try:
                        altered = state(owner)
                        refused(owner, apply)
                        assert state(owner) == altered
                    finally:
                        with fixture_admin.cursor() as c:
                            c.execute(restoration)
                elif case in dirty:
                    execute(owner, dirty[case])
                    altered = state(owner)
                    refused(owner, apply)
                    assert state(owner) == altered, 'Refusal changed privileges'
                elif case == 'postcondition_failure':
                    broken = apply.replace('REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, anon, authenticated;', '-- injected missing sequence revoke')
                    assert broken != apply
                    refused(owner, broken)
                    assert state(owner) == before, 'Failed postcondition did not roll back'
                else:
                    execute(owner, apply)
                    assert state(owner) == after
                    refused(owner, apply)
                    assert state(owner) == after, 'Replay mutated hardened state'
                    if case in ('recovery_drift', 'recovery_new_object'):
                        execute(owner, 'GRANT SELECT ON public."User" TO authenticated' if case == 'recovery_drift' else 'CREATE TABLE public.unreviewed(id integer)')
                        altered = state(owner)
                        refused(owner, recovery)
                        assert state(owner) == altered
                    else:
                        with fixture_admin.cursor() as c:
                            for role in ('anon', 'authenticated'):
                                for command in ('SELECT * FROM public."User"', 'TRUNCATE public."User"', 'SELECT nextval(\'public."User_id_seq"\')'):
                                    c.execute('SET ROLE ' + role)
                                    try:
                                        c.execute(command)
                                    except psycopg2.errors.InsufficientPrivilege:
                                        pass
                                    else:
                                        raise AssertionError('Browser operation allowed')
                                    finally:
                                        c.execute('RESET ROLE')
                            c.execute('SET ROLE service_role')
                            c.execute('SELECT count(*) FROM public."User"')
                            assert c.fetchone()[0] == 1, 'Service role lost seeded data'
                            c.execute('RESET ROLE')
                        execute(owner, 'CREATE TABLE public.future_owner(id integer); CREATE SEQUENCE public.future_owner_seq')
                        with owner.cursor() as c:
                            c.execute("SELECT has_table_privilege('anon','public.future_owner','SELECT'), has_table_privilege('authenticated','public.future_owner','TRUNCATE'), has_sequence_privilege('anon','public.future_owner_seq','USAGE')")
                            assert c.fetchone() == (False, False, False)
                        execute(owner, 'DROP TABLE public.future_owner; DROP SEQUENCE public.future_owner_seq')
                        with fixture_admin.cursor() as c:
                            c.execute('GRANT CREATE ON SCHEMA public TO supabase_admin; SET ROLE supabase_admin; CREATE TABLE public.future_provider(id integer); RESET ROLE')
                            c.execute("SELECT has_table_privilege('anon','public.future_provider','SELECT')")
                            assert c.fetchone()[0], 'Provider limitation must remain visible'
                            c.execute('DROP TABLE public.future_provider; REVOKE CREATE ON SCHEMA public FROM supabase_admin')
                        assert state(owner) == after
                        execute(owner, recovery)
                        assert state(owner) == before, 'Recovery is not exact'
                        refused(owner, recovery)
                report['cases'].append({'case': case, 'result': 'PASS'})
            finally:
                owner.close()
                fixture_admin.close()
                with admin.cursor() as c:
                    c.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(db)))
        admin.close()
        report['result'] = 'PASS'
    except BaseException:
        report['result'] = 'FAILED'
        raise
    finally:
        if started:
            info = json.loads(docker('inspect', name))[0]
            assert info['Image'] == IMAGE and info['Config']['Labels']['otm.task'] == 'mod004-owner-20261118'
            docker('rm', '--force', name)
            report['container_removed'] = True
        report['completed_at'] = datetime.now(timezone.utc).isoformat()
        path = Path(tempfile.mkdtemp(prefix='otm-privilege-test-'))/'result.json'
        path.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'result': report['result'], 'cases': len(report['cases']), 'evidence': str(path)}))


if __name__ == '__main__':
    verify()
