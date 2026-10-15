"""Read back Gallows solids, twelve treads, roof clearance and rail supports."""
import bpy,bmesh,json,hashlib,sys
from pathlib import Path
from math import isfinite
from mathutils import Vector
from mathutils.bvhtree import BVHTree
out=Path(sys.argv[sys.argv.index('--')+1]).resolve()
source=out/'Gallows.blend'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=sha(source)
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
rows=[];bad=[]
for obj in objects:
 bm=bmesh.new();bm.from_mesh(obj.data)
 row=dict(name=obj.name,nonmanifold=sum(not e.is_manifold for e in bm.edges),volume=bm.calc_volume(signed=True),minimum_face_area=min(f.calc_area() for f in bm.faces),finite_uv=all(isfinite(x) and -1e-6<=x<=1.000001 for item in obj.data.uv_layers.active.data for x in item.uv))
 if row['nonmanifold'] or row['volume']<=1e-12 or row['minimum_face_area']<=1e-12 or not row['finite_uv']:bad.append(row)
 rows.append(row);bm.free()
assert not bad,bad[:3]
assert len([o for o in objects if o.name.startswith('Stair_tread_')])==12
assert not bpy.data.actions and not any(o.type=='ARMATURE' for o in bpy.data.objects)
# Measure actual transformed vertices against the roof's lower plane.
clearances=[]
for obj in objects:
 if obj.name.startswith(('Upper_triangular_brace','Upper_centre_block')):
  for v in obj.data.vertices:
   p=obj.matrix_world@v.co
   clearances.append(6-.4*(p.y+2.30)-.055/2*(1+.4**2)**.5-p.z)
assert min(clearances)>0,min(clearances)
rails=[o for o in objects if o.name.startswith('Stair_handrail')]
contacts=[]
for post in [o for o in objects if o.name.startswith('Stair_rail_post')]:
 rail=min(rails,key=lambda o:abs(o.location.x-post.location.x))
 verts=[rail.matrix_world@v.co for v in rail.data.vertices]
 tree=BVHTree.FromPolygons(verts,[list(p.vertices) for p in rail.data.polygons])
 origin=post.matrix_world@Vector((0,0,0))
 hit,normal,index,distance=tree.ray_cast(origin,Vector((0,0,1)),1.)
 post_top=max((post.matrix_world@v.co).z for v in post.data.vertices)
 assert hit is not None and hit.z<=post_top+1e-5,(post.name,hit,post_top)
 contacts.append(dict(post=post.name,handrail=rail.name,overlap_m=post_top-hit.z))
assert sha(source)==before
report=dict(ok=True,source_sha256=before,auditor_sha256=sha(Path(__file__)),solids=rows,objects=len(rows),stair_treads=12,minimum_brace_roof_clearance_m=min(clearances),handrail_contacts=contacts,limitations='Closed component solids; intentional joinery overlaps. Roof and stair supports checked; not a structural-engineering or collision certification. Historical and visual review separate.')
(out/'mesh-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print('GALLOWS_SOURCE_VALIDATED',len(rows),'solids',min(clearances),'roof clearance',flush=True)
