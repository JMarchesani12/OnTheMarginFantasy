import {fixture} from "./leagueContextHarness.ts";
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';
import * as mapping from '../../src/utils/leagueMapping.ts';

export const membersFixture=()=>[
  {id:11,userId:1,teamName:'Commissioner team',displayName:'Alice',draftOrder:2},
  {id:12,userId:2,teamName:null,displayName:'Bob',draftOrder:1},
  {id:13,userId:3,teamName:'Third team',displayName:'Carol',draftOrder:3},
];
export const jsx={jsx:(type:any,props:any)=>({type,props}),jsxs:(type:any,props:any)=>({type,props})};
export function nodes(value:any):any[] {
  if(value==null||typeof value!=='object')return [];
  if(Array.isArray(value))return value.flatMap(nodes);
  if(typeof value.type==='function')return nodes(value.type(value.props));
  return [value,...nodes(value.props?.children)];
}
export function text(value:any):string {
  if(value==null||typeof value==='boolean')return '';
  if(typeof value!=='object')return String(value);
  if(Array.isArray(value))return value.map(text).join('');
  if(typeof value.type==='function')return text(value.type(value.props));
  return text(value.props?.children);
}
export function loadEditor() {
  const url=new URL('../../src/components/League/DraftOrderEditor.tsx',import.meta.url);
  assert.ok(existsSync(url),'DraftOrderEditor component missing');
  const exports:any={};
  runInNewContext(ts.transpileModule(readFileSync(url,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,
    {exports,require:(id:string)=>{if(id==='react')return {useRef:(value:any)=>({current:value}),useState:(value:any)=>[value,()=>{}],useEffect:()=>{}};assert.equal(id,'react/jsx-runtime');return jsx;}});
  return exports.default;
}
export function manageHarness(options:{status?:string;userId?:number;members?:any[];pendingMembers?:boolean;memberError?:string}={}) {
  const league={leagueId:10,leagueName:'Fixture',commissionerId:1,status:options.status??'Pre-Draft',sport:'1',
    settings:{bonuses:{},timezone:'America/Chicago',transactions:{tradeVeto:{enabled:true,requiredVetoCount:2}},
      draft:{draftType:'SNAKE',selectionTime:60,numberOfRounds:4,timeoutAction:'AUTO-SKIP',graceSeconds:3}},
    draftDate:null,tradeDeadline:null,freeAgentDeadline:null};
  let members=options.members??membersFixture(),confirm=true,saveFailure:string|null=null,removeFailure:string|null=null;
  let refreshFailure=false,orderFailure=0;
  const safe=fixture().load("src/api/safeError.ts");
  const calls:{name:string;args:any[]}[]=[],slots:any[]=[];let cursor=0,effects:(()=>void)[]=[],tree:any;
  const react={
    useState(initial:any){const i=cursor++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return [slots[i],(value:any)=>{slots[i]=typeof value==='function'?value(slots[i]):value;}];},
    useMemo(fn:any,deps:any[]){const i=cursor++;const old=slots[i];if(!old||deps.some((v,j)=>!Object.is(v,old.deps[j])))slots[i]={deps,value:fn()};return slots[i].value;},
    useEffect(fn:any,deps:any[]){const i=cursor++;const old=slots[i];if(!old||deps.some((v,j)=>!Object.is(v,old.deps[j])))effects.push(()=>{old?.cleanup?.();slots[i]={deps,cleanup:fn()};});},
  };
  const record=(name:string,args:any[])=>calls.push({name,args});
  const api={
    getLeague:async(...args:any[])=>{record('getLeague',args);if(refreshFailure)throw await safe.parseApiError(new Response('PRIVATE',{status:503}),safe.READ_ERROR);return league;},
    getMembersOfLeague:async(...args:any[])=>{record('members',args);if(options.pendingMembers)return new Promise(()=>{});if(options.memberError)throw new Error(options.memberError);return members;},
    getRequestsToJoinLeague:async()=>[],
    updateLeague:async(...args:any[])=>{record('update',args);if(saveFailure)throw new Error(saveFailure);},
    removeLeagueMember:async(...args:any[])=>{record('remove',args);if(removeFailure)throw new Error(removeFailure);members=members.filter(m=>m.id!==args[1]);},
  };
  const deps:Record<string,any>={react,'react/jsx-runtime':jsx,'../../api/safeError':safe,
    'react-router-dom':{useNavigate:()=>()=>{},useParams:()=>({league_id:'10'}),useLocation:()=>({state:{league}})},
    '../../context/currentUserContext':{useCurrentUser:()=>({userId:options.userId??1,error:null})},
    '../../api/leagues':api,'../../api/draft':{setDraftOrder:async(...args:any[])=>{record('order',args);if(orderFailure)throw await safe.parseApiError(new Response('PRIVATE',{status:orderFailure}),safe.WRITE_UNCERTAIN);}},
    '../../components/League/BonusesEditor':{BonusesEditor:()=>null,BONUS_TEMPLATES:[]},
    '../../utils/leagueMapping':mapping,'../CreateLeague/CreateLeague.css':{},'./ManageLeaguePage.css':{},
  };
  const exports:any={};
  const source=readFileSync(new URL('../../src/screens/League/ManageLeaguePage.tsx',import.meta.url),'utf8');
  const math=Object.create(Math);math.random=()=>0;
  runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,
    {exports,require:(id:string)=>{if(id==='../../components/League/DraftOrderEditor')return {default:loadEditor()};assert.ok(id in deps,id);return deps[id];},
      window:{confirm:(message:string)=>{record('confirm',[message]);return confirm;}},console,Math:math});
  function render(){cursor=0;tree=exports.default();const pending=effects;effects=[];pending.forEach(fn=>fn());return tree;}
  function all(){return nodes(tree);}
  return {calls,render,
    async flush(){for(let i=0;i<4;i++){await new Promise(resolve=>setImmediate(resolve));render();}},
    rows:()=>all().filter(n=>typeof n.props?.className==='string'&&n.props.className.startsWith('ml-draft-order-row')),
    button:(label:string)=>all().find(n=>n.type==='button'&&text(n)===label),
    text:()=>text(tree),all,
    failRefresh(){refreshFailure=true;},failOrder(status:number){orderFailure=status;},
    confirm(value:boolean){confirm=value;},failSave(message:string){saveFailure=message;},failRemove(message:string){removeFailure=message;},
  };
}
