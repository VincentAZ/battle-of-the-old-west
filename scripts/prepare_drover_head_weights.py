"""Recover Drover's omitted head/neck with source-space joints and welded smooth weights.

The approved appearance is read-only. Output is rig settings, never mesh edits.
"""
import bpy,json,heapq,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from weather_drifter_review import geometry_hash,sha
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'art/western/crew/playable-v001/drover'
a=json.loads((ROOT/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects']['drover']
source=ROOT/a['path'];assert sha(source)==a['sha256']
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
o=bpy.data.objects['drover_Appearance_Review'];m=o.data;co=[o.matrix_world@v.co for v in m.vertices]
adj=[set() for _ in co]
for e in m.edges:
 u,v=e.vertices;adj[u].add(v);adj[v].add(u)
seen=set();comps=[]
for i in range(len(co)):
 if i in seen:continue
 todo=[i];seen.add(i);component=[]
 while todo:
  u=todo.pop();component.append(u)
  for v in adj[u]-seen:seen.add(v);todo.append(v)
 comps.append(component)
comps.sort(key=len,reverse=True)
# These two complete UV islands were visually checked to contain the hat,
# hair and face; the lower beard straddles another island and is selected below.
assert [len(c) for c in comps[:2]]==[870,829]
head=set(comps[0]+comps[1]);head.update(i for i,c in enumerate(co) if c.z>=1.510 and abs(c.x)<.09 and c.y<-.035)
# Weld only for weight computation, leaving actual vertices/UV seams untouched.
positions={}
for i,c in enumerate(co):positions.setdefault(tuple(round(v,6) for v in c),[]).append(i)
for group in positions.values():
 for i in group:adj[i].update(group)
dist=[float('inf')]*len(co);q=[]
for i in head:dist[i]=0;heapq.heappush(q,(0,i))
while q:
 d,u=heapq.heappop(q)
 if d!=dist[u] or d>.13:continue
 for v in adj[u]:
  nd=d+(co[v]-co[u]).length
  if nd<dist[v]:dist[v]=nd;heapq.heappush(q,(nd,v))
def smooth(a,b,x):
 t=max(0,min(1,(x-a)/(b-a)));return t*t*(3-2*t)
groups={}
for i,d in enumerate(dist):
 if d>=.13:continue
 h=1-smooth(0,.065,d);n=(1-h)*(1-smooth(.045,.13,d));s=1-h-n
 weights={k:round(v,7) for k,v in [('Head',h),('Neck',n),('Spine2',s)] if v>1e-7}
 groups.setdefault(tuple(weights.items()),[]).append(i)
settings={'source_geometry_uv_sha256':geometry_hash(o),'source_project_sha256':a['sha256'],'synthesize_missing_bones':True,'additional_rest_bones':{'Neck':{'head':[0,.025,1.445],'tail':[0,.025,1.54]},'Head':{'head':[0,.025,1.54],'tail':[0,.025,1.71]}},'weight_overrides':[{'vertex_indices':ids,'weights':dict(w)} for w,ids in groups.items()],'anatomy_notes':['Provider omitted both neck and head anatomy; mislabeled Head_* guide bones belong to right fingers.','Local Neck/Head pivots placed against inspected front and side head/neck geometry; no geometry or texture changes.','Hat, hair, face and beard follow Head rigidly. Weld-aware geodesic smoothstep blends down exposed neck to Neck and Spine2 over13cm.','Compatibility toe ends are unweighted; the existing foot bones retain body weights.']}
for side,x in [('Left',.18),('Right',-.18)]:
 settings['additional_rest_bones'][side+'ToeBase']={'head':[x,-.10,.035],'tail':[x,-.155,.035]}
settings['anatomy_notes'].append('Forefoot pivots measured inside approved boots: x±.18,y-.10,z.035m; foot tails align here instead of the provider extrapolation below the ground.')
(p/'rig-settings.json').write_text(json.dumps(settings,indent=2)+'\n')
(p/'head-weight-selection.json').write_text(json.dumps({'source_geometry_uv_sha256':settings['source_geometry_uv_sha256'],'rigid_head_vertices':sorted(i for i,d in enumerate(dist) if d==0),'blend_vertices':[i for i,d in enumerate(dist) if 0<d<.13],'override_vertices':sum(map(len,groups.values()))},indent=2)+'\n')
print('DROVER_HEAD_SETTINGS',len(head),sum(map(len,groups.values())),len(groups),settings['source_geometry_uv_sha256'])
