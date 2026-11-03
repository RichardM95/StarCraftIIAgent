import {Parser, TypeChecker, bindSourceFile, getLineAndCharacterOfPosition, SyntaxKind} from './upstream/index.js';
import fs from 'node:fs';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const documents=new Map(); const qualifiedDocuments=new Map();
const host={documents,qualifiedDocuments,resolveGlobalSymbol(name:string){
  for(const sf of documents.values()) {const s=sf.symbol?.members?.get(name);if(s)return s;}
}};
const parser=new Parser();
for(const [name,text] of Object.entries(input.files)) {
  const sf=parser.parseFile(name,text as string); documents.set(name,sf);
  qualifiedDocuments.set(name.toLowerCase().replace(/\.galaxy$/,''),new Map([[name,sf]]));
}
const diagnostics:any[]=[];
function add(d:any){
  const pos=d.file && d.start!==undefined ? getLineAndCharacterOfPosition(d.file,d.start):{line:0,character:0};
  diagnostics.push({file:d.file?.fileName,line:pos.line+1,column:pos.character+1,
    severity:d.category===1?'error':d.category===2?'warning':'hint',code:d.code,message:d.messageText});
}
// Reject include cycles explicitly; upstream recursion suppresses repeated files.
const visiting=new Set();const visited=new Set();
function cycle(name:string){
 if(visiting.has(name))throw Error('include cycle: '+name);
 if(visited.has(name))return;
 visiting.add(name);
 for(const statement of documents.get(name).statements){
  if(statement.kind!==SyntaxKind.IncludeStatement)continue;
  const key=(statement.path.value.replace(/\\/g,'/').replace(/\.galaxy$/i,'')+'.galaxy').toLowerCase();
  const target=Object.keys(input.files).find(x=>x.toLowerCase()===key);
  if(target)cycle(target);
 }
 visiting.delete(name);visited.add(name);
}
try{cycle(input.entry);}catch(e){diagnostics.push({severity:'error',code:'include_cycle',message:String(e),file:input.entry,line:1,column:1});}
// Only bind the entry's include closure. Unrelated MapScript files must not
// introduce symbols, duplicate declarations or parser errors into this build.
for(const name of [...documents.keys()])if(!visited.has(name)&&!visiting.has(name))documents.delete(name);
for(const sf of documents.values()) {sf.parseDiagnostics.forEach(add);bindSourceFile(sf,host);}
const entry=documents.get(input.entry);
if(!entry)throw Error('entry missing');
const checked=new TypeChecker(host).checkSourceFileRecursively(entry);
for(const ds of checked.diagnostics.values())ds.forEach(add);
process.stdout.write(JSON.stringify({diagnostics,files:[...checked.sourceFiles.keys()],complete:true}));
