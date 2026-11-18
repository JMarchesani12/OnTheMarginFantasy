import test from 'node:test';
import assert from 'node:assert/strict';
import {harness} from './helpers/draftPageHarness.ts';
const base=Date.parse('2026-11-07T12:00:00Z');
const iso=(ms:number)=>new Date(ms).toISOString();
async function fixture(){const h=harness();h.setNow(base);h.render();await h.flush();return h;}
function snapshot(h:Awaited<ReturnType<typeof fixture>>,status='live',expiresAt:unknown=iso(base+65000),serverNow:unknown=iso(base)) {
  h.controllers.at(-1).options.apply({state:{status,currentMemberId:11,expiresAt},members:[],picks:[],availableTeams:[],serverNow});h.render();
}
test('actual page countdown clamps/formats and timer follows live pause resume completion',async()=>{
  const h=await fixture();assert.equal(h.timerStatus().active,0);
  snapshot(h);assert.match(h.text(),/1:05/);assert.deepEqual(h.timerStatus(),{active:1,starts:1,stops:0});
  h.setNow(base+6000);h.tick();assert.match(h.text(),/0:59/);
  snapshot(h,'paused',iso(base+65000),null);assert.equal(h.timerStatus().active,0);
  h.setNow(base+10000);h.render();assert.match(h.text(),/0:59/);
  snapshot(h,'live',iso(base+65000),null);assert.equal(h.timerStatus().active,1);h.tick();assert.match(h.text(),/0:55/);
  h.setNow(base+70000);h.tick();assert.match(h.text(),/0:00/);
  snapshot(h,'complete',null,null);assert.equal(h.timerStatus().active,0);
  snapshot(h);h.dispose();assert.equal(h.timerStatus().active,0);
});
test('actual page offset preserves last tick and ignores missing/invalid samples without rejoining',async()=>{
  const h=await fixture();const controller=h.controllers.at(-1);const count=h.controllers.length;
  snapshot(h);h.setNow(base+10000);snapshot(h,'live',iso(base+125000),iso(base+40000));
  assert.match(h.text(),/1:35/); // nowMs still initial sample; offset is +30 seconds.
  assert.equal(h.timerStatus().starts,1);h.tick();assert.match(h.text(),/1:25/);
  snapshot(h,'live',iso(base+125000),'invalid');assert.match(h.text(),/1:25/);
  snapshot(h,'live',iso(base+125000),null);assert.match(h.text(),/1:25/);
  for(const expiry of [null,'','invalid',123]) {snapshot(h,'live',expiry,null);assert.doesNotMatch(h.text(),/1:25/);}
  assert.equal(h.controllers.length,count);assert.equal(h.controllers.at(-1),controller);assert.equal(h.timerStatus().starts,1);
  h.dispose();
});
