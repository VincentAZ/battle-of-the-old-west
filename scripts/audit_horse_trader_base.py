"""Measure saved grass-blade contact against the actual Horse Trader terrain."""
import hashlib,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

folder=Path(sys.argv[sys.argv.index('--')+1]).resolve()
project=folder/'horse-trader-Base.blend'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
ground=bpy.data.objects['Holding_Base_Ground']
tree=BVHTree.FromPolygons([ground.matrix_world@v.co for v in ground.data.vertices],
                          [list(p.vertices) for p in ground.data.polygons])
grass=bpy.data.objects['Holding_Base_Tuft'];mesh=grass.data
neighbours={i:set() for i in range(len(mesh.vertices))}
for edge in mesh.edges:
    a,b=edge.vertices;neighbours[a].add(b);neighbours[b].add(a)
unseen=set(neighbours);rows=[]
while unseen:
    todo=[unseen.pop()];component=[]
    while todo:
        i=todo.pop();component.append(i)
        for j in neighbours[i]&unseen:unseen.remove(j);todo.append(j)
    points=[grass.matrix_world@mesh.vertices[i].co for i in component]
    distances=[]
    for p in points:
        hit=tree.ray_cast(Vector((p.x,p.y,20)),Vector((0,0,-1)),40)[0]
        assert hit is not None
        distances.append(p.z-hit.z)
    rows.append(dict(component=len(rows),vertices=component,
                     min_clearance_m=min(distances),max_clearance_m=max(distances),
                     crosses_surface=min(distances)<=1e-5 and max(distances)>0))
report=dict(status='passed' if all(r['crosses_surface'] for r in rows) else 'failed',
    project_sha256=sha(project),scope='Individual connected grass blades measured vertically against actual saved ground triangles',
    components=len(rows),floating=sum(r['min_clearance_m']>1e-5 for r in rows),
    wholly_buried=sum(r['max_clearance_m']<=0 for r in rows),blades=rows)
(folder/'grass-contact-audit.json').write_text(json.dumps(report,indent=2)+'\n')
(folder/'grass-auditor-source.py').write_bytes(Path(__file__).read_bytes())
print('HORSE_TRADER_GRASS_CONTACT',report['status'],report['components'],report['floating'],report['wholly_buried'],flush=True)
assert report['status']=='passed'
