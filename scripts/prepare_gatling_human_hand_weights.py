"""Remove measured nonlocal hand contamination from human only; carriage remains exact."""
import collections,json,math,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'art/western/crew/playable-v001/gatling-gunner';a=p/'before-human-hand-fix';a.mkdir(exist_ok=True)
for f in ['GatlingGunner-Rigged.blend','rig-settings.json','rig-validation.json','animation-visual-review.json']:
 if (p/f).exists() and not (a/f).exists():shutil.copy2(p/f,a/f)
if not (a/'exports').exists():shutil.copytree(p/'exports',a/'exports')
qa=p/'rig-mask-qa';d=qa/'topology-before-human-hand-fix.json'
if not d.exists():shutil.copy2('/tmp/gatling-rig-topology.json',d)
r=json.loads(d.read_text());s=json.loads((p/'rig-settings.json').read_text());protected={i for q in s['rigid_regions'] for i in q['vertex_indices']};overrides={i:dict(x['weights']) for x in s.get('weight_overrides',[]) for i in x['vertex_indices']};groups=collections.defaultdict(list)
for i,v in enumerate(r['vertices']):groups[tuple(round(x,6) for x in v)].append(i)
changes=[]
for pos,ids in groups.items():
 if any(i in protected for i in ids):continue
 w=collections.defaultdict(float)
 for i in ids:
  for n,x in r['weights'][i].items():w[n]+=x/len(ids)
 bad={n:x for n,x in w.items() if 'Hand' in n and math.dist(pos,r['bones'][('Left' if n.startswith('Left') else 'Right')+'Hand']['head'])>.28}
 if not bad:continue
 for n in bad:del w[n]
 assert sum(w.values())>.001,(ids,pos,bad)
 total=sum(w.values());w={n:x/total for n,x in w.items() if x>1e-9}
 for i in ids:overrides[i]=w;changes.append({'vertex':i,'removed':bad,'retained':w})
# Inspection found remaining hip/leg weights inside the actual palm surfaces.
# Paint complete hand components coherently, with a smooth wrist/forearm transition.
hand_sets={'Left':{i for c in [82,121,216] for i in r['components'][c]['indices']},'Right':{i for c in [99,100,111,322] for i in r['components'][c]['indices']}}
hand_changes=[]
for pos,ids in groups.items():
 for side,selected in hand_sets.items():
  if not any(i in selected for i in ids):continue
  assert not any(i in protected for i in ids)
  wrist=r['bones'][side+'Hand']['head'][2];t=max(0,min(1,(pos[2]-(wrist-.02))/.11));t=t*t*(3-2*t);w={side+'Hand':1-t,side+'ForeArm':t};w={n:x for n,x in w.items() if x>1e-9}
  for i in ids:overrides[i]=w;hand_changes.append(i)
s['weight_overrides']=[{'vertex_indices':[i],'weights':w} for i,w in sorted(overrides.items())];s.setdefault('guide_mapping_notes',[]);s['guide_mapping_notes']=[x for x in s['guide_mapping_notes'] if not x.startswith('Human-only repair')]
s['guide_mapping_notes'].append('Human-only repair removes hand/finger influences over28cm from their corresponding wrist; each affected vertex retains normalized existing local anatomical weights. Inspected hand components receive coherent Hand weights with11cm wrist/forearm transition, removing residual hip/leg contamination. All12918 rigid carriage vertices, corrected source geometry, guide placement and bind constraints remain unchanged.')
(p/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n');(qa/'human-hand-weight-correction.json').write_text(json.dumps({'source_geometry_uv_sha256':r['hash'],'before_project_sha256':hashlib.sha256((a/'GatlingGunner-Rigged.blend').read_bytes()).hexdigest(),'carriage_vertices_untouched':len(protected),'changed_vertices':changes,'new_motion_constraints':False,'coherent_hand_vertices':sorted(set(hand_changes))},indent=2)+'\n');print('human vertices corrected',len(changes))
