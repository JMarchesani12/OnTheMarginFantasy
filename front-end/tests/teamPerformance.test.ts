import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture, deferred, settle, text} from './helpers/leagueContextHarness.ts';

test('team performance API uses the selected league/week and propagates cancellation',async()=>{
 const calls:any[]=[]; const controller=new AbortController();
 const api=fixture().load('src/api/teamPerformance.ts',{'./client':{API_BASE_URL:'https://api.test',apiFetch:async(...args:any[])=>{calls.push(args);return new Response(JSON.stringify({weekNumber:3,teams:[]}));}}});
 const result=await api.getTeamPerformance(10,3,controller.signal);
 assert.equal(result.weekNumber,3);
 assert.equal(calls[0][0],'https://api.test/api/roster/teamPerformance');
 assert.equal(calls[0][1].signal,controller.signal);
 assert.deepEqual(JSON.parse(calls[0][1].body),{leagueId:10,weekNumber:3});
});

test('late team stats cannot replace another league/week and cleanup aborts transport',async()=>{
 const h=fixture(),requests:any[]=[];
 const {useTeamPerformance}=h.load('src/hooks/useTeamPerformance.ts',{'../api/teamPerformance':{getTeamPerformance:(league:number,week:number,signal:AbortSignal)=>{const request={...deferred(),league,week,signal};requests.push(request);return request.promise;}}});
 let league=10,week=1,result:any;
 const Probe=()=>{result=useTeamPerformance(league,week);return null;};
 const render=()=>h.render(Probe);
 render();league=20;week=2;render();
 assert.equal(requests[0].signal.aborted,true);
 requests[1].resolve({weekNumber:2,teams:[{teamId:20,seasonDifferential:12}]});await settle();render();
 assert.equal(result.teams[20].seasonDifferential,12);
 requests[0].resolve({weekNumber:1,teams:[{teamId:10,seasonDifferential:99}]});await settle();render();
 assert.equal(result.teams[10],undefined);
 assert.equal(result.teams[20].seasonDifferential,12);
 h.dispose();assert.equal(requests[1].signal.aborted,true);
});

test('team stats distinguish zero differential from no completed games',()=>{
 const h=fixture();const {TeamPerformanceStats}=h.load('src/components/TeamPerformance/TeamPerformanceStats.tsx');
 const stats={teamId:1,weekDifferential:0,seasonDifferential:0,weekGamesPlayed:1,gamesPlayed:2,averageDifferential:0,unconfirmedGames:0};
 h.render(()=>TeamPerformanceStats({stats}));assert.match(text(h.tree),/Week 0/);assert.match(text(h.tree),/Avg\/game 0\.0/);
 h.render(()=>TeamPerformanceStats({stats:{...stats,gamesPlayed:0,weekGamesPlayed:0,averageDifferential:null,unconfirmedGames:3}}));
 assert.match(text(h.tree),/Avg\/game —/);assert.match(text(h.tree),/3 results awaiting confirmation/);h.dispose();
});
