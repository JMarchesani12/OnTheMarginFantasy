import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './helpers/leagueContextHarness.ts';
test('touched league resource APIs pass optional signals without changing paths or bodies',async()=>{
 const h=fixture(),calls:any[]=[];const client={API_BASE_URL:'https://example.test',apiFetch:async(...args:any[])=>{calls.push(args);return {ok:true,json:async()=>[]};}};const signal=new AbortController().signal;
 const leagues=h.load('src/api/leagues.ts',{'./client':client}),roster=h.load('src/api/roster.ts',{'./client':client}),scores=h.load('src/api/scoring.ts',{'./client':client}),transactions=h.load('src/api/transaction.ts',{'./client':client});
 await leagues.getLeague(10,signal);await leagues.getLeaguesForUser(1,'all',signal);await leagues.getMembersOfLeague(10,signal);await roster.getMemberTeams(11,1,10,signal);await roster.getAvailableTeams(1,10,signal);await scores.getScoresForWeek([0,1],10,signal);await transactions.getOpenTradeRequests(10,11,signal);await transactions.getPendingTradesAndAddDrop(10,signal);
 for(const call of calls)assert.equal(call[1].signal,signal,call[0]);assert.equal(calls[0][0],'https://example.test/api/league/10?view=full');assert.deepEqual(JSON.parse(calls[1][1].body),{userId:1,stage:'all'});assert.deepEqual(JSON.parse(calls[3][1].body),{leagueId:10,weekNumber:1,memberId:11});assert.deepEqual(JSON.parse(calls[5][1].body),{weekNumbers:[0,1]});h.dispose();
});
