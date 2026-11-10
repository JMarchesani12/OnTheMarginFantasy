import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';
import ts from 'typescript';
import * as shared from '../src/utils/leagueMapping.ts';

const source=readFileSync(new URL('../src/screens/League/ManageLeaguePage.tsx',import.meta.url),'utf8');
const file=ts.createSourceFile('ManageLeaguePage.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
function loadManageMapper(normalize=shared.normalizeLeagueSettings) {
  // Execute the real component's lexical parser/mapper, preserving its import binding.
  const selected:ts.Statement[]=[];
  function visit(node:ts.Node) {
    if(ts.isImportDeclaration(node)&&ts.isStringLiteral(node.moduleSpecifier)&&node.moduleSpecifier.text==='../../utils/leagueMapping')selected.push(node);
    if(ts.isVariableDeclaration(node)&&ts.isIdentifier(node.name)&&['normalizeLeagueSettings','mapLeagueFromResponse'].includes(node.name.text)) {
      selected.push(ts.factory.createVariableStatement(undefined,ts.factory.createVariableDeclarationList([node],ts.NodeFlags.Const)));
    }
    ts.forEachChild(node,visit);
  }
  visit(file);
  const printer=ts.createPrinter();
  const code=selected.map(node=>printer.printNode(ts.EmitHint.Unspecified,node,file)).join('\n')+'\nexport {mapLeagueFromResponse};';
  const output=ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const exports:any={};
  runInNewContext(output,{exports,require:(id:string)=>{
    assert.equal(id,'../../utils/leagueMapping');return {...shared,normalizeLeagueSettings:normalize};
  }});
  return exports.mapLeagueFromResponse as (payload:any)=>any;
}
const single={id:10,name:'Fixture league',sport:1,createdAt:'2026-01-01',seasonYear:2026,numPlayers:2};
const plain=(value:unknown)=>JSON.parse(JSON.stringify(value));

test('shared settings parser retains falsy, malformed, primitive and identity semantics',()=>{
  for(const value of [undefined,null,'',false,0,NaN])assert.equal(shared.normalizeLeagueSettings(value),undefined);
  for(const value of ['bad','{'])assert.equal(shared.normalizeLeagueSettings(value),undefined);
  for(const [value,expected] of [['null',null],['false',false],['0',0],['"text"','text'],['[]',[]],['{"draft":{"numberOfRounds":2}}',{draft:{numberOfRounds:2}}]] as const) {
    assert.deepEqual(shared.normalizeLeagueSettings(value),expected);
  }
  for(const value of [{draft:{}},[],true,1])assert.equal(shared.normalizeLeagueSettings(value),value);
});

test('actual Manage mapper preserves League settings fallback and metadata',()=>{
  const map=loadManageMapper();
  for(const settings of [undefined,null,'',false,0,'bad','null']) {
    const input={leagueId:10,settings,currentWeekId:99,memberId:11};
    assert.equal(map(input).settings,settings);
    assert.equal(map({league:input}).currentWeekId,99);
  }
  const settings={draft:{numberOfRounds:2}};
  assert.equal(map({leagueId:10,settings}).settings,settings);
  assert.deepEqual(plain(map({leagueId:10,settings:JSON.stringify(settings)}).settings),settings);
  assert.equal(map({leagueId:10,settings:'false'}).settings,false);
  assert.equal(map({leagueId:10,settings:'0'}).settings,0);
});

test('actual Manage single-league fallback remains distinct from shared current-week mapping',()=>{
  const map=loadManageMapper();
  const defaults={bonuses:{},transactions:{tradeVeto:{enabled:false,requiredVetoCount:0}},draft:{draftType:'SNAKE',selectionTime:60,numberOfRounds:0,timeoutAction:'AUTO-SKIP',graceSeconds:0}};
  for(const settings of [undefined,null,'',false,0,'bad','null']) {
    const input={...single,settings,currentWeekId:99,currentWeekNumber:3,currentWeekStartDate:'start',currentWeekEndDate:'end'};
    const result=map(input);
    assert.deepEqual(plain(result.settings),defaults);
    for(const field of ['currentWeekId','currentWeekNumber','currentWeekStartDate','currentWeekEndDate'])assert.equal(result[field],null);
    assert.equal(shared.mapLeagueFromResponse(input as any).currentWeekId,99);
  }
  for(const [settings,expected] of [['false',false],['0',0],['"text"','text'],['[]',[]]] as const) {
    assert.deepEqual(plain(map({...single,settings}).settings),expected);
  }
});

test('actual Manage mapper uses the existing shared import in both response branches',()=>{
  const calls:unknown[]=[];
  const map=loadManageMapper(value=>{calls.push(value);return shared.normalizeLeagueSettings(value);});
  map({...single,settings:'{"draft":{}}'});
  map({league:{leagueId:10,settings:'bad'}});
  assert.deepEqual(calls,['{"draft":{}}','bad']);
});
