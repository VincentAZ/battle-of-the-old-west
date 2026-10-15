"""Verify actual saved woodland ground contact and cabin/scatter clearance."""
import hashlib,json
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'art/western/holdings/expansion-review-v001/packers-cabin/base-v001'
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
project=p/'packers-cabin-Base.blend'
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
def tree(o):
    return BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[list(f.vertices)for f in o.data.polygons])
ground=bpy.data.objects['Holding_Base_Ground'];g=tree(ground)
log=bpy.data.objects['packers_cabin_Holding_Review'];lt=tree(log)
roots=[log.matrix_world@v.co for v in log.data.vertices if abs((log.matrix_world@v.co).z)<1e-6]
assert len(roots)>=30
for r in roots:
    hit=g.ray_cast(r+Vector((0,0,.05)),Vector((0,0,-1)),.06)[0]
    assert hit is not None and abs(hit.z-r.z)<1e-6
counts={}
for name in ('Holding_Base_Tuft','Holding_Base_Needle','Holding_Base_Rock'):
    o=bpy.data.objects[name];assert not tree(o).overlap(lt),'Scatter intersects log'
    bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world)
    assert all(e.is_manifold for e in bm.edges)
    unseen=set(bm.verts);count=0
    while unseen:
        v=unseen.pop();component={v};todo=[v]
        while todo:
            q=todo.pop()
            for edge in q.link_edges:
                n=edge.other_vert(q)
                if n in unseen:unseen.remove(n);component.add(n);todo.append(n)
        low=min(component,key=lambda v:v.co.z).co
        assert low.z>=-1e-6
        hit=g.ray_cast(low+Vector((0,0,.05)),Vector((0,0,-1)),.06)[0]
        assert hit is not None and abs(hit.z-low.z)<1e-6,(name,tuple(low),hit)
        count+=1
    counts[name]=count;bm.free()
assert counts['Holding_Base_Needle']==40
assert 384<=counts['Holding_Base_Tuft']<=576
assert counts['Holding_Base_Rock']==18
report=dict(status='passed',project_sha256=sha(project),script_sha256=sha(Path(__file__)),cabin_ground_contact_vertices=len(roots),scatter_grounded_components=counts,scatter_cabin_intersections=0,scope='Actual saved terrain ray contacts and scatter/cabin BVH clearance; does not prove native gameplay fitting.')
(p/'contact-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('PACKERS_BASE_CONTACTS',counts,flush=True)
