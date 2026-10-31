"""Global lifecycle precedence/atomicity on marked synthetic PostgreSQL."""
import hashlib,json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL,ROOT,engine_for
from verify_member_summary import listing_tests,creation_tests,approval_tests,profile_tests,removal_tests,deletion_tests,settings_tests,league_creation_tests,rules_tests,conference_tests,discovery_tests,detail_tests,tests as summary_tests
from actors import UserActor
from endpoints.league.lifecycle.service import LeagueLifecycleService
from endpoints.league.reads.service import LeagueReadService
from endpoints.league.leagueModel import LeagueModel

FIXTURE='''DROP SCHEMA public CASCADE; CREATE SCHEMA public;
CREATE TABLE "League" (id bigint PRIMARY KEY,status text,"updatedAt" timestamptz,"draftDate" timestamptz,sport bigint,"seasonYear" integer,commissioner bigint);
CREATE TABLE "DraftState" ("leagueId" bigint,status text);
CREATE TABLE "SportSeason" ("sportId" bigint,"seasonYear" integer,"seasonStart" date,"seasonEnd" date);
INSERT INTO "SportSeason" VALUES (1,2026,current_date+10,current_date+30),(2,2026,current_date-10,current_date+10),
(3,2026,current_date-30,current_date-10),(4,2026,current_date,current_date+10),(5,2026,current_date-10,current_date);
INSERT INTO "League" VALUES
(1,'Unknown','2000-01-01',now()+interval '2 days',1,2026,1),
(2,'Unknown','2000-01-01',now()+interval '2 days',1,2026,1),
(3,'Unknown','2000-01-01',now()+interval '2 days',1,2026,1),
(4,'Unknown','2000-01-01',now()+interval '2 days',1,2026,1),
(5,'Unknown','2000-01-01',NULL,2,2026,1),(6,'Unknown','2000-01-01',now()+interval '2 days',3,2026,1),
(7,'Unknown','2000-01-01',now()+interval '2 days',3,2026,1),(8,'Completed','2000-01-01',NULL,2,2026,1),
(9,'Pre-Draft','2000-01-01',now()+interval '2 days',1,2026,1),(10,'Custom','2000-01-01',NULL,99,2026,1),
(11,'Custom','2000-01-01',NULL,2,2025,1),(12,'Unknown','2000-01-01',NULL,4,2026,1),
(13,'Unknown','2000-01-01',NULL,5,2026,1),(14,NULL,'2000-01-01',NULL,3,2026,1);
INSERT INTO "DraftState" VALUES (2,'live'),(3,'paused'),(4,'complete'),(6,'live'),(7,'complete');
CREATE TABLE "LeagueMember" ("leagueId" bigint,"userId" bigint);
CREATE TABLE "Week" (id bigint,"leagueId" bigint,"weekNumber" integer,"startDate" timestamptz,"endDate" timestamptz);'''
EXPECTED={1:'Pre-Draft',2:'Drafting',3:'Drafting',4:'Post-Draft',5:'In-Season',6:'Completed',7:'Completed',
          8:'Completed',9:'Pre-Draft',10:'Custom',11:'Custom',12:'In-Season',13:'In-Season',14:None}


def tests(engine,database):
    service=LeagueLifecycleService(engine)
    def reset():
        with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    def state():
        with engine.connect() as conn:return [dict(r._mapping) for r in conn.execute(text('SELECT * FROM "League" ORDER BY id'))]
    reset();before=state();assert service.synchronize_for_job() is None
    after=state();assert {r['id']:r['status'] for r in after}==EXPECTED
    for row,old in zip(after,before):
        if row['id'] in (8,9,10,11,14):assert row==old
        else:assert row['updatedAt']>old['updatedAt']
    service.synchronize_for_job();assert {r['id']:r['status'] for r in state()}==EXPECTED
    for phase in range(1,6):
        reset();before=state();count=[]
        def fail(conn,cursor,statement,params,context,many):
            if 'UPDATE "League"' in statement:
                count.append(True)
                if len(count)==phase:raise RuntimeError('synthetic post-lifecycle-phase failure')
        event.listen(engine,'after_cursor_execute',fail)
        try:
            try:service.synchronize_for_job()
            except RuntimeError:pass
            else:raise AssertionError('Phase failure swallowed')
        finally:event.remove(engine,'after_cursor_execute',fail)
        assert state()==before
    reset();before=state()
    with engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION reject_in_season() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.status='In-Season' THEN RAISE EXCEPTION 'synthetic actual statement failure'; END IF; RETURN NEW; END $$;
            CREATE TRIGGER reject_transition BEFORE UPDATE ON "League" FOR EACH ROW EXECUTE FUNCTION reject_in_season();''')
    try:service.synchronize_for_job()
    except DBAPIError:pass
    else:raise AssertionError('Real statement failure missing')
    assert state()==before
    reset();before=state()
    with engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION fail_lifecycle_commit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic deferred lifecycle failure'; END $$;
            CREATE CONSTRAINT TRIGGER lifecycle_commit AFTER UPDATE ON "League"
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fail_lifecycle_commit();''')
    try:service.synchronize_for_job()
    except DBAPIError:pass
    else:raise AssertionError('Deferred lifecycle failure missing')
    assert state()==before
    reset();model=LeagueModel.__new__(LeagueModel);model.db=engine
    assert model.sync_due_league_statuses() is None
    assert {r['id']:r['status'] for r in state()}==EXPECTED
    reset()
    row=LeagueReadService(engine).details(UserActor(1,'alice'),5,model.sync_due_league_statuses)
    assert row['status']=='In-Season' and {r['id']:r['status'] for r in state()}==EXPECTED
    assert model.get_league(5)['status']=='In-Season'
    return {'native_order_precedence_date_boundaries_sport_year_null_unchanged':'PASS',
            'repeat_status_convergence':'PASS','each_post_phase_statement_and_deferred_commit_rollback':'PASS',
            'db_only_legacy_none_and_real_read_callback':'PASS',
            'scope_limit':'Existing global read-time writes and intermediate timestamp updates preserved; no concurrency redesign'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_league_lifecycle_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-league-lifecycle')
        prior={'listing_cancellation':listing_tests(engine,name),'creation_denial':creation_tests(engine,name),
               'approval':approval_tests(engine,name),'member_profile':profile_tests(engine,name),'member_removal':removal_tests(engine,name),'league_deletion':deletion_tests(engine,name),'league_settings':settings_tests(engine,name),'league_creation':league_creation_tests(engine,name),'league_rules':rules_tests(engine,name),'league_conferences':conference_tests(engine,name),'league_discovery':discovery_tests(engine,name),'league_details':detail_tests(engine,name),'member_summary':summary_tests(engine,name)}
        lifecycle=tests(engine,name)
        files=['api/endpoints/league/'+f for f in ('lifecycle/service.py','lifecycle/repository.py','reads/service.py','reads/repository.py','administration/service.py','administration/repository.py','members/service.py','members/repository.py','admission/service.py','admission/repository.py','admission/contracts.py','leagueModel.py','leagueEndpoints.py')]
        files+=['api/endpoints/schedule/scheduleModel.py','api/actors.py','api/rules/leagueRules.py','api/utils/authorization.py']+['scripts/modernization/'+f for f in ('verify_admission_slice.py','verify_admission_create_deny.py','verify_admission_approval.py','verify_member_profile.py','verify_member_removal.py','verify_league_delete.py','verify_league_settings.py','verify_league_creation.py','verify_league_rules_read.py','verify_league_conferences.py','verify_league_discovery.py','verify_league_details.py','verify_member_summary.py','verify_league_lifecycle.py')]
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database','prior_slices_rerun':prior,
                'league_lifecycle':lifecycle,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-league-complete-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
