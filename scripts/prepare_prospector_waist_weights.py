"""Weight-only anatomical torso repair; approved coordinates and materials remain untouched."""
import collections,json,math,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'art/western/crew/playable-v001/prospector';r=json.loads((p/'rig-mask-qa/topology-before-repair.json').read_text());s=json.loads((p/'rig-settings.json').read_text())
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def segment_distance(v,a,b):
 d=[b[j]-a[j] for j in range(3)];t=max(0,min(1,sum((v[j]-a[j])*d[j] for j in range(3))/sum(x*x for x in d)));return math.dist(v,[a[j]+t*d[j] for j in range(3)])
arm_segments=[(r['bones'][side+n]['head'],r['bones'][side+n]['tail']) for side in ('Left','Right') for n in ('Arm','ForeArm')]
g=collections.defaultdict(list)
for i,v in enumerate(r['vertices']):g[tuple(round(x,6) for x in v)].append(i)
overrides=[];strengths={}
for (x,y,z),ids in g.items():
 width=.28-(.28-.19)*smooth(1.08,1.22,z)
 strength=smooth(.87,.94,z)*(1-smooth(1.19,1.32,z))*(1-smooth(width,width+.035,abs(x)))
 strength*=smooth(.065,.125,min(segment_distance((x,y,z),a,b) for a,b in arm_segments))
 if strength<1e-6:continue
 anchors=[(.94,'Hips'),(1.08,'Spine'),(1.20,'Spine1'),(1.32,'Spine2')]
 target={'Hips':1.}
 for (a,n),(b,m) in zip(anchors,anchors[1:]):
  if a<=z<=b:
   t=smooth(a,b,z);target={n:1-t,m:t};break
 if z>anchors[-1][0]:target={'Spine2':1.}
 weights=collections.defaultdict(float)
 for i in ids:
  for n,w in r['weights'][i].items():weights[n]+=w*(1-strength)/len(ids)
 for n,w in target.items():weights[n]+=w*strength
 weights=dict(sorted(weights.items(),key=lambda kv:-kv[1])[:4]);total=sum(weights.values());weights={n:w/total for n,w in weights.items() if w>1e-9}
 overrides.append({'vertex_indices':ids,'weights':weights})
 for i in ids:strengths[i]=strength
s['source_geometry_uv_sha256']=r['hash'];s['weight_overrides']=overrides
s['guide_mapping_notes']=[x for x in s['guide_mapping_notes'] if not x.startswith('Waist and vest side repaired')]
s['guide_mapping_notes'].append('Waist and vest side repaired with smooth anatomical Hips/Spine/Spine1/Spine2 blend; removes misplaced arm/leg influence at waist. Blends into original shoulder, sleeve and pelvis weights. All UV duplicates receive identical weights. No motion freeze or geometry changes.')
(p/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n');(p/'rig-mask-qa/repair-strengths.json').write_text(json.dumps(strengths)+'\n');print(len(strengths),'waist/torso vertices')
