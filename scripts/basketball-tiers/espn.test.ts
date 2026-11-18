import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile,writeFile,readdir,mkdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {loadSeasonScoreboards} from './espn.ts';
import {createWarningCollector} from './warnings.ts';

// Invalid publication, repeated recovery or swallowed filesystem errors break these contracts.
async function fixture(run:(h:{dir:string;file:string;load:()=>Promise<unknown[]>;warnings:ReturnType<typeof createWarningCollector>})=>Promise<void>){
 const dir=await mkdtemp(join(tmpdir(),'otm-tier-cache-test-')),original=globalThis.fetch;
 const warnings=createWarningCollector();const file=join(dir,'2025-26-20260101.json');
 try{await run({dir,file,warnings,load:()=>loadSeasonScoreboards([{label:'2025-26',start:'2026-01-01',end:'2026-01-01'}],new Map([['2025-26',[{start:'2026-01-01',end:'2026-01-01'}]]]),dir,warnings,1)});}
 finally{globalThis.fetch=original;await rm(dir,{recursive:true,force:true});}
}
for(const [name,body] of [['malformed','{broken'],['schema','{"unexpected":true}']] as const){
 test(`fresh ${name} response is not published and next explicit call fetches again`,async()=>fixture(async h=>{
  let calls=0;globalThis.fetch=async()=>{calls++;return new Response(body);};
  if(name==='malformed')await assert.rejects(h.load(),SyntaxError);else {assert.deepEqual(await h.load(),[{unexpected:true}]);assert.equal(h.warnings.all()[0].code,'invalid_espn_response');}
  assert.deepEqual(await readdir(h.dir),[]);
  globalThis.fetch=async()=>{calls++;return new Response('{"events":[]}');};assert.deepEqual(await h.load(),[{events:[]}]);assert.equal(calls,2);
 }));
 test(`legacy ${name} entry gets one recovery fetch, repairs and becomes a warm hit`,async()=>fixture(async h=>{
  await writeFile(h.file,body);let calls=0;globalThis.fetch=async()=>{calls++;return new Response('{"events":[]}');};
  assert.deepEqual(await h.load(),[{events:[]}]);assert.equal(calls,1);assert.deepEqual(JSON.parse(await readFile(h.file,'utf8')),{events:[]});await h.load();assert.equal(calls,1);assert.deepEqual(await readdir(h.dir),['2025-26-20260101.json']);
 }));
 test(`legacy ${name} followed by invalid recovery has no retry loop or cache`,async()=>fixture(async h=>{
  await writeFile(h.file,body);let calls=0;globalThis.fetch=async()=>{calls++;return new Response(body);};
  if(name==='malformed')await assert.rejects(h.load(),SyntaxError);else {await h.load();assert.equal(h.warnings.all()[0].code,'invalid_espn_response');}
  assert.equal(calls,1);assert.deepEqual(await readdir(h.dir),[]);
 }));
}
test('valid empty events cache is a hit without fetch',async()=>fixture(async h=>{
 await writeFile(h.file,'{"events":[]}');globalThis.fetch=async()=>{throw Error('Unexpected fetch');};assert.deepEqual(await h.load(),[{events:[]}]);assert.deepEqual(h.warnings.all(),[]);
}));
test('503 warns and returns empty without automatic retry or caching',async()=>fixture(async h=>{
 let calls=0;globalThis.fetch=async()=>{calls++;return new Response('Unavailable',{status:503,statusText:'Unavailable'});};
 assert.deepEqual(await h.load(),[{events:[]}]);assert.equal(calls,1);assert.deepEqual(await h.load(),[{events:[]}]);assert.equal(calls,2);assert.equal(h.warnings.all()[0].code,'invalid_espn_response');assert.deepEqual(await readdir(h.dir),[]);
}));
test('network rejection propagates without cache or retry',async()=>fixture(async h=>{
 let calls=0;const error=Error('Network');globalThis.fetch=async()=>{calls++;throw error;};await assert.rejects(h.load(),e=>e===error);assert.equal(calls,1);assert.deepEqual(await readdir(h.dir),[]);
}));
test('cache read I/O failure propagates without deletion or fetch',async()=>fixture(async h=>{
 await mkdir(h.file);await writeFile(join(h.file,'sentinel'),'keep');let calls=0;globalThis.fetch=async()=>{calls++;return new Response('{"events":[]}');};
 await assert.rejects(h.load(),{code:'EISDIR'});assert.equal(calls,0);assert.equal(await readFile(join(h.file,'sentinel'),'utf8'),'keep');
}));
test('failed rename propagates and removes only its owned temp file',async()=>fixture(async h=>{
 globalThis.fetch=async()=>{await mkdir(h.file);await writeFile(join(h.file,'sentinel'),'keep');return new Response('{"events":[]}');};
 await assert.rejects(h.load(),e=>['EISDIR','ENOTEMPTY'].includes((e as NodeJS.ErrnoException).code??''));assert.deepEqual(await readdir(h.dir),['2025-26-20260101.json']);assert.equal(await readFile(join(h.file,'sentinel'),'utf8'),'keep');
}));
