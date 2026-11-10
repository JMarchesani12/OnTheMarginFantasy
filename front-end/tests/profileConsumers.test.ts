import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,deferred,settle,nodes,text} from './helpers/leagueContextHarness.ts';
function setup(screen:string){const h=fixture(),requests:any[]=[],timers:Function[]=[],calls:any[]=[];let identity='A:1';let profile:any={identityKey:identity,userId:1,authUserId:'A',authLoading:false,loading:false,error:null,displayName:'Alice',email:'a@example.test'};
 const request=(kind:string,args:any[])=>{const d=deferred();requests.push({...d,kind,args});return d.promise;};
 const checks=new Map<string,()=>boolean>();const useCurrentUser=()=>{const key=identity;if(!checks.has(key))checks.set(key,()=>identity===key);return {...profile,isCurrentIdentity:checks.get(key),refreshUser:()=>request('refresh',[key])};};
 const module=h.load(`src/screens/${screen==='Home'?'Home/Home':'Settings/SettingsPage'}.tsx`,{
 'react-router-dom':{useNavigate:()=>(...args:any[])=>calls.push(args)},'../../context/currentUserContext':{useCurrentUser},'../../context/AuthContext':{useAuth:()=>({signOut:async()=>{}})},
 '../../api/user':{updateUser:(...args:any[])=>request('update',args)},'../../api/leagues':{getLeaguesForUser:(...args:any[])=>request('leagues',args),searchLeagues:(...args:any[])=>request('search',args)},'../../api/sport':{getSports:async()=>[]},'../../components/LeagueCard/LeagueCard':{default:({league}:any)=>h.jsx.jsx('article',{children:league.leagueName})},
 },{setTimeout:(fn:Function)=>{timers.push(fn);return timers.length;},clearTimeout:()=>{},window:{setTimeout:(fn:Function)=>{timers.push(fn);return timers.length;},clearTimeout:()=>{}}});
 function render(patch:any={}){if('identityKey'in patch)identity=patch.identityKey;profile={...profile,...patch};return h.render(module.default);}
 return {requests,calls,render,dispose:()=>h.dispose(),all:()=>nodes(h.tree),text:()=>text(h.tree),button:(label:string)=>nodes(h.tree).find(n=>n.type==='button'&&text(n).trim()===label),input:()=>nodes(h.tree).find(n=>n.type==='input'&&n.props.type==='text'&&!n.props.readOnly),submit:()=>nodes(h.tree).find(n=>n.type==='form').props.onSubmit({preventDefault(){}}),async flush(){await settle();render();},timers};
}
test('Home hides both former-account private lists before effects and late A data cannot revive A→B→A; discovery remains available',async()=>{
 const h=setup('Home');h.render();h.requests[0].resolve([{leagueId:10,leagueName:'A private league',status:'In-Season'}]);h.requests[1].resolve([{leagueId:10,leagueName:'A private league',status:'In-Season'}]);await h.flush();assert.match(h.text(),/A private league/);
 h.render({identityKey:'B:2',userId:null,authUserId:'B',loading:true,displayName:null,email:null});assert.doesNotMatch(h.text(),/A private league/);assert.match(h.text(),/profile/i);assert.ok(h.button('Search Leagues'));
 h.render({userId:2,loading:false,displayName:'Bob'});const b=h.requests.slice(2);h.render({identityKey:'A:3',userId:1,authUserId:'A',displayName:'Alice'});for(const r of b)r.resolve([{leagueId:20,leagueName:'B late league',status:'In-Season'}]);await h.flush();assert.doesNotMatch(h.text(),/A private league|B late league/);h.dispose();
});
test('Settings retains draft input on failed write and failed post-save refresh; no false success and retry visible',async()=>{
 for(const failedRefresh of [false,true]){const h=setup('Settings');h.render();h.input().props.onChange({target:{value:'New name'}});h.render();const p=h.submit();assert.deepEqual(h.requests[0].args,[1,'New name']);
 if(failedRefresh){h.requests[0].resolve({});await settle();h.render({loading:true,userId:null,displayName:null});assert.equal(h.input().props.value,'New name');h.requests[1].reject(new Error('refresh failed'));}else h.requests[0].reject(new Error('write failed'));
 await p;h.render(failedRefresh?{loading:false,error:'Could not load your profile. Please retry.'}:{});assert.equal(h.input().props.value,'New name');assert.doesNotMatch(h.text(),/Display name updated/);if(failedRefresh)assert.ok(h.button('Retry profile'));h.dispose();}
});
test('Settings same-account save+refresh succeeds without remount and stale account completions cannot refresh B',async()=>{
 const h=setup('Settings');h.render();h.input().props.onChange({target:{value:'New name'}});h.render();const p=h.submit();h.requests[0].resolve({});await settle();h.render({userId:null,displayName:null,loading:true});h.requests[1].resolve();h.render({userId:1,displayName:'New name',loading:false});await p;h.render();assert.match(h.text(),/Display name updated/);h.dispose();
 for(const patch of [{identityKey:'B:2',authUserId:'B',userId:2,displayName:'Bob'},{identityKey:'signed-out:2',authUserId:null,userId:null,displayName:null}]){const stale=setup('Settings');stale.render();stale.input().props.onChange({target:{value:'A private draft'}});stale.render();const q=stale.submit();stale.render(patch);assert.notEqual(stale.input().props.value,'A private draft');stale.requests[0].resolve({});await settle();assert.equal(stale.requests.length,1);await q;stale.render();assert.doesNotMatch(stale.text(),/Display name updated/);stale.dispose();}
});
test('profile errors are visible in Home and Settings and retry consumes rejection',async()=>{
 for(const screen of ['Home','Settings']){const h=setup(screen);h.render({userId:null,error:'Profile setup failed',loading:false});assert.match(h.text(),/Profile setup failed/);const p=h.button('Retry profile').props.onClick();const read=h.requests.find(r=>r.kind==='refresh');assert.ok(read);read.reject(new Error('still unavailable'));await p;h.dispose();}
});
test('Home keeps public search usable while private membership filtering resets for a new/signed-out identity',async()=>{
 const h=setup('Home');h.render();h.requests[0].resolve([]);h.requests[1].resolve([{leagueId:10,status:'In-Season'}]);await h.flush();h.button('Search Leagues').props.onClick();h.render();h.all().find(n=>n.type==='input'&&n.props.id==='league-search').props.onChange({target:{value:'Public'}});h.render();h.timers.at(-1)!();h.render();const search=h.requests.find(r=>r.kind==='search');assert.ok(search);search.resolve([{id:10,name:'Public League',sport:1}]);await h.flush();assert.doesNotMatch(h.text(),/Public League/);
 h.render({identityKey:'B:2',authUserId:'B',userId:null,displayName:null,loading:true});assert.match(h.text(),/Public League/);h.render({identityKey:'signedout:3',authUserId:null,userId:null,displayName:null,loading:false});assert.match(h.text(),/Public League/);h.dispose();
});
