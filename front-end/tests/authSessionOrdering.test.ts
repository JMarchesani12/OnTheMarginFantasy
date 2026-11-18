import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,deferred,settle} from './helpers/leagueContextHarness.ts';
const session=(id:string)=>({user:{id,email:id+'@example.test'},access_token:id+'-token'});
function setup(){const h=fixture(),reads:any[]=[],listeners=new Set<Function>(),profileCalls:any[]=[];let callback:Function=()=>{},unsubscribed=0;
 const auth={
  getSession:()=>{const d=deferred();reads.push(d);return d.promise;},
  onAuthStateChange:(fn:Function)=>{callback=fn;return {data:{subscription:{unsubscribe:()=>{unsubscribed++;}}}};},
 };
 const module=h.load('src/context/AuthContext.tsx',{
  '../lib/supabaseClient':{supabase:{auth}},
  '../api/user':{getUserByUuid:(...args:any[])=>{profileCalls.push(args);return Promise.resolve({});},createUser:()=>Promise.resolve({})},
  '../utils/safeStorage':{safeLocalStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}}},
 },{document:{visibilityState:'visible',addEventListener:(_name:string,fn:Function)=>listeners.add(fn),removeEventListener:(_name:string,fn:Function)=>listeners.delete(fn)},alert:()=>{}});
 return {reads,profileCalls,render:()=>h.render(module.AuthProvider,{children:null}).props.value,event:(value:any)=>callback('SIGNED_IN',value),visibility:()=>listeners.forEach(fn=>fn()),dispose:()=>h.dispose(),get cleaned(){return unsubscribed===1&&listeners.size===0;}};}
test('new auth event wins over initial/visibility session lookups including logout',async()=>{
 for(const latest of [session('B'),null]){const h=setup();h.render();h.event(latest);h.reads[0].resolve({data:{session:session('A')}});await settle();let v=h.render();assert.equal(v.session,latest);assert.equal(v.user?.id??null,latest?.user.id??null);h.visibility();h.event(session('C'));h.reads[1].resolve({data:{session:session('A')}});await settle();assert.equal(h.render().user.id,'C');h.dispose();assert.ok(h.cleaned);}
});
test('newest visibility lookup wins and no profile work remains in session provider',async()=>{
 const h=setup();h.render();h.reads[0].resolve({data:{session:session('A')}});await settle();h.render();assert.equal(h.profileCalls.length,0);
 h.visibility();h.visibility();h.reads[2].resolve({data:{session:session('C')}});await settle();assert.equal(h.render().user.id,'C');h.reads[1].resolve({data:{session:session('B')}});await settle();assert.equal(h.render().user.id,'C');h.dispose();assert.ok(h.cleaned);
});
test('late rejected lookup cannot clear a newer accepted session and cleanup disposes subscription',async()=>{
 const h=setup();h.render();h.event(session('B'));h.reads[0].reject(new Error('old lookup failed'));await settle();assert.equal(h.render().user.id,'B');h.visibility();h.dispose();h.reads[1].resolve({data:{session:session('A')}});await settle();assert.ok(h.cleaned);
});
