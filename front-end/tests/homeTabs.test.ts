import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,nodes,text,settle} from './helpers/leagueContextHarness.ts';

// Missing roving focus, coupled focus/selection, or retained inactive controls must fail.
function setup(){
 const h=fixture();let calls=0,focus='';
 const Home=h.load('src/screens/Home/Home.tsx',{
  'react-router-dom':{useNavigate:()=>()=>{}},
  '../../context/currentUserContext':{useCurrentUser:()=>({userId:1,identityKey:'A',authUserId:'A',loading:false,error:null,isCurrentIdentity:current})},
  '../../context/AuthContext':{useAuth:()=>({signOut:async()=>{}})},
  '../../components/LeagueCard/LeagueCard':{default:()=>null},
  '../../api/leagues':{getLeaguesForUser:async()=>{calls++;return [];},searchLeagues:async()=>{calls++;return [];}},
  '../../api/sport':{getSports:async()=>[]},
 },{window:{setTimeout:()=>1,clearTimeout:()=>{}}}).default;
 function current(){return true;}
 const all=()=>nodes(h.tree),tabs=()=>all().filter(n=>n.props?.role==='tab');
 const render=()=>{h.render(Home);tabs().forEach(n=>{const el={focus(){focus=text(n);n.props.onFocus?.();}};if(typeof n.props.ref==='function')n.props.ref(el);else if(n.props.ref)n.props.ref.current=el;});};
 render();return {render,tabs,all,get calls(){return calls;},get focus(){return focus;},dispose:()=>h.dispose(),
  key(i:number,key:string){let prevented=false;tabs()[i].props.onKeyDown?.({key,preventDefault(){prevented=true;}});render();return prevented;},
  click(i:number){tabs()[i].props.onClick();render();},async flush(){await settle();render();}};
}
test('tabs expose one stop and stable labelled panel targets with inactive controls unmounted',async()=>{
 const h=setup();await h.flush();const ids=h.tabs().map(t=>t.props.id);
 assert.deepEqual(h.tabs().map(t=>t.props.tabIndex),[0,-1]);
 for(const t of h.tabs()){
  assert.ok(t.props.id);const p=h.all().find(n=>n.props?.id===t.props['aria-controls']);assert.equal(p?.props.role,'tabpanel');assert.equal(p.props['aria-labelledby'],t.props.id);
 }
 assert.equal(h.all().some(n=>n.props?.id==='league-search'),false);
 h.click(1);assert.deepEqual(h.tabs().map(t=>t.props.id),ids);assert.deepEqual(h.tabs().map(t=>t.props['aria-selected']),[false,true]);assert.ok(h.all().some(n=>n.props?.id==='league-search'));
 const inactive=h.all().find(n=>n.props?.role==='tabpanel'&&n.props.hidden);assert.ok(inactive);assert.equal(nodes(inactive).some(n=>n.type==='button'||n.type==='input'||n.type==='select'),false);h.dispose();
});
test('arrows wrap and Home/End move focus without selection or requests; Tab and native activation keys are untouched',async()=>{
 const h=setup();await h.flush();const calls=h.calls;
 for(const [index,key,want] of [[0,'ArrowRight','Search Leagues'],[1,'ArrowRight','Your Leagues'],[0,'ArrowLeft','Search Leagues'],[1,'Home','Your Leagues'],[0,'End','Search Leagues']] as const){
  assert.equal(h.key(index,key),true);assert.equal(h.focus,want);assert.deepEqual(h.tabs().map(t=>t.props['aria-selected']),[true,false]);assert.equal(h.calls,calls);
 }
 assert.deepEqual(h.tabs().map(t=>t.props.tabIndex),[-1,0]);
 for(const key of ['Tab','Enter',' '])assert.equal(h.key(1,key),false);
 h.click(1);assert.deepEqual(h.tabs().map(t=>t.props['aria-selected']),[false,true]);h.click(0);assert.deepEqual(h.tabs().map(t=>t.props['aria-selected']),[true,false]);assert.equal(h.calls,calls);h.dispose();
});
