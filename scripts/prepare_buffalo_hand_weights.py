"""Correct inspected right-hand and right-trouser contamination separately."""
import collections,json,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'art/western/crew/playable-v001/buffalo-soldier-veteran';name='BuffaloSoldierVeteran';a=p/'before-hand-weight-fix';a.mkdir(exist_ok=True)
for f in [name+'-Rigged.blend','rig-settings.json','rig-validation.json','animation-visual-review.json']:
 if (p/f).exists() and not (a/f).exists():shutil.copy2(p/f,a/f)
if not (a/'exports').exists():shutil.copytree(p/'exports',a/'exports')
qa=p/'rig-mask-qa';qa.mkdir(exist_ok=True);d=qa/'topology-before-hand-fix.json'
if not d.exists():shutil.copy2('/tmp/buffalo-soldier-veteran-topology.json',d)
r=json.loads(d.read_text());s=json.loads((p/'rig-settings.json').read_text()) if (p/'rig-settings.json').exists() else {};overrides={i:dict(x['weights']) for x in s.get('weight_overrides',[]) for i in x['vertex_indices']};cloth={i for c in [2,19] for i in r['components'][c]['indices']};hand={i for c in [36,47] for i in r['components'][c]['indices']};groups=collections.defaultdict(list)
for i,v in enumerate(r['vertices']):groups[tuple(round(x,6) for x in v)].append(i)
changed=[]
for pos,ids in groups.items():
 kind='trousers' if any(i in cloth for i in ids) else 'right_hand' if any(i in hand for i in ids) else None
 if not kind:continue
 w=collections.defaultdict(float)
 for i in ids:
  for n,x in r['weights'][i].items():w[n]+=x/len(ids)
 bad={n:x for n,x in w.items() if ('Hand' in n or 'Arm' in n) and (kind=='trousers' or n.startswith('Left'))}
 if not bad:continue
 for n,x in bad.items():del w[n]
 if kind=='right_hand':w['RightHand']+=sum(bad.values())
 if not sum(w.values()):w={'RightUpLeg':1.}
 total=sum(w.values());w={n:x/total for n,x in w.items() if x>1e-9}
 for i in ids:overrides[i]=w;changed.append({'vertex':i,'kind':kind,'removed':bad})
s['source_geometry_uv_sha256']=r['hash'];s['weight_overrides']=[{'vertex_indices':[i],'weights':w} for i,w in sorted(overrides.items())];s.setdefault('guide_mapping_notes',[]).append('Inspected right-hand components36/47 lose contralateral left-hand weights; right trouser panels2/19 lose all hand influences and retain normalized original leg/hip weights. Geometry and animation freedom unchanged.')
(p/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n');(qa/'hand-weight-correction.json').write_text(json.dumps({'source_geometry_uv_sha256':r['hash'],'before_project_sha256':hashlib.sha256((a/(name+'-Rigged.blend')).read_bytes()).hexdigest(),'changes':changed},indent=2)+'\n');print(collections.Counter(x['kind'] for x in changed))
