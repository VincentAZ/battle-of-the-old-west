"""Preserve belt-mounted book and repair adjacent dress weights, without geometry changes."""
import collections,heapq,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'art/western/crew/playable-v001/revival-sister';r=json.loads((p/'rig-mask-qa/topology-before-repair.json').read_text());s=json.loads((p/'rig-settings.json').read_text());vs=r['vertices'];keys=[tuple(round(x,6) for x in v) for v in vs];g=collections.defaultdict(list)
for i,k in enumerate(keys):g[k].append(i)
selected={i for c in [8,35,38,60,180,279] for i in r['components'][c]['indices']};graph=collections.defaultdict(dict)
for f in r['polygons']:
 for i,j in zip(f,f[1:]+f[:1]):
  if keys[i]!=keys[j]:graph[keys[i]][keys[j]]=graph[keys[j]][keys[i]]=math.dist(vs[i],vs[j])
dist={keys[i]:0. for i in selected};heap=[(0.,k) for k in dist];heapq.heapify(heap)
while heap:
 d,k=heapq.heappop(heap)
 if d!=dist[k]:continue
 for q,length in graph[k].items():
  nd=d+length
  if nd<.07 and nd<dist.get(q,100):dist[q]=nd;heapq.heappush(heap,(nd,q))
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
def segment_distance(v,a,b):
 d=[b[j]-a[j] for j in range(3)];t=max(0,min(1,sum((v[j]-a[j])*d[j] for j in range(3))/sum(x*x for x in d)));return math.dist(v,[a[j]+t*d[j] for j in range(3)])
arms=[(r['bones'][side+n]['head'],r['bones'][side+n]['tail']) for side in ('Left','Right') for n in ('Arm','ForeArm')]
skirt={i for c in [50,52,107,160] for i in r['components'][c]['indices']};overrides=[]
for k,ids in g.items():
 targets=[i for i in ids if i not in selected]
 if not targets:continue
 x,y,z=k;width=.215-(.215-.145)*smooth(1.03,1.18,z)
 strength=smooth(.86,.92,z)*(1-smooth(1.12,1.27,z))*(1-smooth(width,width+.03,abs(x)))*smooth(.055,.115,min(segment_distance(k,a,b) for a,b in arms))
 pin=1-smooth(0,.07,dist.get(k,1))
 hand_side=('Left' if x>0 else 'Right') if abs(x)>.22 and .64<z<.87 and not any(i in skirt for i in ids) else None
 cross_hand=hand_side and any(any(n.startswith('Right' if hand_side=='Left' else 'Left') and ('Hand' in n or 'Arm' in n) and w>1e-5 for n,w in r['weights'][i].items()) for i in ids)
 if not strength and not pin and not any(i in skirt for i in ids) and not cross_hand:continue
 weights=collections.defaultdict(float)
 for i in ids:
  for n,w in r['weights'][i].items():
   if any(i in skirt for i in ids) and any(t in n for t in ['Arm','Hand']):n='Hips'
   if cross_hand and n.startswith('Right' if hand_side=='Left' else 'Left') and ('Hand' in n or 'Arm' in n):n=hand_side+'Hand'
   weights[n]+=w/len(ids)
 target={'Hips':1.}
 anchors=[(.91,'Hips'),(1.035,'Spine'),(1.15,'Spine1'),(1.27,'Spine2')]
 for (a,n),(b,m) in zip(anchors,anchors[1:]):
  if a<=z<=b:
   t=smooth(a,b,z);target={n:1-t,m:t};break
 weights={n:w*(1-strength) for n,w in weights.items()}
 for n,w in target.items():weights[n]=weights.get(n,0)+w*strength
 weights={n:w*(1-pin) for n,w in weights.items()};weights['Hips']=weights.get('Hips',0)+pin
 weights=dict(sorted(weights.items(),key=lambda kv:-kv[1])[:4]);total=sum(weights.values());weights={n:w/total for n,w in weights.items() if w>1e-9};overrides.append({'vertex_indices':targets,'weights':weights})
s.update(source_geometry_uv_sha256=r['hash'],rigid_regions=[{'name':'BeltBook','parent':'Hips','vertex_indices':sorted(selected)}],freeze_bones=['BeltBook'],motion_constraints=[{'type':'preserve_bind_local_transform','bones':['BeltBook'],'reason':'The book is strapped at the belt in the approved appearance, so it remains rigid with the hips; arms are free.'}],weight_overrides=overrides)
s['guide_mapping_notes']=[x for x in s['guide_mapping_notes'] if not x.startswith('Belt-mounted book and fused')]
s['guide_mapping_notes'].append('Belt-mounted book and fused cover boundaries preserve shape; 7 cm geodesic boundary blend plus anatomical waist weights. Four inspected dress panels lose stray finger influences; contralateral hand-weight contamination is reassigned to the correct hand. Arm envelopes preserve free sleeve motion. No source geometry/material changes.')
(p/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n');print('book',len(selected),'overrides',sum(len(x['vertex_indices']) for x in overrides))
