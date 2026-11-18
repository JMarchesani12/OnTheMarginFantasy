"""Real Gunicorn lifecycle against fake DB I/O and owned loopback servers only."""
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json,os,signal,socket,subprocess,sys,tempfile,time
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[2];API=ROOT/'api'
FIXTURE=r'''
import os,types
import wsgi
app=wsgi.app
original_initialize=app.initialize

def initialize():
    if app.application is not None:return app.application
    # Gunicorn has patched this worker before invoking post_worker_init.
    import eventlet
    from sqlalchemy.engine import make_url
    from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
    import psycopg2
    psycopg2.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('Real database access forbidden'))
    from endpoints.draft import listener as implementation
    RealListener=implementation.DraftNotifyListener
    class Connection:
        notifies=[]
        def cursor(self):return types.SimpleNamespace(execute=lambda sql:None,close=lambda:None)
        def set_isolation_level(self,value):pass
        def poll(self):pass
        def close(self):pass
    class ControlledListener(RealListener):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs,connect=lambda *a,**k:Connection(),wait=lambda c,t:eventlet.sleep(.01),rooms=lambda:iter([]),dispatch=lambda league:None)
            self.created_pid=os.getpid();self.run_pid=None
        def run(self):
            self.run_pid=os.getpid();super().run()
    implementation.DraftNotifyListener=ControlledListener
    import runtime,db
    runtime.load_runtime_environment=lambda:None
    engine=types.SimpleNamespace(url=make_url('postgresql+psycopg2://synthetic@127.0.0.1/synthetic'),dialect=PGDialect_psycopg2())
    db.get_engine=lambda:engine
    application=original_initialize()
    from flask import request
    @application.after_request
    def diagnostics(response):
        if request.path=='/ready':
            body=response.get_json();controller=application.extensions.get('draft_notify_listener')
            body.update(serving_pid=os.getpid(),created_pid=getattr(controller,'created_pid',None),run_pid=getattr(controller,'run_pid',None),run_id=getattr(controller,'run_id',None))
            response.set_data(application.json.dumps(body))
        return response
    return application
app.initialize=initialize
'''


def probe(port,enabled,previous_pid=None):
    deadline=time.monotonic()+12;last=None
    while time.monotonic()<deadline:
        try:
            try:r=urlopen(f'http://127.0.0.1:{port}/ready',timeout=1)
            except HTTPError as error:r=error
            with r:body=json.loads(r.read());status=r.status
            last=dict(status=status,body=body)
            state='connected' if enabled else 'disabled'
            if status==200 and body['listener']['state']==state and body['serving_pid']!=previous_pid:
                if enabled and not body['created_pid']==body['run_pid']==body['serving_pid']:raise AssertionError('Listener is not owned/running in serving worker')
                return last
        except (OSError,ValueError):pass
        time.sleep(.05)
    raise AssertionError('Readiness did not reach correct worker-local state: '+repr(last))


def case(directory,preload,configuration,enabled,restart):
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    env={'PATH':os.environ.get('PATH',''),'PYTHONPATH':str(directory)+os.pathsep+str(API),'PYTHON_DOTENV_DISABLED':'1','EVENTLET_NO_GREENDNS':'yes','SUPABASE_PROJECT_ID':'synthetic-project','SUPABASE_JWT_SECRET':'synthetic-only-secret-never-used-outside-test','DRAFT_NOTIFY_LISTENER_ENABLED':str(enabled).lower()}
    command=[sys.executable,'-m','gunicorn','-k','eventlet','-w','1','-b',f'127.0.0.1:{port}','--chdir',str(API),'--timeout','10',*(['--preload'] if preload else []),*(['-c',str(API/'gunicorn_conf.py')] if configuration=='explicit' else []),'repro_app:app']
    path=directory/f'{preload}-{configuration}-{enabled}.log';log=path.open('w+')
    process=subprocess.Popen(command,env=env,cwd=API,stdout=log,stderr=log,start_new_session=True)
    record=dict(preload=preload,configuration=configuration,enabled=enabled,master_pid=process.pid,worker_replacement=restart,observations=[])
    try:
        first=probe(port,enabled);record['observations'].append(first)
        if first['body']['created_pid']==process.pid:raise AssertionError('Master created listener')
        if restart:
            pid=first['body']['serving_pid']
            if os.getpgid(pid)!=process.pid:raise AssertionError('Refusing signal outside owned process group')
            os.kill(pid,signal.SIGTERM)
            second=probe(port,enabled,previous_pid=pid);record['observations'].append(second)
            if first['body']['run_id']==second['body']['run_id']:raise AssertionError('Worker replacement reused controller')
    finally:
        if process.poll() is None:process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait();record['forced_cleanup']=True
        log.flush();log.close();record['master_reaped']=process.poll() is not None
    events=[]
    for line in path.read_text().splitlines():
        try:value=json.loads(line)
        except ValueError:continue
        if value.get('operation')=='listener':events.append(value)
    connected=[e['runId'] for e in events if e['event']=='connected'];stopped={e['runId'] for e in events if e['event']=='stopped'}
    expected=2 if restart else 1 if enabled else 0
    if len(connected)!=expected or not set(connected)<=stopped:raise AssertionError('Missing/duplicate startup or graceful stop: '+repr(events))
    record['events']=events
    if record.get('forced_cleanup'):raise AssertionError('Graceful shutdown required forced cleanup')
    # Gunicorn has reaped worker children on clean master exit; verify the port closed.
    with socket.socket() as check:
        check.settimeout(.2)
        if check.connect_ex(('127.0.0.1',port))==0:raise AssertionError('Owned HTTP server still listening')
    record['cleanup']='verified';return record


def run():
    path=ROOT/f'docs/modernization/evidence/listener-gunicorn-2026-11-18-{uuid4().hex}.json'
    report=dict(result='RUNNING',started_at=datetime.now(timezone.utc).isoformat(),scope='Real Gunicorn/eventlet; fake DB; synthetic configuration/temporary loopback HTTP only',cases=[],production_preload_flag='unconfirmed',provenance={})
    def persist():
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(report,indent=2)+'\n');tmp.replace(path)
    persist()
    try:
        files=['api/runtime.py','api/wsgi.py','api/gunicorn_conf.py','api/gunicorn.conf.py','api/endpoints/draft/listener.py','api/api.py','scripts/modernization/verify_gunicorn_listener.py']
        report['provenance']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}
        report['versions']={p:importlib.metadata.version(p) for p in ['gunicorn','eventlet','Flask-SocketIO','python-engineio']}
        with tempfile.TemporaryDirectory(prefix='otm-listener-proof-') as directory:
            directory=Path(directory);(directory/'repro_app.py').write_text(FIXTURE)
            for preload,configuration,enabled,restart in [(False,'autoload',True,False),(True,'autoload',True,True),(False,'explicit',True,False),(True,'explicit',True,False),(True,'autoload',False,False)]:
                record=case(directory,preload,configuration,enabled,restart);report['cases'].append(record);persist()
                print(json.dumps({k:record[k] for k in ['preload','configuration','enabled','worker_replacement','cleanup']}),flush=True)
        if len(report['cases'])!=5:raise AssertionError('Incomplete matrix')
        report.update(result='PASS',cleanup='verified',completed_at=datetime.now(timezone.utc).isoformat())
    except BaseException as error:report.update(result='FAILED',error_type=type(error).__name__);raise
    finally:persist()
    print(path.relative_to(ROOT));return report
if __name__=='__main__':run()
