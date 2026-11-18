"""Actual eventlet scheduling in a fresh process; no server/DB/config is started."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

class DevCooperativeTests(unittest.TestCase):
    def test_dev_listener_yields_to_other_socket_tasks(self):
        script=r'''
import sys,types,time
import eventlet
sys.path.insert(0,sys.argv[1])
runtime=types.ModuleType('runtime')
holder={};heartbeat=[]
def compose(**kwargs):
    from flask import Flask
    from flask_socketio import SocketIO
    from sqlalchemy.engine import make_url
    from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
    from endpoints.draft.listener import DraftNotifyListener
    app=Flask('cooperative-only');server=SocketIO(app,async_mode='eventlet')
    class Conn:
        notifies=[]
        def set_isolation_level(self,value):pass
        def cursor(self):return types.SimpleNamespace(execute=lambda sql:None,close=lambda:None)
        def close(self):pass
        def poll(self):
            holder['polls']+=1
            if holder['polls']>=5:holder['listener'].stop()
    engine=types.SimpleNamespace(url=make_url('postgresql://postgres@127.0.0.1/synthetic'),dialect=PGDialect_psycopg2())
    holder['polls']=0
    listener=DraftNotifyListener(engine,server,connect=lambda *a,**kw:Conn(),wait=lambda c,t:time.sleep(.02),rooms=lambda:iter([]),dispatch=lambda league:None)
    holder['listener']=listener;listener.start()
    server.start_background_task(lambda:heartbeat.append(not listener.stopping.is_set()))
    def serve(app,**kwargs):
        eventlet.sleep(.2)
        assert heartbeat==[True], 'listener starved the eventlet task until stop: '+str(heartbeat)
    server.run=serve
    module=types.ModuleType('socketioInstance');module.socketio=server;sys.modules['socketioInstance']=module
    return app
runtime.create_web_app=compose
runtime.stop_web_listener=lambda app:holder['listener'].stop()
sys.modules['runtime']=runtime
import dev
dev.main()
'''
        result=subprocess.run([sys.executable,'-c',script,str(Path(__file__).parents[1])],
            capture_output=True,text=True,timeout=15,env={'PATH':os.environ.get('PATH',''),'PYTHON_DOTENV_DISABLED':'1','EVENTLET_NO_GREENDNS':'yes'})
        self.assertEqual(result.returncode,0,result.stderr)
