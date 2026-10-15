"""Generate reproducible local weight-only repair from inspected approved topology."""
import collections,heapq,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'art/western/crew/playable-v001/jesse-james'
r=json.loads((p/'rig-mask-qa/topology-before-repair.json').read_text())
s=json.loads((p/'rig-settings.json').read_text());selected=set(s['rigid_regions'][0]['vertex_indices'])
verts=r['vertices'];keys=[tuple(round(x,6) for x in v) for v in verts];weld=collections.defaultdict(list)
for i,k in enumerate(keys):weld[k].append(i)
graph=collections.defaultdict(dict)
for face in r['polygons']:
 for i,j in zip(face,face[1:]+face[:1]):
  if keys[i]!=keys[j]:graph[keys[i]][keys[j]]=graph[keys[j]][keys[i]]=math.dist(verts[i],verts[j])
dist={keys[i]:0. for i in selected};heap=[(0.,k) for k in dist];heapq.heapify(heap)
while heap:
 d,k=heapq.heappop(heap)
 if d!=dist[k]:continue
 for q,length in graph[k].items():
  nd=d+length
  if nd<.04 and nd<dist.get(q,100):dist[q]=nd;heapq.heappush(heap,(nd,q))
cloth=set()
overrides=[]
for k,ids in weld.items():
 targets=[i for i in ids if i not in selected]
 if not targets:continue
 blend=max(0,1-dist.get(k,1)/.04);blend=blend*blend*(3-2*blend)
 if blend==0 and not any(i in cloth for i in targets):continue
 weights=collections.defaultdict(float)
 for i in ids:
  for bone,value in r['weights'][i].items():
   if any(j in cloth for j in ids) and any(t in bone for t in ['Hand','Arm','Shoulder']):bone='LeftHand'
   weights[bone]+=value/len(ids)
 weights={bone:value*(1-blend) for bone,value in weights.items()};weights['LeftHand']=weights.get('LeftHand',0)+blend
 weights=dict(sorted(weights.items(),key=lambda kv:-kv[1])[:4]);total=sum(weights.values());weights={k:v/total for k,v in weights.items() if v>1e-9}
 overrides.append({'vertex_indices':targets,'weights':weights})
s['weight_overrides']=overrides
s['guide_mapping_notes'].append('Welded wrist boundary follows LeftHand exactly, with an 4 cm geodesic smooth blend into original forearm weights; original forearm influence retained outside the wrist transition. No geometry edits.')
(p/'rig-settings.json').write_text(json.dumps(s,indent=2)+'\n')
print('Overridden boundary/garment vertices',sum(len(x['vertex_indices']) for x in overrides))
