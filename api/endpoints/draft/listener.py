"""Dedicated LISTEN connection with cooperative recovery and bounded wakeups."""
import json
import os
import select
import threading
import time
import psycopg2
from psycopg2.extensions import make_dsn, parse_dsn, ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy.engine import make_url
from operations import safe_event, run_id
from .realtime import league_id_from


def connection_arguments(engine, legacy_url=None):
    try:
        if engine.dialect.name != 'postgresql' or engine.dialect.driver != 'psycopg2': raise ValueError()
        args, params=engine.dialect.create_connect_args(engine.url)
        params=dict(params)
        # Normalize effective options (query parameters may override URL fields).
        def target(args,params):
            parsed=parse_dsn(make_dsn(*args,**params))
            return (parsed.get('host',''),parsed.get('hostaddr',''),parsed.get('service',''),str(parsed.get('port') or 5432),
                    parsed.get('dbname',''),parsed.get('user',''))
        if legacy_url is not None:
            url=make_url(legacy_url)
            if url.drivername == 'postgres':url=url.set(drivername='postgresql')
            if url.get_backend_name() != 'postgresql':raise ValueError()
            other_args,other_params=engine.dialect.create_connect_args(url)
            if target(args,params) != target(other_args,other_params): raise ValueError()
        timeout=int(params.get('connect_timeout',5))
        if not 1 <= timeout <= 30: raise ValueError()
        params['connect_timeout']=timeout
        # Ensure idle network loss eventually reaches the recovery loop.
        for key,value in {'keepalives':1,'keepalives_idle':30,'keepalives_interval':10,'keepalives_count':3}.items():
            params.setdefault(key,value)
        return args,params
    except Exception:
        raise ValueError('Listener database configuration is invalid') from None


def subscribed_leagues(socket):
    rooms=socket.server.manager.rooms.get('/',{})
    for room in tuple(rooms):
        if isinstance(room,str) and room.startswith('draft:'):
            try: yield league_id_from({'leagueId':room[6:]})
            except ValueError: continue


class DraftNotifyListener:
    MAX_PENDING=256
    BATCH=64
    PROBE_SECONDS=15

    def __init__(self,engine,socket_server,*,connect=None,wait=None,clock=None,dispatch=None,rooms=None,legacy_url=None):
        self.engine,self.socket=engine,socket_server
        self.args,self.params=connection_arguments(engine,legacy_url)
        self.connect=connect or psycopg2.connect
        self.wait=wait or (lambda conn,timeout: bool(select.select([conn],[],[],timeout)[0]))
        self.clock=clock or time.monotonic
        if dispatch is None:
            from .startDraftNotifyListener import dispatch_draft_notification
            dispatch=lambda league:dispatch_draft_notification(self.socket,self.engine,{'leagueId':league},should_deliver=lambda:not self.stopping.is_set())
        self.dispatch=dispatch
        self.rooms=rooms or (lambda:subscribed_leagues(self.socket))
        self.stopping=threading.Event()
        self.conn=None;self.task=None;self.pending={};self.resync=None
        self.state='starting';self.category=None;self.attempt=0;self.next_connect=0
        self.last_probe=0;self.opened=0;self.run_id=run_id();self.resync_offset=0

    def status(self):
        return {'enabled':True,'state':self.state,'category':self.category}

    def _state(self,state,category=None):
        self.state,self.category=state,category

    def _execute(self,statement):
        cursor=self.conn.cursor()
        try:cursor.execute(statement)
        finally:cursor.close()

    def _close(self):
        conn,self.conn=self.conn,None
        if conn is not None:
            try:conn.close()
            except Exception:pass

    def stop(self):
        if self.stopping.is_set():return
        self.stopping.set();self._close();self.pending.clear();self.resync=None
        self._state('stopped')
        safe_event('listener','stopped',self.run_id)

    def start(self):
        if self.task is None and not self.stopping.is_set():
            self.task=self.socket.start_background_task(self.run)
        return self

    def run(self):
        try:
            while not self.stopping.is_set():
                self.stopping.wait(self.step())
        finally:self.stop()

    def _failed(self,category='transport'):
        self._close();self.pending.clear();self.resync=None
        if self.stopping.is_set():return 0
        delay=min(30,2**min(self.attempt,5));self.attempt+=1
        self.next_connect=self.clock()+delay
        self._state('retrying',category)
        safe_event('listener','retrying',self.run_id,category=category,attempt=self.attempt)
        return delay

    def _deliver(self,league,attempt=0):
        if self.stopping.is_set():return
        try:
            self.dispatch(league)
            self.pending.pop(league,None)
        except Exception:
            if self.stopping.is_set():return
            if league not in self.pending and len(self.pending)>=self.MAX_PENDING:
                raise OverflowError()
            self.pending[league]=(self.clock()+min(30,2**min(attempt,5)),attempt+1)
            safe_event('listener','degraded',self.run_id,category='snapshot',leagueId=league)

    def step(self):
        if self.stopping.is_set():return 0
        now=self.clock()
        if self.conn is None and now<self.next_connect:return self.next_connect-now
        try:
            if self.conn is None:
                conn=self.connect(*self.args,**self.params)
                if self.stopping.is_set():conn.close();return 0
                self.conn=conn
                conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                self._execute('LISTEN draft_updated')
                self.opened=self.last_probe=now
                room_ids=tuple(self.rooms())
                offset=self.resync_offset % len(room_ids) if room_ids else 0
                self.resync_offset=offset
                self.resync=iter(room_ids[offset:]+room_ids[:offset])
                self._state('degraded')
                safe_event('listener','connected',self.run_id)
            # Resync streams existing room IDs; only failed deliveries enter the bounded set.
            if self.resync is not None:
                for _ in range(self.BATCH):
                    if self.stopping.is_set():return 0
                    try:league=next(self.resync)
                    except StopIteration:self.resync=None;break
                    # Advance before delivery: overflow must not restart a failing prefix.
                    self.resync_offset+=1
                    self._deliver(league)
            for league,(due,attempt) in list(self.pending.items()):
                if self.clock()>=due:self._deliver(league,attempt)
            if self.stopping.is_set():return 0
            self.wait(self.conn,1)
            if self.stopping.is_set():return 0
            self.conn.poll()
            notifications=self.conn.notifies[:]
            self.conn.notifies.clear()
            for item in notifications:
                if self.stopping.is_set():return 0
                try:
                    if len(item.payload)>4096:raise ValueError()
                    league=league_id_from(json.loads(item.payload))
                except (ValueError,TypeError):
                    safe_event('listener','rejected',self.run_id,category='invalid_notification');continue
                if league not in self.pending:
                    if len(self.pending)>=self.MAX_PENDING:raise OverflowError()
                    self.pending[league]=(self.clock(),0)
            for league,(due,attempt) in list(self.pending.items()):
                if self.clock()>=due:self._deliver(league,attempt)
            if self.clock()-self.last_probe>=self.PROBE_SECONDS:
                self._execute('SELECT 1');self.last_probe=self.clock()
            if self.clock()-self.opened>=self.PROBE_SECONDS:self.attempt=0
            if not self.stopping.is_set():
                self._state('degraded' if self.pending or self.resync is not None else 'connected',
                            'snapshot' if self.pending else None)
            return .01
        except Exception:return self._failed()
