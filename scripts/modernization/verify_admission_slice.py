"""Admission list/cancel on marked disposable PostgreSQL; never .env/DSN."""
import hashlib
import json
import threading
import time
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL,ROOT,engine_for
from actors import UserActor
from endpoints.league.admission.service import AdmissionService
from endpoints.league.admission.contracts import AdmissionDenied,AdmissionRejected
from endpoints.league.leagueModel import LeagueModel

FIXTURE='''
CREATE TABLE "User" (id bigint PRIMARY KEY,email text,"displayName" text);
INSERT INTO "User" VALUES (1,'alice@example.test','Alice'),(2,'bob@example.test','Bob'),(3,'other@example.test','Other');
CREATE TABLE "League" (id bigint PRIMARY KEY,commissioner bigint);
INSERT INTO "League" VALUES (10,1),(20,2);
CREATE TABLE "LeagueJoinRequest" (id bigint PRIMARY KEY,"createdAt" timestamptz,"leagueId" bigint,"userId" bigint,
    status text,message text,"resolvedAt" timestamptz,"resolvedByUserId" bigint);
INSERT INTO "LeagueJoinRequest" VALUES (100,'2026-10-27',10,2,'PENDING','Bob private',NULL,NULL),
    (101,'2026-10-28',10,3,'DENIED','Other private','2026-10-28',1),
    (200,'2026-10-28',20,1,'PENDING','Alice private',NULL,NULL);
'''


def tests(engine,database):
    with engine.begin() as conn: conn.exec_driver_sql(FIXTURE)
    service=AdmissionService(engine)
    rows=service.list_requests(UserActor(1,'alice'),10)
    assert [r['id'] for r in rows]==[101,100],rows
    assert set(rows[0])=={'id','createdAt','leagueId','userId','status','message','resolvedAt','resolvedByUserId','userEmail','userDisplayName'}
    assert rows[1]['userEmail']=='bob@example.test'
    assert [r['id'] for r in service.list_requests(UserActor(1,'alice'),10,'PENDING')]==[100]
    for actor,league,error in ((UserActor(2,'bob'),10,AdmissionDenied),(UserActor(1,'alice'),999,AdmissionRejected)):
        try: service.list_requests(actor,league)
        except error: pass
        else: raise AssertionError('Invalid commissioner was allowed')
    revoker=engine_for(database,'otm-admission-revoker'); revoked=False
    def revoke(conn,cursor,statement,params,context,many):
        nonlocal revoked
        if 'FROM "LeagueJoinRequest" r' in statement and not revoked:
            revoked=True
            with revoker.begin() as other: other.execute(text('UPDATE "League" SET commissioner=2 WHERE id=10'))
    event.listen(engine,'before_cursor_execute',revoke)
    try:
        assert service.list_requests(UserActor(1,'alice'),10)==[]
        assert revoked
    finally:
        event.remove(engine,'before_cursor_execute',revoke)
        with revoker.begin() as other: other.execute(text('UPDATE "League" SET commissioner=1 WHERE id=10'))
        revoker.dispose()
    def state():
        with engine.connect() as conn: return [dict(r._mapping) for r in conn.execute(text('SELECT * FROM "LeagueJoinRequest" ORDER BY id'))]
    before=state()
    for actor,league,request,error in ((UserActor(1,'commissioner'),10,100,AdmissionDenied),
            (UserActor(2,'bob'),20,100,AdmissionRejected),(UserActor(3,'other'),10,101,AdmissionRejected)):
        try: service.cancel_request(actor,league,request)
        except error: pass
        else: raise AssertionError('Invalid cancellation allowed')
        assert state()==before
    def fail_after_update(conn,cursor,statement,params,context,many):
        if 'UPDATE "LeagueJoinRequest"' in statement: raise RuntimeError('synthetic after-update failure')
    event.listen(engine,'after_cursor_execute',fail_after_update)
    try:
        try: service.cancel_request(UserActor(2,'bob'),10,100)
        except RuntimeError: pass
        else: raise AssertionError('Post-update fault did not abort')
    finally: event.remove(engine,'after_cursor_execute',fail_after_update)
    assert state()==before
    with engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION fail_cancel_commit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.status='CANCELLED' THEN RAISE EXCEPTION 'synthetic deferred failure'; END IF; RETURN NEW; END $$;
            CREATE CONSTRAINT TRIGGER cancel_commit AFTER UPDATE ON "LeagueJoinRequest"
                DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fail_cancel_commit();''')
    try: service.cancel_request(UserActor(2,'bob'),10,100)
    except DBAPIError: pass
    else: raise AssertionError('Deferred cancellation did not abort')
    assert state()==before
    with engine.begin() as conn: conn.exec_driver_sql('DROP TRIGGER cancel_commit ON "LeagueJoinRequest"')
    concurrent=[]
    for facade in (False,True):
        with engine.begin() as conn:
            conn.execute(text('UPDATE "LeagueJoinRequest" SET status=\'PENDING\',"resolvedAt"=NULL WHERE id=100'))
        first=engine_for(database,'otm-admission-first'); second=engine_for(database,'otm-admission-second')
        locked,release=threading.Event(),threading.Event(); outcomes={}
        def hold(conn,cursor,statement,params,context,many):
            if 'FOR UPDATE' in statement:
                locked.set(); assert release.wait(10),'First cancellation not released'
        event.listen(first,'after_cursor_execute',hold)
        def cancel(label,db):
            try:
                if facade:
                    model=LeagueModel.__new__(LeagueModel); model.db=db
                    result=model.cancel_join_request(10,100,2)
                else: result=AdmissionService(db).cancel_request(UserActor(2,'bob'),10,100)
                outcomes[label]=['success',result['status'],result['resolvedByUserId']]
            except Exception as exc: outcomes[label]=[type(exc).__name__,str(exc)]
        a=threading.Thread(target=cancel,args=('first',first)); b=threading.Thread(target=cancel,args=('second',second))
        a.start()
        try:
            assert locked.wait(5),'First cancellation did not lock row'; b.start()
            blocked=False; deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                with engine.connect() as conn:
                    blocked=conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE application_name='otm-admission-second' AND wait_event_type='Lock' AND cardinality(pg_blocking_pids(pid))>0)")).scalar_one()
                if blocked: break
                time.sleep(.02)
            assert blocked,'No competing cancellation lock wait observed'
        finally:
            release.set(); a.join(10)
            if b.ident is not None: b.join(10)
            first.dispose(); second.dispose()
        assert not a.is_alive() and not b.is_alive()
        assert outcomes=={'first':['success','CANCELLED',None],
            'second':['ValueError' if facade else 'AdmissionRejected','Only pending requests can be cancelled']},outcomes
        concurrent.append({'path':'legacy_facade' if facade else 'service','observed_lock_wait':True,'outcomes':outcomes})
    model=LeagueModel.__new__(LeagueModel); model.db=engine
    assert [r['id'] for r in model.list_join_requests(20)]==[200]
    assert model._list_join_requests(10,None,commissioner_id=99)==[]
    return {'listing_projection_filter_and_commissioner_revocation':'PASS','cancellation_scope_owner_state':'PASS',
            'post_update_and_deferred_commit_rollback':'PASS','legacy_helpers_and_new_only_db_models':'PASS',
            'concurrent_cancellation':concurrent}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL); admin.autocommit=True
    name='otm_admission_'+uuid4().hex; created=False; engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name))); created=True
        engine=engine_for(name,'otm-admission')
        results=tests(engine,name)
        files=['api/endpoints/league/'+f for f in ('admission/service.py','admission/repository.py','admission/contracts.py','leagueModel.py','leagueEndpoints.py')]
        files+=['api/actors.py','scripts/modernization/verify_admission_slice.py']
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database',
                'admission_listing_cancellation':results,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-admission-postgres-2026-10-29.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None: engine.dispose()
        if created:
            with admin.cursor() as cur: cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__': main()
