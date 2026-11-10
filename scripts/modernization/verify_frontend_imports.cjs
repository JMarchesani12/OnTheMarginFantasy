/** Read-only literal-relative TS/TSX graph; no app/env/provider is loaded. */
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const root = path.resolve(__dirname, '../..');
const sourceRoot = path.join(root, 'front-end/src');
const ts = createRequire(path.join(root, 'front-end/package.json'))('typescript');
function filesIn(directory) {
  return fs.readdirSync(directory, {withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name)).flatMap(entry => {
    const file=path.join(directory,entry.name);
    return entry.isDirectory() ? filesIn(file) : /\.tsx?$/.test(entry.name) ? [file] : [];
  });
}
function scan() {
  const files=filesIn(sourceRoot), known=new Set(files);
  const graph=new Map(files.map(file=>[file,new Set()]));
  const unresolved=[];let relativeEdges=0;
  const relative=file=>path.relative(root,file).split(path.sep).join('/');
  function resolve(from,specifier) {
    if (!specifier.startsWith('.')) return;
    const spec=specifier.split('?')[0];
    const extension=path.extname(spec);
    if (extension && !['.ts','.tsx','.js','.jsx','.mjs','.mts'].includes(extension)) return;
    const base=path.resolve(path.dirname(from),spec);
    const candidates=[base,base+'.ts',base+'.tsx',base+'.d.ts',path.join(base,'index.ts'),path.join(base,'index.tsx')];
    if (/\.(?:jsx?|mjs)$/.test(base)) candidates.push(base.replace(/\.(?:jsx?|mjs)$/,'.ts'),base.replace(/\.(?:jsx?|mjs)$/,'.tsx'));
    const found=candidates.find(file=>known.has(file));
    if (!found) unresolved.push({from:relative(from),specifier});
    else {graph.get(from).add(found);relativeEdges++;}
  }
  for (const file of files) {
    const source=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true);
    function visit(node) {
      if ((ts.isImportDeclaration(node)||ts.isExportDeclaration(node)) && node.moduleSpecifier && ts.isStringLiteralLike(node.moduleSpecifier)) resolve(file,node.moduleSpecifier.text);
      if (ts.isCallExpression(node) && node.expression.kind===ts.SyntaxKind.ImportKeyword && node.arguments.length && ts.isStringLiteralLike(node.arguments[0])) resolve(file,node.arguments[0].text);
      ts.forEachChild(node,visit);
    }
    visit(source);
  }
  const active=new Map(),done=new Set(),stack=[],cycles=[];
  function visit(file) {
    if (active.has(file)) {cycles.push([...stack.slice(active.get(file)),file].map(relative));return;}
    if (done.has(file)) return;
    active.set(file,stack.length);stack.push(file);
    for (const target of [...graph.get(file)].sort()) visit(target);
    stack.pop();active.delete(file);done.add(file);
  }
  for (const file of files) visit(file);
  const editor=path.join(sourceRoot,'components/League/BonusesEditor.tsx');
  return {result:unresolved.length||cycles.length?'FAIL':'PASS',files:files.length,literalRelativeEdges:relativeEdges,unresolved,cycles,
    canonicalEditorConsumers:files.filter(file=>graph.get(file).has(editor)).map(relative),
    exclusions:['package/alias imports','computed imports','CSS/assets','package internals']};
}
if (require.main===module) {
  const report=scan();process.stdout.write(JSON.stringify(report,null,2)+'\n');
  if(report.result!=='PASS')process.exitCode=1;
}
module.exports={scan};
