import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,deferred,settle} from './helpers/leagueContextHarness.ts';

function setup(){
 const h=fixture(),requests:any[]=[];let state:any;
 const {useTeamSearchCatalog}=h.load('src/hooks/useTeamSearchCatalog.ts',{
  '../api/teamSearch':{getTeamSearchCatalog:(force:boolean)=>{const request={...deferred(),force};requests.push(request);return request.promise;}},
 });
 const Observer=()=>{state=useTeamSearchCatalog();return null;};
 const render=()=>h.render(Observer);
 return {h,requests,render,state:()=>state};
}
const catalog=(alias:string)=>({teams:[{teamId:369,schoolId:369,teamName:'UNI',aliases:[alias]}]});

test('alias loading failure preserves direct search and retry refreshes database metadata',async()=>{
 const x=setup();x.render();assert.equal(x.state().error,false);
 x.requests[0].reject(new Error('private transport detail'));await settle();x.render();
 assert.equal(x.state().error,true);assert.deepEqual([...x.state().index.aliasesFor({teamId:369,teamName:'UNI'})],[]);
 x.state().retry();x.render();assert.equal(x.requests[1].force,true);
 x.requests[1].resolve(catalog('Northern Iowa'));await settle();x.render();
 assert.equal(x.state().error,false);assert.deepEqual([...x.state().index.aliasesFor({teamId:369,teamName:'UNI'})],['Northern Iowa']);x.h.dispose();
});

test('obsolete catalog response cannot overwrite an explicitly refreshed index',async()=>{
 const x=setup();x.render();x.state().retry();x.render();
 x.requests[1].resolve(catalog('Current Name'));await settle();x.render();
 x.requests[0].resolve(catalog('Obsolete Name'));await settle();x.render();
 assert.deepEqual([...x.state().index.aliasesFor({teamId:369,teamName:'UNI'})],['Current Name']);x.h.dispose();
});
