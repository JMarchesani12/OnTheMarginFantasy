import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,deferred,settle,nodes,text} from './helpers/leagueContextHarness.ts';
function setup(panel:string){const h=fixture(),requests:any[]=[];let current=true;const api:any={};for(const name of ['getOpenTradeRequests','getPendingTradesAndAddDrop','responseToTradeRequest','cancelTradeRequest','vetoTrade'])api[name]=(...args:any[])=>{const d=deferred();requests.push({...d,name,args});return d.promise;};const Component=h.load(`src/components/League/${panel}.tsx`,{'../../api/transaction':api}).default;const isCurrent=()=>current;const render=()=>h.render(Component,{leagueId:10,memberId:11,tradeDeadlinePassed:false,members:[],teamNameLookup:{},isCurrent});return {requests,render,obsolete(){current=false;h.dispose();},all:()=>nodes(h.tree)};}
test('nested trade response/cancel/veto do not reload obsolete context, and stale handlers cannot submit',async()=>{
 for(const label of ['Accept','Reject','Cancel','Veto']){const h=setup('TradeRequestsPanel');h.render();const trade={transactionId:1,status:'PROPOSED',fromTeams:[],toTeams:[]};h.requests[0].resolve({mine:{incoming:[trade],outgoing:[trade]},others:[trade]});await settle();h.render();
 if(label==='Cancel'||label==='Veto'){const tab=h.all().find(n=>n.type==='button'&&text(n).trim()===(label==='Cancel'?'Outgoing':'League'));assert.ok(tab);tab.props.onClick();h.render();}
 const button=h.all().find(n=>n.type==='button'&&text(n).trim()===label);assert.ok(button,label);
 const handler=button.props.onClick,p=handler();assert.equal(h.requests.length,2);h.obsolete();h.requests[1].resolve();await settle();assert.equal(h.requests.length,2);await p;await handler();assert.equal(h.requests.length,2);
 }
});
test('pending panel ignores obsolete refresh results and stale refresh callbacks',async()=>{
 const h=setup('PendingTransactionsPanel');h.render();const refresh=h.all().find(n=>n.type==='button'&&text(n).trim()==='↻');h.obsolete();h.requests[0].resolve([]);await settle();const p=refresh.props.onClick();assert.equal(h.requests.length,1);await p;
});
test('nested resource refresh latest result wins and older finally cannot hide loading',async()=>{
 for(const panel of ['TradeRequestsPanel','PendingTransactionsPanel']){const h=setup(panel);h.render();const refresh=h.all().find(n=>n.type==='button'&&text(n).trim()==='↻');const next=refresh.props.onClick();assert.equal(h.requests.length,2);assert.equal(h.requests[0].args.at(-1).aborted,true);
 h.requests[0].reject(new Error('Obsolete failure'));await settle();h.render();assert.ok(h.all().some(n=>typeof n.props?.className==='string'&&n.props.className.includes('loading')));assert.ok(!h.all().some(n=>text(n).includes('Obsolete failure')));
 h.requests[1].resolve(panel==='TradeRequestsPanel'?{mine:{incoming:[],outgoing:[]},others:[]}:[]);await next;h.render();h.obsolete();}
});
