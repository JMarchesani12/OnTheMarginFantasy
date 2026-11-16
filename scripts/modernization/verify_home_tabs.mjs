/** Keyboard-only acceptance: owned synthetic fixture, fresh Chrome profile, no configured app. */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {buildFixture} from './measure_mod036.mjs';
import {browserProbe} from './mod036_browser.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const work=path.join(root,'.superpowers/sdd/2026-11-16-post-audit-home-tabs');
const evidence=path.join(root,'docs/modernization/evidence');
const id=crypto.randomUUID().replaceAll('-','');const file=path.join(evidence,`mod-036-home-tabs-${id}.json`);
const report={runId:id,result:'RUNNING',startedAt:new Date().toISOString(),sourceHashes:{},browserCleanup:{notStarted:true}};
async function persist(){await fs.mkdir(evidence,{recursive:true});await fs.writeFile(file,JSON.stringify(report,null,2)+'\n');}
await persist();
try{
 const fixture=await buildFixture(work);
 const inputs=JSON.parse(await fs.readFile(path.join(work,'fixture-inputs.json'),'utf8'));
 const files=[...inputs.filter(p=>!p.startsWith('audit:')),'scripts/modernization/measure_mod036.mjs','scripts/modernization/mod036_browser.mjs','scripts/modernization/home_tabs_acceptance.mjs','scripts/modernization/verify_home_tabs.mjs'];
 for(const f of files)report.sourceHashes[f]=crypto.createHash('sha256').update(await fs.readFile(path.resolve(root,f))).digest('hex');
 report.browser=await browserProbe(fixture,work,report,{homeOnly:true});
 if(!report.browserCleanup.childExited||!report.browserCleanup.serverClosed||!report.browserCleanup.profileRemoved)throw Error('Cleanup unverified');
 report.result='PASS';
}catch(e){report.result='FAILED';report.error=String(e);process.exitCode=1;}
finally{report.finishedAt=new Date().toISOString();await persist();console.log(JSON.stringify({artifact:path.relative(root,file),result:report.result,cleanup:report.browserCleanup,error:report.error}));}
