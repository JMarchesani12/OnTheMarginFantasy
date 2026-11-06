"""Owned marked loopback verification; controlled steps, no configured runtime/jobs."""
import hashlib
import json
import os
import select
import time
from uuid import uuid4
from unittest.mock import patch
import jwt
import psycopg2
from psycopg2 import sql
from flask import Flask
from flask_socketio import SocketIO
from sqlalchemy import text
from assess_postgres import LOCAL,ROOT,engine_for
from verify_mod023 import tests as notifications, prior_pick_tests, prior_snapshot_tests, prior_control_tests, prior_order_tests, prior_finalization_tests, prior_ownership_tests, FIXTURE
from endpoints.draft.listener import DraftNotifyListener
from endpoints.draft.draftSocket import register_draft_socket_handlers
from operations import job_gate,GateLost


def tests(engine,database):
    with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    app=Flask('mod024-native');app.config['TESTING']=True
    socket=SocketIO(app,async_mode='threading')
    register_draft_socket_handlers(engine,socket_server=socket)
    now=[0.]
    listener=DraftNotifyListener(engine,socket,clock=lambda:now[0],wait=lambda c,t:bool(select.select([c],[],[],.25)[0]))
    other=engine_for(database,'mod024-killer')
    def kill(pid):
        with other.begin() as conn:assert conn.execute(text('SELECT pg_terminate_backend(:pid)'),{'pid':pid}).scalar_one()
    def mutate(statement):
        with engine.begin() as conn:conn.exec_driver_sql(statement)
    client=None
    try:
        with patch.dict(os.environ,{'SUPABASE_PROJECT_ID':'mod024-synthetic','SUPABASE_JWT_SECRET':'mod024-synthetic-secret-never-used-outside-owned-tests'},clear=True):
            token=jwt.encode({'sub':'00000000-0000-4000-8000-000000000002','aud':'authenticated',
                'iss':'https://mod024-synthetic.supabase.co/auth/v1','exp':int(time.time())+600},os.environ['SUPABASE_JWT_SECRET'],algorithm='HS256')
            client=socket.test_client(app,auth={'token':token});assert client.is_connected()
            client.emit('draft:join',{'leagueId':10});assert client.get_received()[0]['name']=='draft:snapshot'
            listener.step();assert listener.status()['state']=='connected'
            assert client.get_received()[0]['name']=='draft:updated'
            # Real LISTEN delivery enters the production controller, still guarded per recipient.
            mutate("SELECT pg_notify('draft_updated','{\"leagueId\":10}')")
            listener.step();assert client.get_received()[0]['name']=='draft:updated'
            pid=listener.conn.get_backend_pid();kill(pid)
            mutate('UPDATE "DraftState" SET status=\'paused\',"expiresAt"=NULL WHERE "leagueId"=10')
            now[0]+=16.;listener.step();assert listener.status()['state']=='retrying'
            now[0]+=1.;listener.step();assert listener.status()['state']=='connected'
            updates=client.get_received();assert updates[0]['args'][0]['snapshot']['state']['status']=='paused',updates
            # Revoked stale room membership must not receive the reconnect resync.
            pid=listener.conn.get_backend_pid();kill(pid)
            mutate('DELETE FROM "LeagueMember" WHERE id=12')
            now[0]+=16.;listener.step();assert listener.status()['state']=='retrying'
            now[0]+=2.;listener.step();messages=client.get_received()
            assert any(m['name']=='draft:error' for m in messages) and not any(m['name']=='draft:updated' for m in messages),messages
            pid=listener.conn.get_backend_pid();listener.stop();listener.step()
            assert listener.status()['state']=='stopped' and listener.conn is None
            with other.begin() as conn:assert conn.execute(text('SELECT count(*) FROM pg_stat_activity WHERE pid=:pid'),{'pid':pid}).scalar_one()==0
        # Actual session contention, independent keys, exception and disconnect release.
        with job_gate(engine,'weekly') as first:
            assert first;first.check()
            with job_gate(other,'weekly') as competing:assert not competing
            with job_gate(other,'refresh') as independent:assert independent
            from cronJobs import cronComputeWeeklyScores as weekly
            with patch.object(weekly,'WeeklyCompletionService',side_effect=AssertionError('Busy job executed domain work')):
                assert weekly.main(engine=other)['outcome']=='already_running'
        try:
            with job_gate(engine,'weekly') as gate:
                assert gate;raise ValueError('synthetic owned fault')
        except ValueError:pass
        with job_gate(other,'weekly') as gate:assert gate
        try:
            with job_gate(engine,'weekly') as gate:
                kill(gate.pid)
                gate.check()
        except GateLost:pass
        else:raise AssertionError('Lost gate was not detected')
        with job_gate(other,'weekly') as gate:assert gate
        return {'actual_listen_and_reconnect_resync':'PASS','revoked_member_reconnect_no_private_delivery':'PASS',
                'owned_listener_shutdown_session_gone':'PASS','same_job_contention_skips_work_independent_keys':'PASS',
                'gate_exception_disconnect_release_and_no_reconnect':'PASS'}
    finally:
        listener.stop()
        if client is not None and client.is_connected():client.disconnect()
        other.dispose()


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_mod024_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'mod024-owner');result=tests(engine,name)
        result['prior']={'mod023':notifications(engine,name),'pick':prior_pick_tests(engine,name),'snapshot':prior_snapshot_tests(engine,name),
            'controls':prior_control_tests(engine,name),'order':prior_order_tests(engine,name),'finalization':prior_finalization_tests(engine,name),
            'ownership':prior_ownership_tests(engine,name)}
        paths=['api/endpoints/draft/realtime.py','api/endpoints/draft/draftBroadcast.py','api/operations.py','api/endpoints/draft/listener.py','api/endpoints/draft/startDraftNotifyListener.py','api/runtime.py','api/api.py','api/httpBoundary.py','api/dev.py','api/start.sh','api/gunicorn_conf.py','api/worker/draftTimeoutWorker.py',
            'api/cronJobs/cronComputeWeeklyScores.py','api/cronJobs/cronComputeFinalScoreboard.py','api/cronJobs/cronIngestScoreboard.py','api/cronJobs/cronRefreshSchedules.py','api/endpoints/schedule/ingestion_service.py','api/endpoints/schedule/helpers/espn/espnClient.py',
            'api/tests/test_dev_cooperative.py','api/tests/test_operations.py','api/tests/test_draft_listener.py','api/tests/test_runtime_readiness.py','api/tests/test_operational_jobs.py','api/tests/test_operational_trusted_contract.py','api/tests/test_startup_isolation.py','scripts/modernization/verify_mod024.py']
        report={'result':'PASS','scope':'Owned marked PostgreSQL and controlled listener steps only; no configured runtime/provider/hosted operations',
            'tests':result,'sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}}
        (ROOT/'docs/modernization/evidence/mod-024-postgres-2026-11-06.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
        print(json.dumps(report,indent=2,default=str))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()
if __name__=='__main__':main()
