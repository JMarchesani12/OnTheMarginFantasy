"""Member updates on marked disposable PostgreSQL; never configured DSN/.env."""
import hashlib,json,threading,time
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL,ROOT,engine_for
from verify_admission_slice import tests as listing_tests
from verify_admission_create_deny import current_tests as creation_tests
from verify_admission_approval import tests as approval_tests
from actors import UserActor
from endpoints.league.member_service import MemberService
from endpoints.league.leagueModel import LeagueModel

FIXTURE='''DROP SCHEMA public CASCADE; CREATE SCHEMA public;
CREATE TABLE "LeagueMember" (id bigint PRIMARY KEY,"leagueId" bigint,"userId" bigint,
    "teamName" text,"draftOrder" integer,"seasonPoints" integer,"createdAt" timestamptz DEFAULT now());
INSERT INTO "LeagueMember" (id,"leagueId","userId","teamName","draftOrder","seasonPoints")
    VALUES (11,10,1,'Alice',1,10),(12,10,2,'Bob',2,20),(21,20,2,'Bob Other',1,30);'''


def tests(engine,database):
    with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    service=MemberService(engine);actor=UserActor(1,'alice')
    def state():
        with engine.connect() as conn:return [dict(r._mapping) for r in conn.execute(text('SELECT * FROM "LeagueMember" ORDER BY id'))]
    before=state();name=" O'Brien :teamName; -- "
    assert service.rename(actor,11,name)=={**before[0],'teamName':name}
    for target in (12,21,999):
        prior=state()
        try:service.rename(actor,target,'Stolen')
        except LookupError:pass
        else:raise AssertionError('Foreign/missing target renamed')
        assert state()==prior
    before=state();row=service.update_for_job(12,{'userId':1,'leagueId':20,'teamName':name,'draftOrder':4,'seasonPoints':99})
    assert row=={**before[1],'teamName':name,'draftOrder':4,'seasonPoints':99}
    for operation in (lambda:service.rename(actor,11,'Failed'),lambda:service.update_for_job(11,{'seasonPoints':999})):
        before=state()
        def fail(conn,cursor,statement,params,context,many):
            if 'UPDATE "LeagueMember"' in statement:raise RuntimeError('synthetic post-update failure')
        event.listen(engine,'after_cursor_execute',fail)
        try:
            try:operation()
            except RuntimeError:pass
            else:raise AssertionError('Post-update failure did not propagate')
        finally:event.remove(engine,'after_cursor_execute',fail)
        assert state()==before
    with engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION fail_member_commit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic deferred member failure'; END $$;
            CREATE CONSTRAINT TRIGGER member_commit AFTER UPDATE ON "LeagueMember"
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fail_member_commit();''')
    for operation in (lambda:service.rename(actor,11,'Failed'),lambda:service.update_for_job(11,{'seasonPoints':999})):
        before=state()
        try:operation()
        except DBAPIError:pass
        else:raise AssertionError('Deferred commit failure did not propagate')
        assert state()==before
    with engine.begin() as conn:conn.exec_driver_sql('DROP TRIGGER member_commit ON "LeagueMember"')
    waits=[]
    for facade in (False,True):
        with engine.begin() as conn:conn.execute(text('UPDATE "LeagueMember" SET "userId"=1 WHERE id=11'))
        contender=engine_for(database,'otm-member-rename');outcomes=[]
        def rename():
            try:
                if facade:
                    model=LeagueModel.__new__(LeagueModel);model.db=contender
                    model.update_owned_league_member(11,1,'Stolen after revocation')
                else:MemberService(contender).rename(actor,11,'Stolen after revocation')
                outcomes.append('unexpected success')
            except Exception as exc:outcomes.append(type(exc).__name__)
        thread=threading.Thread(target=rename,daemon=True)
        try:
            with engine.begin() as conn:
                conn.execute(text('UPDATE "LeagueMember" SET "userId"=2 WHERE id=11'))
                thread.start();blocked=False;deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    blocked=conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE application_name='otm-member-rename' AND wait_event_type='Lock' AND cardinality(pg_blocking_pids(pid))>0)")).scalar_one()
                    if blocked:break
                    # pg_stat_activity can cache snapshots inside a transaction.
                    conn.execute(text('SELECT pg_stat_clear_snapshot()'))
                    time.sleep(.02)
                assert blocked,'Rename did not wait on ownership update'
        finally:
            if thread.ident is not None:thread.join(10)
            contender.dispose()
        assert not thread.is_alive() and outcomes==['LookupError'],outcomes
        assert state()[0]['teamName']==name
        waits.append({'path':'legacy_facade' if facade else 'service','observed_lock_wait':True,'outcomes':outcomes})
    model=LeagueModel.__new__(LeagueModel);model.db=engine
    assert model.update_owned_league_member(11,2,'')['teamName']==''
    assert model.update_league_member(12,{'seasonPoints':17})['seasonPoints']==17
    return {'projection_bound_values_owner_scope':'PASS','trusted_allowlist_and_legacy_compatibility':'PASS',
            'post_update_and_deferred_commit_rollback':'PASS','ownership_revocation':waits}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_member_profile_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-member-profile')
        prior={'listing_cancellation':listing_tests(engine,name),'creation_denial':creation_tests(engine,name),'approval':approval_tests(engine,name)}
        member=tests(engine,name)
        files=['api/endpoints/league/'+f for f in ('member_service.py','member_repository.py','admission_service.py','admission_repository.py','contracts.py','leagueModel.py','leagueEndpoints.py')]
        files+=['api/actors.py','scripts/modernization/'+ 'verify_admission_slice.py','scripts/modernization/verify_admission_create_deny.py','scripts/modernization/verify_admission_approval.py','scripts/modernization/verify_member_profile.py']
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database','admission_rerun':prior,'member_profile':member,
            'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-member-profile-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
