"""Draft finalization native authority/atomicity; marked synthetic PostgreSQL."""
import hashlib,json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL,ROOT,engine_for
from verify_draft_snapshot import FIXTURE as SNAPSHOT_FIXTURE,tests as snapshot_tests
from actors import UserActor
from endpoints.draft.control_service import DraftControlService
from endpoints.draft.draftModel import DraftModel

FIXTURE=SNAPSHOT_FIXTURE+'''
ALTER TABLE "League" ADD COLUMN sport bigint DEFAULT 1;
ALTER TABLE "League" ADD COLUMN status text DEFAULT 'Drafting';
ALTER TABLE "League" ADD COLUMN "updatedAt" timestamptz DEFAULT '2000-01-01T00:00:00Z';
CREATE TABLE "SportSeason" ("sportId" bigint,"seasonYear" integer,"seasonStart" date,"seasonEnd" date);
INSERT INTO "SportSeason" VALUES (1,2026,current_date+10,current_date+30);'''


def tests(engine,database):
    service=DraftControlService(engine);alice=UserActor(1,'alice')
    def reset():
        with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    def state():
        with engine.connect() as conn:
            return {table:[dict(r._mapping) for r in conn.execute(text(f'SELECT * FROM "{table}" ORDER BY 1'))]
                    for table in ('League','DraftState')}
    reset();before=state()
    for actor,league,error in ((UserActor(2,'bob'),10,PermissionError),(alice,999,ValueError)):
        try:service.finalize(actor,league)
        except error:pass
        else:raise AssertionError('Finalization authority/missing guard bypass')
        assert state()==before
    for start,end,wanted in ((10,30,'Post-Draft'),(-10,10,'In-Season'),(-30,-1,'Completed'),(0,0,'In-Season')):
        reset();before=state()
        with engine.begin() as conn:
            conn.execute(text('UPDATE "SportSeason" SET "seasonStart"=current_date+:start,"seasonEnd"=current_date+:end'),{'start':start,'end':end})
        result=service.finalize(alice,10)
        assert set(result)=={'leagueId','draftComplete','state','leagueStatus'}
        assert result['leagueStatus']==wanted and result['draftComplete'] is True
        assert set(result['state'])=={'leagueId','status','currentOverallPickNumber','currentMemberId','expiresAt','lastPickAt','updatedAt'}
        assert result['state']['status']=='complete' and result['state']['currentMemberId'] is None and result['state']['expiresAt'] is None
        assert result['state']['lastPickAt']==before['DraftState'][0]['lastPickAt']
        assert result['state']['currentOverallPickNumber']==2 and result['state']['updatedAt']>before['DraftState'][0]['updatedAt']
        after=state();assert after['League'][0]['status']==wanted
        assert after['League'][1:]==before['League'][1:] and after['DraftState'][1:]==before['DraftState'][1:]
    reset()
    with engine.begin() as conn:conn.exec_driver_sql('DELETE FROM "SportSeason"')
    before=state();result=service.finalize_for_job(20)
    assert result['leagueStatus'] is None and result['state']['lastPickAt'] is not None
    assert state()['League']==before['League']
    reset()
    with engine.begin() as conn:conn.execute(text('DELETE FROM "DraftState" WHERE "leagueId"=20'))
    before=state()
    try:service.finalize(UserActor(2,'bob'),20)
    except ValueError:pass
    else:raise AssertionError('Missing state accepted')
    assert state()==before
    for fragment in ('UPDATE "DraftState"','UPDATE "League" l'):
        reset();before=state()
        def fail(conn,cursor,statement,params,context,many):
            if fragment in statement:raise RuntimeError('synthetic post-finalization-write failure')
        event.listen(engine,'after_cursor_execute',fail)
        try:
            try:service.finalize(alice,10)
            except RuntimeError:pass
            else:raise AssertionError('Post-write failure missing')
        finally:event.remove(engine,'after_cursor_execute',fail)
        assert state()==before
    reset();before=state()
    with engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION reject_finalize() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic finalization statement failure'; END $$;
            CREATE TRIGGER reject_finalize BEFORE UPDATE ON "League" FOR EACH ROW EXECUTE FUNCTION reject_finalize();''')
    try:service.finalize(alice,10)
    except DBAPIError:pass
    else:raise AssertionError('Real statement failure missing')
    assert state()==before
    reset();before=state()
    with engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION fail_finalize_commit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic deferred finalization failure'; END $$;
            CREATE CONSTRAINT TRIGGER finalize_commit AFTER UPDATE ON "DraftState"
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fail_finalize_commit();''')
    try:service.finalize(alice,10)
    except DBAPIError:pass
    else:raise AssertionError('Deferred finalization failure missing')
    assert state()==before
    reset();before=state();other=engine_for(database,'otm-finalize-revoke');changed=[]
    def revoke(conn,cursor,statement,params,context,many):
        if 'UPDATE "DraftState"' in statement and not changed:
            changed.append(True)
            with other.begin() as separate:separate.execute(text('UPDATE "League" SET commissioner=2 WHERE id=10'))
    event.listen(engine,'before_cursor_execute',revoke)
    try:
        try:service.finalize(alice,10)
        except PermissionError:pass
        else:raise AssertionError('Post-check failed to reject lost commissioner')
    finally:event.remove(engine,'before_cursor_execute',revoke);other.dispose()
    before['League'][0]['commissioner']=2;assert changed==[True] and state()==before
    reset();before=state();model=DraftModel.__new__(DraftModel)
    try:
        with engine.begin() as conn:
            result=model.finalize_draft(10,conn=conn)
            assert result['draftComplete'] is True
            raise RuntimeError('caller abort')
    except RuntimeError:pass
    assert state()==before
    model.db=engine
    assert model.force_finalize_draft(10,'1')['draftComplete'] is True
    return {'native_final_state_season_date_boundaries_projection_timestamps':'PASS','no_season_and_missing_state_compatibility':'PASS',
            'post_write_real_statement_commit_and_caller_rollback':'PASS','separate_connection_pre_post_authority_rejection':'PASS',
            'trusted_and_legacy_supplied_connection':'PASS','scope_limit':'Original pre/post authority checks add no locks or replay/concurrency guarantee'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_draft_finalize_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-draft-finalize');prior=snapshot_tests(engine,name);result=tests(engine,name)
        files=['api/endpoints/draft/'+f for f in ('control_service.py','control_repository.py','snapshot_service.py','snapshot_repository.py','draftModel.py','draftEndpoints.py','routes.py')]
        files+=['api/actors.py','scripts/modernization/verify_draft_snapshot.py','scripts/modernization/verify_draft_finalization.py']
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database','snapshot_rerun':prior,'finalization':result,
                'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-draft-finalization-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
