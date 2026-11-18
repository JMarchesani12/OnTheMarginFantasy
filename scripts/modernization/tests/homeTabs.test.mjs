import test from 'node:test';
import assert from 'node:assert/strict';
import {validateHomeTabs} from '../home_tabs_acceptance.mjs';
test('native acceptance rejects old unmoving arrows, missing relations and visible inactive panels',()=>{
 const s={focus:'Search Leagues',tabs:[{id:'a',controls:'p',selected:'true',tabIndex:-1},{id:'b',controls:'q',selected:'false',tabIndex:0}],panels:[{id:'p',label:'a',hidden:false,display:'grid',controls:1},{id:'q',label:'b',hidden:true,display:'none',controls:0}]};
 validateHomeTabs(s,'Search Leagues',0);
 for(const mutate of [x=>x.focus='Your Leagues',x=>x.tabs[1].controls=null,x=>x.panels[1].display='grid',x=>x.panels[1].controls=1,x=>x.tabs[1].selected='true']){const bad=structuredClone(s);mutate(bad);assert.throws(()=>validateHomeTabs(bad,'Search Leagues',0));}
});
