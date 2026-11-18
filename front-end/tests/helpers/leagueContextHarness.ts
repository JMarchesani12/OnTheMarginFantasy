import {readFileSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';

export const deferred=()=>{let resolve!:(value?:any)=>void,reject!:(value:any)=>void;const promise=new Promise<any>((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
export const settle=()=>new Promise(resolve=>setImmediate(resolve));
export function fixture() {
  let current:any,index=0,effects:any[]=[],seen=new Set<string>(),tree:any;
  const instances=new Map<string,any>(),cache=new Map<string,any>();
  const depsEqual=(a:any[],b:any[])=>a?.length===b?.length&&a.every((v,i)=>Object.is(v,b[i]));
  const react:any={
    useState(initial:any){const host=current,i=index++;if(!(i in host.slots))host.slots[i]=typeof initial==='function'?initial():initial;return [host.slots[i],(v:any)=>{host.slots[i]=typeof v==='function'?v(host.slots[i]):v;}];},
    useRef(initial:any){const i=index++;return current.slots[i]??(current.slots[i]={current:initial});},
    useMemo(fn:any,deps:any[]){const i=index++,old=current.slots[i];if(!old||!depsEqual(old.deps,deps))current.slots[i]={deps,value:fn()};return current.slots[i].value;},
    useEffect(fn:any,deps:any[]){const host=current,i=index++,old=host.slots[i];if(!old||!depsEqual(old.deps,deps))effects.push(()=>{old?.cleanup?.();host.slots[i]={deps,cleanup:fn(),effect:fn};});},
    createContext(value:any){return {Provider:'provider',value};},useContext(ctx:any){return ctx.value;},
  };
  react.useCallback=(fn:any,deps:any[])=>react.useMemo(()=>fn,deps);
  const jsx={jsx:(type:any,props:any,key:any)=>({type,props,key}),jsxs:(type:any,props:any,key:any)=>({type,props,key})};
  function load(path:string,stubs:Record<string,any>={},globals:any={}) {
    const absolute=resolve(path);if(cache.has(absolute))return cache.get(absolute);
    const exports:any={};cache.set(absolute,exports);
    const source=readFileSync(absolute,'utf8');
    runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText,
      {exports,console,AbortController,Date,Error,...globals,require:(id:string)=>{
        if(id in stubs)return stubs[id];if(id==='react')return react;if(id==='react/jsx-runtime')return jsx;
        if(id.endsWith('.css'))return {};
        if(id.startsWith('.')){const base=resolve(dirname(absolute),id);for(const ext of ['.ts','.tsx']){try {readFileSync(base+ext);return load(base+ext,stubs,globals);}catch(e:any){if(e.code!=='ENOENT')throw e;}}}
        throw new Error('Unexpected dependency '+id);
      }});
    return exports;
  }
  function walk(node:any,path:string):any {
    if(node==null||typeof node!=='object')return node;
    if(Array.isArray(node))return node.map((n,i)=>walk(n,path+'.'+i));
    if(typeof node.type==='function') {
      const id=path+':'+(node.key??'')+':'+node.type.name;seen.add(id);
      let host=instances.get(id);if(!host){host={slots:[],type:node.type};instances.set(id,host);}
      current=host;index=0;return walk(node.type(node.props),id);
    }
    return {...node,props:{...node.props,children:walk(node.props?.children,path+'.c')}};
  }
  function dispose(host:any){for(const slot of host.slots)slot?.cleanup?.();}
  return {load,react,jsx,
    render(Component:any,props:any={},commit=true){effects=[];seen=new Set();tree=walk({type:Component,props},'root');if(commit){for(const [id,host]of instances)if(!seen.has(id)){dispose(host);instances.delete(id);}const pending=effects;effects=[];pending.forEach(fn=>fn());}return tree;},
    replayEffects(){const slots=[...instances.values()].flatMap(host=>host.slots).filter(slot=>typeof slot?.effect==='function');slots.forEach(slot=>slot.cleanup?.());slots.forEach(slot=>{slot.cleanup=slot.effect();});},
    dispose(){instances.forEach(dispose);instances.clear();},get tree(){return tree;},
  };
}
export function nodes(tree:any):any[]{if(tree==null||typeof tree!=='object')return [];if(Array.isArray(tree))return tree.flatMap(nodes);return [tree,...nodes(tree.props?.children)];}
export function text(tree:any):string{if(tree==null||typeof tree==='boolean')return '';if(typeof tree!=='object')return String(tree);if(Array.isArray(tree))return tree.map(text).join('');return text(tree.props?.children);}
