import test from 'node:test';
import assert from 'node:assert/strict';
import {manageHarness,nodes,text} from './helpers/manageLeagueHarness.ts';

test('parent keeps commissioner Pre-Draft visibility across lifecycle states',async()=>{
  for(const status of ['Pre-Draft','Drafting','Post-Draft','In-Season','Completed'])for(const userId of [1,2]) {
    const h=manageHarness({status,userId});h.render();await h.flush();
    assert.equal(Boolean(h.button('Randomize Draft Order')),status==='Pre-Draft'&&userId===1,`${status}/${userId}`);
  }
});
test('parent renders order/rank/name/self removal and loading/error/empty states',async()=>{
  const h=manageHarness();h.render();await h.flush();
  assert.deepEqual(h.rows().map(row=>text(row).replace(/\s/g,'')),['1Member12BobRemoveMoveupMovedown⇅','2CommissionerteamAliceRemoveMoveupMovedown⇅','3ThirdteamCarolRemoveMoveupMovedown⇅']);
  const remove=nodes(h.rows()[1]).find(n=>n.type==='button');assert.equal(remove.props.disabled,true);assert.equal(remove.props.title,'You cannot remove yourself.');
  for(const options of [{members:[]},{pendingMembers:true},{memberError:'member read failed'}]) {
    const x=manageHarness(options);x.render();await x.flush();
    assert.equal(x.rows().length,0);assert.equal(x.button('Randomize Draft Order').props.disabled,true);
    if('pendingMembers' in options)assert.match(x.text(),/Loading league members/);
    if('memberError' in options)assert.match(x.text(),/member read failed/);
  }
});
test('actual parent drag/randomize actions preserve ordered save payload and sequence',async()=>{
  const h=manageHarness();h.render();await h.flush();
  h.rows()[0].props.onDragStart();h.render();assert.match(h.rows()[0].props.className,/is-dragging/);
  let prevented=false;h.rows()[1].props.onDragOver({preventDefault(){prevented=true;}});h.render();assert.equal(prevented,true);
  h.rows()[1].props.onDragEnd();h.render();assert.ok(h.rows().every(row=>!row.props.className.includes('is-dragging')));
  h.calls.length=0;await h.button('Save').props.onClick();await h.flush();
  assert.deepEqual(h.calls.filter(c=>['update','order','getLeague'].includes(c.name)).map(c=>c.name),['update','order','getLeague']);
  assert.deepEqual(JSON.parse(JSON.stringify(h.calls.find(c=>c.name==='order')?.args)),[10,[11,12,13]]);
  h.button('Randomize Draft Order').props.onClick();h.render();h.calls.length=0;
  await h.button('Save and Start Draft').props.onClick();await h.flush();
  assert.deepEqual(JSON.parse(JSON.stringify(h.calls.find(c=>c.name==='order')?.args)),[10,[12,13,11]]);
  assert.match(h.text(),/Draft settings saved\. Draft start will be enabled soon\./);
});
test('parent owns remove confirmation, API arguments, cancellation, failure and reload',async()=>{
  const h=manageHarness();h.render();await h.flush();
  const remove=()=>nodes(h.rows()[0]).find(n=>n.type==='button');
  h.confirm(false);await remove().props.onClick();assert.ok(!h.calls.some(c=>c.name==='remove'));
  h.confirm(true);h.failRemove('remove failed');await remove().props.onClick();h.render();assert.match(h.text(),/remove failed/);
  h.failRemove('');h.calls.length=0;await remove().props.onClick();await h.flush();
  assert.deepEqual(JSON.parse(JSON.stringify(h.calls.find(c=>c.name==='remove')?.args)),[10,12,1]);
  assert.ok(h.calls.some(c=>c.name==='members'));assert.equal(h.rows().length,2);
  h.calls.length=0;await h.button('Save').props.onClick();
  assert.deepEqual(JSON.parse(JSON.stringify(h.calls.find(c=>c.name==='order')?.args)),[10,[11,13]]);
});
test('parent save failure keeps existing error and avoids order request',async()=>{
  const h=manageHarness();h.render();await h.flush();h.failSave('save failed');h.calls.length=0;
  await h.button('Save').props.onClick();h.render();assert.match(h.text(),/save failed/);
  assert.ok(!h.calls.some(c=>c.name==='order'));
});
