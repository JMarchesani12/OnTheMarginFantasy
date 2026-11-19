import {buildTeamSearchIndex} from '../src/utils/teamSearch.ts';
import test from 'node:test';
import assert from 'node:assert/strict';
import {shiftScoreboardDate,isScoreboardDate,filterDailyGames,getScoreboardTimezone} from '../src/utils/dailyScoreboard.ts';
import {fixture,deferred,settle,nodes,text} from './helpers/leagueContextHarness.ts';
import {leagueFixture} from './helpers/leagueFixture.ts';
import type {DailyScoreboardGame} from '../src/types/dailyScoreboard.ts';

const aliases=[{teamId:10,schoolId:369,teamName:'Northern Iowa Panthers',aliases:['Northern Iowa','UNI']}];
const searchIndex=buildTeamSearchIndex(aliases);
const game=(changes:Partial<DailyScoreboardGame>={}):DailyScoreboardGame=>({id:1,externalGameId:'1',date:'2027-02-13T22:00:00Z',timeTBD:false,isCompleted:true,broadcast:null,ownershipWeekNumber:15,
 homeTeamId:10,homeTeamName:'Northern Iowa Panthers',homeScore:74,homeConferenceName:'Missouri Valley',homeOwnerMemberId:11,homeOwnerTeamName:'My squad',homeOwnerDisplayName:'Me',
 awayTeamId:20,awayTeamName:'Duke Blue Devils',awayScore:70,awayConferenceName:'ACC',awayOwnerMemberId:null,awayOwnerTeamName:null,awayOwnerDisplayName:null,...changes});

test('calendar navigation crosses month/year boundaries without DST shifting the date',()=>{
 assert.equal(shiftScoreboardDate('2027-03-01',-1),'2027-02-28');
 assert.equal(shiftScoreboardDate('2026-12-31',1),'2027-01-01');
 assert.equal(shiftScoreboardDate('2027-03-14',1),'2027-03-15');
 assert.equal(isScoreboardDate('2027-02-30'),false);
 assert.equal(isScoreboardDate('2028-02-29'),true);
});

test('conference filters match either side without duplicating cross-conference games',()=>{
 const games=[game(),game({id:2,homeConferenceName:'Big Ten',awayConferenceName:'Big Ten'})];
 assert.deepEqual(filterDailyGames(games,'ACC','').map(g=>g.id),[1]);
 assert.deepEqual(filterDailyGames(games,'Missouri Valley','DUKE').map(g=>g.id),[1]);
 assert.equal(filterDailyGames(games,'','').length,2);
});

function setup(){
 const h=fixture(),requests:any[]=[],navigations:any[]=[];let params=new URLSearchParams('view=scoreboard&date=2027-02-13');
 const Page=h.load('src/components/League/LeagueScoreboardBrowser.tsx',{
  'react-router-dom':{useNavigate:()=> (...args:any[])=>navigations.push(args),useSearchParams:()=>[params,(update:any)=>{params=typeof update==='function'?update(params):update;}]},
  '../api/teamSearch':{getTeamSearchCatalog:async()=>({teams:aliases})},
  '../../api/dailyScoreboard':{getDailyScoreboard:(...args:any[])=>{const request={...deferred(),args};requests.push(request);return request.promise;}},
  '../../api/schedule':{searchTeamsForLeague:async()=>({teams:[]})},
 },{URLSearchParams,window:{setTimeout,clearTimeout}}).default;
 const render=()=>h.render(Page,{league:leagueFixture()});
 const button=(label:string)=>nodes(h.tree).find(n=>n.type==='button'&&(n.props['aria-label']===label||text(n)===label));
 return {h,requests,navigations,render,button,params:()=>params};
}

test('daily cards show owned and unowned teams once and retain browsing date in navigation',async()=>{
 const x=setup();x.render();
 assert.equal(x.requests[0].args[1],'2027-02-13');
 x.requests[0].resolve({date:'2027-02-13',timezone:'America/Chicago',games:[game()]});await settle();x.render();
 assert.equal(nodes(x.h.tree).filter(n=>n.type==='article').length,1);
 assert.match(text(x.h.tree),/You · My squad/);assert.match(text(x.h.tree),/Unowned/);
 x.button('Next day').props.onClick();x.render();assert.equal(x.params().get('date'),'2027-02-14');
 assert.equal(x.requests[0].args[2].aborted,true);
 assert.doesNotMatch(text(x.h.tree),/Northern Iowa Panthers/);
 x.requests[1].resolve({date:'2027-02-14',timezone:'America/Chicago',games:[game()]});await settle();x.render();
 x.button('Northern Iowa Panthers').props.onClick();
 assert.equal(x.navigations[0][0],'/leagues/10/teams/10');x.h.dispose();
});

test('obsolete day results cannot overwrite a newer day and empty states stay distinct',async()=>{
 const x=setup();x.render();x.button('Next day').props.onClick();x.render();
 x.requests[1].resolve({date:'2027-02-14',timezone:'America/Chicago',games:[]});await settle();x.render();
 assert.match(text(x.h.tree),/No games scheduled for this date/);
 x.requests[0].resolve({date:'2027-02-13',timezone:'America/Chicago',games:[game()]});await settle();x.render();
 assert.doesNotMatch(text(x.h.tree),/Northern Iowa Panthers/);x.h.dispose();
});

test('scoreboard Today uses the same nested timezone precedence as the backend',()=>{
 assert.equal(getScoreboardTimezone({timezone:'UTC',schedule:{timeZone:'America/Chicago'}}),'America/Chicago');
 assert.equal(getScoreboardTimezone({timeZone:'America/New_York'}),'America/New_York');
 assert.equal(getScoreboardTimezone({timezone:'invalid',schedule:{timezone:'America/Chicago'}}),'America/Chicago');
 assert.equal(getScoreboardTimezone('{"schedule":{"timezone":"America/Chicago"}}'),'America/Chicago');
 assert.equal(getScoreboardTimezone(undefined),'UTC');
});

test('game search accepts aliases and typos within the selected conference',()=>{
 const games=[game(),game({id:2,homeTeamId:11,homeTeamName:'Northern Illinois Huskies',homeConferenceName:'MAC',awayConferenceName:'MAC'})];
 assert.deepEqual(filterDailyGames(games,'','UNI',searchIndex).map(g=>g.id),[1]);
 assert.deepEqual(filterDailyGames(games,'Missouri Valley','nothern iwoa').map(g=>g.id),[1]);
 assert.deepEqual(filterDailyGames(games,'MAC','UNI',searchIndex).map(g=>g.id),[]);
 assert.deepEqual(filterDailyGames(games,'','Northern Devils').map(g=>g.id),[]);
});
