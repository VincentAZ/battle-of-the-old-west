"""Author a separate fictional slab-fall damage; preserve reviewed ridge/base."""
import hashlib
import json
import math
import random
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/rockslide-ridge'
OUT = BASE/'damage-source-v001'
BRIEF = BASE/'damage-brief-v001.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
source = BASE/brief['preservation']['source']
base_project = BASE/brief['preservation']['base']
assert sha(source) == brief['preservation']['sha256']
assert sha(base_project) == brief['preservation']['base_sha256']
assert not OUT.exists()
OUT.mkdir()
bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
original = [o for o in bpy.context.scene.objects if o.type == 'MESH']
points = [o.matrix_world@v.co for o in original for v in o.data.vertices]
lo = Vector([min(p[k] for p in points) for k in range(3)])
hi = Vector([max(p[k] for p in points) for k in range(3)])
scale = 6/max(hi.x-lo.x, hi.y-lo.y)
shift = Vector((-(hi.x+lo.x)/2, -(hi.y+lo.y)/2, -lo.z))
normalize = Matrix.Scale(scale, 4)@Matrix.Translation(shift)
material = original[0].data.materials[0]
kept = list(original)
rng = random.Random(18720327)


def fresh_uv(obj):
    mesh = obj.data; mesh.update()
    uv = mesh.uv_layers.active or mesh.uv_layers.new()
    for face in mesh.polygons:
        axis = max(range(3), key=lambda i: abs(face.normal[i]))
        for loop in face.loop_indices:
            p = mesh.vertices[mesh.loops[loop].vertex_index].co
            u = ((p.x if axis != 0 else p.y)+3)/6
            v = p.z/5.5 if axis != 2 else (p.y+3)/6
            uv.data[loop].uv = (.76+.23*u, .01+.98*v)


slab = bpy.data.objects['Supported exfoliation slab']
# Lay the broad sheet on its former front, with a slight broken slope.
centre = sum((v.co for v in slab.data.vertices), Vector())/len(slab.data.vertices)
rotation = Matrix.Rotation(math.radians(83),4,'X')
for v in slab.data.vertices: v.co = rotation@(v.co-centre)
slab.location = (.30,-.65,0)
slab.location.z = -min(v.co.z for v in slab.data.vertices)
slab.name = 'Toppled exfoliation sheet'

for index in range(12):
    x = rng.uniform(-1.55,1.55); y = rng.uniform(-2.1,-.9)
    size = rng.uniform(.09,.22)
    bm = bmesh.new()
    for _ in range(17):
        p = Vector([rng.uniform(-1,1) for _ in range(3)]).normalized()
        bm.verts.new((p.x*size, p.y*size*.85, p.z*size*.7))
    bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
    unused = [v for v in bm.verts if not v.link_faces]
    if unused: bmesh.ops.delete(bm,geom=unused,context='VERTS')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    low = min(v.co.z for v in bm.verts)
    # Pieces embedded in the surviving remnant remain supported. Outer ones
    # sit directly on the ground; overlaps represent a compact rubble pile.
    floor = 0
    for v in bm.verts: v.co += Vector((x,y,floor-low))
    mesh = bpy.data.meshes.new('Fallen granite block'); bm.to_mesh(mesh); bm.free()
    obj = bpy.data.objects.new(f'Fallen granite block {index:02d}', mesh)
    bpy.context.collection.objects.link(obj);mesh.materials.append(material)
    fresh_uv(obj);kept.append(obj)

bpy.context.view_layer.update()
for obj in kept: obj.matrix_world = normalize@obj.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for obj in kept: obj.select_set(True)
bpy.context.view_layer.objects.active = kept[0]
bpy.ops.object.join()
ruin = bpy.context.object; ruin.name = 'SM_HoldingDamaged_RockslideRidge'
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bm = bmesh.new(); bm.from_mesh(ruin.data)
bmesh.ops.triangulate(bm, faces=list(bm.faces))
bm.to_mesh(ruin.data); bm.free()
ruin.data.calc_loop_triangles(); triangles = len(ruin.data.loop_triangles)
coords = [v.co.copy() for v in ruin.data.vertices]
bounds = {'min':[min(p[k] for p in coords) for k in range(3)],
          'max':[max(p[k] for p in coords) for k in range(3)]}
assert 0 < triangles < 30000 and len(ruin.data.materials) == 1
assert abs(bounds['min'][2]) < .0001 and bounds['max'][2] < 5.3
project = OUT/'RockslideRidge-Damaged.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
ruin.matrix_world = Matrix.Rotation(math.pi,4,'Z')
fbx = OUT/'SM_HoldingDamaged_RockslideRidge.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'MESH'},
    apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y',axis_up='Z',
    bake_anim=False, add_leaf_bones=False, mesh_smooth_type='FACE',use_tspace=True,
    path_mode='STRIP', embed_textures=False)
ruin.matrix_world = Matrix.Identity(4)
with bpy.data.libraries.load(str(base_project),link=False) as (src,dst):
    dst.objects = [n for n in src.objects if n.startswith('Holding_Base_')]
for obj in dst.objects: bpy.context.collection.objects.link(obj)
scene = bpy.context.scene; scene.render.engine = 'CYCLES'; scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.threads_mode = 'FIXED'; scene.render.threads = 8
scene.render.resolution_x,scene.render.resolution_y = 1024,768
scene.render.resolution_percentage = 100
if scene.world is None: scene.world = bpy.data.worlds.new('Review daylight')
scene.world.color = (.25,.30,.36)
scene.view_settings.view_transform = 'AgX'; scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = .7
sun_data = bpy.data.lights.new('Clear warm sunlight','SUN'); sun_data.energy = 2.2
sun_data.angle = math.radians(12);sun_data.color = (1,.93,.83)
sun = bpy.data.objects.new('Clear warm sunlight',sun_data);scene.collection.objects.link(sun)
sun.rotation_euler = (math.radians(25),math.radians(-20),math.radians(-30))
for name,pos,power,size in [('Warm daylight',(-5,-6,9),1700,6),('Sky fill',(5,3,8),1200,7)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
    obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj)
    obj.location=pos;obj.rotation_euler=(-obj.location).to_track_quat('-Z','Y').to_euler()
views={}
for name,pos in [('front',(7,-11,7)),('rear',(-7,11,7)),('right',(12,2,6)),('overhead',(0,-.01,15))]:
    data=bpy.data.cameras.new(name);data.type='ORTHO';data.ortho_scale=13
    camera=bpy.data.objects.new('Review_'+name,data);scene.collection.objects.link(camera)
    camera.location=pos;camera.rotation_euler=(Vector((0,0,1.2))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera=camera;scene.render.filepath=str(OUT/(name+'.png'))
    bpy.ops.render.render(write_still=True)
    projected=[world_to_camera_view(scene,camera,obj.matrix_world@v.co)
               for obj in scene.objects if obj.type=='MESH' for v in obj.data.vertices]
    assert all(0<=p.x<=1 and 0<=p.y<=1 and p.z>0 for p in projected),name
    views[name]=sha(OUT/(name+'.png'))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'RockslideRidge-Damaged-Review.blend'))
assert sha(source)==brief['preservation']['sha256']
assert sha(base_project)==brief['preservation']['base_sha256']
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',
    brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,
    normalization=dict(scale=scale,shift=list(shift)),triangles=triangles,bounds_m=bounds,
    project_sha256=sha(project),base_project_sha256=sha(base_project),fbx_sha256=sha(fbx),
    views=views,imported=False,limitations=brief['reconstruction']),indent=2)+'\n')
print('ROCKSLIDE_RIDGE_DAMAGE_AUTHORED',flush=True)
