import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,deferred,settle} from './helpers/leagueContextHarness.ts';
import {leagueFixture} from './helpers/leagueFixture.ts';
function setup(){const h=fixture(),requests:any[]=[];let user:any={userId:1,authUserId:'A',authLoading:false,loading:false,error:null},route='10',result:any;
 const api:any={getLeaguesForUser:(...args:any[])=>{const d=deferred();requests.push({...d,kind:'list',args});return d.promise;},getLeague:(...args:any[])=>{const d=deferred();requests.push({...d,kind:'single',args});return d.promise;}};
 const stubs={'../api/leagues':api,'../context/currentUserContext':{useCurrentUser:()=>user}};
 const resolver=h.load('src/utils/leagueContext.ts',stubs);const hook=h.load('src/hooks/useLeagueContext.ts',stubs);
 function Component(){result=hook.useLeagueContext(route);return null;}
 return {requests,api,resolver,render:(patch:any={},id=route)=>{user={...user,...patch};route=id;h.render(Component);return result;},dispose:()=>h.dispose()};}
test('resolver maps member and fallback with explicit provenance, rejects mismatches and list errors',async()=>{
 const h=setup();let p=h.resolver.resolveLeagueContext(10,1,new AbortController().signal);h.requests[0].resolve({leagues:[leagueFixture()]});let r=await p;assert.equal(r.isMember,true);assert.equal(r.league.leagueId,10);
 p=h.resolver.resolveLeagueContext(10,1,new AbortController().signal);h.requests[1].resolve([]);await settle();h.requests[2].resolve(leagueFixture(10,999));r=await p;assert.equal(r.isMember,false);assert.equal(r.league.memberId,0);
 p=h.resolver.resolveLeagueContext(10,1,new AbortController().signal);h.requests[3].resolve([]);await settle();h.requests[4].resolve(leagueFixture(20));await assert.rejects(p,/match/i);
 p=h.resolver.resolveLeagueContext(10,1,new AbortController().signal);h.requests[5].reject(new Error('denied'));await assert.rejects(p,/denied/);assert.equal(h.requests.length,6);h.dispose();
});
test('hook masks route/account generations immediately, aborts old reads and never revives A→B→A',async()=>{
 const h=setup();h.render();h.requests[0].resolve([leagueFixture()]);await settle();const first=h.render();assert.ok(first.league);assert.equal(first.isCurrent(),true);
 let r=h.render({},'20');assert.equal(r.league,null);assert.equal(first.isCurrent(),false);assert.equal(h.requests[0].args[2].aborted,true);
 r=h.render({authUserId:'B',userId:2},'10');assert.equal(r.league,null);r=h.render({authUserId:'A',userId:1});assert.equal(r.league,null);
 h.requests[1].resolve([leagueFixture(20)]);h.requests[2].resolve([leagueFixture()]);await settle();assert.equal(h.render().league,null);
 h.requests[3].resolve([leagueFixture()]);await settle();r=h.render();assert.ok(r.league);assert.equal(first.isCurrent(),false);h.dispose();assert.equal(r.isCurrent(),false);
});
test('invalid routes and unresolved identity issue no requests; error/empty profiles cannot enable context',()=>{
 for(const id of ['0','-1','NaN','1.5','9007199254740992','10junk','']){const h=setup();const r=h.render({},id);assert.equal(r.league,null);assert.ok(r.error);assert.equal(h.requests.length,0);h.dispose();}
 for(const patch of [{loading:true},{authLoading:true},{userId:null},{authUserId:null},{error:'No profile',userId:null}]){const h=setup();assert.equal(h.render(patch).league,null);assert.equal(h.requests.length,0);h.dispose();}
});
test('explicit retry starts a fresh matching generation and cannot publish an earlier attempt',async()=>{
 const h=setup();h.render();h.requests[0].reject(new Error('Temporary failure'));await settle();let r=h.render();assert.match(r.error,/Temporary/);r.retry();r=h.render();assert.equal(r.error,null);assert.equal(r.loading,true);assert.equal(h.requests.length,2);h.requests[1].resolve([leagueFixture()]);await settle();r=h.render();assert.ok(r.league);const old=r;r.retry();r=h.render();assert.equal(r.league,null);assert.equal(old.isCurrent(),false);h.dispose();
});
