"""Small operational boundaries: safe events and per-command session gates."""
import json
import sys
import re
from contextlib import contextmanager
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

OPERATIONS = {'weekly','finalization','ingest','refresh','listener','timeout'}
EVENTS = {'started','connected','retrying','stopped','failed','completed','skipped','rejected','degraded','recovered','unit_completed'}
CATEGORIES = {'unexpected','database','configuration','invalid_notification','already_running','snapshot','transport','gate_lost','partial_failure'}
INTEGER_FIELDS = {'leagueId','sportSeasonId','count','failures','attempt','pending'}
JOB_KEYS = {'weekly':1,'finalization':2,'ingest':3,'refresh':4}
JOB_NAMESPACE = 1330924874


def run_id():
    return uuid4().hex


def safe_event(operation, event, run_id, **fields):
    data = {'operation':operation if operation in OPERATIONS else 'unknown',
            'event':event if event in EVENTS else 'failed',
            'runId':run_id if isinstance(run_id,str) and re.fullmatch(r'[a-zA-Z0-9-]{1,64}',run_id) else 'unknown'}
    category = fields.get('category')
    if category is not None:
        data['category'] = (category if isinstance(category,str) and category in CATEGORIES else
                            'database' if isinstance(category,SQLAlchemyError) else 'unexpected')
    for key in INTEGER_FIELDS:
        if type(fields.get(key)) is int: data[key] = fields[key]
    if isinstance(fields.get('date'),str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',fields['date']): data['date']=fields['date']
    duration=fields.get('durationMs')
    if type(duration) in (int,float) and 0 <= duration < 1e15: data['durationMs']=round(duration,2)
    print(json.dumps(data,sort_keys=True),flush=True,file=sys.stderr)


class GateLost(RuntimeError):
    def __init__(self): super().__init__('Job gate connection lost')


class JobGate:
    def __init__(self, conn, key, acquired, pid):
        self.conn,self.key,self.acquired,self.pid = conn,key,acquired,pid

    def __bool__(self): return self.acquired

    def check(self):
        # Never execute on an invalidated SQLAlchemy connection: that could reconnect.
        if self.conn.invalidated is True or self.conn.closed is True: raise GateLost()
        try:
            pid=self.conn.execute(text('SELECT pg_backend_pid()')).scalar_one()
            self.conn.commit()
            if pid != self.pid: raise GateLost()
        except Exception:
            self.conn.invalidate()
            raise GateLost() from None


@contextmanager
def job_gate(engine, name):
    key=JOB_KEYS[name]
    conn=engine.connect()
    gate=None;body_failed=False
    try:
        try:
            acquired=bool(conn.execute(text('SELECT pg_try_advisory_lock(:namespace,:key)'),{'namespace':JOB_NAMESPACE,'key':key}).scalar_one())
            pid=conn.execute(text('SELECT pg_backend_pid()')).scalar_one() if acquired else None
            conn.commit()
        except Exception:
            conn.invalidate()
            raise GateLost() from None
        except BaseException:
            conn.invalidate()
            raise
        gate=JobGate(conn,key,acquired,pid)
        try: yield gate
        except BaseException:
            body_failed=True
            raise
    finally:
        try:
            if gate is not None and gate.acquired:
                if conn.invalidated is True or conn.closed is True: raise GateLost()
                released=conn.execute(text('SELECT pg_advisory_unlock(:namespace,:key)'),{'namespace':JOB_NAMESPACE,'key':key}).scalar_one()
                conn.commit()
                if not released: raise GateLost()
        except Exception:
            conn.invalidate()
            if not body_failed: raise GateLost() from None
        except BaseException:
            conn.invalidate()
            raise
        finally: conn.close()
