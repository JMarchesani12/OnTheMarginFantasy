import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,deferred,settle,nodes,text} from './helpers/leagueContextHarness.ts';
import {leagueFixture} from './helpers/leagueFixture.ts';

// Removing the ineligible reset or cancellation guards restores loading/stale state.
function setup(){
 const h=fixture(),timers=new Map<number,()=>Promise<void>>(),requests:any[]=[];let next=0;
 const league=leagueFixture();
 const Page=h.load('src/screens/League/TeamLookupPage.tsx',{
  'react-router-dom':{useNavigate:()=>()=>{},useLocation:()=>({state:{league}}),useParams:()=>({league_id:'10'})},
  '../../context/currentUserContext':{useCurrentUser:()=>({userId:1})},
  '../../api/leagues':{getLeague:async()=>league,getLeaguesForUser:async()=>[league]},
  '../../api/schedule':{searchTeamsForLeague:(...args:any[])=>{const r={...deferred(),args};requests.push(r);return r.promise;}},
 },{window:{setTimeout:(fn:()=>Promise<void>)=>{timers.set(++next,fn);return next;},clearTimeout:(id:number)=>timers.delete(id)}}).default;
 const render=()=>h.render(Page);render();render();
 return {requests,render,text:()=>text(h.tree),dispose:()=>h.dispose(),
  query(value:string){nodes(h.tree).find(n=>n.props?.id==='team-lookup-search').props.onChange({target:{value}});render();render();},
  start(){const [id,fn]=[...timers.entries()].at(-1)!;timers.delete(id);const p=fn();render();return p;},
  async flush(){await settle();render();},timerCount:()=>timers.size};
}
for(const query of ['', 'a','   '])for(const rejected of [false,true])test(`ineligible ${JSON.stringify(query)} clears loading and ignores late ${rejected?'failure':'success'} before fresh search`,async()=>{
 const h=setup();h.query('Duke');const old=h.start();assert.match(h.text(),/Searching teams/);h.query(query);assert.doesNotMatch(h.text(),/Searching teams/);
 h.query('Iowa');const fresh=h.start();assert.match(h.text(),/Searching teams/);
 if(rejected)h.requests[0].reject(new Error('Obsolete error'));else h.requests[0].resolve({teams:[{teamId:1,teamName:'Obsolete team'}]});await old;await h.flush();assert.match(h.text(),/Searching teams/);assert.doesNotMatch(h.text(),/Obsolete/);
 h.requests[1].resolve({teams:[{teamId:2,teamName:'Fresh team',conferenceName:'Conference'}]});await fresh;await h.flush();assert.doesNotMatch(h.text(),/Searching teams|Obsolete/);assert.match(h.text(),/Fresh team/);assert.deepEqual(h.requests[1].args,[10,'Iowa']);h.dispose();
});
test('shortening before debounce prevents dispatch and unmount cancels scheduled work',()=>{
 const h=setup();h.query('Duke');assert.equal(h.timerCount(),1);h.query('a');assert.equal(h.timerCount(),0);assert.equal(h.requests.length,0);h.query('Iowa');h.dispose();assert.equal(h.timerCount(),0);
});
