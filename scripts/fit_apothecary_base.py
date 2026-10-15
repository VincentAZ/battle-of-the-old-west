"""Versioned local correction: bed the Apothecary pebbles in its actual ground."""
from pathlib import Path
import hashlib,json
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];B=R/'art/western/holdings/expansion-review-v001/apothecary'
SRC=B/'base-v001';OUT=B/'base-v002'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not OUT.exists();OUT.mkdir()
evidence=json.loads((B/'base-evidence-v002.json').read_text());assert evidence['pre_modeling_review']['completed']
bpy.ops.wm.open_mainfile(filepath=str(SRC/'apothecary-Base.blend'),use_scripts=False)
ground=bpy.data.objects['Holding_Base_Ground'];pebbles=bpy.data.objects['Holding_Base_Stone']
tree=BVHTree.FromPolygons([ground.matrix_world@v.co for v in ground.data.vertices],[list(p.vertices) for p in ground.data.polygons],all_triangles=False)
mesh=pebbles.data;neighbours={i:set() for i in range(len(mesh.vertices))}
for edge in mesh.edges:
 a,b=edge.vertices;neighbours[a].add(b);neighbours[b].add(a)
unseen=set(neighbours);records=[]
while unseen:
 todo=[unseen.pop()];component=[]
 while todo:
  i=todo.pop();component.append(i)
  for j in neighbours[i]&unseen:unseen.remove(j);todo.append(j)
 points=[pebbles.matrix_world@mesh.vertices[i].co for i in component]
 centre=sum(points,Vector())/len(points)
 hit,_,_,_=tree.ray_cast(Vector((centre.x,centre.y,100)),Vector((0,0,-1)),200)
 assert hit is not None
 dz=hit.z-centre.z
 delta=pebbles.matrix_world.inverted().to_3x3()@Vector((0,0,dz))
 for i in component:mesh.vertices[i].co+=delta
 points=[pebbles.matrix_world@mesh.vertices[i].co for i in component]
 lo=min(p.z for p in points);hi=max(p.z for p in points)
 assert lo<hit.z<hi
 records.append(dict(component=len(records),vertices=len(component),ground_z_m=hit.z,centre_shift_m=dz,min_z_m=lo,max_z_m=hi,partly_buried=True,visible_above_surface=True))
assert len(records)==8
mesh.update()
record=json.loads((SRC/'base.json').read_text());record['source_base_project_sha256']=sha(SRC/'apothecary-Base.blend');record['scatter_surface_fit']=records;record['source_script_sha256']=sha(Path(__file__))
(OUT/'base.json').write_text(json.dumps(record,indent=2)+'\n')
scene=bpy.context.scene
for name in ('three-quarter','game-camera','overhead'):
 scene.camera=bpy.data.objects['Review_'+name];scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'apothecary-Base.blend'))
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'surface-fit.json').write_text(json.dumps(dict(status='passed',project_sha256=sha(OUT/'apothecary-Base.blend'),evidence_sha256=sha(B/'base-evidence-v002.json'),all_eight_pebbles_cross_ground_surface=True,pebbles=records),indent=2)+'\n')
print('APOTHECARY_BASE_SURFACE_FIT',len(records),flush=True)
