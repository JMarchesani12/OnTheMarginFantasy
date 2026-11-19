import test from 'node:test';
import assert from 'node:assert/strict';
import {createTeamSearchCatalogCache} from '../src/lib/teamSearchCatalogCache.ts';
import {buildTeamSearchIndex,filterTeamSearch} from '../src/utils/teamSearch.ts';

const teams=[{teamId:369,schoolId:369,teamName:'UNI',aliases:['Northern Iowa','UNI']},
 {teamId:525,schoolId:369,teamName:'UNI',aliases:['Northern Iowa','UNI']},
 {teamId:600,schoolId:400,teamName:'State',aliases:['OSU']},
 {teamId:601,schoolId:401,teamName:'State',aliases:['ORST']}];

test('database identity chooses aliases across sports without borrowing a shared display name',()=>{
 const index=buildTeamSearchIndex(teams);
 assert.deepEqual(filterTeamSearch(teams,'Northern Iowa',row=>row,index).map(row=>row.teamId),[369,525]);
 assert.deepEqual(filterTeamSearch(teams,'OSU',row=>row,index).map(row=>row.teamId),[600]);
 assert.deepEqual(filterTeamSearch([{teamId:999,teamName:'State'}],'OSU',row=>row,index),[]);
 assert.deepEqual(filterTeamSearch(['State'],'OSU',row=>row,index),[]);
});

test('one catalog load serves concurrent readers and expires after five minutes',async()=>{
 let calls=0,now=0;
 const cache=createTeamSearchCatalogCache(async()=>{calls++;return {teams};},()=>now);
 const [a,b]=await Promise.all([cache.read(),cache.read()]);
 assert.equal(calls,1);assert.equal(a,b);
 now=299999;await cache.read();assert.equal(calls,1);
 now=300000;await cache.read();assert.equal(calls,2);
 await cache.read(true);assert.equal(calls,3);
});

test('failed catalog loads can retry without caching the rejected promise',async()=>{
 let calls=0;
 const cache=createTeamSearchCatalogCache(async()=>{if(++calls===1)throw new Error('offline');return {teams};});
 await assert.rejects(cache.read(),/offline/);
 assert.equal((await cache.read()).teams.length,4);assert.equal(calls,2);
});
