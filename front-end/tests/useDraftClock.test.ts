import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';
const base=Date.parse('2026-11-07T12:00:00Z');const iso=(n:number)=>new Date(n).toISOString();
function fixture() {
  const file=new URL('../src/hooks/useDraftClock.ts',import.meta.url);assert.ok(existsSync(file),'clock hook missing');
  let now=base,index=0,id=0,starts=0,stops=0;const slots:any[]=[],timers=new Map<number,()=>void>();let effects:(()=>void)[]=[];
  class ClockDate extends Date {static now(){return now;}}
  const react={
    useState(initial:any){const i=index++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return [slots[i],(v:any)=>{slots[i]=typeof v==='function'?v(slots[i]):v;}];},
    useMemo(fn:any,deps:any[]){const i=index++,old=slots[i];if(!old||deps.some((v,j)=>!Object.is(v,old.deps[j])))slots[i]={deps,value:fn()};return slots[i].value;},
    useCallback(fn:any,deps:any[]){return react.useMemo(()=>fn,deps);},
    useEffect(fn:any,deps:any[]){const i=index++,old=slots[i];if(!old||deps.some((v,j)=>!Object.is(v,old.deps[j])))effects.push(()=>{old?.cleanup?.();slots[i]={deps,cleanup:fn()};});},
  };
  const exports:any={};runInNewContext(ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,
    {exports,require:(name:string)=>{assert.equal(name,'react');return react;},Date:ClockDate,
      window:{setInterval:(fn:()=>void,delay:number)=>{assert.equal(delay,1000);timers.set(++id,fn);starts++;return id;},clearInterval:(id:number)=>{timers.delete(id);stops++;}}});
  return {render(live:boolean,expiry:string|null){index=0;const value=exports.useDraftClock(live,expiry);const pending=effects;effects=[];pending.forEach(fn=>fn());return value;},
    setNow(ms:number){now=ms;},tick(){for(const fn of [...timers.values()])fn();},status:()=>({active:timers.size,starts,stops}),dispose(){for(const slot of slots)slot?.cleanup?.();}};
}
test('hook owns one live timer and preserves frozen samples until tick',()=>{
  const h=fixture();const expiry=iso(base+65000);assert.equal(h.render(false,expiry).timeLeftLabel,'1:05');assert.equal(h.status().active,0);
  h.render(true,expiry);h.render(true,iso(base+66000));assert.deepEqual(h.status(),{active:1,starts:1,stops:0});
  h.setNow(base+6000);h.tick();assert.equal(h.render(true,expiry).remainingSeconds,59);
  h.render(false,expiry);h.setNow(base+10000);assert.equal(h.render(false,expiry).timeLeftLabel,'0:59');
  h.render(true,expiry);assert.equal(h.status().starts,2);h.tick();assert.equal(h.render(true,expiry).timeLeftLabel,'0:55');
  h.dispose();assert.equal(h.status().active,0);
});
test('hook offset callback is stable, ignores invalid/missing samples, and does not eagerly tick',()=>{
  const h=fixture();let value=h.render(true,iso(base+125000));const callback=value.updateServerNow;
  h.setNow(base+10000);callback(iso(base+40000));value=h.render(true,iso(base+125000));assert.equal(value.timeLeftLabel,'1:35');
  h.tick();value=h.render(true,iso(base+125000));assert.equal(value.timeLeftLabel,'1:25');
  callback('invalid');callback();callback('');assert.equal(h.render(true,iso(base+125000)).timeLeftLabel,'1:25');
  assert.equal(h.render(false,iso(base+125000)).updateServerNow,callback);assert.equal(h.status().starts,1);h.dispose();
});
test('hook preserves null/invalid expiry, floor/zero clamp and minute formatting',()=>{
  const h=fixture();for(const expiry of [null,'','invalid']){const value=h.render(false,expiry);assert.equal(value.remainingSeconds,null);assert.equal(value.timeLeftLabel,null);}
  for(const [delta,label] of [[-1000,'0:00'],[999,'0:00'],[59000,'0:59'],[60000,'1:00'],[3600000,'60:00']] as const)assert.equal(h.render(false,iso(base+delta)).timeLeftLabel,label);
});
