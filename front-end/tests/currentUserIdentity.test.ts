import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,deferred,settle} from './helpers/leagueContextHarness.ts';
function authSource(){let identity=0,credential=0,subject:string|null=null,currentToken:string|null=null;
 return (id:string|null,loading=false,token=id+'-token')=>{if(subject!==id)identity++;if(subject!==id||currentToken!==token)credential++;subject=id;currentToken=token;const capturedIdentity=identity,capturedCredential=credential;
 const user=id?{id,email:id.toLowerCase()+'@example.test',user_metadata:{username:'Name '+id}}:null;
 return {user,loading,session:user?{user,access_token:token}:null,sessionIdentityKey:String(identity),isSessionIdentityCurrent:()=>identity===capturedIdentity,isSessionCredentialCurrent:()=>credential===capturedCredential};};}
function setup(){const h=fixture(),requests:any[]=[];const source=authSource();let auth:any=source('A');
 const setAuth=(id:string|null,loading=false,token=id+'-token')=>{auth=source(id,loading,token);};
 const module=h.load('src/context/currentUserContext.tsx',{'./AuthContext':{useAuth:()=>auth},'../lib/supabaseClient':{supabase:{from:()=>{throw new Error('Direct User-table reads forbidden');}}},
 '../api/user':{getUserByUuid:(...args:any[])=>{const d=deferred();requests.push({...d,kind:'get',args});return d.promise;},createUser:(...args:any[])=>{const d=deferred();requests.push({...d,kind:'create',args});return d.promise;}},'../utils/safeStorage':{safeLocalStorage:{getItem:()=>null,removeItem:()=>{}}}});
 return {requests,render:()=>h.render(module.CurrentUserProvider,{children:null}).props.value,auth:setAuth,replay:()=>h.replayEffects(),dispose:()=>h.dispose()};}
const profile=(id:number,uuid='A')=>({id,uuid,email:id+'@example.test',displayName:'user'+id});
test('provider masks identity during account changes and rejects delayed old subject',async()=>{
 const h=setup();h.render();h.requests[0].resolve(profile(1));await settle();assert.equal(h.render().userId,1);
 h.auth('B');assert.equal(h.render().userId,null);h.auth('A');h.render();h.requests[2].resolve(profile(3));await settle();assert.equal(h.render().userId,3);
 h.requests[1].resolve(profile(2,'B'));await settle();assert.equal(h.render().userId,3);
 h.auth(null);assert.equal(h.render().userId,null);h.dispose();
});
test('provider refresh failure/empty withholds old identity; latest refresh wins',async()=>{
 const h=setup();h.render();h.requests[0].resolve(profile(1));await settle();let value=h.render();
 const first=value.refreshUser(),second=value.refreshUser();h.requests[2].resolve(profile(2));await second;h.requests[1].resolve(profile(9));await assert.rejects(first);assert.equal(h.render().userId,2);
 value=h.render();const fail=value.refreshUser();h.requests[3].reject(new Error('denied'));await assert.rejects(fail);value=h.render();assert.equal(value.userId,null);assert.ok(value.error);
 const empty=value.refreshUser();h.requests[4].resolve(undefined);await assert.rejects(empty);assert.equal(h.render().userId,null);h.dispose();
});
test('auth loading and logout prevent pending profile exposure',async()=>{
 const h=setup();h.render();h.auth(null,true);assert.equal(h.render().userId,null);h.requests[0].resolve(profile(1));await settle();assert.equal(h.render().userId,null);h.auth(null);assert.equal(h.render().userId,null);h.dispose();
});
test('same-identity renders coalesce pending load; ready token renewal preserves profile, deliberate refresh uses latest credential',async()=>{
 const h=setup();h.render();h.render();assert.equal(h.requests.length,1);h.requests[0].resolve(profile(1));await settle();const ready=h.render();h.auth('A',false,'renewed-token');const next=h.render();assert.equal(next.userId,1);assert.equal(next.identityKey,ready.identityKey);assert.equal(h.requests.length,1);
 const p=next.refreshUser();assert.equal(h.requests[1].args[1],'renewed-token');assert.equal(h.render().userId,null);h.requests[1].resolve(profile(1));await p;assert.equal(h.render().userId,1);h.dispose();
});
test('pending/failed bootstrap restarts once with changed credential; stale response cannot provision',async()=>{
 const h=setup();h.render();h.auth('A',false,'new-token');h.render();assert.equal(h.requests[0].args[2].aborted,true);assert.equal(h.requests.length,2);h.requests[0].resolve(null);await settle();assert.equal(h.requests.length,2);h.requests[1].reject(new Error('denied'));await settle();assert.ok(h.render().error);h.render();assert.equal(h.requests.length,2);
 h.auth('A',false,'another-token');h.render();assert.equal(h.requests.length,3);h.requests[2].resolve(profile(1));await settle();assert.equal(h.render().userId,1);h.dispose();
});
test('old create completion and stale refresh callback cannot publish into B or issue B work',async()=>{
 const h=setup();h.render();h.requests[0].resolve(null);await settle();assert.equal(h.requests[1].kind,'create');const old=h.render();h.auth('B');assert.equal(h.render().userId,null);h.requests[1].resolve(profile(1));await settle();assert.equal(h.render().userId,null);const count=h.requests.length;await assert.rejects(old.refreshUser());assert.equal(h.requests.length,count);h.requests[2].resolve(profile(2,'B'));await settle();assert.equal(h.render().userId,2);h.dispose();
});
test('a refresh superseded between bootstrap validation and publication rejects rather than announcing success',async()=>{
 const h=setup();h.render();h.requests[0].resolve(profile(1));await settle();const value=h.render();const promise=value.refreshUser();h.requests[1].resolve(profile(1));queueMicrotask(()=>{h.auth('B');h.render();});await assert.rejects(promise);assert.equal(h.render().userId,null);h.dispose();
});
test('provider publication guard rejects a validated result whose identity was superseded before its callback',async()=>{
 const h=fixture(),requests:any[]=[];const source=authSource();let auth:any=source('A');
 const module=h.load('src/context/currentUserContext.tsx',{'./AuthContext':{useAuth:()=>auth},'../lib/profileBootstrap':{ProfileSetupError:class extends Error{},loadApplicationProfile:()=>{const d=deferred();requests.push(d);return d.promise;}}});
 const render=()=>h.render(module.CurrentUserProvider,{children:null}).props.value;render();requests[0].resolve(profile(1));await settle();const p=render().refreshUser();
 queueMicrotask(()=>{auth=source('B');render();});requests[1].resolve(profile(1));await assert.rejects(p);assert.equal(render().userId,null);h.dispose();
});
test('effect cleanup/setup replay starts a fresh read rather than coalescing an aborted attempt',async()=>{
 const h=setup();h.render();h.replay();assert.equal(h.requests[0].args[2].aborted,true);assert.equal(h.requests.length,2);h.requests[0].resolve(profile(9));await settle();assert.equal(h.render().userId,null);h.requests[1].resolve(profile(1));await settle();assert.equal(h.render().userId,1);h.dispose();
});
