import test from 'node:test';
import assert from 'node:assert/strict';
import {harness} from './helpers/draftPageHarness.ts';
async function setup(){const h=harness();h.render();await h.flush();return h;}
function complete(h:any){h.controllers.at(-1).options.apply({state:{status:'complete'},members:[],picks:[],availableTeams:[]});h.render();h.render();}
const dialog=(h:any)=>h.all().find((n:any)=>n.type==='dialog');
test('completion opens native named dialog once; Close stays in Draft Center and does not reopen on repeated complete',async()=>{const h=await setup();complete(h);assert.ok(dialog(h));assert.equal(dialog(h).props['aria-labelledby'],'draft-complete-title');const close=h.all().find(n=>n.props?.['aria-label']==='Close draft summary');close.props.onClick();h.render();assert.equal(dialog(h),undefined);assert.equal(h.navigations.length,0);complete(h);assert.equal(dialog(h),undefined);h.dispose();});
test('native cancel dismisses in place and replacement context hides previous completion',async()=>{const h=await setup();complete(h);let prevented=false;dialog(h).props.onCancel({preventDefault(){prevented=true;}});h.render();assert.equal(prevented,true);assert.equal(dialog(h),undefined);h.navigate('20');assert.equal(dialog(h),undefined);await h.flush();complete(h);assert.ok(dialog(h));h.account();assert.equal(dialog(h),undefined);h.dispose();});
