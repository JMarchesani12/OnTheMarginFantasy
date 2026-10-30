"""Draft-order arrays/atomicity on marked synthetic PostgreSQL."""
import hashlib,json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL,ROOT,engine_for
from verify_draft_controls import FIXTURE as CONTROL_FIXTURE,snapshot_tests,finalize_tests,tests as control_tests
from actors import UserActor
from endpoints.draft.control_service import DraftControlService
from endpoints.draft.draftModel import DraftModel

FIXTURE=CONTROL_FIXTURE+'''CREATE UNIQUE INDEX member_order_unique ON "LeagueMember" ("leagueId","draftOrder");'''


def tests(engine,database):
    service=DraftControlService(engine);actor=UserActor(1,'alice')
    def reset():
        with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    def state():
        with engine.connect() as conn:
            return {t:[dict(r._mapping) for r in conn.execute(text(f'SELECT * FROM "{t}" ORDER BY 1'))]
                    for t in ('League','LeagueMember','DraftState')}
    reset();before=state();row=service.set_order(actor,10,[12,11])
    assert row=={'members':[{'memberId':12,'userId':2,'teamName':'Bob Open','draftOrder':1},
                           {'memberId':11,'userId':1,'teamName':'Alice Open','draftOrder':2}]}
    assert state()['League']==before['League'] and state()['LeagueMember'][2:]==before['LeagueMember'][2:]
    partial=service.set_order(actor,10,[11]);assert [m['draftOrder'] for m in partial['members']]==[1,100001]
    reset();before=state()
    for who,league,ids,error in ((UserActor(2,'bob'),10,[12,11],PermissionError),(actor,999,[11],ValueError),
            (actor,10,[12,12],ValueError),(actor,10,[21,11],ValueError),(actor,10,[999],ValueError),(actor,10,[],ValueError)):
        try:service.set_order(who,league,ids)
        except error:pass
        else:raise AssertionError('Order authority/input guard missing')
        assert state()==before
    for status in ('live','paused','complete'):
        reset()
        with engine.begin() as conn:conn.execute(text('INSERT INTO "DraftState" ("leagueId",status) VALUES (10,:status)'),{'status':status})
        before=state()
        try:service.set_order(actor,10,[12,11])
        except ValueError as exc:assert str(exc)=='Cannot change draft order after draft has started'
        else:raise AssertionError('Started draft reordered')
        assert state()==before
    for fragment in ('"draftOrder" + 100000','WITH input AS','SELECT id AS "memberId"'):
        reset();before=state()
        def fail(conn,cursor,statement,params,context,many):
            if fragment in statement:raise RuntimeError('synthetic after-order-phase failure')
        event.listen(engine,'after_cursor_execute',fail)
        try:
            try:service.set_order(actor,10,[12,11])
            except RuntimeError:pass
            else:raise AssertionError('Order phase failure missing')
        finally:event.remove(engine,'after_cursor_execute',fail)
        assert state()==before
    reset();before=state()
    with engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION reject_order_assignment() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW."draftOrder"<100000 THEN RAISE EXCEPTION 'synthetic assignment statement failure'; END IF; RETURN NEW; END $$;
            CREATE TRIGGER reject_order BEFORE UPDATE ON "LeagueMember" FOR EACH ROW EXECUTE FUNCTION reject_order_assignment();''')
    try:service.set_order(actor,10,[12,11])
    except DBAPIError:pass
    else:raise AssertionError('Real assignment failure missing')
    assert state()==before
    reset();before=state()
    with engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION fail_order_commit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic deferred order failure'; END $$;
            CREATE CONSTRAINT TRIGGER order_commit AFTER UPDATE ON "LeagueMember"
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fail_order_commit();''')
    try:service.set_order(actor,10,[12,11])
    except DBAPIError:pass
    else:raise AssertionError('Deferred order failure missing')
    assert state()==before
    reset();before=state();other=engine_for(database,'otm-order-revoke');changed=[]
    def revoke(conn,cursor,statement,params,context,many):
        if '"draftOrder" + 100000' in statement and not changed:
            changed.append(True)
            with other.begin() as separate:separate.execute(text('UPDATE "League" SET commissioner=2 WHERE id=10'))
    event.listen(engine,'before_cursor_execute',revoke)
    try:
        try:service.set_order(actor,10,[12,11])
        except PermissionError:pass
        else:raise AssertionError('Late order authority loss accepted')
    finally:event.remove(engine,'before_cursor_execute',revoke);other.dispose()
    before['League'][0]['commissioner']=2;assert changed==[True] and state()==before
    reset();model=DraftModel.__new__(DraftModel);model.db=engine
    assert model.set_draft_order(10,[12,11])['members'][0]['memberId']==12
    assert model.set_draft_order(10,[11,12],acting_user_id='1')['members'][0]['memberId']==11
    return {'native_bigint_arrays_any_unnest_generate_series_unique_swap':'PASS','exact_projection_partial_guard_compatibility':'PASS',
            'post_bump_assignment_read_statement_commit_rollback':'PASS','separate_connection_late_authority_rejection':'PASS',
            'legacy_trusted_coercion':'PASS','scope_limit':'Original partial lists and unlocked state check preserved; no permutation/concurrent-start redesign'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_draft_order_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-draft-order');snapshot=snapshot_tests(engine,name);finalization=finalize_tests(engine,name);controls=control_tests(engine,name);order=tests(engine,name)
        files=['api/endpoints/draft/'+f for f in ('draft_rules.py','control_service.py','control_repository.py','snapshot_service.py','snapshot_repository.py','draftModel.py','draftEndpoints.py','routes.py')]
        files+=['api/actors.py']+['scripts/modernization/'+f for f in ('verify_draft_snapshot.py','verify_draft_finalization.py','verify_draft_controls.py','verify_draft_order.py')]
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database','snapshot_rerun':snapshot,'finalization_rerun':finalization,'controls_rerun':controls,'order':order,
                'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-draft-order-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
