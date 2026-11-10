import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';
import * as mapping from '../../src/utils/leagueMapping.ts';
import * as teams from '../../src/utils/teams.ts';
import * as tiers from '../../src/utils/teamTierGroups.ts';
import * as drafted from '../../src/utils/draftedTeamGroups.ts';

const settle=()=>new Promise(resolve=>setImmediate(resolve));
function fixtureLeague(leagueId=10,memberId=11) {
  return {leagueId,memberId,leagueName:`League ${leagueId}`,commissionerId:1,sport:'1',
    settings:{draft:{numberOfRounds:2},transactions:{}},status:'Pre-Draft'};
}
export function harness() {
  let now=Date.now();let timerId=0;const timers=new Map<number,()=>void>();let timerStarts=0,timerStops=0;
  class ClockDate extends Date { static now(){return now;} }
  let route='10', userId=1, token='alice', authId='alice';
  let locationState: any={league:fixtureLeague()};
  const slots:any[]=[];let index=0;let effects:(()=>void)[]=[];
  const readCalls:any[]=[];
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
    '../../api/draft':{getDraftState:async(id:number,signal:AbortSignal)=>{readCalls.push({kind:'state',id,signal});return {state:null,picks:[],members:[]};},startDraft:()=>new Promise((_,reject)=>commands.push({reject}))},
    '../../api/roster':{getAvailableTeams:async(week:number,id:number,signal:AbortSignal)=>{readCalls.push({kind:'available',week,id,signal});if(rosterFailure)throw rosterFailure;return []; }},
    '../../api/leagues':{getConferences:async()=>({conferences:[]}),getLeaguesForUser:async(id:number)=>{metadata.push(id);return [fixtureLeague(Number(route),id===1?11:12)];},getLeague:async(id:number)=>fixtureLeague(id,userId===1?11:12)},
    '../../context/AuthContext':{useAuth:()=>({session:{access_token:token,user:{id:authId}}})},
    '../../context/currentUserContext':{useCurrentUser:()=>({userId})},
    '../../utils/leagueMapping':mapping,'../../utils/teams':teams,'../../utils/teamTierGroups':tiers,'../../utils/draftedTeamGroups':drafted,
    '../../utils/safeStorage':{safeLocalStorage:{getItem:()=>null,setItem:()=>{}}},
    '../../utils/teamSearch':{teamSearchMatches:()=>true},'./LeagueDraftPage.css':{},
    './client':{apiFetch,API_BASE_URL:'https://api.example.test'},
  };
  const clockWindow={setInterval:(callback:()=>void,delay:number)=>{assert.equal(delay,1000);timers.set(++timerId,callback);timerStarts++;return timerId;},clearInterval:(id:number)=>{timers.delete(id);timerStops++;},confirm:()=>true};
  function loadClock() {
    const result:any={};
    const clock=readFileSync(new URL('../../src/hooks/useDraftClock.ts',import.meta.url),'utf8');
    runInNewContext(ts.transpileModule(clock,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,
      {exports:result,require:(name:string)=>{assert.equal(name,'react');return react;},Date:ClockDate,window:clockWindow});
    return result;
  }
  function loadConnection() {
    const result:any={};
    const source=readFileSync(new URL('../../src/hooks/useDraftConnection.ts',import.meta.url),'utf8');
    runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,
      {exports:result,require:(id:string)=>{
        if(id==='react')return react;
        if(id==='socket.io-client')return deps[id];
        assert.equal(id,'../lib/draftRealtime');return deps['../../lib/draftRealtime'];
      }});
    return result;
  }
  const exports:any={};
  const source=readFileSync(new URL('../../src/screens/League/LeagueDraftPage.tsx',import.meta.url),'utf8').replaceAll('import.meta.env.','testEnv.');
  const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  runInNewContext(compiled,{exports,require:(id:string)=>{if(id==='../../hooks/useDraftClock')return loadClock();if(id==='../../hooks/useDraftConnection')return loadConnection();assert.ok(id in deps,id);return deps[id];},testEnv:{},console,
    window:clockWindow,Date:ClockDate,Map,Set});
  let tree:any;
  function render() {index=0;tree=exports.default();const pending=effects;effects=[];pending.forEach(fn=>fn());return tree;}
  function nodes(value:any):any[] {if(!value||typeof value!=='object')return [];if(Array.isArray(value))return value.flatMap(nodes);return [value,...nodes(value.props?.children)];}
  function button(label:string){return nodes(tree).find(n=>n.type==='button'&&n.props.children===label);}
  return {render,controllers,metadata,commands,button,readCalls,
    setNow(value:number){now=value;},
    tick(){for(const callback of [...timers.values()])callback();render();},
    timerStatus(){return {active:timers.size,starts:timerStarts,stops:timerStops};},
    dispose(){for(const slot of slots)slot?.cleanup?.();},
    async flush(){await settle();render();await settle();render();},
    navigate(id:string){route=id;locationState=null;render();},
    account(){userId=2;authId='bob';token='bob';render();},
    rotateToken(){token+='-new';render();},
    failRoster(error:any){rosterFailure=error;},
    text(){return JSON.stringify(tree);},
  };
}

