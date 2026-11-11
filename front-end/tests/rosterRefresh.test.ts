import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,deferred,settle,nodes,text} from './helpers/leagueContextHarness.ts';
import {leagueFixture} from './helpers/leagueFixture.ts';

// Missing sibling invalidation, optimistic ownership, or obsolete publication breaks these tests.
function setup(clock?:()=>number) {
 const h=fixture(),requests:any[]=[];let key='A:10';let league:any=leagueFixture();
 const checks=new Map<string,()=>boolean>();
 const req=(kind:string,args:any[])=>{const d=deferred();const r={...d,kind,args,done:false};requests.push(r);return d.promise;};
 const Page=h.load('src/screens/League/LeagueRosterPage.tsx',{
  'react-router-dom':{useNavigate:()=>()=>{},useParams:()=>({league_id:String(league.leagueId)})},
  '../../hooks/useLeagueContext':{useLeagueContext:()=>{const captured=key;if(!checks.has(key))checks.set(key,()=>key===captured);return {league,isMember:true,scopeKey:key,isCurrent:checks.get(key)};}},
  '../../api/leagues':{getMembersOfLeague:(...a:any[])=>req('members',a)},
  '../../api/roster':{getMemberTeams:(...a:any[])=>req('teams',a),getAvailableTeams:(...a:any[])=>req('available',a)},
  '../../api/transaction':Object.fromEntries(Object.entries({submitFreeAgencyRequest:'addDrop',tradeRequestProposal:'proposal',getOpenTradeRequests:'open',getPendingTradesAndAddDrop:'pending',responseToTradeRequest:'respond',cancelTradeRequest:'cancel',vetoTrade:'veto'}).map(([name,kind])=>[name,(...a:any[])=>req(kind,a)])),
  '../../utils/safeStorage':{safeLocalStorage:{getItem:()=>null,setItem:()=>{}}},
 },{window:{},Date:class extends Date {static now(){return clock?clock():Date.now();}}}).default;
 const render=()=>h.render(Page);const all=()=>nodes(h.tree);
 const button=(label:string)=>all().find(n=>n.type==='button'&&(text(n).trim()===label||n.props['aria-label']===label));
 const resolve=(r:any,value:any)=>{r.done=true;r.resolve(value);};
 const reject=(r:any)=>{r.done=true;r.reject(new Error('Read unavailable'));};
 const waiting=(kind:string)=>requests.filter(r=>r.kind===kind&&!r.done);
 const flush=async()=>{await settle();render();await settle();render();};
 const settleReads=async(override:any={})=>{
  for(let i=0;i<3;i++){
   for(const r of requests.filter(r=>!r.done&&['teams','available','members','open','pending'].includes(r.kind))){
    const value=r.kind in override?override[r.kind]:r.kind==='teams'?(r.args[0]===11?[team(1,'Owned')]:[team(2,'Partner team')]):r.kind==='available'?[team(3,'Available')]:r.kind==='members'?[{id:11,teamName:'Me'},{id:12,teamName:'Partner'},{id:13,teamName:'Other partner'}]:r.kind==='open'?openTrades():[];
    resolve(r,typeof value === 'function' ? value(r) : value);
   }await flush();
  }
 };
 return {requests,waiting,render,all,button,resolve,reject,flush,settleReads,text:()=>text(h.tree),dispose:()=>h.dispose(),
  async ready(){render();await settleReads();},
  click(label:string){const b=button(label);assert.ok(b,label);assert.equal(b.props.disabled===true,false,label);const p=b.props.onClick();render();return p;},
  switchContext(){key='B:20';league=leagueFixture(20,22);render();},
  setLeague(patch:any){league={...league,...patch};render();},
 };
}
const team=(teamId:number,teamName:string)=>({teamId,teamName,conferenceName:'Conference'});
const trade={transactionId:7,status:'PROPOSED',createdAt:'2026-11-01',weekNumber:1,fromTeams:[],toTeams:[]};
const openTrades=()=>({mine:{incoming:[trade],outgoing:[trade]},others:[trade]});
const pending=[{id:7,type:'TRADE',status:'PENDING_APPLY',createdAt:'2026-11-01',weekNumber:1,memberFromId:11,memberToId:12}];

test('add/drop refreshes pending and all roster resources without optimistic projected ownership',async()=>{
 const h=setup();await h.ready();h.click('Available');const before=h.requests.length;const p=h.click('Submit Add / Drop Request');h.resolve(h.waiting('addDrop')[0],{status:'PENDING_APPLY',memberRosterTeamIds:[3]});await h.flush();
 const reads=h.requests.slice(before).filter(r=>r.kind!=='addDrop');assert.deepEqual(reads.map(r=>r.kind).sort(),['available','pending','teams','teams']);assert.equal(h.button('Submit Add / Drop Request').props.disabled,true);
 await h.settleReads({pending});assert.match(h.text(),/PENDING_APPLY/);assert.ok(h.button('Owned'));assert.equal(h.button('Submit Add / Drop Request').props.disabled,true);h.dispose();
});

test('proposal refreshes outgoing and pending without remounting the trade tab or selected partner',async()=>{
 const h=setup();await h.ready();h.click('Trade');await h.settleReads({open:{mine:{incoming:[],outgoing:[]},others:[]}});h.click('Outgoing');h.click('Owned');h.click('Partner team');const p=h.click('Submit Trade Proposal');h.resolve(h.waiting('proposal')[0],{status:'PROPOSED'});await h.flush();assert.equal(h.waiting('open').length,1);assert.equal(h.waiting('pending').length,1);await h.settleReads();assert.match(h.text(),/Cancel/);assert.match(h.text(),/Request from Partner/);assert.equal(h.button('Trade').props.className.includes('is-active'),true);h.dispose();
});

for(const label of ['Accept','Reject','Cancel','Veto','Unveto'])test(`${label} refreshes siblings and retains authoritative ownership`,async()=>{
 const h=setup();await h.ready();h.click('Trade');await h.settleReads({open:label==='Unveto'?{...openTrades(),others:[{...trade,memberHasVetoed:true}]}:openTrades()});
 if(label==='Cancel')h.click('Outgoing');if(label==='Veto'||label==='Unveto')h.click('League');const before=h.requests.length;const p=h.click(label);const kind=label==='Cancel'?'cancel':label==='Veto'||label==='Unveto'?'veto':'respond';h.resolve(h.waiting(kind)[0],{status:'PENDING_APPLY'});await h.flush();
 assert.deepEqual(h.requests.slice(before).filter(r=>r.kind!==kind).map(r=>r.kind).sort(),['available','open','pending','teams','teams']);await h.settleReads({pending});assert.match(h.text(),/PENDING_APPLY/);assert.ok(h.button('Owned'));h.dispose();
});

test('failed write retains selected teams and does not refresh siblings',async()=>{
 const h=setup();await h.ready();h.click('Available');const before=h.requests.length;const p=h.click('Submit Add / Drop Request');h.reject(h.waiting('addDrop')[0]);await h.flush();assert.equal(h.requests.length,before+1);assert.equal(h.button('Submit Add / Drop Request').props.disabled,false);h.dispose();
});

test('confirmed write followed by failed read remains submitted and retry only reads',async()=>{
 const h=setup();await h.ready();h.click('Available');const p=h.click('Submit Add / Drop Request');h.resolve(h.waiting('addDrop')[0],{});await h.flush();h.reject(h.waiting('teams').find(r=>r.args[0]===11));await h.flush();assert.match(h.text(),/submitted/i);assert.match(h.text(),/Read unavailable/);assert.equal(h.button('Submit Add / Drop Request').props.disabled,true);
 h.click('Retry roster data');await h.flush();await h.settleReads({teams:[team(3,'Applied owned')],pending});assert.equal(h.requests.filter(r=>r.kind==='addDrop').length,1);assert.match(h.text(),/PENDING_APPLY/);assert.ok(h.button('Applied owned'));h.dispose();
});

test('late mutation cannot refresh replacement context and pending reads are aborted on unmount',async()=>{
 const h=setup();await h.ready();h.click('Available');const p=h.click('Submit Add / Drop Request');h.switchContext();const count=h.requests.length;h.resolve(h.waiting('addDrop')[0],{});await h.flush();assert.equal(h.requests.length,count);const pendingReads=h.requests.filter(r=>!r.done&&r.args.at(-1)?.aborted!==undefined);h.dispose();assert.ok(pendingReads.every(r=>r.args.at(-1).aborted));for(const r of pendingReads)h.resolve(r,[]);await settle();
});

test('failed open-trade refresh never leaves stale trade actions usable',async()=>{
 const h=setup();await h.ready();h.click('Trade');await h.settleReads();const oldAccept=h.button('Accept').props.onClick;h.click('Refresh trade requests');h.reject(h.waiting('open').at(-1));await h.flush();assert.equal(h.button('Accept'),undefined);const count=h.requests.filter(r=>r.kind==='respond').length;await oldAccept();assert.equal(h.requests.filter(r=>r.kind==='respond').length,count);h.dispose();
});

test('partner change during proposal preserves the newer partner selection across refresh',async()=>{
 const h=setup();await h.ready();h.click('Trade');await h.settleReads();h.click('Owned');h.click('Partner team');h.click('Submit Trade Proposal');h.click('Other partner');await h.settleReads({teams:(r:any)=>r.args[0]===11?[team(1,'Owned')]:[team(4,'New partner team')]});h.click('New partner team');h.resolve(h.waiting('proposal')[0],{});await h.flush();await h.settleReads({teams:(r:any)=>r.args[0]===11?[team(1,'Owned')]:[team(4,'New partner team')]});const selected=h.all().find(n=>n.type==='button'&&text(n)==='New partner team');assert.equal(selected.props['aria-pressed'],true);assert.match(h.text(),/Request from Other partner/);h.dispose();
});

test('overlapping mutation refreshes supersede old reads and stale failures cannot re-enable old teams',async()=>{
 const h=setup();await h.ready();h.click('Trade');await h.settleReads();h.click('Accept');h.resolve(h.waiting('respond')[0],{});await h.flush();const oldReads=h.requests.filter(r=>!r.done&&r.kind!=='respond');
 // A manual retry starts the next revision while prior requests are unresolved.
 const own=oldReads.find(r=>r.kind==='teams'&&r.args[0]===11);h.reject(own);await h.flush();h.click('Retry roster data');await h.flush();for(const r of oldReads.filter(r=>!r.done)){h.reject(r);}await h.flush();assert.equal(h.button('Submit Trade Proposal').props.disabled,true);await h.settleReads();assert.ok(h.button('Owned'));assert.doesNotMatch(h.text(),/Read unavailable/);h.dispose();
});

test('trade acceptance completing after cutoff before render cannot refresh the new week',async()=>{
 let now=Date.parse('2026-11-09T01:00:00Z');const h=setup(()=>now);h.setLeague({currentWeekNumber:2,currentWeekStartDate:'2026-11-09T00:00:00Z'});await h.settleReads();h.click('Trade');await h.settleReads();h.click('Accept');const before=h.requests.length;now=Date.parse('2026-11-09T03:00:00Z');h.resolve(h.waiting('respond')[0],{});await settle();assert.equal(h.requests.length,before);h.dispose();
});

test('week replacement masks old trade actions before refreshed open trades resolve',async()=>{
 let now=Date.parse('2026-11-09T01:00:00Z');const h=setup(()=>now);h.setLeague({currentWeekNumber:2,currentWeekStartDate:'2026-11-09T00:00:00Z'});await h.settleReads();h.click('Trade');await h.settleReads();assert.ok(h.button('Accept'));now=Date.parse('2026-11-09T03:00:00Z');h.render();assert.equal(h.button('Accept'),undefined);h.dispose();
});

test('obsolete submission does not leave the replacement week permanently submitting',async()=>{
 let now=Date.parse('2026-11-09T01:00:00Z');const h=setup(()=>now);h.setLeague({currentWeekNumber:2,currentWeekStartDate:'2026-11-09T00:00:00Z'});await h.settleReads();h.click('Available');h.click('Submit Add / Drop Request');const mutation=h.waiting('addDrop')[0];now=Date.parse('2026-11-09T03:00:00Z');h.render();await h.settleReads();h.resolve(mutation,{});await h.flush();h.click('Available');assert.equal(h.button('Submit Add / Drop Request').props.disabled,false);h.dispose();
});

test('pending refresh crossing cutoff starts a replacement read and cannot stay loading forever',async()=>{
 let now=Date.parse('2026-11-09T01:00:00Z');const h=setup(()=>now);h.setLeague({currentWeekNumber:2,currentWeekStartDate:'2026-11-09T00:00:00Z'});await h.settleReads();h.click('Available');h.click('Submit Add / Drop Request');h.resolve(h.waiting('addDrop')[0],{});await h.flush();const pendingRead=h.waiting('pending')[0];now=Date.parse('2026-11-09T03:00:00Z');h.resolve(pendingRead,pending);await h.flush();assert.equal(h.waiting('pending').length,1);await h.settleReads({pending});assert.doesNotMatch(h.text(),/Syncing pending items/);assert.equal(h.button('Refresh pending transactions').props.disabled,false);h.dispose();
});

test('successful proposal clears submitted IDs after concurrent acceptance refresh replaces team objects',async()=>{
 const h=setup();await h.ready();h.click('Trade');await h.settleReads();h.click('Owned');h.click('Partner team');h.click('Submit Trade Proposal');const proposal=h.waiting('proposal')[0];h.click('Accept');h.resolve(h.waiting('respond')[0],{});await h.flush();await h.settleReads();h.resolve(proposal,{});await h.flush();await h.settleReads();assert.equal(h.button('Submit Trade Proposal').props.disabled,true);assert.equal(h.button('Owned').props['aria-pressed'],false);assert.equal(h.button('Partner team').props['aria-pressed'],false);h.dispose();
});

test('a genuinely edited draft survives a delayed write even when it reselects the same team ID',async()=>{
 const h=setup();await h.ready();h.click('Available');h.click('Submit Add / Drop Request');h.click('Available');h.click('Available');h.resolve(h.waiting('addDrop')[0],{});await h.flush();await h.settleReads();assert.equal(h.button('Available').props['aria-pressed'],true);h.dispose();
});
