import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,deferred,settle} from './helpers/leagueContextHarness.ts';
const key='otm:pending-user-create';
const profile=(id=1,uuid='A')=>({id,uuid,email:'a@example.test',displayName:'Canonical',createdAt:'2026-01-01'});
function setup(raw?:string){const h=fixture(),calls:any[]=[],store=new Map<string,string>();if(raw)store.set(key,raw);let current=true;
 const request=(kind:string,args:any[])=>{const d=deferred();calls.push({...d,kind,args});return d.promise;};
 const module=h.load('src/lib/profileBootstrap.ts',{'../api/user':{getUserByUuid:(...args:any[])=>request('get',args),createUser:(...args:any[])=>request('create',args)},'../utils/safeStorage':{safeLocalStorage:{getItem:(k:string)=>store.get(k)??null,removeItem:(k:string)=>store.delete(k)}}});
 const controller=new AbortController();return {calls,store,controller,obsolete:()=>{current=false;},load:(patch:any={})=>module.loadApplicationProfile({subject:'A',accessToken:'A-token',email:'a@example.test',username:'Metadata',signal:controller.signal,isCurrent:()=>current,...patch})};}
test('profile read and missing-profile create bind exact subject/token/signal and clear matching unchanged hint only',async()=>{
 const h=setup(JSON.stringify({email:' A@example.test ',displayName:' Signup '}));const p=h.load();assert.equal(h.calls[0].kind,'get');assert.equal(h.calls[0].args[0],'A');assert.equal(h.calls[0].args[1],'A-token');assert.equal(h.calls[0].args[2],h.controller.signal);
 h.calls[0].resolve(null);await settle();assert.equal(h.calls[1].kind,'create');assert.equal(h.calls[1].args[0],'Signup');assert.equal(h.calls[1].args[1],'A-token');assert.equal(h.calls[1].args[2],h.controller.signal);h.calls[1].resolve(profile());assert.equal((await p).id,1);assert.equal(h.store.has(key),false);assert.equal(h.calls.length,2);
});
test('create409 converges by exactly one self-read, while empty reread fails without second creation',async()=>{
 for(const canonical of [profile(),null]){const h=setup(),p=h.load();h.calls[0].resolve(null);await settle();h.calls[1].reject(Object.assign(new Error('conflict'),{status:409}));await settle();assert.equal(h.calls[2].kind,'get');h.calls[2].resolve(canonical);if(canonical)assert.equal((await p).uuid,'A');else await assert.rejects(p);assert.equal(h.calls.length,3);}
});
test('denied/network reads and ambiguous create failures never replay writes',async()=>{
 for(const error of [Object.assign(new Error('denied'),{status:403}),Object.assign(new Error('expired'),{status:401}),new Error('network')]){const h=setup(),p=h.load();h.calls[0].reject(error);await assert.rejects(p);assert.equal(h.calls.length,1);}
 const h=setup(),p=h.load();h.calls[0].resolve(null);await settle();h.calls[1].reject(new Error('unknown commit outcome'));await assert.rejects(p);assert.equal(h.calls.length,2);
});
test('mismatched hints never supply name/email authority, existing profiles never get renamed, and newer hints survive',async()=>{
 const raw=JSON.stringify({email:'other@example.test',displayName:'Other private name'}),h=setup(raw),p=h.load();h.calls[0].resolve(null);await settle();assert.equal(h.calls[1].args[0],'Metadata');h.calls[1].resolve(profile());await p;assert.equal(h.store.get(key),raw);
 const current=setup(JSON.stringify({email:'a@example.test',displayName:'Signup'})),q=current.load();current.store.set(key,'newer signup');current.calls[0].resolve(profile());await q;assert.equal(current.calls.length,1);assert.equal(current.store.get(key),'newer signup');
});
test('obsolete read cannot create and obsolete creation cannot clear storage; aborted/mismatched profiles never publish',async()=>{
 const h=setup(),p=h.load();h.obsolete();h.calls[0].resolve(null);await assert.rejects(p);assert.equal(h.calls.length,1);
 const raw=JSON.stringify({email:'a@example.test',displayName:'Signup'}),late=setup(raw),q=late.load();late.calls[0].resolve(null);await settle();late.obsolete();late.calls[1].resolve(profile());await assert.rejects(q);assert.equal(late.store.get(key),raw);
 for(const value of [profile(1,'B'),profile(0),profile(Number.MAX_SAFE_INTEGER+1)]){const wrong=setup(),r=wrong.load();wrong.calls[0].resolve(value);await assert.rejects(r);assert.equal(wrong.calls.length,1);}
 const aborted=setup(),r=aborted.load();aborted.controller.abort();aborted.calls[0].resolve(profile());await assert.rejects(r);
});
test('malformed hints are discarded safely, metadata/email fallback works, and no session email means no create',async()=>{
 for(const [raw,username,name] of [['bad json',' Metadata ','Metadata'],['null',null,'a'],['[]',12,'a']]){const h=setup(raw as string),p=h.load({username});h.calls[0].resolve(null);await settle();assert.equal(h.calls[1].args[0],name);h.calls[1].resolve(profile());await p;assert.equal(h.store.has(key),false);}
 const h=setup(JSON.stringify({email:'spoof@example.test',displayName:'Spoof'})),p=h.load({email:undefined});h.calls[0].resolve(null);await assert.rejects(p);assert.equal(h.calls.length,1);
});
