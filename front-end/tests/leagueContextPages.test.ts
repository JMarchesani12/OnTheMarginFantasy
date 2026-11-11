import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,deferred,settle,nodes,text} from './helpers/leagueContextHarness.ts';
import {leagueFixture} from './helpers/leagueFixture.ts';
function setup(screen:string,seed=true,clock?:()=>number){const h=fixture(),requests:any[]=[],calls:any[]=[],store=new Map<string,string>();let route='10',user:any={userId:1,authUserId:'A',authLoading:false,loading:false,error:null};
 const request=(kind:string,args:any[])=>{const d=deferred();requests.push({...d,kind,args});return d.promise;};
 const api:any={getLeaguesForUser:(...args:any[])=>request('list',args),getLeague:(...args:any[])=>request('single',args),getMembersOfLeague:(...args:any[])=>request('members',args),updateLeagueMember:(...args:any[])=>request('rename',args),removeLeagueMember:(...args:any[])=>request('leave',args)};
 const stubs:any={'react-router-dom':{useParams:()=>({league_id:route}),useLocation:()=>({state:seed?{league:leagueFixture()}:null}),useNavigate:()=>(...args:any[])=>calls.push(['navigate',...args])},
 '../api/leagues':api,'../../api/leagues':api,'../context/currentUserContext':{useCurrentUser:()=>user},'../../context/currentUserContext':{useCurrentUser:()=>user},
 '../../components/League/LeagueScheduleTabs':{LeagueScheduleTabs:()=>null},'../../components/League/LeagueScoreboard':{default:()=>null},
 '../../api/scoring':{getScoresForWeek:(...args:any[])=>request('scores',args)},
 '../../api/roster':{getMemberTeams:(...args:any[])=>request('teams',args),getAvailableTeams:(...args:any[])=>request('available',args)},
 '../../api/transaction':{getPendingTradesAndAddDrop:(...args:any[])=>request('pending',args),getOpenTradeRequests:(...args:any[])=>request('trades',args),submitFreeAgencyRequest:(...args:any[])=>request('addDrop',args),tradeRequestProposal:(...args:any[])=>request('trade',args),responseToTradeRequest:(...args:any[])=>request('respond',args),cancelTradeRequest:(...args:any[])=>request('cancel',args),vetoTrade:(...args:any[])=>request('veto',args)},
 '../../utils/safeStorage':{safeLocalStorage:{getItem:(key:string)=>store.get(key)??null,setItem:(key:string,value:string)=>{store.set(key,value);calls.push(['storage',key,value]);}}},
 };
 const Page=h.load(`src/screens/League/League${screen}Page.tsx`,stubs,{window:{confirm:()=>true},Date:class extends Date {static now(){return clock?clock():Date.now();}}}).default;
 const render=(id=route,patch:any={})=>{route=id;user={...user,...patch};return h.render(Page);};
 return {requests,calls,store,render,dispose:()=>h.dispose(),all:()=>nodes(h.tree),text:()=>text(h.tree),button:(label:string)=>nodes(h.tree).find(n=>n.type==='button'&&(n.props['aria-label']===label||text(n).trim()===label)),async ready(league=leagueFixture()){render();requests.find(r=>r.kind==='list').resolve([league]);await settle();render();},async flush(){await settle();render();}};
}
for(const screen of ['Detail','Roster']) {
 test(`${screen} seeded/cold require fresh matching context and clear actions before route/account responses`,async()=>{
  for(const seed of [true,false]){const h=setup(screen,seed);h.render();assert.match(h.text(),/Loading league details/);assert.equal(h.requests.length,1);assert.equal(h.requests[0].kind,'list');
   h.requests[0].resolve([leagueFixture()]);await h.flush();assert.match(h.text(),/League 10/);const oldEdit=h.button('Edit team name');
   h.render('20');assert.doesNotMatch(h.text(),/League 10/);assert.match(h.text(),/Loading league details/);if(oldEdit)oldEdit.props.onClick();
   h.render('20',{userId:2,authUserId:'B'});assert.doesNotMatch(h.text(),/League 10/);h.render('20',{userId:null,authUserId:null});assert.doesNotMatch(h.text(),/League 10/);h.dispose();}
 });
 test(`${screen} fallback stays read-only despite member-like payload; list error never falls back`,async()=>{
  const h=setup(screen);h.render();h.requests[0].resolve([]);await settle();assert.equal(h.requests[1].kind,'single');h.requests[1].resolve(leagueFixture(10,999));await h.flush();assert.equal(h.button('Edit team name'),undefined);assert.equal(h.requests.filter(r=>['teams','available','trades','pending'].includes(r.kind)).length,0);h.dispose();
  const failed=setup(screen);failed.render();failed.requests[0].reject(new Error('Forbidden'));await failed.flush();assert.match(failed.text(),/Could not load/);assert.doesNotMatch(failed.text(),/Forbidden/);assert.equal(failed.requests.length,1);failed.dispose();
 });
}
test('Detail rename/leave capture member context and obsolete mutation cannot navigate/update replacement',async()=>{
 const h=setup('Detail');await h.ready({...leagueFixture(),status:'Pre-Draft',commissionerId:9});
 h.button('Edit team name').props.onClick();h.render();const input=h.all().find(n=>n.type==='input');input.props.onChange({target:{value:'New name'}});h.render();const saving=h.button('Save').props.onClick();assert.deepEqual(h.requests.find(r=>r.kind==='rename').args,[11,'New name']);
 const leave=h.button('Leave League').props.onClick();h.render('20');h.requests.find(r=>r.kind==='rename').resolve();h.requests.find(r=>r.kind==='leave').resolve();await Promise.all([saving,leave]);await h.flush();assert.equal(h.calls.filter(c=>c[0]==='navigate').length,0);assert.doesNotMatch(h.text(),/New name|updated/);h.dispose();
});
test('Roster keeps fresh payload/week defaults and does not reload after obsolete add/drop; league tabs restore',async()=>{
 const h=setup('Roster');h.store.set('rosterTab:10','addDrop');h.store.set('rosterTab:20','trade');await h.ready();
 h.requests.find(r=>r.kind==='teams').resolve([{teamId:1,teamName:'Owned'}]);h.requests.find(r=>r.kind==='available').resolve([{teamId:2,teamName:'Available'}]);await h.flush();
 const team=h.all().find(n=>n.type==='button'&&text(n).includes('Available'));assert.ok(team);team.props.onClick();h.render();const submit=h.all().find(n=>n.type==='button'&&text(n).includes('Submit'));assert.ok(submit);const pending=submit.props.onClick();assert.deepEqual(h.requests.find(r=>r.kind==='addDrop').args,[10,1,101,11,2,null]);
 h.render('20');const next=h.requests.filter(r=>r.kind==='list').at(-1);next.resolve([leagueFixture(20,22)]);await h.flush();assert.equal(h.store.get('rosterTab:20'),'trade');
 const count=h.requests.length;h.requests.find(r=>r.kind==='addDrop').resolve();await pending;await h.flush();assert.equal(h.requests.length,count);h.dispose();
});
test('Roster partner switch hides former roster and selection in the first render; obsolete partner results stay hidden',async()=>{
 const h=setup('Roster');await h.ready();h.requests.find(r=>r.kind==='members').resolve([{id:11,teamName:'Me'},{id:12,teamName:'Partner B'},{id:13,teamName:'Partner C'}]);await h.flush();h.render();
 const b=h.requests.find(r=>r.kind==='teams'&&r.args[0]===12);b.resolve([{teamId:120,teamName:'B private team'}]);await h.flush();
 h.button('Trade').props.onClick();h.render();assert.match(h.text(),/B private team/);h.all().find(n=>n.type==='button'&&text(n).includes('B private team')).props.onClick();h.render();
 h.button('Partner C').props.onClick();h.render();assert.doesNotMatch(h.text(),/B private team/);const c=h.requests.find(r=>r.kind==='teams'&&r.args[0]===13);h.button('Partner B').props.onClick();h.render();c.resolve([{teamId:130,teamName:'C stale team'}]);await h.flush();assert.doesNotMatch(h.text(),/C stale team/);h.dispose();
});
test('Detail and Roster ignore delayed resource responses after route replacement',async()=>{
 for(const screen of ['Detail','Roster']){const h=setup(screen);await h.ready();const old=h.requests.filter(r=>r.kind!=='list');h.render('20');h.requests.filter(r=>r.kind==='list').at(-1).resolve([leagueFixture(20,22)]);await h.flush();
 for(const r of old)r.reject(new Error('Old private resource failure'));await h.flush();assert.match(h.text(),/League 20/);assert.doesNotMatch(h.text(),/Old private/);h.dispose();}
});
test('paired page retry clears error and revalidates without trusting navigation seeds',async()=>{
 for(const screen of ['Detail','Roster']){const h=setup(screen);h.render();h.requests[0].reject(new Error('Temporary failure'));await h.flush();assert.match(h.text(),/Could not load/);assert.doesNotMatch(h.text(),/Temporary failure/);h.button('Retry').props.onClick();h.render();assert.match(h.text(),/Loading league details/);assert.equal(h.requests.length,2);h.requests[1].resolve([leagueFixture()]);await h.flush();assert.match(h.text(),/League 10/);h.dispose();}
});
test('paired seeded/cold request counts stay bounded without duplicate resolution',async()=>{
 for(const screen of ['Detail','Roster'])for(const seed of [true,false]){const h=setup(screen,seed);await h.ready();h.render();h.render();const counts=h.requests.reduce((out:any,r:any)=>({...out,[r.kind]:(out[r.kind]??0)+1}),{});assert.deepEqual(counts,screen==='Detail'?{list:1,members:1,scores:1}:{list:1,teams:1,available:1,members:1,pending:1});h.dispose();}
});
test('Roster fresh trade uses matching partner/member/week and obsolete completion never reloads',async()=>{
 const h=setup('Roster');await h.ready();h.requests.find(r=>r.kind==='members').resolve([{id:11,teamName:'Me'},{id:12,teamName:'Partner'}]);h.requests.find(r=>r.kind==='teams').resolve([{teamId:1,teamName:'Own offer'}]);h.requests.find(r=>r.kind==='available').resolve([]);await h.flush();h.render();h.requests.find(r=>r.kind==='teams'&&r.args[0]===12).resolve([{teamId:2,teamName:'Receive team'}]);await h.flush();h.button('Trade').props.onClick();h.render();
 for(const label of ['Own offer','Receive team']){h.all().find(n=>n.type==='button'&&text(n).includes(label)).props.onClick();h.render();}
 const submit=h.button('Submit Trade Proposal');assert.equal(submit.props.disabled,false);const promise=submit.props.onClick();assert.deepEqual(JSON.parse(JSON.stringify(h.requests.find(r=>r.kind==='trade').args)),[10,1,101,12,11,[2],[1]]);h.render('10',{authUserId:'B',userId:2});const count=h.requests.length;h.requests.find(r=>r.kind==='trade').resolve();await promise;assert.equal(h.requests.length,count);h.dispose();
});
test('week cutoff masks previous roster/selections immediately and failed new-week reads never enable old choices',async()=>{
 let now=Date.parse('2026-11-09T01:00:00Z');const h=setup('Roster',true,()=>now);await h.ready({...leagueFixture(),currentWeekNumber:2,currentWeekStartDate:'2026-11-09T00:00:00Z'});
 h.requests.find(r=>r.kind==='teams').resolve([{teamId:1,teamName:'Old owned'}]);h.requests.find(r=>r.kind==='available').resolve([{teamId:2,teamName:'Old available'}]);await h.flush();h.all().find(n=>n.type==='button'&&text(n).includes('Old available')).props.onClick();h.render();const oldHandler=h.button('Submit Add / Drop Request').props.onClick;assert.equal(h.button('Submit Add / Drop Request').props.disabled,false);
 now=Date.parse('2026-11-09T03:00:00Z');h.render();assert.doesNotMatch(h.text(),/Old owned|Old available/);assert.equal(h.button('Submit Add / Drop Request').props.disabled,true);await oldHandler();assert.equal(h.requests.filter(r=>r.kind==='addDrop').length,0);
 const next=h.requests.filter(r=>r.kind==='teams').at(-1);assert.equal(next.args[1],2);next.reject(new Error('New week unavailable'));await h.flush();assert.equal(h.button('Submit Add / Drop Request').props.disabled,true);await h.button('Submit Add / Drop Request').props.onClick();assert.equal(h.requests.filter(r=>r.kind==='addDrop').length,0);h.dispose();
});
test('week change invalidates delayed mutation reload and command guards handle cutoff before a render',async()=>{
 for(const pendingMutation of [true,false]){let now=Date.parse('2026-11-09T01:00:00Z');const h=setup('Roster',true,()=>now);await h.ready({...leagueFixture(),currentWeekNumber:2,currentWeekStartDate:'2026-11-09T00:00:00Z'});
 h.requests.find(r=>r.kind==='teams').resolve([{teamId:1,teamName:'Owned'}]);h.requests.find(r=>r.kind==='available').resolve([{teamId:2,teamName:'Available'}]);await h.flush();h.all().find(n=>n.type==='button'&&text(n).includes('Available')).props.onClick();h.render();const handler=h.button('Submit Add / Drop Request').props.onClick;let promise:any;if(pendingMutation)promise=handler();
 now=Date.parse('2026-11-09T03:00:00Z');if(pendingMutation){h.render();const count=h.requests.length;h.requests.find(r=>r.kind==='addDrop').resolve();await settle();assert.equal(h.requests.length,count);await promise;assert.equal(h.requests.filter(r=>r.kind==='teams').at(-1).args[1],2);}else{await handler();assert.equal(h.requests.filter(r=>r.kind==='addDrop').length,0);h.render();assert.equal(h.requests.filter(r=>r.kind==='teams').at(-1).args[1],2);}h.dispose();}
});
test('fresh next-week success requires reselection and never restores previous-week form input',async()=>{
 let now=Date.parse('2026-11-09T01:00:00Z');const h=setup('Roster',true,()=>now);await h.ready({...leagueFixture(),currentWeekNumber:2,currentWeekStartDate:'2026-11-09T00:00:00Z'});
 h.requests.find(r=>r.kind==='teams').resolve([]);h.requests.find(r=>r.kind==='available').resolve([{teamId:2,teamName:'Old team'}]);await h.flush();h.all().find(n=>n.type==='button'&&text(n).includes('Old team')).props.onClick();h.render();now=Date.parse('2026-11-09T03:00:00Z');h.render();h.requests.filter(r=>r.kind==='teams').at(-1).resolve([]);h.requests.filter(r=>r.kind==='available').at(-1).resolve([{teamId:2,teamName:'Fresh team'}]);await h.flush();assert.equal(h.button('Submit Add / Drop Request').props.disabled,true);h.all().find(n=>n.type==='button'&&text(n).includes('Fresh team')).props.onClick();h.render();const p=h.button('Submit Add / Drop Request').props.onClick();assert.deepEqual(h.requests.find(r=>r.kind==='addDrop').args,[10,2,101,11,2,null]);h.dispose();h.requests.find(r=>r.kind==='addDrop').resolve();await p;
});
