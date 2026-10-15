"""Measure saved canopy openings and source-to-setting wheel contacts."""
import hashlib
import json
import math
from pathlib import Path
from collections import Counter
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'art/western/holdings/expansion-review-v001/wagon-fort'
SOURCE=FOLDER/'local-source-v004'
REVIEW=FOLDER/'review-v002'
BASE=FOLDER/'base-v004'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((REVIEW/'manifest.json').read_text())
authoring=json.loads((SOURCE/'authoring.json').read_text())
assert sha(SOURCE/'WagonFort.blend')==authoring['project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(SOURCE/'WagonFort.blend'),use_scripts=False)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
trees={o.name:BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],
      [tuple(p.vertices) for p in o.data.polygons]) for o in objects}
openings=[]
for i in range(8):
    theta=i*math.tau/9
    transform=Matrix.Translation((6.7*math.cos(theta),6.7*math.sin(theta),0))@Matrix.Rotation(theta,4,'Z')
    direction=transform.to_3x3()@Vector((0,1,0))
    own=[o for o in objects if o.get('wagon_index')==i]
    for x in (-.15,0,.15):
        for z in (1.78,1.96,2.14):
            start=transform@Vector((x,-1.60,z))
            hits=[o.name for o in own if trees[o.name].ray_cast(start,direction,3.20)[0] is not None]
            assert not hits,(i,x,z,hits)
            openings.append(dict(wagon=i+1,x=x,z=z,clear_length=3.20))
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
    if 'Iron wheel tire' not in o.name and not o.name.startswith('Entrance slack chain'):continue
    pts=[rotation@(o.matrix_world@v.co) for v in o.data.vertices]
    bottom=min(p.z for p in pts)
    feet[o.name]=[(p+shift)*scale for p in pts if abs(p.z-bottom)<1e-6]
assert len(feet)==37
bpy.ops.wm.open_mainfile(filepath=str(BASE/'wagon-fort-Base.blend'),use_scripts=False)
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
report=dict(status='passed',scope='Saved source interior clearance, bidirectional normalized-vertex agreement, and actual base ray contacts; not native terrain fitting',
    source_project_sha256=sha(SOURCE/'WagonFort.blend'),
    review_project_sha256=sha(REVIEW/manifest['project']),
    base_project_sha256=sha(BASE/'wagon-fort-Base.blend'),
    script_sha256=sha(Path(__file__)),canopy_clearance_rays=openings,
    wheel_and_slack_chain_contacts=contacts,
    source_to_review_maximum_vertex_error_m=maximum,
    review_to_source_maximum_vertex_error_m=reverse,
    normalized_source_vertices=len(normalized),review_vertices=len(actual))
(BASE/'contact-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('WAGON_FORT_CONTACTS_PASSED',len(openings),len(contacts),maximum,reverse,flush=True)
