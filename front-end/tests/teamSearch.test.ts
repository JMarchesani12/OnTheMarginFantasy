import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {rankTeamSearchMatch, teamSearchMatches, filterTeamSearch,buildTeamSearchIndex} from '../src/utils/teamSearch.ts';

const cases=JSON.parse(readFileSync(new URL('../../tests/fixtures/team-search-cases.json',import.meta.url),'utf8'));
const index=buildTeamSearchIndex([...new Map(cases.map((row:any)=>[row.candidate,row])).values()].map((row:any,i)=>({teamId:i,schoolId:i,teamName:row.candidate,aliases:row.aliases})));
test('browser matches shared literal aliases, typo thresholds and identity boundaries',()=>{
  for(const row of cases) {
    const score=rankTeamSearchMatch(row.candidate,row.query,row.aliases);
    const label=JSON.stringify(row);
    if('score' in row)assert.equal(score,row.score,label);
    if('minimum' in row)assert.ok(score>=row.minimum,label);
    if('maximum' in row)assert.ok(score<=row.maximum,label);
    assert.equal(teamSearchMatches(row.candidate,row.query,row.aliases),!row.query||score>0,label);
  }
});

test('strong matches suppress typo noise, while misspellings still find real teams',()=>{
  const teams=['Iona Gaels','Iowa Hawkeyes','Iowa State Cyclones'];
  assert.deepEqual(filterTeamSearch(teams,'iowa',name=>name,index),['Iowa Hawkeyes','Iowa State Cyclones']);
  assert.deepEqual(filterTeamSearch(['Northern Iowa Panthers','Northern Illinois Huskies'],'nothern iwoa',name=>name,index),['Northern Iowa Panthers']);
});

test('alias exact matches rank first and ambiguous abbreviations return every matching school',()=>{
  const teams=['Oklahoma State Cowboys','Ohio State Buckeyes','Oregon State Beavers'];
  assert.deepEqual(filterTeamSearch(teams,'OSU',name=>name,index),teams);
  assert.deepEqual(filterTeamSearch(['East Northern Iowa','Northern Iowa Panthers'],'UNI',name=>name,index),['Northern Iowa Panthers']);
});

test('blank search preserves order and long queries are bounded',()=>{
  const teams=['B','A'];
  assert.deepEqual(filterTeamSearch(teams,' ',name=>name,index),teams);
  for(const query of ['iowa '.repeat(100),'i'.repeat(200),'one two three four five six seven eight nine'])
    assert.equal(rankTeamSearchMatch('Iowa State',query),0);
});

test('multiple searchable names match independently, never across opponents',()=>{
  const games=[{home:'Northern Iowa Panthers',away:'Iowa State Cyclones'}];
  assert.equal(filterTeamSearch(games,'UNI',game=>[game.home,game.away],index).length,1);
  assert.equal(filterTeamSearch(games,'nothern iwoa',game=>[game.home,game.away],index).length,1);
  assert.equal(filterTeamSearch(games,'Northern Cyclones',game=>[game.home,game.away],index).length,0);
});
