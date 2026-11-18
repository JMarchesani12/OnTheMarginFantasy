import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture, deferred, settle, nodes, text} from './helpers/leagueContextHarness.ts';

// Removing current-selection feedback/masking or request disposal must break these assertions.
function setup() {
  const h=fixture(), requests:any[]=[];
  let identity='A:1';
  let profile:any={userId:1,identityKey:identity,authUserId:'A',loading:false,error:null,displayName:'Alice'};
  const checks=new Map<string,()=>boolean>();
  const Home=h.load('src/screens/Home/Home.tsx',{
    'react-router-dom':{useNavigate:()=>()=>{}},
    '../../context/currentUserContext':{useCurrentUser:()=>{
      const key=identity;
      if(!checks.has(key))checks.set(key,()=>identity===key);
      return {...profile,isCurrentIdentity:checks.get(key)};
    }},
    '../../context/AuthContext':{useAuth:()=>({signOut:async()=>{}})},
    '../../components/LeagueCard/LeagueCard':{default:({league}:any)=>h.jsx.jsx('article',{children:league.leagueName})},
    '../../api/leagues':{getLeaguesForUser:(...args:any[])=>{
      const d=deferred();requests.push({...d,args});return d.promise;
    },searchLeagues:async()=>[]},
    '../../api/sport':{getSports:async()=>[]},
  },{window:{setTimeout:()=>1,clearTimeout:()=>{}}}).default;
  const render=(patch:any={},commit=true)=>{
    if('identityKey' in patch)identity=patch.identityKey;
    profile={...profile,...patch};return h.render(Home,{},commit);
  };
  const all=()=>nodes(h.tree);
  const button=(label:string)=>all().find(n=>n.type==='button'&&text(n)===label);
  return {requests,render,all,button,text:()=>text(h.tree),dispose:()=>h.dispose(),
    stage(value:string,commit=true){all().find(n=>n.props?.id==='league-stage').props.onChange({target:{value}});render({},commit);},
    async flush(){await settle();render();},
  };
}
const league=(name:string,status='In-Season')=>({leagueId:name,leagueName:name,status});

test('primary list distinguishes initial pending, successful empty and failure with safe retry',async()=>{
 const h=setup();h.render();assert.match(h.text(),/Loading your leagues/);assert.doesNotMatch(h.text(),/You have no/);
 h.requests[0].reject(new Error('secret provider response'));await h.flush();assert.match(h.text(),/Could not load your leagues/);assert.doesNotMatch(h.text(),/secret provider|You have no|Loading your leagues/);
 assert.ok(h.all().some(n=>n.props?.role==='alert'));
 h.button('Retry leagues').props.onClick();h.render();assert.match(h.text(),/Loading your leagues/);assert.equal(h.button('Retry leagues'),undefined);
 const retry=h.requests.at(-1);assert.deepEqual(retry.args.slice(0,2),[1,'active']);retry.reject(new Error('again'));await h.flush();assert.ok(h.button('Retry leagues'));
 h.button('Retry leagues').props.onClick();h.render();h.requests.at(-1).resolve([]);await h.flush();assert.match(h.text(),/You have no active leagues\./);assert.equal(h.button('Retry leagues'),undefined);h.dispose();
});

test('stage-specific emptiness follows successful matching responses and both accepted containers filter cards',async()=>{
 const h=setup();h.render();h.requests[0].resolve({leagues:[league('Current'),league('Past','Completed')]});await h.flush();assert.match(h.text(),/Current/);assert.doesNotMatch(h.text(),/Past/);
 h.stage('completed',false);assert.doesNotMatch(h.text(),/Current/);assert.match(h.text(),/Loading your leagues/);
 h.render();h.requests.at(-1).resolve([]);await h.flush();assert.match(h.text(),/You have no completed leagues\./);
 h.stage('all');h.requests.at(-1).resolve([]);await h.flush();assert.match(h.text(),/You have no leagues yet\./);
 h.stage('completed');h.requests.at(-1).resolve([league('Current'),league('Past','Completed')]);await h.flush();assert.match(h.text(),/Past/);assert.doesNotMatch(h.text(),/Current/);h.dispose();
});

test('stage replacement aborts work and rejects out-of-order successes/errors through a round trip',async()=>{
 const h=setup();h.render();const first=h.requests[0];h.stage('completed');const completed=h.requests.at(-1);assert.equal(first.args[2].aborted,true);
 h.stage('active');const current=h.requests.at(-1);first.resolve([league('Obsolete active')]);completed.reject(new Error('Obsolete completed'));await h.flush();assert.match(h.text(),/Loading your leagues/);assert.doesNotMatch(h.text(),/Obsolete|Could not load/);
 current.resolve([league('Fresh active')]);await h.flush();assert.match(h.text(),/Fresh active/);h.dispose();assert.equal(current.args[2].aborted,true);
});

test('failure is hidden before stage effects and retry uses the current stage',async()=>{
 const h=setup();h.render();h.requests[0].reject(new Error('failed'));await h.flush();assert.ok(h.button('Retry leagues'));
 h.stage('completed',false);assert.equal(h.button('Retry leagues'),undefined);assert.doesNotMatch(h.text(),/Could not load/);h.render();h.requests.at(-1).reject(new Error('failed'));await h.flush();h.button('Retry leagues').props.onClick();h.render();assert.deepEqual(h.requests.at(-1).args.slice(0,2),[1,'completed']);h.requests.at(-1).resolve([]);await h.flush();assert.match(h.text(),/no completed leagues/);h.dispose();
});

test('invalid primary containers fail rather than pretending to be empty',async()=>{
 for(const payload of [null,{}, {leagues:null},'invalid']){
  const h=setup();h.render();h.requests[0].resolve(payload);await h.flush();assert.match(h.text(),/Could not load your leagues/);assert.doesNotMatch(h.text(),/You have no/);h.dispose();
 }
});

test('account changes, pending profiles and disposal suppress old primary outcomes',async()=>{
 const h=setup();h.render();const old=h.requests[0];h.render({identityKey:'B:2',authUserId:'B',userId:null,loading:true});assert.doesNotMatch(h.text(),/You have no|Loading your leagues|Could not load your leagues/);assert.equal(h.requests.length,2);assert.equal(old.args[2].aborted,true);
 h.render({userId:2,loading:false});const b=h.requests.at(-2);old.resolve([league('Old account')]);await h.flush();assert.doesNotMatch(h.text(),/Old account/);assert.match(h.text(),/Loading your leagues/);
 b.reject(new Error('failed'));await h.flush();h.button('Retry leagues').props.onClick();h.render();const retry=h.requests.at(-1);assert.deepEqual(retry.args.slice(0,2),[2,'active']);
 h.render({identityKey:'signedout:3',authUserId:null,userId:null});retry.resolve([league('Late retry')]);await h.flush();assert.doesNotMatch(h.text(),/Late retry|You have no|Could not load your leagues/);h.dispose();
});

test('same-identity profile refresh cancels prior list work and reloads without reviving it',async()=>{
 const h=setup();h.render();const old=h.requests[0];h.render({userId:null,loading:true});h.render({userId:1,loading:false});const fresh=h.requests.at(-2);old.resolve([league('Disposed result')]);await h.flush();assert.doesNotMatch(h.text(),/Disposed result/);assert.match(h.text(),/Loading your leagues/);fresh.resolve([]);await h.flush();assert.match(h.text(),/no active leagues/);h.dispose();
});
