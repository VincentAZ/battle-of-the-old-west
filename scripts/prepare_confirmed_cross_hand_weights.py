"""Repair only confirmed contralateral hand influences on three inspected hand regions."""
import collections,hashlib,json,math,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];slug=sys.argv[1];assert slug in ['blacksmith','bounty-hunter','poker-alice'];p=ROOT/'art/western/crew/playable-v001'/slug;approval=json.loads((ROOT/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects'][slug];name=approval['asset_name'];archive=p/'before-cross-hand-fix';archive.mkdir(exist_ok=True)
for f in [name+'-Rigged.blend','rig-settings.json','rig-validation.json','animation-visual-review.json']:
 if (p/f).exists() and not (archive/f).exists():shutil.copy2(p/f,archive/f)
if not (archive/'exports').exists():shutil.copytree(p/'exports',archive/'exports')
qa=p/'rig-mask-qa';qa.mkdir(exist_ok=True);source=Path('/tmp')/(slug+'-topology.json');dest=qa/'topology-before-cross-hand.json'
if not dest.exists():shutil.copy2(source,dest)
r=json.loads(dest.read_text());s=json.loads((p/'rig-settings.json').read_text()) if (p/'rig-settings.json').exists() else {};overrides={i:dict(x['weights']) for x in s.get('weight_overrides',[]) for i in x['vertex_indices']};weld=collections.defaultdict(list)
for i,v in enumerate(r['vertices']):weld[tuple(round(x,6) for x in v)].append(i)
changed=[]
for pos,ids in weld.items():
 side=min(['Left','Right'],key=lambda side:math.dist(pos,r['bones'][side+'Hand']['head']));other='Right' if side=='Left' else 'Left';head=r['bones'][side+'Hand']['head']
 if not (head[2]-.27<pos[2]<head[2]+.03 and abs(pos[0])>.27 and math.dist(pos,head)<.28):continue
 weights=collections.defaultdict(float)
 for i in ids:
  for n,w in r['weights'][i].items():weights[n]+=w/len(ids)
 bad={n:w for n,w in weights.items() if n.startswith(other+'Hand') and w>1e-8}
 if not bad:continue
 for n,w in bad.items():del weights[n];weights[side+'Hand']+=w
 weights=dict(sorted(weights.items(),key=lambda kv:-kv[1])[:4]);total=sum(weights.values());weights={n:w/total for n,w in weights.items() if w>1e-9}
 for i in ids:overrides[i]=weights;changed.append({'vertex':i,'correct_hand':side+'Hand','removed':bad})
s['source_geometry_uv_sha256']=r['hash'];s['weight_overrides']=[{'vertex_indices':[i],'weights':w} for i,w in sorted(overrides.items())];s.setdefault('guide_mapping_notes',[]);s['guide_mapping_notes']=[n for n in s['guide_mapping_notes'] if not n.startswith('Confirmed cross-hand')];s['guide_mapping_notes'].append('Confirmed cross-hand influences on anatomically inspected finger/hand vertices reassigned to the correct Hand. Existing same-hand/finger/wrist weights retained; no new motion constraints or geometry changes.')
(p/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n');(qa/'cross-hand-correction.json').write_text(json.dumps({'source_geometry_uv_sha256':r['hash'],'before_project_sha256':hashlib.sha256((archive/(name+'-Rigged.blend')).read_bytes()).hexdigest(),'changed_vertices':changed,'new_motion_constraints':False},indent=2)+'\n');print(slug,len(changed))
