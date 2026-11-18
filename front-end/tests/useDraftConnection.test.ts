import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';
import {createDraftRealtime} from '../src/lib/draftRealtime.ts';
class Socket {
  connected=false;handlers=new Map<string,Function>();events:any[]=[];disconnects=0;
  on(name:string,fn:Function){this.handlers.set(name,fn);}
  off(name:string){this.handlers.delete(name);}
  emit(...args:any[]){this.events.push(args);}
  connect(){this.connected=true;this.fire('connect');}
  disconnect(){this.connected=false;this.disconnects++;}
  fire(name:string,data?:any){this.handlers.get(name)?.(data);}
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function fixture() {
  const url=new URL('../src/hooks/useDraftConnection.ts',import.meta.url);assert.ok(existsSync(url),'connection hook missing');
  const slots:any[]=[],sockets:Socket[]=[],socketCalls:any[]=[],requests:any[]=[],applied:any[]=[],ready:boolean[]=[],errors:any[]=[];let index=0,effects:(()=>void)[]=[],clears=0;
  const react={useRef(initial:any){const i=index++;return slots[i]??(slots[i]={current:initial});},
    useEffect(fn:any,deps:any[]){const i=index++,old=slots[i];if(!old||deps.some((v,j)=>!Object.is(v,old.deps[j])))effects.push(()=>{old?.cleanup?.();slots[i]={deps,cleanup:fn()};});}};
  const exports:any={};runInNewContext(ts.transpileModule(readFileSync(url,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,
    {exports,require:(id:string)=>{
      if(id==='react')return react;
      if(id==='socket.io-client')return {io:(...args:any[])=>{socketCalls.push(args);const s=new Socket();sockets.push(s);return s;}};
      assert.equal(id,'../lib/draftRealtime');return {createDraftRealtime};
    }});
  const defaults={leagueId:10,token:'alice',socketUrl:'https://socket.test',scopeKey:'10:alice',memberId:11,
    readSnapshot:(leagueId:number,signal:AbortSignal)=>new Promise((resolve,reject)=>requests.push({leagueId,signal,resolve,reject})),
    applySnapshot:(snapshot:any)=>applied.push(snapshot),clearDraftView:()=>{clears++;},onReady:(v:boolean)=>ready.push(v),onError:(v:any)=>errors.push(v),onLoading:()=>{}};
  let options={...defaults};
  function render(patch:any={}){options={...options,...patch};index=0;const ref=exports.useDraftConnection(options);const pending=effects;effects=[];pending.forEach(fn=>fn());return ref;}
  return {render,requests,applied,ready,errors,sockets,socketCalls,get clears(){return clears;},dispose(){for(const slot of slots)slot?.cleanup?.();}};
}
test('real hook retains controller on callbacks/member changes and applies latest callback',async()=>{
  const h=fixture();const ref=h.render();const controller=ref.current;
  assert.equal(h.sockets.length,1);assert.equal(h.socketCalls[0][1].autoConnect,false);
  assert.equal(h.socketCalls[0][1].auth.token,'alice');assert.equal(h.requests[0].leagueId,10);
  // Settle startup's coalesced refresh before testing a distinct member signal.
  h.requests[0].resolve({initial:1});await settle();h.requests[1].resolve({initial:2});await settle();
  assert.equal(h.requests.length,2);
  const latest:any[]=[];h.render({applySnapshot:(value:any)=>latest.push(value)});
  assert.equal(h.requests.length,2);h.sockets[0].fire('draft:updated');
  h.requests[2].resolve({value:1});await settle();assert.deepEqual(latest,[{value:1}]);
  h.render({memberId:12});assert.equal(h.requests.length,4);
  h.requests[3].resolve({value:2});await settle();assert.equal(h.requests.length,4);
  assert.equal(ref.current,controller);assert.equal(h.sockets.length,1);
  h.dispose();assert.equal(ref.current,null);assert.equal(h.sockets[0].disconnects,1);
});
test('token/league/account/endpoint epochs dispose actual controllers and ignore obsolete reads',async()=>{
  for(const patch of [{token:'bob'},{leagueId:20},{scopeKey:'10:another-account'},{socketUrl:'https://other.test'}]) {
    const h=fixture();const ref=h.render();const old=ref.current;h.render(patch);
    assert.notEqual(ref.current,old);assert.equal(h.sockets[0].disconnects,1);assert.equal(h.requests[0].signal.aborted,true);
    h.requests[0].resolve({private:'old'});await settle();assert.deepEqual(h.applied,[]);
    h.dispose();assert.equal(ref.current,null);
  }
});
test('missing token/league clear without subscription, then valid input starts fresh',()=>{
  for(const patch of [{token:undefined},{leagueId:null}]) {
    const h=fixture();const ref=h.render(patch);assert.equal(ref.current,null);assert.equal(h.sockets.length,0);assert.ok(h.clears>0);
    h.render({leagueId:10,token:'alice'});assert.equal(h.sockets.length,1);h.dispose();
  }
});
test('real controller reconnect/denial behavior survives the hook boundary',async()=>{
  const h=fixture();h.render();const socket=h.sockets[0];
  socket.fire('disconnect');assert.equal(h.requests[0].signal.aborted,true);socket.connect();
  assert.equal(socket.events.filter(e=>e[0]==='draft:join').length,2);
  h.requests[0].resolve({old:true});await settle();assert.equal(h.requests.length,2);assert.deepEqual(h.applied,[]);
  h.requests[1].reject(Object.assign(new Error('denied'),{status:403}));await settle();assert.equal(h.ready.at(-1),false);assert.ok(h.clears>1);
  socket.fire('draft:updated',{snapshot:{private:'ignore'}});assert.equal(h.requests.length,2);h.dispose();
});
