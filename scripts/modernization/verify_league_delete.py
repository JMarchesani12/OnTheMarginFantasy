"""League deletion on marked synthetic loopback PostgreSQL; no configured DSN."""
import hashlib,json,threading,time
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL,ROOT,engine_for
from verify_member_removal import listing_tests,creation_tests,approval_tests,profile_tests,tests as removal_tests
from actors import UserActor
from endpoints.league.administration.service import LeagueAdminService
from endpoints.league.leagueModel import LeagueModel

FIXTURE='''DROP SCHEMA public CASCADE; CREATE SCHEMA public;
CREATE TABLE "League" (id bigint PRIMARY KEY,name text,commissioner bigint);
INSERT INTO "League" VALUES (10,'Alice League',1),(20,'Bob League',2);
CREATE TABLE "LeagueMember" (id bigint PRIMARY KEY,"leagueId" bigint REFERENCES "League"(id) ON DELETE CASCADE,"userId" bigint,"teamName" text);
INSERT INTO "LeagueMember" VALUES (11,10,1,'Alice'),(12,10,2,'Bob'),(21,20,2,'Other');
CREATE TABLE "LeagueJoinRequest" (id bigint PRIMARY KEY,"leagueId" bigint REFERENCES "League"(id) ON DELETE CASCADE);
INSERT INTO "LeagueJoinRequest" VALUES (101,10),(201,20);
CREATE TABLE "Week" (id bigint PRIMARY KEY,"leagueId" bigint REFERENCES "League"(id) ON DELETE CASCADE);
INSERT INTO "Week" VALUES (1001,10),(2001,20);
CREATE TABLE "WeeklyScores" (id bigint PRIMARY KEY,"weekId" bigint REFERENCES "Week"(id) ON DELETE CASCADE,points integer);
INSERT INTO "WeeklyScores" VALUES (1,1001,10),(2,2001,20);'''


def tests(engine,database):
    service=LeagueAdminService(engine);actor=UserActor(1,'alice')
    def reset():
        with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    def state():
        with engine.connect() as conn:
            return {table:[dict(r._mapping) for r in conn.execute(text(f'SELECT * FROM "{table}" ORDER BY id'))]
                    for table in ('League','LeagueMember','LeagueJoinRequest','Week','WeeklyScores')}
    reset();before=state()
    for who,league,error in ((UserActor(2,'bob'),10,PermissionError),(actor,20,PermissionError),(actor,999,ValueError)):
        try:service.delete(who,league)
        except error:pass
        else:raise AssertionError('Deletion authority/missing guard bypass')
        assert state()==before
    assert service.delete(actor,10)=={'deletedLeagueId':10,'deletedLeagueName':'Alice League'}
    after=state()
    assert after=={'League':[before['League'][1]],'LeagueMember':[before['LeagueMember'][2]],
                   'LeagueJoinRequest':[before['LeagueJoinRequest'][1]],'Week':[before['Week'][1]],'WeeklyScores':[before['WeeklyScores'][1]]}
    try:service.delete(actor,10)
    except ValueError:pass
    else:raise AssertionError('Deletion replay accepted')
    assert state()==after
    reset();before=state()
    with engine.begin() as conn:conn.exec_driver_sql('CREATE TABLE dependency (league bigint REFERENCES "League"(id)); INSERT INTO dependency VALUES (10)')
    try:service.delete(actor,10)
    except DBAPIError:pass
    else:raise AssertionError('Real FK restriction missing')
    assert state()==before
    reset();before=state()
    def fail(conn,cursor,statement,params,context,many):
        if 'DELETE FROM "League"' in statement:raise RuntimeError('synthetic post-delete failure')
    event.listen(engine,'after_cursor_execute',fail)
    try:
        try:service.delete(actor,10)
        except RuntimeError:pass
        else:raise AssertionError('Post-delete failure missing')
    finally:event.remove(engine,'after_cursor_execute',fail)
    assert state()==before
    with engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION fail_delete_commit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic deferred deletion failure'; END $$;
            CREATE CONSTRAINT TRIGGER delete_commit AFTER DELETE ON "League"
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fail_delete_commit();''')
    try:service.delete(actor,10)
    except DBAPIError:pass
    else:raise AssertionError('Deferred delete failure missing')
    assert state()==before
    reset();before=state()
    with engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION suppress_delete() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN UPDATE "LeagueMember" SET "teamName"='synthetic side effect' WHERE "leagueId"=OLD.id; RETURN NULL; END $$;
            CREATE TRIGGER suppress_delete BEFORE DELETE ON "League" FOR EACH ROW EXECUTE FUNCTION suppress_delete();''')
    try:service.delete(actor,10)
    except RuntimeError as exc:assert str(exc)=='Failed to delete league'
    else:raise AssertionError('Missing DELETE RETURNING guard')
    assert state()==before

    concurrency=[]
    for facade in (False,True):
        reset();first=engine_for(database,'otm-delete-first');second=engine_for(database,'otm-delete-second')
        locked,release=threading.Event(),threading.Event();outcomes={};locks=[]
        def hold(conn,cursor,statement,params,context,many):
            if 'FOR UPDATE' in statement:
                locks.append('league');locked.set()
                if not release.wait(10):raise RuntimeError('Synthetic deletion lock timeout')
        event.listen(first,'after_cursor_execute',hold)
        def delete(label,owner):
            try:
                if facade:
                    model=LeagueModel.__new__(LeagueModel);model.db=owner
                    result=model.delete_league(10,1)
                else:result=LeagueAdminService(owner).delete(actor,10)
                outcomes[label]=['deleted',result['deletedLeagueId']]
            except Exception as exc:outcomes[label]=[type(exc).__name__,str(exc)]
        a=threading.Thread(target=delete,args=('first',first),daemon=True)
        b=threading.Thread(target=delete,args=('second',second),daemon=True);a.start()
        try:
            assert locked.wait(5),'First deletion failed to lock';b.start()
            blocked=False;deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                with engine.connect() as conn:
                    blocked=conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE application_name='otm-delete-second' AND wait_event_type='Lock' AND cardinality(pg_blocking_pids(pid))>0)")).scalar_one()
                if blocked:break
                time.sleep(.02)
            assert blocked,'Competing deletion failed to wait'
        finally:
            release.set();a.join(10)
            if b.ident is not None:b.join(10)
            event.remove(first,'after_cursor_execute',hold);first.dispose();second.dispose()
        assert not a.is_alive() and not b.is_alive()
        assert locks==['league'] and outcomes=={'first':['deleted',10],'second':['ValueError','League not found']},outcomes
        assert len(state()['League'])==1 and state()['WeeklyScores']==[{'id':2,'weekId':2001,'points':20}]
        concurrency.append({'path':'legacy_facade' if facade else 'service','mode':'competing_deletion','observed_lock_wait':True,'outcomes':outcomes})

        reset();before=state();contender=engine_for(database,'otm-delete-second');outcomes={}
        thread=threading.Thread(target=delete,args=('revoked',contender),daemon=True)
        try:
            with engine.begin() as conn:
                conn.execute(text('UPDATE "League" SET commissioner=2 WHERE id=10'))
                thread.start();blocked=False;deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    with engine.connect() as observer:
                        blocked=observer.execute(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE application_name='otm-delete-second' AND wait_event_type='Lock' AND cardinality(pg_blocking_pids(pid))>0)")).scalar_one()
                    if blocked:break
                    time.sleep(.02)
                assert blocked,'Deletion failed to wait on commissioner update'
        finally:
            if thread.ident is not None:thread.join(10)
            contender.dispose()
        assert not thread.is_alive() and outcomes=={'revoked':['PermissionError','Only the commissioner can delete this league']},outcomes
        before['League'][0]['commissioner']=2;assert state()==before
        concurrency.append({'path':'legacy_facade' if facade else 'service','mode':'commissioner_revocation','observed_lock_wait':True,'outcomes':outcomes})
    reset();model=LeagueModel.__new__(LeagueModel);model.db=engine
    assert model.delete_league(10,'1')=={'deletedLeagueId':10,'deletedLeagueName':'Alice League'}
    return {'authority_scope_projection_direct_multilevel_cascades':'PASS','real_fk_post_delete_commit_rollback':'PASS',
            'suppressed_delete_return_guard_rollback':'PASS','legacy_coercion':'PASS','concurrent_deletion':concurrency}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_league_delete_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-league-delete')
        prior={'listing_cancellation':listing_tests(engine,name),'creation_denial':creation_tests(engine,name),
               'approval':approval_tests(engine,name),'member_profile':profile_tests(engine,name),'member_removal':removal_tests(engine,name)}
        removal=tests(engine,name)
        files=['api/endpoints/league/'+f for f in ('administration/service.py','administration/repository.py','members/service.py','members/repository.py','admission/service.py','admission/repository.py','admission/contracts.py','leagueModel.py','leagueEndpoints.py')]
        files+=['api/actors.py']+['scripts/modernization/'+f for f in ('verify_admission_slice.py','verify_admission_create_deny.py','verify_admission_approval.py','verify_member_profile.py','verify_member_removal.py','verify_league_delete.py')]
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database','prior_slices_rerun':prior,
                'league_deletion':removal,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-league-delete-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
