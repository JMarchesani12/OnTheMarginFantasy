import assert from 'node:assert/strict';
import test from 'node:test';
import { applySeasonStandings } from '../src/utils/seasonBonuses.ts';

test('season totals include bonus points while preserving weekly cells', () => {
  const row = { memberId: 1, totalPoints: 2, weeklyPoints: { 1: 2 } };
  const result = applySeasonStandings([row], { leagueId: 10, members: [{ memberId: 1, teamName: 'A', weeklyPoints: 2, bonusPoints: 1.5, totalPoints: 3.5 }] });
  assert.equal(result[0].totalPoints, 3.5);
  assert.equal(result[0].bonusPoints, 1.5);
  assert.deepEqual(result[0].weeklyPoints, { 1: 2 });
  assert.equal(row.totalPoints, 2);
});

test('pending awards retain totals without adding pending UI state', () => {
  const result = applySeasonStandings([{memberId: 1,totalPoints: 2}], {leagueId: 10,members: [{memberId: 1,teamName: 'A',weeklyPoints: 2,bonusPoints: 0,totalPoints: 2}],bonusStatus: {state: 'pending',components: {conferenceChampion: 'pending'},snapshotIds: []}});
  assert.equal(result[0].totalPoints,2);
  assert.equal('bonusPending' in result[0],false);
});

test('missing member total is unavailable rather than a fabricated season total', () => {
  const [row] = applySeasonStandings([{memberId: 2,totalPoints: 5}], {leagueId: 10,members: []});
  assert.equal(row.seasonTotalAvailable,false);
});

// Render the actual scoreboard, including legacy pending flags, to prove no
// bonus copy appears before completion and final awards remain visible afterward.
import { fixture, text } from './helpers/leagueContextHarness.ts';

function renderScoreboard(showBonuses?: boolean) {
  const h=fixture();
  const Component=h.load('src/components/League/LeagueScoreboard.tsx').default;
  h.render(Component,{weekNumbers:[1],currentWeekNumber:1,loading:false,error:null,showBonuses,
    rows:[{memberId:1,teamName:'A',totalPoints:3.5,bonusPoints:1.5,bonusPending:true,
           weeklyPoints:{1:2},weeklyDifferentials:{1:5}}]});
  const content=text(h.tree);h.dispose();return content;
}

test('active-season scoreboard contains no bonus amounts or pending messages',()=>{
  assert.doesNotMatch(renderScoreboard(false),/bonus/i);
  assert.doesNotMatch(renderScoreboard(),/bonus/i);
});

test('completed-season scoreboard shows the awarded bonus without pending messages',()=>{
  const content=renderScoreboard(true);
  assert.match(content,/\+1\.5 bonus/);
  assert.doesNotMatch(content,/pending/i);
});
