import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';
import * as mapping from '../src/utils/leagueMapping.ts';
import * as teams from '../src/utils/teams.ts';
import * as tiers from '../src/utils/teamTierGroups.ts';
import * as drafted from '../src/utils/draftedTeamGroups.ts';

const settle=()=>new Promise(resolve=>setImmediate(resolve));
function fixtureLeague(leagueId=10,memberId=11) {
  return {leagueId,memberId,leagueName:`League ${leagueId}`,commissionerId:1,sport:'1',
    settings:{draft:{numberOfRounds:2},transactions:{}},status:'Pre-Draft'};
}
function harness() {
  let route='10', userId=1, token='alice', authId='alice';
  let locationState: any={league:fixtureLeague()};
  const slots:any[]=[];let index=0;let effects:(()=>void)[]=[];
  const controllers:any[]=[];const metadata:number[]=[];
  const commands:{reject:(e:any)=>void}[]=[];
  let rosterFailure:any=null;
  const react={
    useState(initial:any) {const i=index++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return [slots[i],(value:any)=>{slots[i]=typeof value==='function'?value(slots[i]):value;}];},
    useRef(initial:any) {const i=index++;return slots[i]??(slots[i]={current:initial});},
    useMemo(fn:()=>any,deps:any[]) {const i=index++;const old=slots[i];if(!old||deps.some((v,j)=>!Object.is(v,old.deps[j])))slots[i]={deps,value:fn()};return slots[i].value;},
    useCallback(fn:any,deps:any[]) {return react.useMemo(()=>fn,deps);},
    useEffect(fn:any,deps:any[]) {const i=index++;const old=slots[i];if(!old||deps.some((v,j)=>!Object.is(v,old.deps[j])))effects.push(()=>{old?.cleanup?.();slots[i]={deps,cleanup:fn()};});},
  };
  const apiFetch=async()=>new Response('{}');
  const deps:Record<string,any>={
    react, 'react/jsx-runtime':{jsx:(type:any,props:any)=>({type,props}),jsxs:(type:any,props:any)=>({type,props})},
    'react-router-dom':{useNavigate:()=>()=>{},useParams:()=>({league_id:route}),useLocation:()=>({state:locationState})},
    'socket.io-client':{io:()=>({})},
    '../../lib/draftRealtime':{createDraftRealtime:(options:any)=>{
      const controller={options,disposed:false,refreshes:0,refresh(){this.refreshes++;},join(){},dispose(){this.disposed=true;}};
      controllers.push(controller);return controller;
    }},
    '../../api/draft':{getDraftState:async()=>({state:null,picks:[],members:[]}),startDraft:()=>new Promise((_,reject)=>commands.push({reject}))},
    '../../api/roster':{getAvailableTeams:async()=>{if(rosterFailure)throw rosterFailure;return []; }},
    '../../api/leagues':{getConferences:async()=>({conferences:[]}),getLeaguesForUser:async(id:number)=>{metadata.push(id);return [fixtureLeague(Number(route),id===1?11:12)];},getLeague:async(id:number)=>fixtureLeague(id,userId===1?11:12)},
    '../../context/AuthContext':{useAuth:()=>({session:{access_token:token,user:{id:authId}}})},
    '../../context/currentUserContext':{useCurrentUser:()=>({userId})},
    '../../utils/leagueMapping':mapping,'../../utils/teams':teams,'../../utils/teamTierGroups':tiers,'../../utils/draftedTeamGroups':drafted,
    '../../utils/safeStorage':{safeLocalStorage:{getItem:()=>null,setItem:()=>{}}},
    '../../utils/teamSearch':{teamSearchMatches:()=>true},'./LeagueDraftPage.css':{},
    './client':{apiFetch,API_BASE_URL:'https://api.example.test'},
  };
  const exports:any={};
  const source=readFileSync(new URL('../src/screens/League/LeagueDraftPage.tsx',import.meta.url),'utf8').replaceAll('import.meta.env.','testEnv.');
  const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  runInNewContext(compiled,{exports,require:(id:string)=>{assert.ok(id in deps,id);return deps[id];},testEnv:{},console,
    window:{setInterval:()=>1,clearInterval:()=>{},confirm:()=>true},Date,Map,Set});
  let tree:any;
  function render() {index=0;tree=exports.default();const pending=effects;effects=[];pending.forEach(fn=>fn());return tree;}
  function nodes(value:any):any[] {if(!value||typeof value!=='object')return [];if(Array.isArray(value))return value.flatMap(nodes);return [value,...nodes(value.props?.children)];}
  function button(label:string){return nodes(tree).find(n=>n.type==='button'&&n.props.children===label);}
  return {render,controllers,metadata,commands,button,
    async flush(){await settle();render();await settle();render();},
    navigate(id:string){route=id;locationState=null;render();},
    account(){userId=2;authId='bob';token='bob';render();},
    rotateToken(){token+='-new';render();},
    failRoster(error:any){rosterFailure=error;},
    text(){return JSON.stringify(tree);},
  };
}

test('actual page combined reader propagates roster denial and transport failure',async()=>{
  const h=harness();h.render();await h.flush();
  for(const failure of [Object.assign(new Error('denied'),{status:403}),new Error('offline')]) {
    h.failRoster(failure);
    await assert.rejects(h.controllers.at(-1).options.read(new AbortController().signal),error=>error===failure);
  }
});

test('route change replaces controller scope and reloads matching league metadata',async()=>{
  const h=harness();h.render();await h.flush();const old=h.controllers.at(-1);
  h.navigate('20');await h.flush();
  assert.equal(h.controllers.at(-1).options.leagueId,20);assert.equal(old.disposed,true);
  assert.match(h.text(),/League 20/);assert.doesNotMatch(h.text(),/League 10/);
});

test('account change reloads member metadata and personal turn',async()=>{
  const h=harness();h.render();await h.flush();h.account();await h.flush();
  assert.ok(h.metadata.includes(2),'new account must reload its league membership');
  h.controllers.at(-1).options.apply({state:{status:'live',currentMemberId:12},members:[],picks:[],availableTeams:[]});
  h.render();assert.match(h.text(),/You are on the clock/);
});

test('late old command failure cannot overwrite next token command state',async()=>{
  const h=harness();h.render();await h.flush();
  const old=h.button('Start Draft').props.onClick();assert.equal(h.commands.length,1);
  h.rotateToken();await h.flush();const current=h.button('Start Draft').props.onClick();h.render();
  assert.equal(h.button('Start Draft').props.disabled,true);
  h.commands[0].reject(new Error('obsolete command error'));await old;h.render();
  assert.equal(h.button('Start Draft').props.disabled,true);
  assert.doesNotMatch(h.text(),/obsolete command error/);
  h.commands[1].reject(new Error('current command error'));await current;
});

test('available-team HTTP reader preserves final status and abort signal',async()=>{
  for(const status of [401,403,404,500]) {
    const exports:any={};const controller=new AbortController();let seen:any;
    const source=readFileSync(new URL('../src/api/roster.ts',import.meta.url),'utf8');
    const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
    runInNewContext(compiled,{exports,require:()=>({API_BASE_URL:'https://api.example.test',apiFetch:async(_url:any,init:any)=>{seen=init;return new Response('{}',{status});}})});
    await assert.rejects(exports.getAvailableTeams(1,10,controller.signal),(error:any)=>error.status===status);
    assert.equal(seen.signal,controller.signal);
  }
});
