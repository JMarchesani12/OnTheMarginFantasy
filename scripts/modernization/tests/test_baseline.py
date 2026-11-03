"""Real PostgreSQL tests; only the marked disposable loopback server is accepted."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4

import psycopg2
from sqlalchemy import create_engine, text

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
ROOT=HERE.parents[1]
PACKAGE=ROOT/'db/baselines/20261029'


class BaselinePackageTests(unittest.TestCase):
    def test_checksums_and_order_are_versioned(self):
        self.assertTrue((PACKAGE/'manifest.json').is_file(), 'Versioned baseline manifest is missing')
        module=importlib.import_module('baseline')
        package=module.load_package(PACKAGE)
        self.assertEqual(package['version'],'20261029_observed_public_v1')
        self.assertEqual([p['path'] for p in package['steps']],['001_schema.sql','002_access.sql'])


class BaselineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin=psycopg2.connect(host='127.0.0.1',port=55439,user='postgres',dbname='postgres',connect_timeout=3)
        cls.admin.autocommit=True
        with cls.admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            if cur.fetchone()[0]!='otm-modernization-assessment-20261029-synthetic-only':
                raise RuntimeError('Refusing unmarked test server')
            cls.created_roles=[]
            for role,attrs in [('anon',''),('authenticated',''),('service_role','BYPASSRLS'),('supabase_admin','')]:
                cur.execute('CREATE ROLE '+role+' NOLOGIN '+attrs)
                cls.created_roles.append(role)

    @classmethod
    def tearDownClass(cls):
        with cls.admin.cursor() as cur:
            for role in cls.created_roles:
                cur.execute('DROP ROLE '+role)
        cls.admin.close()

    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('baseline'), 'Baseline runner is missing')
        self.module=importlib.import_module('baseline')
        self.name='otm_baseline_'+uuid4().hex
        with self.admin.cursor() as cur:cur.execute('CREATE DATABASE '+self.name)
        self.addCleanup(self.drop_database)
        self.engine=create_engine('postgresql+psycopg2://postgres@127.0.0.1:55439/'+self.name)
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as conn:
            conn.exec_driver_sql("""CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY);
                CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS
                $$ SELECT NULLIF(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
                GRANT USAGE ON SCHEMA auth TO anon,authenticated,service_role;
                CREATE EXTENSION pg_trgm WITH SCHEMA public;
                ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
                    GRANT ALL ON TABLES TO postgres,anon,authenticated,service_role;
                ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
                    GRANT ALL ON SEQUENCES TO postgres,anon,authenticated,service_role;
                ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public
                    GRANT EXECUTE ON FUNCTIONS TO postgres,anon,authenticated,service_role;""")

    def drop_database(self):
        with self.admin.cursor() as cur:cur.execute('DROP DATABASE '+self.name+' WITH (FORCE)')

    def apply(self,mode='initialize',package=PACKAGE):
        with self.engine.begin() as conn:return self.module.apply_baseline(conn,package,mode)

    def ledger(self):
        with self.engine.connect() as conn:
            return conn.execute(text('SELECT version,checksum,mode FROM app_migrations.baseline')).all()

    def test_blank_initialization_and_replay_converge(self):
        self.assertEqual(self.apply(),'initialized')
        self.assertEqual(self.apply(),'already_applied')
        self.assertEqual(len(self.ledger()),1)
        with self.engine.connect() as conn:
            self.module.verify_state(conn,self.module.load_package(PACKAGE))

    def test_concurrent_initialization_records_one_verified_baseline(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(self.apply) for _ in range(2)]
            results=sorted(f.result(timeout=10) for f in futures)
        self.assertEqual(results,['already_applied','initialized'])
        self.assertEqual(len(self.ledger()),1)

    def test_adoption_records_verified_state_without_recreating_tables(self):
        self.apply()
        with self.engine.begin() as conn:
            conn.exec_driver_sql('DROP SCHEMA app_migrations CASCADE')
            conn.exec_driver_sql('CREATE TABLE public.extra_object(id bigint)')
        with self.assertRaisesRegex(ValueError,'state'):
            self.apply('adopt')
        with self.engine.begin() as conn:conn.exec_driver_sql('DROP TABLE public.extra_object')
        self.assertEqual(self.apply('adopt'),'adopted')
        self.assertEqual(self.ledger()[0][2],'adopt')

    def test_initialization_does_not_replace_preexisting_custom_routine(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql("""CREATE FUNCTION public.rls_auto_enable() RETURNS event_trigger
                LANGUAGE plpgsql AS $$ BEGIN RAISE NOTICE 'existing'; END $$""")
        with self.assertRaisesRegex(ValueError,'empty'):
            self.apply()
        with self.engine.connect() as conn:
            definition=conn.execute(text("SELECT pg_get_functiondef('public.rls_auto_enable()'::regprocedure)")).scalar_one()
            self.assertIn('existing',definition)
            self.assertIsNone(conn.execute(text("SELECT to_regnamespace('app_migrations')")).scalar())

    def test_existing_schema_is_not_silently_initialized(self):
        self.apply()
        with self.engine.begin() as conn:conn.exec_driver_sql('DROP SCHEMA app_migrations CASCADE')
        with self.assertRaisesRegex(ValueError,'empty'):
            self.apply()
        self.assertEqual(self.apply('adopt'),'adopted')

    def test_schema_and_access_drift_reject_even_after_recorded_success(self):
        self.apply()
        for sql,undo in [('ALTER TABLE public."User" ADD COLUMN unexpected integer',
                         'ALTER TABLE public."User" DROP COLUMN unexpected'),
                        ('GRANT UPDATE ON public."User" TO PUBLIC',
                         'REVOKE UPDATE ON public."User" FROM PUBLIC')]:
            with self.subTest(sql=sql):
                with self.engine.begin() as conn:conn.exec_driver_sql(sql)
                with self.assertRaisesRegex(ValueError,'state'):
                    self.apply('adopt')
                with self.engine.begin() as conn:conn.exec_driver_sql(undo)
        self.assertEqual(len(self.ledger()),1)

    def test_untracked_privilege_and_routine_drift_is_rejected(self):
        self.apply()
        mutations=[
            ('CREATE FUNCTION public.unexpected() RETURNS int LANGUAGE sql AS $$ SELECT 1 $$',
             'DROP FUNCTION public.unexpected()'),
            ('ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT SELECT ON TABLES TO PUBLIC',
             'ALTER DEFAULT PRIVILEGES FOR ROLE postgres REVOKE SELECT ON TABLES FROM PUBLIC'),
            ('GRANT SELECT(email) ON public."User" TO anon',
             'REVOKE SELECT(email) ON public."User" FROM anon'),
            ('ALTER ROLE authenticated BYPASSRLS','ALTER ROLE authenticated NOBYPASSRLS')]
        for sql,undo in mutations:
            with self.subTest(sql=sql):
                with self.engine.begin() as conn:conn.exec_driver_sql(sql)
                try:
                    with self.assertRaisesRegex(ValueError,'state'):
                        self.apply('adopt')
                finally:
                    with self.engine.begin() as conn:conn.exec_driver_sql(undo)

    def test_hardening_refuses_global_grants_it_cannot_safely_revoke(self):
        self.apply()
        with self.engine.begin() as conn:
            conn.exec_driver_sql('ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT SELECT ON TABLES TO PUBLIC')
        with self.assertRaisesRegex(Exception,'global'):
            with self.engine.begin() as conn:
                conn.execute(text((ROOT/'db/proposals/mod004_browser_privileges.sql').read_text()))

    def test_disabled_foreign_key_triggers_reject_adoption(self):
        self.apply()
        with self.engine.begin() as conn:
            conn.exec_driver_sql('DROP SCHEMA app_migrations CASCADE')
            conn.exec_driver_sql('ALTER TABLE public."User" DISABLE TRIGGER ALL')
        with self.assertRaisesRegex(ValueError,'state'):
            self.apply('adopt')
        with self.engine.connect() as conn:
            self.assertIsNone(conn.execute(text("SELECT to_regnamespace('app_migrations')")).scalar())

    def test_unlogged_table_rejects_baseline_replay(self):
        self.apply()
        with self.engine.begin() as conn:
            conn.exec_driver_sql('ALTER TABLE public."TransactionVote" SET UNLOGGED')
        with self.assertRaisesRegex(ValueError,'state'):
            self.apply('adopt')

    def test_checksum_edit_is_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            import shutil
            copy=Path(tmp)/'package'
            shutil.copytree(PACKAGE,copy)
            with (copy/'001_schema.sql').open('a') as out:out.write('\n-- edited\n')
            with self.assertRaisesRegex(ValueError,'checksum'):
                self.apply(package=copy)
        with self.engine.connect() as conn:
            self.assertIsNone(conn.execute(text("SELECT to_regnamespace('app_migrations')")).scalar())

    def test_failed_install_rolls_back_schema_and_ledger(self):
        with self.engine.connect() as conn:
            transaction=conn.begin()
            self.module.apply_baseline(conn,PACKAGE,'initialize')
            transaction.rollback()
        with self.engine.connect() as conn:
            self.assertIsNone(conn.execute(text("SELECT to_regclass('public.\"User\"')")).scalar())
            self.assertIsNone(conn.execute(text("SELECT to_regnamespace('app_migrations')")).scalar())

    def test_failed_state_check_cannot_commit_partial_install(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql('ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT SELECT ON TABLES TO PUBLIC')
            with self.assertRaisesRegex(ValueError,'state'):
                self.module.apply_baseline(conn,PACKAGE,'initialize')
        with self.engine.connect() as conn:
            self.assertIsNone(conn.execute(text("SELECT to_regclass('public.\"User\"')")).scalar())
            self.assertIsNone(conn.execute(text("SELECT to_regnamespace('app_migrations')")).scalar())

    def test_conflicting_ledger_checksum_rejected(self):
        self.apply()
        with self.engine.begin() as conn:
            conn.exec_driver_sql("UPDATE app_migrations.baseline SET checksum=repeat('0',64)")
        with self.assertRaisesRegex(ValueError,'ledger'):
            self.apply('adopt')

    def test_hardening_and_recovery_are_separate_and_preserve_profile_reads(self):
        self.apply()
        with self.engine.begin() as conn:
            conn.exec_driver_sql("""INSERT INTO auth.users VALUES
                ('00000000-0000-4000-8000-000000000001'),('00000000-0000-4000-8000-000000000002');
                INSERT INTO public."User"(id,uuid,email) VALUES
                (1,'00000000-0000-4000-8000-000000000001','a@synthetic.test'),
                (2,'00000000-0000-4000-8000-000000000002','b@synthetic.test');""")
        hardening=ROOT/'db/proposals/mod004_browser_privileges.sql'
        recovery=ROOT/'db/proposals/mod004_browser_privileges_recovery.sql'
        self.assertTrue(hardening.is_file(),'Hardening proposal missing')
        with self.engine.begin() as conn:
            conn.exec_driver_sql(hardening.read_text())
            self.assertFalse(conn.execute(text("SELECT has_table_privilege('anon','public.\"School\"','TRUNCATE')")).scalar())
            self.assertTrue(conn.execute(text("SELECT has_table_privilege('authenticated','public.\"User\"','SELECT')")).scalar())
            self.assertTrue(conn.execute(text("SELECT has_table_privilege('service_role','public.\"School\"','TRUNCATE')")).scalar())
            catalog=json.loads((PACKAGE/'expected.json').read_text())
            for role in ('anon','authenticated'):
                for table in catalog['tables']:
                    for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN'):
                        actual=conn.execute(text('SELECT has_table_privilege(:role,:table,:privilege)'),
                            {'role':role,'table':'public."'+table['table_name']+'"','privilege':privilege}).scalar_one()
                        self.assertEqual(actual,role=='authenticated' and table['table_name']=='User' and privilege=='SELECT')
                for sequence in catalog['sequence_options']:
                    for privilege in ('USAGE','SELECT','UPDATE'):
                        self.assertFalse(conn.execute(text('SELECT has_sequence_privilege(:role,:sequence,:privilege)'),
                            {'role':role,'sequence':'public."'+sequence['sequencename']+'"','privilege':privilege}).scalar_one())
            conn.exec_driver_sql('SET LOCAL ROLE authenticated')
            conn.exec_driver_sql("SELECT set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000001',true)")
            self.assertEqual(list(conn.execute(text('SELECT id FROM public."User" ORDER BY id')).scalars()),[1])
            conn.exec_driver_sql('RESET ROLE')
            conn.exec_driver_sql('CREATE TABLE public.new_privilege_probe(id bigint GENERATED ALWAYS AS IDENTITY)')
            self.assertFalse(conn.execute(text("SELECT has_table_privilege('authenticated','public.new_privilege_probe','SELECT')")).scalar())
            conn.exec_driver_sql('DROP TABLE public.new_privilege_probe')
            conn.exec_driver_sql('GRANT CREATE ON SCHEMA public TO supabase_admin')
            conn.exec_driver_sql('SET LOCAL ROLE supabase_admin')
            conn.exec_driver_sql('CREATE TABLE public.admin_privilege_probe(id bigint GENERATED ALWAYS AS IDENTITY)')
            conn.exec_driver_sql('RESET ROLE')
            self.assertFalse(conn.execute(text("SELECT has_table_privilege('authenticated','public.admin_privilege_probe','SELECT')")).scalar())
            self.assertTrue(conn.execute(text("SELECT has_table_privilege('service_role','public.admin_privilege_probe','SELECT')")).scalar())
            conn.exec_driver_sql('DROP TABLE public.admin_privilege_probe')
            conn.exec_driver_sql('REVOKE CREATE ON SCHEMA public FROM supabase_admin')
            conn.exec_driver_sql(recovery.read_text())
            self.module.verify_state(conn,self.module.load_package(PACKAGE))


if __name__=='__main__':unittest.main(verbosity=2)
