import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';

import { harness } from './helpers/draftPageHarness.ts';

test('actual page combined reader propagates roster denial and transport failure',async()=>{
  const h=harness();h.render();await h.flush();
  for(const failure of [Object.assign(new Error('denied'),{status:403}),new Error('offline')]) {
    h.failRoster(failure);
    await assert.rejects(h.controllers.at(-1).options.read(new AbortController().signal),error=>error===failure);
  }
});

test('route change replaces controller scope and reloads matching league metadata',async()=>{
  const h=harness();h.render();await h.flush();const old=h.controllers.at(-1);
  h.navigate('20');await h.flush();
  assert.equal(h.controllers.at(-1).options.leagueId,20);assert.equal(old.disposed,true);
  assert.match(h.text(),/League 20/);assert.doesNotMatch(h.text(),/League 10/);
});

test('account change reloads member metadata and personal turn',async()=>{
  const h=harness();h.render();await h.flush();h.account();await h.flush();
  assert.ok(h.metadata.includes(2),'new account must reload its league membership');
  h.controllers.at(-1).options.apply({state:{status:'live',currentMemberId:12},members:[],picks:[],availableTeams:[]});
  h.render();assert.match(h.text(),/You are on the clock/);
});

test('late old command failure cannot overwrite next token command state',async()=>{
  const h=harness();h.render();await h.flush();
  const old=h.button('Start Draft').props.onClick();assert.equal(h.commands.length,1);
  h.rotateToken();await h.flush();const current=h.button('Start Draft').props.onClick();h.render();
  assert.equal(h.button('Start Draft').props.disabled,true);
  h.commands[0].reject(new Error('obsolete command error'));await old;h.render();
  assert.equal(h.button('Start Draft').props.disabled,true);
  assert.doesNotMatch(h.text(),/obsolete command error/);
  h.commands[1].reject(new Error('current command error'));await current;
});

test('available-team HTTP reader preserves final status and abort signal',async()=>{
  for(const status of [401,403,404,500]) {
    const exports:any={};const controller=new AbortController();let seen:any;
    const source=readFileSync(new URL('../src/api/roster.ts',import.meta.url),'utf8');
    const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
    runInNewContext(compiled,{exports,require:()=>({API_BASE_URL:'https://api.example.test',apiFetch:async(_url:any,init:any)=>{seen=init;return new Response('{}',{status});}})});
    await assert.rejects(exports.getAvailableTeams(1,10,controller.signal),(error:any)=>error.status===status);
    assert.equal(seen.signal,controller.signal);
  }
});


test('page read capability preserves request order, league and identical AbortSignal',async()=>{
  const h=harness();h.render();await h.flush();const signal=new AbortController().signal;
  const result=await h.controllers.at(-1).options.read(signal);
  assert.deepEqual(h.readCalls.map(call=>call.kind),['state','available']);
  assert.ok(h.readCalls.every(call=>call.id===10&&call.signal===signal));
  assert.equal(h.readCalls[1].week,1);
  assert.equal(result.state,null);assert.deepEqual(Array.from(result.picks),[]);assert.deepEqual(Array.from(result.availableTeams),[]);
});
