"""Measure saved canopy openings and source-to-setting wheel contacts."""
import hashlib
import json
import math
from pathlib import Path
from collections import Counter
import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'art/western/holdings/expansion-review-v001/revival-tent'
SOURCE=FOLDER/'local-source-v002'
REVIEW=FOLDER/'review-v002'
BASE=FOLDER/'base-v001'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((REVIEW/'manifest.json').read_text())
authoring=json.loads((SOURCE/'authoring.json').read_text())
assert sha(SOURCE/'RevivalTent.blend')==authoring['project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(SOURCE/'RevivalTent.blend'),use_scripts=False)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
# Reconstruct the documented review normalization from actual source vertices.
rotation=Matrix.Rotation(math.radians(manifest['heading_degrees']),4,'Z')
points=[rotation@(o.matrix_world@v.co) for o in objects for v in o.data.vertices]
lo=Vector([min(p[k] for p in points) for k in range(3)])
hi=Vector([max(p[k] for p in points) for k in range(3)])
scale=manifest['footprint_m']/max(hi.x-lo.x,hi.y-lo.y)
shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z))
normalized=[(p+shift)*scale for p in points]
feet={}
for o in objects:
    if min((o.matrix_world@v.co).z for v in o.data.vertices)>1e-6:continue
    pts=[rotation@(o.matrix_world@v.co) for v in o.data.vertices]
    bottom=min(p.z for p in pts)
    feet[o.name]=[(p+shift)*scale for p in pts if abs(p.z-bottom)<1e-6]
assert len(feet)==86
bpy.ops.wm.open_mainfile(filepath=str(BASE/'revival-tent-Base.blend'),use_scripts=False)
ground=bpy.data.objects['Holding_Base_Ground']
assert all(abs((ground.matrix_world@v.co).z)<1e-7 for v in ground.data.vertices)
tree=BVHTree.FromPolygons([ground.matrix_world@v.co for v in ground.data.vertices],
    [tuple(p.vertices) for p in ground.data.polygons])
contacts={}
for name,pts in feet.items():
    distances=[]
    for p in pts:
        hit=tree.ray_cast(p+Vector((0,0,.1)),Vector((0,0,-1)),.2)[0]
        assert hit is not None and abs(hit.z-p.z)<2e-6,(name,p,hit)
        distances.append(abs(hit.z-p.z))
    contacts[name]=dict(points=len(pts),maximum_gap_m=max(distances))
holding=bpy.data.objects[manifest['mesh_object']]
actual=[holding.matrix_world@v.co for v in holding.data.vertices]
kd=KDTree(len(actual))
for i,p in enumerate(actual):kd.insert(p,i)
kd.balance()
maximum=max(kd.find(p)[2] for p in normalized)
assert maximum<1e-5,maximum
# Reverse direction catches geometry introduced during review import or base creation.
kd=KDTree(len(normalized))
for i,p in enumerate(normalized):kd.insert(p,i)
kd.balance()
reverse=max(kd.find(p)[2] for p in actual)
assert reverse<1e-5,reverse
# Inspect every grass blade as a connected component against the actual ground
# and the unchanged holding, not just scatter centres.
grass=bpy.data.objects['Holding_Base_Tuft']
bm=bmesh.new();bm.from_mesh(grass.data);bm.transform(grass.matrix_world);bm.verts.ensure_lookup_table();bm.verts.index_update()
unseen=set(bm.verts);blade_contacts=[]
holding_tree=BVHTree.FromPolygons(actual,[tuple(p.vertices)for p in holding.data.polygons])
while unseen:
    seed=next(iter(unseen));component={seed};todo=[seed];unseen.remove(seed)
    while todo:
        v=todo.pop()
        for e in v.link_edges:
            w=e.other_vert(v)
            if w in unseen:unseen.remove(w);component.add(w);todo.append(w)
    points=[v.co.copy()for v in component];lowest=min(points,key=lambda p:p.z)
    assert abs(lowest.z)<2e-6,lowest
    hit=tree.ray_cast(lowest+Vector((0,0,.1)),Vector((0,0,-1)),.2)[0]
    assert hit is not None and abs(hit.z-lowest.z)<2e-6,(lowest,hit)
    vertices=list(component);indices={v:i for i,v in enumerate(vertices)}
    faces=list({f for v in component for f in v.link_faces})
    bt=BVHTree.FromPolygons([v.co for v in vertices],[[indices[v]for v in f.verts]for f in faces])
    assert not bt.overlap(holding_tree),'Grass intersects tent'
    blade_contacts.append(dict(root=list(lowest),gap=abs(hit.z-lowest.z)))
bm.free()
assert len(blade_contacts)>=390,len(blade_contacts)
report=dict(status='passed',scope='Saved source-to-base normalized-vertex agreement, all tent root contacts, and every grass blade support/collision; not native terrain fitting',source_project_sha256=sha(SOURCE/'RevivalTent.blend'),review_project_sha256=sha(REVIEW/manifest['project']),base_project_sha256=sha(BASE/'revival-tent-Base.blend'),script_sha256=sha(Path(__file__)),tent_ground_contacts=contacts,grass_blade_contacts=blade_contacts,grass_tent_intersections=0,source_to_review_maximum_vertex_error_m=maximum,review_to_source_maximum_vertex_error_m=reverse,normalized_source_vertices=len(normalized),review_vertices=len(actual))
(BASE/'contact-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('REVIVAL_TENT_CONTACTS_PASSED',len(contacts),len(blade_contacts),maximum,reverse,flush=True)
