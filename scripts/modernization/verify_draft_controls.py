"""Start/pause/resume native SQL, locks and rollback on marked PostgreSQL."""
import hashlib,json,threading,time
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL,ROOT,engine_for
from verify_draft_finalization import FIXTURE as FINALIZE_FIXTURE,snapshot_tests,tests as finalize_tests
from actors import UserActor
from endpoints.draft.control_service import DraftControlService
from endpoints.draft.draftModel import DraftModel

FIXTURE=FINALIZE_FIXTURE+'''
UPDATE "League" SET settings='{"draft":{"draftType":"SNAKE","selectionTime":60,"numberOfRounds":2,"timeoutAction":"AUTO-SKIP","graceSeconds":0}}' WHERE id=10;
DELETE FROM "DraftPick" WHERE "leagueId"=10;
DELETE FROM "DraftTurn" WHERE "leagueId"=10;
DELETE FROM "DraftState" WHERE "leagueId"=10;
CREATE UNIQUE INDEX turn_identity ON "DraftTurn" ("leagueId","overallPickNumber");'''


def tests(engine,database):
    service=DraftControlService(engine);actor=UserActor(1,'alice')
    def reset():
        with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    def state():
        with engine.connect() as conn:
            return {t:[dict(r._mapping) for r in conn.execute(text(f'SELECT * FROM "{t}" ORDER BY 1,2'))]
                    for t in ('League','DraftState','DraftTurn','DraftPick')}
    def prepare(action):
        reset()
        if action!='start':
            service.start(actor,10)
            if action=='resume':service.pause(actor,10)
    def turns():
        with engine.connect() as conn:return conn.execute(text('SELECT "memberId" FROM "DraftTurn" WHERE "leagueId"=10 ORDER BY "overallPickNumber"')).scalars().all()
    # Provider-sensitive validation: the missing-order alias must match the consumer key.
    reset()
    with engine.begin() as conn:conn.execute(text('DELETE FROM "LeagueMember" WHERE id=12'))
    before=state()
    try:service.start(actor,10)
    except ValueError as exc:assert 'Missing draftOrder values: [2]' in str(exc)
    else:raise AssertionError('Incomplete-order validation missing')
    assert state()==before
    reset();row=service.start(actor,10)
    assert turns()==[11,12,12,11] and row['state']['currentOverallPickNumber']==1 and row['state']['currentMemberId']==11
    with engine.connect() as conn:now=conn.execute(text('SELECT now()')).scalar_one()
    assert 0<(row['state']['expiresAt']-now).total_seconds()<=60
    service.start(actor,10);assert turns()==[11,12,12,11]
    paused=service.pause(actor,10);assert paused['state']['status']=='paused' and paused['state']['expiresAt'] is None
    resumed=service.resume(actor,10);assert resumed['state']['status']=='live' and resumed['state']['currentMemberId']==11 and resumed['state']['expiresAt'] is not None
    service.finalize_for_job(10);before=state()
    for method in (service.pause,service.resume):
        try:method(actor,10)
        except ValueError as exc:assert str(exc)=='Draft is complete'
        else:raise AssertionError('Complete state accepted')
        assert state()==before
    assert service.start(actor,10)['state']['status']=='live'  # Existing restart behavior.
    reset()
    with engine.begin() as conn:conn.execute(text('UPDATE "League" SET settings=jsonb_set(settings,\'{draft,draftType}\',\'"STRAIGHT"\') WHERE id=10'))
    service.start(actor,10);assert turns()==[11,12,11,12]
    reset()
    for method in (service.pause,service.resume):
        try:method(actor,10)
        except ValueError as exc:assert str(exc)=='DraftState not found. Start draft first.'
        else:raise AssertionError('Missing state accepted')
    # Pause does not validate timing; resume validates config before locking state.
    service.start(actor,10)
    with engine.begin() as conn:conn.execute(text('UPDATE "League" SET settings=jsonb_set(settings,\'{draft,selectionTime}\',\'0\') WHERE id=10'))
    assert service.pause(actor,10)['state']['status']=='paused';before=state()
    try:service.resume(actor,10)
    except ValueError:pass
    else:raise AssertionError('Invalid timing accepted')
    assert state()==before
    try:service.start(UserActor(2,'bob'),10)
    except PermissionError:pass
    else:raise AssertionError('Authority did not precede config')

    for action,fragment in (('start','INSERT INTO "DraftTurn"'),('start','INSERT INTO "DraftState"'),
                            ('start','UPDATE "League"'),('pause','UPDATE "DraftState"'),('resume','UPDATE "DraftState"')):
        prepare(action);before=state()
        def fail(conn,cursor,statement,params,context,many):
            if fragment in statement:raise RuntimeError('synthetic post-control-write failure')
        event.listen(engine,'after_cursor_execute',fail)
        try:
            try:getattr(service,action)(actor,10)
            except RuntimeError:pass
            else:raise AssertionError('Control write failure missing')
        finally:event.remove(engine,'after_cursor_execute',fail)
        assert state()==before
    for action in ('start','pause','resume'):
        prepare(action);before=state()
        with engine.begin() as conn:
            conn.exec_driver_sql('''CREATE FUNCTION fail_control_commit() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'synthetic deferred control failure'; END $$;
                CREATE CONSTRAINT TRIGGER control_commit AFTER INSERT OR UPDATE ON "DraftState"
                DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fail_control_commit();''')
        try:getattr(service,action)(actor,10)
        except DBAPIError:pass
        else:raise AssertionError('Deferred control failure missing')
        assert state()==before
        prepare(action);before=state();other=engine_for(database,'otm-controls-revoke');changed=[]
        def revoke(conn,cursor,statement,params,context,many):
            marker='INSERT INTO "DraftTurn"' if action=='start' else 'UPDATE "DraftState"'
            if marker in statement and not changed:
                changed.append(True)
                with other.begin() as separate:separate.execute(text('UPDATE "League" SET commissioner=2 WHERE id=10'))
        event.listen(engine,'before_cursor_execute',revoke)
        try:
            try:getattr(service,action)(actor,10)
            except PermissionError:pass
            else:raise AssertionError('Late commissioner loss accepted')
        finally:event.remove(engine,'before_cursor_execute',revoke);other.dispose()
        before['League'][0]['commissioner']=2;assert changed==[True] and state()==before

    locks=[]
    for facade in (False,True):
        prepare('pause');first=engine_for(database,'otm-controls-first');second=engine_for(database,'otm-controls-second')
        locked,release=threading.Event(),threading.Event();outcomes={}
        def hold(conn,cursor,statement,params,context,many):
            if 'SELECT status FROM "DraftState"' in statement and 'FOR UPDATE' in statement:
                locked.set()
                if not release.wait(10):raise RuntimeError('Control lock timeout')
        event.listen(first,'after_cursor_execute',hold)
        def run(label,owner,action):
            try:
                if facade:
                    model=DraftModel.__new__(DraftModel);model.db=owner
                    result=getattr(model,action+'_draft')(10,acting_user_id=1)
                else:result=getattr(DraftControlService(owner),action)(actor,10)
                outcomes[label]=result['state']['status']
            except Exception as exc:outcomes[label]=[type(exc).__name__,str(exc)]
        a=threading.Thread(target=run,args=('first',first,'pause'),daemon=True)
        b=threading.Thread(target=run,args=('second',second,'resume'),daemon=True);a.start()
        try:
            assert locked.wait(5);b.start();blocked=False;deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                with engine.connect() as conn:blocked=conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE application_name='otm-controls-second' AND wait_event_type='Lock' AND cardinality(pg_blocking_pids(pid))>0)")).scalar_one()
                if blocked:break
                time.sleep(.02)
            assert blocked,'Resume did not wait on pause lock'
        finally:
            release.set();a.join(10)
            if b.ident is not None:b.join(10)
            event.remove(first,'after_cursor_execute',hold);first.dispose();second.dispose()
        assert not a.is_alive() and not b.is_alive() and outcomes=={'first':'paused','second':'live'},outcomes
        locks.append({'path':'legacy_facade' if facade else 'service','observed_lock_wait':True,'outcomes':outcomes})
    reset();model=DraftModel.__new__(DraftModel);model.db=engine
    assert model.start_draft(10)['state']['status']=='live'
    return {'native_generate_series_snake_straight_interval_upsert':'PASS','incomplete_order_config_missing_complete_guards':'PASS',
            'post_write_deferred_commit_and_authority_rollback':'PASS','concurrent_pause_resume':locks,
            'legacy_trusted_reset_compatibility':'PASS','scope_limit':'Existing restart/ON CONFLICT behavior preserved; no new replay guarantee'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_draft_controls_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-draft-controls');snapshot=snapshot_tests(engine,name);finalization=finalize_tests(engine,name);controls=tests(engine,name)
        files=['api/endpoints/draft/'+f for f in ('draft_rules.py','control_service.py','control_repository.py','snapshot_service.py','snapshot_repository.py','draftModel.py','draftEndpoints.py','routes.py')]
        files+=['api/actors.py']+['scripts/modernization/'+f for f in ('verify_draft_snapshot.py','verify_draft_finalization.py','verify_draft_controls.py')]
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database','snapshot_rerun':snapshot,'finalization_rerun':finalization,'controls':controls,
                'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-draft-controls-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
