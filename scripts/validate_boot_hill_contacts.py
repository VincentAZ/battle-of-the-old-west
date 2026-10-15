"""Read-only saved Boot Hill terrain, grave, marker and grass support checks."""
import hashlib
import json
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

out=Path(sys.argv[sys.argv.index('--')+1]).resolve()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
project=out/'BootHill.blend'
record=json.loads((out/'authoring.json').read_text())
assert sha(project)==record['project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
hill=bpy.data.objects['Low prairie cemetery rise']
points=lambda o:[o.matrix_world@v.co for v in o.data.vertices]
surface=BVHTree.FromPolygons(points(hill),[p.vertices for p in hill.data.polygons])
rows=[]
for obj in objects:
    vertices=points(obj)
    bm=bmesh.new();bm.from_mesh(obj.data);bm.transform(obj.matrix_world)
    centre=sum((v.co for v in bm.verts),Vector())/len(bm.verts)
    for v in bm.verts:v.co-=centre
    bm.normal_update()
    assert all(e.is_manifold for e in bm.edges),obj.name
    volume=bm.calc_volume(signed=True)
    assert volume>0 and all(f.calc_area()>1e-12 for f in bm.faces),obj.name
    bm.free()
    if obj==hill:
        assert abs(min(v.z for v in vertices))<1e-6
        rows.append(dict(name=obj.name,support='ground plane',positive_volume_m3=volume));continue
    if 'crossbar' in obj.name:
        post=bpy.data.objects[obj.name.replace('crossbar','upright')];pv=points(post)
        overlap=[min(max(v[k]for v in vertices),max(v[k]for v in pv))-max(min(v[k]for v in vertices),min(v[k]for v in pv))for k in range(3)]
        assert all(x>0 for x in overlap),(obj.name,overlap)
        rows.append(dict(name=obj.name,support=post.name,overlap_m=overlap,positive_volume_m3=volume));continue
    gaps=[]
    for v in vertices:
        hit,*_=surface.ray_cast(Vector((v.x,v.y,3)),Vector((0,0,-1)))
        assert hit is not None,obj.name
        gaps.append(v.z-hit.z)
    assert min(gaps)<0<max(gaps),(obj.name,min(gaps),max(gaps))
    rows.append(dict(name=obj.name,support=hill.name,minimum_surface_gap_m=min(gaps),maximum_surface_gap_m=max(gaps),positive_volume_m3=volume))
counts=dict(grave_mounds=sum(o.name.startswith('Low earth grave mound')for o in objects),headboards=sum(o.name.startswith('Plain plank headboard')for o in objects),crosses=sum('upright' in o.name for o in objects),grass_blades=sum(o.name.startswith('Rooted short prairie grass')for o in objects))
assert counts==dict(grave_mounds=6,headboards=4,crosses=2,grass_blades=850),counts
assert sha(project)==record['project_sha256']
(out/'contact-validation.json').write_text(json.dumps(dict(status='passed',project_sha256=sha(project),counts=counts,components=len(rows),checks=rows,scope='Saved component closure/outward volume and actual terrain intersection or timber-joint support. Not engineering strength, Boolean-union, native terrain or historical approval.'),indent=2)+'\n')
print('BOOT_HILL_CONTACTS_VALIDATED',counts,flush=True)
