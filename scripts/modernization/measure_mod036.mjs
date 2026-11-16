/** Bounded audit helpers; no app/runtime/provider startup. */
import fs from 'node:fs/promises';
import {existsSync} from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
import {gzipSync,brotliCompressSync} from 'node:zlib';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';

export const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const require=createRequire(path.join(ROOT,'front-end/package.json'));
export const WORK=path.join(ROOT,'.superpowers/sdd/2026-11-16-mod-036-local-audit');
export function assetSizes(buffer){return {raw:buffer.length,gzip:gzipSync(buffer).length,brotli:brotliCompressSync(buffer).length};}
export function staticClosure(manifest,key,seen=new Set()){
  const files=new Set();if(seen.has(key))return files;seen.add(key);const item=manifest[key];if(!item)throw Error('Missing manifest import '+key);files.add(item.file);
  for(const dep of item.imports??[])for(const file of staticClosure(manifest,dep,seen))files.add(file);return files;
}
export function sha(buffer){return crypto.createHash('sha256').update(buffer).digest('hex');}
export async function providerProbe(){
  const {loadSeasonScoreboards}=await import(pathToFileURL(path.join(ROOT,'scripts/basketball-tiers/espn.ts')));
  const {createWarningCollector}=await import(pathToFileURL(path.join(ROOT,'scripts/basketball-tiers/warnings.ts')));
  const temp=await fs.mkdtemp(path.join(os.tmpdir(),'otm-mod036-provider-'));const original=globalThis.fetch;let calls=0;const result={};
  const seasons=[{label:'2025-26',start:'2026-01-01',end:'2026-01-01'}],ranges=new Map([['2025-26',[{start:'2026-01-01',end:'2026-01-01'}]]]);
  const invoke=async(name)=>{const warnings=createWarningCollector();try{return {value:await loadSeasonScoreboards(seasons,ranges,path.join(temp,name),warnings,1),warnings:warnings.all()};}catch(e){return {error:e.name,warnings:warnings.all()};}};
  try{
    globalThis.fetch=async()=>{calls++;return new Response('{"events":[]}',{status:200});};let first=await invoke('success');let before=calls;let second=await invoke('success');assert.deepEqual(first.value,[{events:[]}]);assert.deepEqual(second.value,first.value);result.success={fetches:before,secondFetches:calls-before,first,second};
    calls=0;globalThis.fetch=async()=>{calls++;return new Response('Unavailable',{status:503,statusText:'Synthetic unavailable'});};first=await invoke('http');second=await invoke('http');result.http={fetches:calls,returnedEmpty:first.value?.[0]?.events?.length===0,first,second,cacheFiles:await fs.readdir(path.join(temp,'http'))};assert.equal(calls,2);assert.equal(result.http.cacheFiles.length,0);
    calls=0;globalThis.fetch=async()=>{calls++;throw Error('Synthetic network rejection');};first=await invoke('network');result.network={fetches:calls,...first};assert.equal(first.error,'Error');assert.equal(calls,1);
    calls=0;globalThis.fetch=async()=>{calls++;return new Response('{broken',{status:200});};first=await invoke('malformed');before=calls;second=await invoke('malformed');result.malformed={fetches:before,secondFetches:calls-before,error:first.error,secondError:second.error,cacheFiles:await fs.readdir(path.join(temp,'malformed'))};assert.equal(first.error,'SyntaxError');assert.equal(second.error,'SyntaxError');assert.equal(calls,1);
    calls=0;globalThis.fetch=async()=>{calls++;return new Response('{"unexpected":true}',{status:200});};first=await invoke('schema');before=calls;second=await invoke('schema');result.schema={fetches:before,secondFetches:calls-before,first,second};assert.equal(first.warnings[0].code,'invalid_espn_response');assert.equal(calls,1);
  }finally{globalThis.fetch=original;await fs.rm(temp,{recursive:true,force:true});result.cleanup=!existsSync(temp);}
  return result;
}

export async function bundleProbe(){
  const {build}=await import(pathToFileURL(path.join(ROOT,'front-end/node_modules/vite/dist/node/index.js')));
  const empty=path.join(WORK,'empty-env'),out=path.join(WORK,'production');await fs.mkdir(empty,{recursive:true});let checked=false;
  const values={VITE_API_BASE_URL:'https://synthetic.invalid',VITE_SOCKET_URL:'https://synthetic.invalid',VITE_SUPABASE_URL:'https://audit.invalid',VITE_SUPABASE_ANON_KEY:'synthetic-anon-placeholder'};
  await build({root:path.join(ROOT,'front-end'),configFile:path.join(ROOT,'front-end/vite.config.ts'),envDir:empty,envPrefix:'MOD036_AUDIT_ONLY_',mode:'audit',define:Object.fromEntries(Object.entries(values).map(([k,v])=>['import.meta.env.'+k,JSON.stringify(v)])),logLevel:'silent',plugins:[{name:'audit-env-guard',configResolved(c){assert.equal(path.resolve(c.envDir),empty);assert.ok(!Object.keys(c.env).some(k=>k.startsWith('VITE_')));checked=true;}}],build:{outDir:out,emptyOutDir:true,manifest:true,sourcemap:false}});assert.ok(checked);
  const manifest=JSON.parse(await fs.readFile(path.join(out,'.vite/manifest.json'),'utf8'));const assets={};
  for(const item of Object.values(manifest))for(const file of [item.file,...(item.css??[])])if(!assets[file]){const bytes=await fs.readFile(path.join(out,file));assets[file]={...assetSizes(bytes),sha256:sha(bytes)};}
  const entry=Object.keys(manifest).find(k=>manifest[k].isEntry);assert.ok(entry);const initial=staticClosure(manifest,entry);
  const sum=files=>[...files].reduce((a,f)=>{for(const k of ['raw','gzip','brotli'])a[k]+=assets[f][k];return a;},{raw:0,gzip:0,brotli:0});
  const routes=Object.entries(manifest).filter(([,v])=>v.isDynamicEntry).map(([key])=>{const all=new Set([...initial,...staticClosure(manifest,key)]);return {source:key,own:manifest[key].file,additionalFiles:[...all].filter(f=>!initial.has(f)),additionalJS:sum([...all].filter(f=>!initial.has(f))),coldJS:sum(all),routeCSS:manifest[key].css??[]};});
  return {controlledEnvironment:true,envDirEmpty:true,manifest,assets,entry,initialFiles:[...initial],initialJS:sum(initial),initialCSS:manifest[entry].css??[],routes,limits:'Per-file gzip/Brotli sums,not wire transfers; shared static chunks counted once, no runtime profile or size budget'};
}

export async function buildFixture(work=WORK){
  const esbuild=require('esbuild');const out=path.join(work,'fixture');await fs.mkdir(out,{recursive:true});
  const profile=`const value={userId:1,displayName:'Synthetic user',email:'audit@example.test',identityKey:'audit:1',isCurrentIdentity:()=>true,authUserId:'audit',loading:false,error:null,refreshUser:async()=>{}};export const useCurrentUser=()=>value;`;
  const leagues=`export async function getLeaguesForUser(){return Array.from({length:globalThis.__auditCount??8},(_,i)=>({leagueId:i+1,leagueName:'Synthetic league '+(i+1),sport:'Basketball',numPlayers:8,status:'In-Season',commissionerId:1,commissionerDisplayName:'Audit',teamName:'Team '+(i+1),seasonPoints:i,currentWeekNumber:13,currentWeekId:13,seasonYear:2026,draftOrder:1,settings:{timezone:'UTC'}}));}export async function searchLeagues(){return [];}`;
  const built=await esbuild.build({absWorkingDir:ROOT,nodePaths:[path.join(ROOT,'front-end/node_modules')],metafile:true,entryPoints:[path.join(ROOT,'scripts/modernization/mod036_fixture.tsx')],outfile:path.join(out,'fixture.js'),bundle:true,format:'esm',jsx:'automatic',minify:true,define:{'process.env.NODE_ENV':'"production"'},loader:{'.svg':'dataurl','.png':'dataurl'},plugins:[{name:'controlled-fixture-only',setup(b){b.onResolve({filter:/context\/(currentUserContext|AuthContext)$|api\/(leagues|sport)$/},args=>({path:args.path.includes('currentUserContext')?'profile':args.path.includes('AuthContext')?'auth':args.path.endsWith('leagues')?'leagues':'sport',namespace:'audit'}));b.onLoad({filter:/.*/,namespace:'audit'},args=>({contents:args.path==='profile'?profile:args.path==='auth'?`const value={signOut:async()=>{}};export const useAuth=()=>value;`:args.path==='leagues'?leagues:`export async function getSports(){return [{id:1,name:'Basketball'}];}`,loader:'js'}));}}],logLevel:'silent'});
  const inputs=Object.keys(built.metafile.inputs);assert.ok(!inputs.some(p=>p.includes('supabaseClient')||p.endsWith('/api/client.ts')));await fs.writeFile(path.join(work,'fixture-inputs.json'),JSON.stringify(inputs,null,2));
  await fs.writeFile(path.join(out,'index.html'),'<!doctype html><html><head><meta charset="utf-8"><title>MOD036 synthetic fixture</title><link rel="stylesheet" href="/fixture.css"></head><body><div id="root"></div><script type="module" src="/fixture.js"></script></body></html>');return out;
}

async function sourceHashes(root){
 const files=['front-end/package.json','front-end/package-lock.json','front-end/vite.config.ts','scripts/modernization/measure_mod036.mjs','scripts/modernization/mod036_browser.mjs','scripts/modernization/mod036_fixture.tsx','scripts/modernization/tests/mod036.test.mjs'];
 async function add(dir){for(const e of await fs.readdir(path.join(root,dir),{withFileTypes:true})){const name=path.join(dir,e.name);if(e.isDirectory())await add(name);else if(/\.(ts|tsx|css|json)$/.test(name))files.push(name);}}
 await add('front-end/src');await add('scripts/basketball-tiers');const result={};for(const name of files)result[name]=sha(await fs.readFile(path.join(root,name)));return result;
}
export async function run({sourceRoot=ROOT,evidenceDir=path.join(ROOT,'docs/modernization/evidence'),browser=true}={}){
 await fs.mkdir(evidenceDir,{recursive:true});const runId=crypto.randomUUID().replaceAll('-',''),file=path.join(evidenceDir,`mod-036-local-${runId}.json`),manifest=path.join(evidenceDir,'mod-036-local-current-2026-11-16.json');const report={date:'2026-11-16',runId,result:'RUNNING',startedAt:new Date().toISOString(),provenance:{},browserCleanup:{notStarted:true}};
 async function persist(){for(const [name,value] of [[file,report],[manifest,{runId,result:report.result,artifact:path.basename(file),browserCleanup:report.browserCleanup}]]){await fs.writeFile(name+'.tmp',JSON.stringify(value,null,2)+'\n');await fs.rename(name+'.tmp',name);}}
 await persist();
 try{
  report.provenance=await sourceHashes(sourceRoot);report.provider=await providerProbe();report.bundle=await bundleProbe();const fixture=await buildFixture();
  const app=await fs.readFile(path.join(ROOT,'front-end/src/App.tsx'),'utf8'),main=await fs.readFile(path.join(ROOT,'front-end/src/main.tsx'),'utf8');report.sourceInventory={scope:'App.tsx/main.tsx only,static observation not runtime failure',lazyDeclarations:(app.match(/React\.lazy\(/g)??[]).length,catchAllRouteDeclared:/path=["']\*["']/.test(app),appOrMainErrorBoundary:/ErrorBoundary/.test(app+main)};
  if(browser){const {browserProbe}=await import('./mod036_browser.mjs');report.browser=await browserProbe(fixture,WORK,report);assert.ok(report.browserCleanup.childExited&&report.browserCleanup.serverClosed&&report.browserCleanup.profileRemoved);}
  report.result='PASS';return report;
 }catch(e){report.result='FAILED';report.error={name:e.name,message:e.message};throw e;}
 finally{report.finishedAt=new Date().toISOString();await persist();}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){await run();console.log('MOD036 controlled bundle/provider/native component audit PASS');}
