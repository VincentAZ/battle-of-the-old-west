"""Reopen the saved plain trunk and verify its topology, support and UV map."""
import hashlib,json,math,sys
from pathlib import Path
import bpy,bmesh
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1]
folder=Path(sys.argv[sys.argv.index('--')+1]).resolve()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((folder/'authoring.json').read_text());project=folder/'TimberRam.blend'
assert sha(project)==a['project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(objects)==1
assert not bpy.data.actions and not any(o.type=='ARMATURE' for o in bpy.data.objects)
o=objects[0];m=o.data;bm=bmesh.new();bm.from_mesh(m);bm.transform(o.matrix_world);bm.normal_update()
assert all(e.is_manifold for e in bm.edges)
assert all(f.calc_area()>1e-12 for f in bm.faces)
assert bm.calc_volume(signed=True)>0
assert all(math.isfinite(c)for v in bm.verts for c in v.co)
unseen=set(bm.verts);todo=[next(iter(unseen))];unseen.remove(todo[0])
while todo:
 v=todo.pop()
 for e in v.link_edges:
  n=e.other_vert(v)
  if n in unseen:unseen.remove(n);todo.append(n)
assert not unseen,'Disconnected trunk'
points=[v.co.copy()for v in bm.verts]
assert min(p.z for p in points)>=-1e-7
roots=[p for p in points if abs(p.z)<1e-7]
assert len(roots)>150 and max(p.y for p in roots)-min(p.y for p in roots)>4.19
bm.verts.index_update();faces=[[v.index for v in f.verts]for f in bm.faces]
tree=BVHTree.FromPolygons(points,faces)
crossings=[]
for aidx,bidx in tree.overlap(tree):
 if aidx>=bidx or set(faces[aidx])&set(faces[bidx]):continue
 crossings.append([aidx,bidx])
assert not crossings,crossings[:20]
volume=bm.calc_volume(signed=True);bm.free()
assert len(m.materials)==1 and m.uv_layers
assert all(math.isfinite(c)and 0<=c<=1 for v in m.uv_layers.active.data for c in v.uv)
images=[n.image for n in m.materials[0].node_tree.nodes if n.type=='TEX_IMAGE']
assert len(images)==1 and images[0].packed_file and tuple(images[0].size)==(2048,2048)
m.calc_loop_triangles();assert len(m.loop_triangles)==a['triangles']<=30000
d={'status':'passed','scope':'Saved closed trunk, one connected component, nonadjacent face intersections, grounded lower strip and packed texture; not engineering strength or user approval','project_sha256':sha(project),'script_sha256':sha(Path(__file__)),'closed_positive_solids':1,'volume_m3':volume,'triangles':len(m.loop_triangles),'ground_contact_vertices':len(roots),'ground_contact_length_m':max(p.y for p in roots)-min(p.y for p in roots),'below_ground':False,'nonadjacent_face_intersections':crossings,'materials':1,'packed_atlas':[2048,2048],'rigs':0,'animations':0}
(folder/'geometry-audit.json').write_text(json.dumps(d,indent=2)+'\n');print('TIMBER_RAM_SOURCE_AUDIT',len(m.loop_triangles),len(roots),flush=True)
