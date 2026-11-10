import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,deferred,settle} from './helpers/leagueContextHarness.ts';
const session=(id='A',token='A-token')=>({user:{id,email:id.toLowerCase()+'@example.test',user_metadata:{}},access_token:token});
const profile=(id=1,uuid='A')=>({id,uuid,email:'a@example.test',displayName:'Name'});
function setup(){const auth=fixture(),owner=fixture(),reads:any[]=[],calls:any[]=[],storage=new Map<string,string>(),listeners=new Set<Function>();let event:Function=()=>{},published:any;
 const request=(kind:string,args:any[])=>{const d=deferred();calls.push({...d,kind,args});return d.promise;};
 const Auth=auth.load('src/context/AuthContext.tsx',{'../lib/supabaseClient':{supabase:{auth:{getSession:()=>{const d=deferred();reads.push(d);return d.promise;},onAuthStateChange:(callback:Function)=>{event=callback;return {data:{subscription:{unsubscribe(){}}}};}}}},
 },{document:{visibilityState:'visible',addEventListener:(_name:string,fn:Function)=>listeners.add(fn),removeEventListener:(_name:string,fn:Function)=>listeners.delete(fn)}}).AuthProvider;
 const Current=owner.load('src/context/currentUserContext.tsx',{'./AuthContext':{useAuth:()=>published},'../api/user':{getUserByUuid:(...args:any[])=>request('get',args),createUser:(...args:any[])=>request('create',args)},'../utils/safeStorage':{safeLocalStorage:{getItem:(k:string)=>storage.get(k)??null,removeItem:(k:string)=>storage.delete(k)}}}).CurrentUserProvider;
 function render(){published=auth.render(Auth,{children:null}).props.value;return owner.render(Current,{children:null}).props.value;}
 render();return {calls,reads,storage,render,event:(value:any)=>event(value?'SIGNED_IN':'SIGNED_OUT',value),visibility:()=>listeners.forEach(fn=>fn()),dispose(){owner.dispose();auth.dispose();}};
}
test('accepted logout blocks a pending404 from creating before either provider rerenders',async()=>{
 const h=setup();h.event(session());h.render();assert.equal(h.calls.length,1);h.event(null);h.calls[0].resolve(null);await settle();assert.equal(h.calls.length,1);h.dispose();
});
test('batched A→logout→A preserves the account boundary, rejects old create/hint cleanup and starts fresh lookup',async()=>{
 const h=setup();const raw=JSON.stringify({email:'a@example.test',displayName:'Signup'});h.storage.set('otm:pending-user-create',raw);h.event(session());const old=h.render();h.calls[0].resolve(null);await settle();assert.equal(h.calls[1].kind,'create');
 h.event(null);h.event(session());assert.equal(old.isCurrentIdentity(),false);h.calls[1].resolve(profile(1));await settle();const next=h.render();assert.notEqual(next.identityKey,old.identityKey);assert.equal(next.userId,null);assert.equal(h.storage.get('otm:pending-user-create'),raw);assert.equal(h.calls[2].kind,'get');h.calls[2].resolve(profile(2));await settle();assert.equal(h.render().userId,2);h.dispose();
});
test('token continuity changes immediately while ready same-subject identity remains stable',async()=>{
 const pending=setup();pending.event(session());pending.render();pending.event(session('A','renewed'));pending.calls[0].resolve(null);await settle();assert.equal(pending.calls.length,1);pending.render();assert.equal(pending.calls[1].args[1],'renewed');pending.dispose();
 const ready=setup();ready.event(session());ready.render();ready.calls[0].resolve(profile());await settle();const before=ready.render();ready.event(session('A','renewed'));const after=ready.render();assert.equal(after.identityKey,before.identityKey);assert.equal(after.userId,1);assert.equal(ready.calls.length,1);ready.dispose();
});
test('accepted visibility lookup results also invalidate old profile work before rerender',async()=>{
 const h=setup();h.event(session());h.render();h.visibility();h.reads[1].resolve({data:{session:null}});await settle();h.calls[0].resolve(null);await settle();assert.equal(h.calls.length,1);h.dispose();
});
test('credential continuity compares captured values even if the SDK reuses a mutable session object',async()=>{
 const h=setup();const reused=session();h.event(reused);h.render();reused.access_token='renewed';h.event(reused);h.calls[0].resolve(null);await settle();assert.equal(h.calls.length,1);h.render();assert.equal(h.calls[1].args[1],'renewed');h.dispose();
});
