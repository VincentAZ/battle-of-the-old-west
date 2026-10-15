"""Audit actual saved plant supports, source contact and scatter clearance."""
from pathlib import Path
import hashlib,json
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];O=R/'art/western/holdings/expansion-review-v001/nitro-works/base-v001';P=O/'nitro-works-Base.blend';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(P),use_scripts=False)
def tree(o):return BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[list(f.vertices)for f in o.data.polygons])
ground=tree(bpy.data.objects['Holding_Base_Ground']);holding=bpy.data.objects['nitro_works_Holding_Review'];building=tree(holding)
roots=[holding.matrix_world@v.co for v in holding.data.vertices if abs((holding.matrix_world@v.co).z)<1e-6];assert len(roots)>=16
for p in roots:
 hit=ground.ray_cast(p+Vector((0,0,.05)),Vector((0,0,-1)),.06)[0];assert hit is not None and abs(hit.z-p.z)<1e-6
reports={}
for name in ('Holding_Base_Sorrel','Holding_Base_Litter'):
 o=bpy.data.objects[name];assert not tree(o).overlap(building),name
 bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world);assert all(e.is_manifold for e in bm.edges);unseen=set(bm.verts);parts=[]
 while unseen:
  v=unseen.pop();vs={v};pending=[v]
  while pending:
   p=pending.pop()
   for ed in p.link_edges:
    q=ed.other_vert(p)
    if q in unseen:unseen.remove(q);vs.add(q);pending.append(q)
  vs=list(vs);index={v:i for i,v in enumerate(vs)};faces={f for v in vs for f in v.link_faces};pts=[v.co.copy()for v in vs];fs=[[index[v]for v in f.verts]for f in faces];low=min(p.z for p in pts);assert low>=-1e-6
  parts.append(dict(points=pts,tree=BVHTree.FromPolygons(pts,fs,epsilon=1e-7),lo=[min(p[k]for p in pts)for k in range(3)],hi=[max(p[k]for p in pts)for k in range(3)]))
 bm.free();rootids=set();edges=[];graph={i:set()for i in range(len(parts))}
 for i,a in enumerate(parts):
  if a['lo'][2]<1e-6:
   low=min(a['points'],key=lambda p:p.z);hit=ground.ray_cast(low+Vector((0,0,.02)),Vector((0,0,-1)),.04)[0];assert hit is not None and abs(hit.z-low.z)<1e-6;rootids.add(i)
  for j,b in enumerate(parts[:i]):
   if any(a['lo'][k]>b['hi'][k]+1e-6 or b['lo'][k]>a['hi'][k]+1e-6 for k in range(3)):continue
   if a['tree'].overlap(b['tree']) or any(b['tree'].find_nearest(p,1e-6)[0]is not None for p in a['points']):graph[i].add(j);graph[j].add(i);edges.append([i,j])
 reached=set(rootids);pending=list(rootids)
 while pending:
  i=pending.pop()
  for j in graph[i]-reached:reached.add(j);pending.append(j)
 assert len(reached)==len(parts),(name,'unsupported',len(parts)-len(reached))
 if name.endswith('Sorrel'):assert len(parts)==256 and len(rootids)==64
 else:assert len(parts)==54 and len(rootids)==54
 reports[name]=dict(closed_solids=len(parts),grounded_roots=len(rootids),supported_solids=len(reached),actual_contacts=len(edges))
r=dict(status='passed',project_sha256=sha(P),holding_ground_contact_vertices=len(roots),scatter_support=reports,scatter_holding_intersections=0,scope='Saved terrain rays, closed plant/litter shells, actual leaf-to-stem support graph and building clearance. Not native fitting or historical approval.')
(O/'contact-validation.json').write_text(json.dumps(r,indent=2)+'\n');(O/'contact-validator-source.py').write_bytes(Path(__file__).read_bytes());print('NITRO_BASE_CONTACTS',r,flush=True)
