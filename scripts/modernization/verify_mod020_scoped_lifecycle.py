"""Bounded explicit scoped lifecycle contract on marked disposable PostgreSQL only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from threading import Event
from time import monotonic,sleep
from uuid import uuid4
import hashlib
import psycopg2
from psycopg2 import sql
from sqlalchemy import create_engine,event,text
from sqlalchemy.exc import DBAPIError
import measure_mod017 as base
import measure_mod020_lifecycle as fixture
from measure_mod017_transactions import save_json,verify_cleanup
from actors import UserActor
from endpoints.league.lifecycle.query_service import LeagueLifecycleQueryService
from endpoints.league.lifecycle.repository import LeagueLifecycleRepository
from endpoints.league.lifecycle.service import LeagueLifecycleService
from endpoints.league.reads.service import LeagueReadService
from endpoints.draft.control_repository import DraftControlRepository
from endpoints.league.members.repository import MemberRepository

PHASES=('mark_pre_draft','mark_drafting','mark_post_draft','mark_in_season','mark_completed')


def assert_untouched(before,after,eligible):
    for old,new in zip(before,after):
        if old['id'] not in eligible and old!=new:raise AssertionError('Unrelated league changed')


def equivalence(engine):
    records=[];query=LeagueLifecycleQueryService(engine);reader=LeagueReadService(engine)
    with engine.connect() as conn:anchor=conn.execute(text('SELECT now()')).scalar_one()
    # Same timestamp for both sides makes every returned field directly comparable.
    # SQL predicates are unchanged apart from replacing transaction-time now() with
    # this one fixed instant; unadapted v2 measurement runs separately below.
    def fixed(conn,cursor,statement,params,context,many):
        return statement.replace('now()',"TIMESTAMPTZ '"+anchor.isoformat()+"'"),params
    event.listen(engine,'before_cursor_execute',fixed,retval=True)
    try:
        cases=[('detail',i,2,None) for i in range(1,11)]+[('detail',11,1,None),('detail',1,99999,None),('detail',9999,2,None)]+[('mine',None,2,stage) for stage in ('all','active','completed')]+[('mine',None,99999,'all')]
        with engine.begin() as conn:
            conn.execute(text('UPDATE "LeagueMember" SET "userId"=2 WHERE "leagueId"<=10 AND "draftOrder"=2'))
            conn.execute(text('UPDATE "LeagueMember" SET "userId"=701 WHERE "leagueId"=11 AND "draftOrder"=1'))
        for mode in ('dirty','steady'):
            for kind,target,user,stage in cases:
                fixture.prepare(engine,mode);before=fixture.snapshot(engine);trace=[];updates=[]
                def capture(conn,cursor,statement,params,context,many):
                    role=fixture.classify(statement);trace.append(role)
                    if role in fixture.PHASES.values():updates.append(dict(phase=role,rows=cursor.rowcount))
                event.listen(engine,'after_cursor_execute',capture)
                try:actual=query.details(UserActor(user,'synthetic'),target) if kind=='detail' else query.mine(UserActor(user,'synthetic'),stage)
                finally:event.remove(engine,'after_cursor_execute',capture)
                after=fixture.snapshot(engine)
                eligible=([target] if target is not None and (user!=99999 and target<=100) else []) if kind=='detail' else (list(range(1,11)) if user==2 else [])
                assert_untouched(before,after,eligible)
                for row in after:
                    if row['id'] in eligible:assert row['status']==fixture.final_status(row['id'])
                fixture.prepare(engine,mode);LeagueLifecycleService(engine).synchronize_for_job()
                expected=reader.details(UserActor(user,'synthetic'),target) if kind=='detail' else reader.mine(UserActor(user,'synthetic'),stage)
                assert actual==expected,(mode,kind,target,stage)
                phase_trace=[x for x in trace if x in fixture.PHASES.values()]
                assert phase_trace==(list(fixture.PHASES.values()) if eligible else [])
                if eligible:assert trace.index('authorize')<trace.index('pre')<trace.index('read')
                records.append(dict(mode=mode,kind=kind,target=target,user=user,stage=stage,scope=eligible,sequence=trace,phase_rows=updates,full_payload=fixture.read_signature(actual),touched_ids=[a['id'] for b,a in zip(before,after) if a!=b]))
    finally:event.remove(engine,'before_cursor_execute',fixed)
    return dict(fixed_transaction_instant=anchor.isoformat(),cases=records)


def rollback_checks(engine):
    records=[]
    for phase in (*PHASES,'read','commit'):
        fixture.prepare(engine,'dirty');before=fixture.snapshot(engine)
        class FailingRepository(LeagueLifecycleRepository):
            pass
        repo=FailingRepository();reader=LeagueReadService(engine)
        if phase in PHASES:
            original=getattr(repo,phase)
            def fail(*args,**kw):original(*args,**kw);raise RuntimeError('post-phase')
            setattr(repo,phase,fail)
        elif phase=='read':reader.details_in_transaction=lambda *a:(_ for _ in ()).throw(RuntimeError('read'))
        else:
            with engine.begin() as conn:
                conn.exec_driver_sql('''CREATE FUNCTION mod020_fail_commit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic deferred commit'; END $$;
                CREATE CONSTRAINT TRIGGER mod020_fail_commit AFTER UPDATE ON "League" DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION mod020_fail_commit();''')
        try:
            try:LeagueLifecycleQueryService(engine,repo,reader).details(UserActor(2,'synthetic'),1)
            except (RuntimeError,DBAPIError):pass
            else:raise AssertionError('Failure swallowed')
            assert fixture.snapshot(engine)==before
        finally:
            if phase=='commit':
                with engine.begin() as conn:conn.exec_driver_sql('DROP TRIGGER mod020_fail_commit ON "League"; DROP FUNCTION mod020_fail_commit()')
        assert LeagueLifecycleQueryService(engine).details(UserActor(2,'synthetic'),1)['status']=='Pre-Draft'
        records.append(dict(failure=phase,rollback=True,retry=True))
    return records


def wait_for_block(engine,pid):
    deadline=monotonic()+4
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
        while monotonic()<deadline:
            if conn.execute(text('SELECT cardinality(pg_blocking_pids(:pid))'),dict(pid=pid)).scalar_one()>0:return
            sleep(.01)
    raise AssertionError('Expected native lock wait missing')


def interleavings(engine):
    records=[]
    for scenario,target in [('existing_start',2),('finalization',2),('first_start',1),('removal',1),('join_after_discovery',1)]:
        fixture.prepare(engine,'dirty')
        with engine.begin() as conn:
            conn.execute(text('INSERT INTO "LeagueMember" (id,"leagueId","userId","teamName","draftOrder") VALUES (9999,12,2,\'join\',9) ON CONFLICT (id) DO NOTHING'))
            conn.execute(text('DELETE FROM "LeagueMember" WHERE id=9999'))
            # Restore membership if a previous removal happened.
            conn.execute(text('UPDATE "LeagueMember" SET "userId"=2 WHERE id=2'))
            if scenario=='first_start':conn.execute(text('DELETE FROM "DraftState" WHERE "leagueId"=1'))
        ready=Event();box={};attempts=[]
        class Observed(LeagueLifecycleRepository):
            def candidate_ids(self,conn,user_id,league_id=None):
                value=super().candidate_ids(conn,user_id,league_id);attempts.append(value);box['pid']=conn.connection.driver_connection.get_backend_pid();ready.set();return value
        blocker=engine.connect();tx=blocker.begin()
        try:
            control=DraftControlRepository()
            if scenario in ('existing_start','finalization'):control.lock_state(blocker,target)
            control.lock_league(blocker,target)
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(lambda:LeagueLifecycleQueryService(engine,Observed()).mine(UserActor(2,'synthetic')) if scenario=='join_after_discovery' else LeagueLifecycleQueryService(engine,Observed()).details(UserActor(2,'synthetic'),target))
                assert ready.wait(3);wait_for_block(engine,box['pid'])
                if scenario=='first_start':blocker.execute(text('INSERT INTO "DraftState" ("leagueId",status) VALUES (1,\'live\')'))
                elif scenario=='existing_start':blocker.execute(text('UPDATE "DraftState" SET status=\'live\' WHERE "leagueId"=:id'),dict(id=target))
                elif scenario=='finalization':control.finalize_state(blocker,target);control.finalize_league(blocker,target)
                elif scenario=='removal':
                    members=MemberRepository();members.lock_member_for_removal(blocker,1,2)
                    # Preserve dependent fixture histories while changing entitlement.
                    blocker.execute(text('UPDATE "LeagueMember" SET "userId"=701 WHERE id=2'))
                else:blocker.execute(text('INSERT INTO "LeagueMember" (id,"leagueId","userId","teamName","draftOrder") VALUES (9999,12,2,\'join\',9)'))
                tx.commit();result=future.result(timeout=8)
            if scenario=='first_start':assert len(attempts)==2 and result['status']=='Drafting'
            elif scenario=='removal':assert result is None
            elif scenario=='finalization':assert result['status']=='In-Season'
            elif scenario=='existing_start':assert result['status']=='Drafting'
            else:assert 12 not in [r['leagueId'] for r in result]
            records.append(dict(scenario=scenario,attempts=len(attempts),lock_wait_observed=True,result=fixture.read_signature(result),scope_limit='Actual control/member repository lock protocol; state/membership writes simulated, not full start/pick/removal workflow'))
        finally:
            if tx.is_active:tx.rollback()
            blocker.close()
    return records


def boundary_checks(engine):
    # Exercise actual SQL at controlled UTC instants and league-local calendars.
    cases=[]
    with engine.begin() as conn:
        conn.execute(text('UPDATE "SportSeason" SET "seasonStart"=\'2026-11-16\',"seasonEnd"=\'2026-11-17\' WHERE "seasonYear"=2026'))
        conn.execute(text('UPDATE "League" SET "seasonYear"=2026 WHERE id IN (4,5)'))
    # Baseline status is NOT NULL; relax only this disposable boundary fixture
    # to characterize legacy/null policy without implying deployable null rows.
    with engine.begin() as conn:conn.exec_driver_sql('ALTER TABLE "League" ALTER COLUMN status DROP NOT NULL')
    for instant,zone,status,target,want in [('2026-11-16T00:30:00+00:00','America/Chicago','Post-Draft',4,'Post-Draft'),('2026-11-16T06:30:00+00:00','America/Chicago','Post-Draft',4,'In-Season'),('2026-11-18T00:30:00+00:00','America/Chicago','In-Season',5,'In-Season'),('2026-11-18T06:30:00+00:00','America/Chicago','In-Season',5,'Completed'),('2026-11-16T12:00:00+00:00','UTC',None,4,None)]:
        with engine.begin() as conn:conn.execute(text('UPDATE "League" SET status=:status,settings=jsonb_build_object(\'timezone\',:zone) WHERE id=:id'),dict(status=status,zone=zone,id=target))
        def fixed(conn,cursor,statement,params,context,many):return statement.replace('now()',"TIMESTAMPTZ '"+instant+"'"),params
        event.listen(engine,'before_cursor_execute',fixed,retval=True)
        try:result=LeagueLifecycleQueryService(engine).details(UserActor(2,'synthetic'),target)
        finally:event.remove(engine,'before_cursor_execute',fixed)
        assert result['status']==want
        cases.append(dict(instant=instant,timezone=zone,initial=status,expected=want,actual=result['status'],adaptation='Only now() replaced by fixed timestamptz; actual date predicates unchanged'))
    return cases


def permission_and_lock(engine,admin,name):
    records=[];role='otm_mod020_'+uuid4().hex
    with admin.cursor() as cur:cur.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(role)))
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql('GRANT USAGE ON SCHEMA public TO '+role)
            conn.exec_driver_sql('GRANT SELECT ON ALL TABLES IN SCHEMA public TO '+role)
        fixture.prepare(engine,'dirty');before=fixture.snapshot(engine)
        def restricted(conn):conn.exec_driver_sql('SET LOCAL ROLE '+role)
        event.listen(engine,'begin',restricted)
        try:
            try:LeagueLifecycleQueryService(engine).details(UserActor(2,'synthetic'),1)
            except DBAPIError as e:assert e.orig.pgcode=='42501'
            else:raise AssertionError('Permission failure missing')
        finally:event.remove(engine,'begin',restricted)
        assert fixture.snapshot(engine)==before;records.append(dict(permission_failure=True,rollback=True))
        blocker=engine.connect();tx=blocker.begin();blocker.execute(text('SELECT id FROM "League" WHERE id=1 FOR UPDATE'))
        def short(conn):conn.exec_driver_sql("SET LOCAL lock_timeout='100ms'")
        event.listen(engine,'begin',short)
        try:
            try:LeagueLifecycleQueryService(engine).details(UserActor(2,'synthetic'),1)
            except DBAPIError as e:assert e.orig.pgcode=='55P03'
            else:raise AssertionError('Lock failure missing')
        finally:event.remove(engine,'begin',short);tx.rollback();blocker.close()
        assert fixture.snapshot(engine)==before;records.append(dict(lock_timeout=True,rollback=True))
    finally:
        with engine.begin() as conn:conn.exec_driver_sql('DROP OWNED BY '+role)
        with admin.cursor() as cur:cur.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
    return dict(checks=records,role=role,role_removed=True)


def run():
    directory=base.ROOT/'docs/modernization/evidence';run_id=uuid4().hex;artifact=directory/f'mod-020-scoped-{run_id}.json';manifest=directory/'mod-020-scoped-current-2026-11-16.json'
    report=dict(run_id=run_id,result='RUNNING',started_at=datetime.now(timezone.utc).isoformat(),databases=[],cleanup='no database created',provenance={})
    def persist():save_json(artifact,report);save_json(manifest,dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist();admin=None
    try:
        files=[base.BASELINE,*base.MIGRATIONS,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod020_lifecycle.py','scripts/modernization/verify_mod020_scoped_lifecycle.py','api/endpoints/league/lifecycle/query_service.py','api/endpoints/league/lifecycle/repository.py','api/endpoints/league/lifecycle/service.py','api/endpoints/league/reads/service.py','api/endpoints/league/reads/repository.py','api/endpoints/league/leagueEndpoints.py','api/utils/authorization.py','api/endpoints/draft/control_repository.py','api/endpoints/league/members/repository.py']
        report['provenance']={f:hashlib.sha256((base.ROOT/f).read_bytes()).hexdigest() for f in files}
        admin=psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        try:
            with base.owned_database(admin) as name:
                record=dict(name=name,cleanup='pending');report['databases'].append(record);persist()
                engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=name,**base.LOCAL))
                try:
                    with engine.connect() as conn:base.schema(conn);report['fixture']=fixture.seed(conn,100)
                    report['unadapted_measurement']=[fixture.measure(engine,100,call,mode) for call in fixture.CALLS for mode in ('dirty','steady')]
                    report['equivalence']=equivalence(engine);report['rollback']=rollback_checks(engine);report['interleavings']=interleavings(engine);report['permission_lock']=permission_and_lock(engine,admin,name);report['boundaries']=boundary_checks(engine)
                finally:engine.dispose()
        finally:
            for record in report['databases']:verify_cleanup(admin,record)
            report['cleanup']='verified' if report['databases'] and all(x['cleanup']=='removed' for x in report['databases']) else 'unverified'
        assert report['cleanup']=='verified';report['result']='PASS';return report
    except BaseException as error:report['result']='FAILED';report['error']=str(error);report['error_type']=type(error).__name__;raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();persist()
        if admin is not None:admin.close()
        print(artifact.name,report['result'],report['cleanup'],flush=True)
if __name__=='__main__':run()
