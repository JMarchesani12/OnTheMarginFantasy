import assert from 'node:assert/strict';
export function validateHomeTabs(snapshot,focus,selected){
 assert.equal(snapshot.focus,focus);
 assert.deepEqual(snapshot.tabs.map(t=>t.selected),selected===0?['true','false']:['false','true']);
 assert.deepEqual(snapshot.tabs.map(t=>t.tabIndex),focus==='Your Leagues'?[0,-1]:[-1,0]);
 for(const [i,t] of snapshot.tabs.entries()){
  assert.ok(t.id);assert.ok(t.controls);const p=snapshot.panels.find(p=>p.id===t.controls);assert.ok(p);assert.equal(p.label,t.id);assert.equal(p.hidden,i!==selected);assert.equal(p.display==='none',i!==selected);if(i!==selected)assert.equal(p.controls,0);
 }
}
export async function homeTabsAcceptance(cdp){
 await cdp.evaluate('window.audit.mount("home",8)');
 await cdp.evaluate('document.querySelectorAll("[role=tab]")[0].focus()');
 await cdp.evaluate('window.audit.frames()');
 const read=()=>cdp.evaluate(`({focus:document.activeElement?.textContent,tabs:[...document.querySelectorAll('[role=tab]')].map(t=>({id:t.id,controls:t.getAttribute('aria-controls'),selected:t.getAttribute('aria-selected'),tabIndex:t.tabIndex})),panels:[...document.querySelectorAll('[role=tabpanel]')].map(p=>({id:p.id,label:p.getAttribute('aria-labelledby'),hidden:p.hidden,display:getComputedStyle(p).display,controls:p.querySelectorAll('button,input,select,a').length}))})`);
 const records=[];const snap=async(label,focus,selected)=>{const s=await read();validateHomeTabs(s,focus,selected);records.push({label,...s});return s;};
 const initial=await snap('initial','Your Leagues',0);
 for(const [key,code,vk,focus] of [['ArrowRight','ArrowRight',39,'Search Leagues'],['ArrowRight','ArrowRight',39,'Your Leagues'],['ArrowLeft','ArrowLeft',37,'Search Leagues'],['Home','Home',36,'Your Leagues'],['End','End',35,'Search Leagues']]){await cdp.key(key,code,vk);await snap(key,focus,0);}
 await cdp.key('Enter','Enter',13);const active=await snap('Enter','Search Leagues',1);assert.deepEqual(active.tabs.map(t=>t.id),initial.tabs.map(t=>t.id));
 await cdp.key('Tab','Tab',9);assert.equal(await cdp.evaluate('document.activeElement.id'),'league-search');records.push({label:'Tab exit',focusId:'league-search'});
 await cdp.evaluate('document.querySelectorAll("[role=tab]")[1].focus()');await cdp.key('ArrowLeft','ArrowLeft',37);await snap('focus leagues','Your Leagues',1);await cdp.key(' ','Space',32);await snap('Space','Your Leagues',0);
 // A genuine pointer activation, rather than evaluate().click().
 const point=await cdp.evaluate('(()=>{const r=document.querySelectorAll("[role=tab]")[1].getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()');
 await cdp.send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point});await cdp.send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point});await cdp.evaluate('window.audit.frames()');await snap('click','Search Leagues',1);
 const ax=await cdp.send('Accessibility.getFullAXTree');const panels=ax.nodes.filter(n=>!n.ignored&&n.role?.value==='tabpanel');assert.equal(panels.length,1);assert.equal(panels[0].name?.value,'Search Leagues');
 return {contract:'manual-activation-v1',records,accessiblePanels:panels.map(p=>({name:p.name?.value,properties:p.properties}))};
}
