"""Read back the ruin, unchanged graves, terrain contacts and joined geometry."""
import hashlib,json,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree

out=Path(sys.argv[sys.argv.index('--')+1]).resolve()
base=out.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record=json.loads((out/'authoring.json').read_text())
source=base/'local-source-v001/BootHill.blend'
assert sha(source)==record['source_sha256']
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
def signature(o):
    return ([tuple(o.matrix_world@v.co)for v in o.data.vertices],
            sorted(tuple(sorted(p.vertices))for p in o.data.polygons))
original={name:signature(bpy.data.objects[name])for name in record['preserved_geometry']}
components=out/'BootHill-Ruin-Components.blend'
assert sha(components)==record['components_project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(components),use_scripts=False)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
assert len(objects)==record['component_count']
for name,sig in original.items():assert signature(bpy.data.objects[name])==sig,name
hill=bpy.data.objects['Low prairie cemetery rise']
surface=BVHTree.FromPolygons([hill.matrix_world@v.co for v in hill.data.vertices],[p.vertices for p in hill.data.polygons])
transform=Matrix.Scale(record['normalization']['scale'],4)@Matrix.Translation(Vector(record['normalization']['shift']))
expected=[];rows=[]
for o in objects:
    pts=[o.matrix_world@v.co for v in o.data.vertices]
    expected.extend(tuple(transform@p)for p in pts)
    bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world)
    centre=sum((v.co for v in bm.verts),Vector())/len(bm.verts)
    for v in bm.verts:v.co-=centre
    bm.normal_update();volume=bm.calc_volume(signed=True)
    assert all(e.is_manifold for e in bm.edges)and volume>0,o.name
    assert all(f.calc_area()>1e-12 for f in bm.faces),o.name
    bm.free()
    if o==hill:
        assert abs(min(v.z for v in pts))<1e-6
        rows.append(dict(name=o.name,support='ground plane',closed=True,positive_volume_m3=volume));continue
    gaps=[]
    for p in pts:
        hit,*_=surface.ray_cast(Vector((p.x,p.y,3)),Vector((0,0,-1)))
        assert hit is not None,o.name
        gaps.append(p.z-hit.z)
    assert min(gaps)<0<max(gaps),(o.name,min(gaps),max(gaps))
    rows.append(dict(name=o.name,support=hill.name,closed=True,positive_volume_m3=volume,minimum_surface_gap_m=min(gaps),maximum_surface_gap_m=max(gaps)))
assert len([o for o in objects if o.name.startswith('Charred ')])==6
assert len([o for o in objects if o.name.startswith('Fallen charred')])==6
project=out/'BootHill-Ruin.blend';assert sha(project)==record['project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(meshes)==1
actual=[tuple(meshes[0].matrix_world@v.co)for v in meshes[0].data.vertices]
assert len(actual)==len(expected)
error=max(abs(a-b)for p,q in zip(sorted(actual),sorted(expected))for a,b in zip(p,q));assert error<1e-5,error
assert sha(source)==record['source_sha256']
(out/'support-validation.json').write_text(json.dumps(dict(status='passed',project_sha256=sha(project),components_project_sha256=sha(components),healthy_source_sha256=sha(source),unchanged_graves_and_hill=list(original),maximum_joined_coordinate_error_m=error,components=len(rows),checks=rows,scope='Saved closed outward components, terrain intersections and preserved hill/grave geometry. No native terrain, fire simulation, Boolean overlap or structural-strength claim.'),indent=2)+'\n')
print('BOOT_HILL_RUIN_SUPPORT_VALIDATED',len(rows),flush=True)
