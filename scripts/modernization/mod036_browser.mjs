/** Native CDP for a task-owned synthetic component fixture only. */
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {existsSync} from 'node:fs';
import assert from 'node:assert/strict';
const pause=ms=>new Promise(r=>setTimeout(r,ms));
export function keyDownPayload(key,code,vk){const text=key==='Enter'?'\r':key===' '?' ':null;return {type:'keyDown',key,code,windowsVirtualKeyCode:vk,...(text===null?{}:{text,unmodifiedText:text})};}
export function focusExpression(selector){return `document.querySelector(${JSON.stringify(selector)}).focus()`;}
class CDP{
 constructor(ws){this.ws=ws;this.serial=0;this.pending=new Map();this.handlers={};ws.addEventListener('message',e=>{const data=JSON.parse(String(e.data));if(data.id){const p=this.pending.get(data.id);if(p){clearTimeout(p.timer);this.pending.delete(data.id);data.error?p.reject(Error(data.error.message)):p.resolve(data.result);}}else this.handlers[data.method]?.(data.params);});}
 static async open(url){const ws=new WebSocket(url);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});return new CDP(ws);}
 send(method,params={}){return new Promise((resolve,reject)=>{const id=++this.serial,timer=setTimeout(()=>{this.pending.delete(id);reject(Error('CDP timeout '+method));},15000);this.pending.set(id,{resolve,reject,timer});this.ws.send(JSON.stringify({id,method,params}));});}
 async evaluate(expression){const r=await this.send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description??r.exceptionDetails.text);return r.result.value;}
 async key(key,code,vk){await this.send('Input.dispatchKeyEvent',keyDownPayload(key,code,vk));await this.send('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:vk});await this.evaluate('window.audit.frames()');}
}
export async function browserProbe(fixture,work,report,{homeOnly=false}={}){
 const profile=await fs.mkdtemp(path.join(os.tmpdir(),'otm-mod036-chrome-'));let child,cdp,exited=false;const exceptions=[],blocked=[],requests=[];const result={records:[]};report.browser=result;
 const server=http.createServer(async(req,res)=>{try{const file=path.resolve(fixture,'.'+new URL(req.url,'http://127.0.0.1').pathname.replace(/\/$/,'/index.html'));if(!file.startsWith(fixture+path.sep))throw Error('Forbidden');const bytes=await fs.readFile(file);res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(bytes);}catch{res.statusCode=404;res.end('Not found');}});
 try{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const origin=`http://127.0.0.1:${server.address().port}`;
  child=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless=new','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',`--user-data-dir=${profile}`,`--crash-dumps-dir=${profile}`,'--disable-background-networking','--disable-component-update','--disable-sync','--disable-crash-reporter','--no-first-run','--no-default-browser-check','--no-proxy-server','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1','about:blank'],{stdio:'ignore'});child.on('exit',()=>{exited=true;});child.on('error',e=>exceptions.push(String(e)));
  let port;for(let i=0;i<200;i++){if(exited)throw Error('Owned Chrome exited before CDP ready');try{port=Number((await fs.readFile(path.join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}catch{await pause(50);}}
  if(!port)throw Error('Owned Chrome CDP unavailable');const targets=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();cdp=await CDP.open(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
  cdp.handlers['Runtime.exceptionThrown']=p=>exceptions.push(p.exceptionDetails.exception?.description??p.exceptionDetails.text);
  cdp.handlers['Fetch.requestPaused']=p=>{requests.push(p.request.url);const allowed=p.request.url.startsWith(origin+'/');if(!allowed)blocked.push(p.request.url);cdp.send(allowed?'Fetch.continueRequest':'Fetch.failRequest',allowed?{requestId:p.requestId}:{requestId:p.requestId,errorReason:'BlockedByClient'}).catch(e=>exceptions.push(String(e)));};
  await cdp.send('Page.enable');await cdp.send('Runtime.enable');await cdp.send('Performance.enable');await cdp.send('Fetch.enable',{patterns:[{urlPattern:'*'}]});await cdp.send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});result.browser=await cdp.send('Browser.getVersion');
  await cdp.send('Page.navigate',{url:origin+'/'});let ready=false;for(let i=0;i<200;i++){if(await cdp.evaluate('typeof window.audit === "object"')){ready=true;break;}await pause(50);}if(!ready)throw Error('Synthetic fixture did not load: '+exceptions.join(';'));
  if(homeOnly){const {homeTabsAcceptance}=await import('./home_tabs_acceptance.mjs');result.homeTabs=await homeTabsAcceptance(cdp);assert.deepEqual(exceptions,[]);result.exceptions=exceptions;result.pageRequestOrigins=[...new Set(requests.map(u=>new URL(u).origin))];result.blockedRequests=blocked;assert.deepEqual(result.pageRequestOrigins,[origin]);return result;}
  for(const kind of ['home','draft','scoreboard'])for(const count of [8,32,128]){
   const samples=[];for(let i=0;i<6;i++){const x=await cdp.evaluate(`window.audit.mount(${JSON.stringify(kind)},${count})`);assert.equal(x.rows,count);const metrics=await cdp.send('Performance.getMetrics');if(i)samples.push({...x,browserMetrics:Object.fromEntries(metrics.metrics.filter(m=>['JSHeapUsedSize','LayoutDuration','ScriptDuration','Nodes'].includes(m.name)).map(m=>[m.name,m.value]))});}
   const ordered=samples.map(x=>x.settleMs).sort((a,b)=>a-b);result.records.push({kind,count,samples,medianSettleMs:ordered[2]});
  }
  const {homeTabsAcceptance}=await import('./home_tabs_acceptance.mjs');result.homeTabs=await homeTabsAcceptance(cdp);
  await cdp.evaluate('window.audit.mount("draft",8)');await cdp.evaluate(focusExpression('button[aria-label="Move Team 2 up"]'));await cdp.key(' ','Space',32);
  result.draftKeyboard=await cdp.evaluate('({order:[...document.querySelectorAll(".ml-draft-member")].map(x=>x.textContent),focus:document.activeElement?.getAttribute("aria-label"),announcement:document.querySelector(".ml-draft-order [role=status]")?.textContent})');assert.deepEqual(result.draftKeyboard.order.slice(0,2),['Team 2','Team 1']);assert.equal(result.draftKeyboard.focus,'Move Team 2 down');assert.match(result.draftKeyboard.announcement,/position 1 of 8/);
  assert.deepEqual(exceptions,[]);result.exceptions=exceptions;result.pageRequestOrigins=[...new Set(requests.map(u=>new URL(u).origin))];result.blockedRequests=blocked;assert.deepEqual(result.pageRequestOrigins,[origin]);
  return result;
 }finally{
  if(cdp){try{cdp.ws.send(JSON.stringify({id:++cdp.serial,method:'Browser.close'}));}catch{}for(let i=0;i<100&&!exited;i++)await pause(50);try{cdp.ws.close();}catch{}}
  if(child&&!exited){child.kill('SIGTERM');for(let i=0;i<60&&!exited;i++)await pause(50);if(!exited){child.kill('SIGKILL');await new Promise(r=>child.once('exit',r));}}
  server.closeAllConnections();await new Promise(resolve=>server.close(resolve));await fs.rm(profile,{recursive:true,force:true});report.browserCleanup={ownedChildPid:child?.pid??null,childExited:!child||exited,serverClosed:!server.listening,profileRemoved:!existsSync(profile)};
 }
}
