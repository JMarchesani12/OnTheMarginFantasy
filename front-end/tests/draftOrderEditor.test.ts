import test from 'node:test';
import assert from 'node:assert/strict';
import {loadEditor,membersFixture,nodes,text} from './helpers/manageLeagueHarness.ts';
function fixture() {
  const calls:any[]=[];const members=membersFixture();
  return {calls,members,props:{orderedMembers:members,memberCount:members.length,membersLoading:false,membersError:null,memberActionError:null,
    draggingMemberId:12,currentUserId:1,
    onMoveMember:()=>{},onRandomize:()=>calls.push(['random']),onRemoveMember:(member:any)=>calls.push(['remove',member]),
    onDragStart:(id:number)=>calls.push(['start',id]),onDragOver:(id:number)=>calls.push(['over',id]),onDragEnd:()=>calls.push(['end'])}};
}
test('editor forwards original member/IDs and prevents default before drag-over',()=>{
  const f=fixture();const tree=loadEditor()(f.props);const all=nodes(tree);
  all.find(n=>n.type==='button'&&text(n)==='Randomize Draft Order').props.onClick();
  const rows=all.filter(n=>n.props?.className?.startsWith('ml-draft-order-row'));
  rows[1].props.onDragStart();rows[2].props.onDragOver({preventDefault:()=>f.calls.push(['prevent'])});rows[1].props.onDragEnd();
  nodes(rows[1]).find(n=>n.type==='button').props.onClick();
  assert.deepEqual(f.calls,[['random'],['start',12],['prevent'],['over',13],['end'],['remove',f.members[1]]]);
  assert.equal(f.calls.at(-1)[1],f.members[1]);assert.match(rows[1].props.className,/is-dragging/);
});
test('editor uses original memberCount even when ordered array differs',()=>{
  const f=fixture();const editor=loadEditor();
  const hasList=(tree:any)=>nodes(tree).some(n=>n.props?.className==='ml-draft-order-list');
  const positive=editor({...f.props,orderedMembers:[],memberCount:3});
  assert.equal(nodes(positive).find(n=>n.type==='button').props.disabled,false);assert.equal(hasList(positive),true);
  const zero=editor({...f.props,memberCount:0});
  assert.equal(nodes(zero).find(n=>n.type==='button').props.disabled,true);assert.equal(hasList(zero),false);
});
test('editor preserves loading/errors, labels, fallback and self-disabled title',()=>{
  const f=fixture();const tree=loadEditor()({...f.props,membersLoading:true,membersError:'load failure',memberActionError:'remove failure'});
  assert.match(text(tree),/Loading league members/);assert.match(text(tree),/load failure/);assert.match(text(tree),/remove failure/);assert.match(text(tree),/Member 12Bob/);
  const buttons=nodes(tree).filter(n=>n.props?.className==='ml-remove-btn');
  assert.equal(buttons[0].props.disabled,true);assert.equal(buttons[0].props.title,'You cannot remove yourself.');
  assert.equal(buttons[1].props.disabled,false);assert.equal(buttons[1].props.title,'Remove member');
});
