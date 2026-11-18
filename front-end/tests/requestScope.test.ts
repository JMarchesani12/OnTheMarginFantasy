import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture} from './helpers/leagueContextHarness.ts';
test('request scope rejects obsolete channel requests, unmounted callbacks and obsolete parent context',()=>{
 const h=fixture();let parent=true,scope:any;const module=h.load('src/hooks/useRequestScope.ts');
 function Component(){scope=module.useRequestScope(()=>parent);return null;}h.render(Component);
 const a=scope.capture('teams'),b=scope.capture('teams'),other=scope.capture('members'),command=scope.capture();assert.equal(a(),false);assert.equal(b(),true);assert.equal(other(),true);
 parent=false;assert.equal(command(),false);parent=true;h.dispose();assert.equal(command(),false);assert.equal(b(),false);assert.equal(scope.isCurrent(),false);
});
test('read channels abort replaced requests and dispose all outstanding reads',()=>{
 const h=fixture();let scope:any;const module=h.load('src/hooks/useRequestScope.ts');function Component(){scope=module.useRequestScope();return null;}h.render(Component);
 const first=scope.capture('teams');assert.equal(first.signal.aborted,false);const second=scope.capture('teams');assert.equal(first.signal.aborted,true);const members=scope.capture('members');h.dispose();assert.equal(second.signal.aborted,true);assert.equal(members.signal.aborted,true);
});
