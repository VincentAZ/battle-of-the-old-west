"""Verify actual saved town ground contact and hall/scatter clearance."""
import hashlib,json
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'art/western/holdings/expansion-review-v001/vigilance-committee/base-v001'
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
project=p/'vigilance-committee-Base.blend'
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
def tree(o):
    return BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[list(f.vertices)for f in o.data.polygons])
ground=bpy.data.objects['Holding_Base_Ground'];g=tree(ground)
hall=bpy.data.objects['vigilance_committee_Holding_Review'];lt=tree(hall)
roots=[hall.matrix_world@v.co for v in hall.data.vertices if abs((hall.matrix_world@v.co).z)<1e-6]
assert len(roots)>=4
for r in roots:
    hit=g.ray_cast(r+Vector((0,0,.05)),Vector((0,0,-1)),.06)[0]
    assert hit is not None and abs(hit.z-r.z)<1e-6
counts={}
for name in ('Holding_Base_Tuft','Holding_Base_Rock'):
    o=bpy.data.objects[name];assert not tree(o).overlap(lt),'Scatter intersects hall'
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
assert 288<=counts['Holding_Base_Tuft']<=432
assert counts['Holding_Base_Rock']==12
report=dict(status='passed',project_sha256=sha(project),script_sha256=sha(Path(__file__)),holding_ground_contact_vertices=len(roots),scatter_grounded_components=counts,scatter_holding_intersections=0,scope='Actual saved terrain ray contacts and scatter/hall BVH clearance; does not prove native gameplay fitting.')
(p/'contact-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('VIGILANCE_BASE_CONTACTS',counts,flush=True)
