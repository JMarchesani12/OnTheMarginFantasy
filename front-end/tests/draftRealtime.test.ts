import test from 'node:test';
import assert from 'node:assert/strict';
import { createDraftRealtime } from '../src/lib/draftRealtime.ts';

class Socket {
  connected = false;
  handlers = new Map<string, Function>();
  emitted: unknown[][] = [];
  disconnects = 0;
  on(event: string, handler: Function) { this.handlers.set(event, handler); }
  off(event: string) { this.handlers.delete(event); }
  emit(...args: unknown[]) { this.emitted.push(args); }
  connect() { this.connected = true; this.fire('connect'); }
  disconnect() { this.connected = false; this.disconnects++; }
  fire(event: string, payload?: unknown) { this.handlers.get(event)?.(payload); }
}
const settle = () => new Promise(resolve => setImmediate(resolve));
function harness() {
  const socket = new Socket();
  const requests: {signal: AbortSignal, resolve: (v: any) => void, reject: (e: any) => void}[] = [];
  const applied: any[] = []; const errors: string[] = []; const readiness: boolean[] = []; let clears = 0;
  const controller = createDraftRealtime({socket, leagueId:10,
    read: signal => new Promise((resolve,reject) => requests.push({signal,resolve,reject})),
    apply: value => applied.push(value), clear: () => { clears++; },
    ready: value => readiness.push(value), error: value => { if(value) errors.push(value); }, loading: () => {},
  });
  return {socket,requests,applied,errors,readiness,controller,get clears() {return clears;}};
}

test('bursts serialize HTTP reads and embedded snapshots are only signals', async () => {
  const h=harness(); assert.equal(h.requests.length,1);
  h.socket.fire('draft:updated',{snapshot:{state:'old'}});
  h.socket.fire('draft:updated',{snapshot:{state:'older'}});
  assert.equal(h.requests.length,1);assert.deepEqual(h.applied,[]);
  h.requests[0].resolve({state:'first'});await settle();
  assert.equal(h.requests.length,2);
  h.requests[1].resolve({state:'current'});await settle();
  assert.deepEqual(h.applied,[{state:'first'},{state:'current'}]);
  h.controller.dispose();
});

test('every reconnect rejoins and discards an old in-flight read', async () => {
  const h=harness();h.socket.connected=false;h.socket.fire('disconnect');
  assert.equal(h.requests[0].signal.aborted,true);
  h.socket.connect();assert.equal(h.requests.length,1);
  h.requests[0].resolve({state:'obsolete'});await settle();
  assert.equal(h.requests.length,2);assert.deepEqual(h.applied,[]);
  h.requests[1].resolve({state:null,picks:[]});await settle();
  assert.deepEqual(h.applied,[{state:null,picks:[]}]);
  assert.equal(h.socket.emitted.filter(v=>v[0]==='draft:join').length,2);
  h.controller.dispose();
});

test('access denial clears view and invalidates a late success until valid join',async()=>{
  const h=harness();h.socket.fire('draft:error',{message:'Draft access denied'});
  assert.equal(h.requests[0].signal.aborted,true);assert.equal(h.readiness.at(-1),false);
  h.requests[0].resolve({private:'stale'});await settle();assert.deepEqual(h.applied,[]);
  h.socket.fire('draft:updated',{snapshot:{private:'stale'}});assert.equal(h.requests.length,1);
  h.controller.join();assert.equal(h.requests.length,2);
  h.requests[1].resolve({state:'authorized'});await settle();assert.equal(h.applied.length,1);
  h.controller.dispose();
});

test('HTTP denial blocks retries while transient failures wait for another signal',async()=>{
  const h=harness();h.requests[0].reject(Object.assign(new Error('denied'),{status:403}));await settle();
  assert.equal(h.requests.length,1);assert.equal(h.readiness.at(-1),false);
  h.controller.refresh();assert.equal(h.requests.length,1);
  h.controller.join();h.requests[1].reject(new Error('offline'));await settle();
  assert.equal(h.requests.length,2);
  h.controller.refresh();assert.equal(h.requests.length,3);
  h.requests[2].resolve({state:null,picks:[]});await settle();assert.equal(h.applied.length,1);
  h.controller.dispose();
});

test('scope disposal removes handlers, leaves once and ignores obsolete success',async()=>{
  const old=harness();old.controller.dispose();old.controller.dispose();
  const next=harness();old.requests[0].resolve({scope:'old'});await settle();
  assert.deepEqual(old.applied,[]);assert.equal(old.socket.handlers.size,0);
  assert.equal(old.socket.disconnects,1);
  assert.equal(old.socket.emitted.filter(v=>v[0]==='draft:leave').length,1);
  next.requests[0].resolve({scope:'new'});await settle();assert.deepEqual(next.applied,[{scope:'new'}]);
  next.controller.dispose();
});
