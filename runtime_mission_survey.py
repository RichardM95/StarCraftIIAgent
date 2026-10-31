from pathlib import Path
import json,hashlib,re,xml.etree.ElementTree as E
root=Path('C:/Users/43732/.codex/visualizations/2026/10/24/01a16c07-c304-7e40-88f7-474e34da920d/自由之翼羁绊战线')
sources={'忠诚之翼':Path('E:/Program Files (x86)/StarCraft II/Maps/Campaign'),'起义狂潮':Path('E:/夸克网盘/起义狂潮3.0')}
out={}
for label,folder in sources.items():
 out[label]={}
 for p in sorted(folder.glob('*.SC2Map')):
  if not p.is_dir():continue
  d={'path':str(p),'components':{},'trigger_names':[]}
  for name in ['DocumentInfo','Triggers','Objects','Regions','MapInfo','t3HeightMap','t3Terrain.xml','MapScript.galaxy']:
   f=p/name
   if not f.exists():continue
   b=f.read_bytes();d['components'][name]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
   if name=='DocumentInfo':d['dependencies']=re.findall(r'<Value>(.*?)</Value>',b.decode('utf-8-sig',errors='replace'))
   if name=='Triggers':
    try:
     t=E.fromstring(b);d['trigger_elements']=len(list(t.iter()));d['trigger_names']=[x.text for x in t.iter('Identifier') if x.text]
    except E.ParseError:d['trigger_parse']='failed'
   if name=='MapScript.galaxy':
    s=b.decode('utf-8-sig',errors='replace');d['victory_symbols']=sorted(set(re.findall(r'\b\w*(?:Victory|Defeat|WinGame|MissionComplete)\w*\b',s)))[:35]
    d['bank_literals']=sorted(set(re.findall(r'Bank\w*\([^\n]{0,180}',s)))[:12]
  out[label][p.stem]=d
target=root/'runtime/research/map-selection-evidence.json';target.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:len(v) for k,v in out.items()},ensure_ascii=False))
print('海文标识', {k:{n:v['victory_symbols'] for n,v in maps.items() if n.startswith('thanson03')} for k,maps in out.items()})
