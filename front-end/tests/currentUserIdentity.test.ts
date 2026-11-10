import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,deferred,settle} from './helpers/leagueContextHarness.ts';
function setup(){const h=fixture(),requests:any[]=[];let auth:any={user:{id:'A'},loading:false};
 const module=h.load('src/context/currentUserContext.tsx',{'./AuthContext':{useAuth:()=>auth},'../lib/supabaseClient':{supabase:{from:()=>({select:()=>({eq:(_key:any,subject:any)=>({maybeSingle:()=>{const d=deferred();requests.push({...d,subject});return d.promise;}})})})}}});
 return {requests,render:()=>h.render(module.CurrentUserProvider,{children:null}).props.value,auth:(id:string|null,loading=false)=>{auth={user:id?{id}:null,loading};},dispose:()=>h.dispose()};}
const profile=(id:number)=>({data:{id,email:id+'@example.test',displayName:'user'+id},error:null});
test('provider masks identity during account changes and rejects delayed old subject',async()=>{
 const h=setup();h.render();h.requests[0].resolve(profile(1));await settle();assert.equal(h.render().userId,1);
 h.auth('B');assert.equal(h.render().userId,null);h.auth('A');h.render();h.requests[2].resolve(profile(3));await settle();assert.equal(h.render().userId,3);
 h.requests[1].resolve(profile(2));await settle();assert.equal(h.render().userId,3);
 h.auth(null);assert.equal(h.render().userId,null);h.dispose();
});
test('provider refresh failure/empty withholds old identity; latest refresh wins',async()=>{
 const h=setup();h.render();h.requests[0].resolve(profile(1));await settle();let value=h.render();
 const first=value.refreshUser(),second=value.refreshUser();h.requests[2].resolve(profile(2));await second;h.requests[1].resolve(profile(9));await first;assert.equal(h.render().userId,2);
 value=h.render();const fail=value.refreshUser();h.requests[3].resolve({data:null,error:new Error('denied')});await fail;value=h.render();assert.equal(value.userId,null);assert.ok(value.error);
 const empty=value.refreshUser();h.requests[4].resolve({data:null,error:null});await empty;assert.equal(h.render().userId,null);h.dispose();
});
test('auth loading and logout prevent pending profile exposure',async()=>{
 const h=setup();h.render();h.auth(null,true);assert.equal(h.render().userId,null);h.requests[0].resolve(profile(1));await settle();assert.equal(h.render().userId,null);h.auth(null);assert.equal(h.render().userId,null);h.dispose();
});
