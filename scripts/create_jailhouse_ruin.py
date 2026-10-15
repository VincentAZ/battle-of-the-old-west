"""Separate fictional masonry ruin from the reviewed Jailhouse; preserve sources."""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
from mathutils import Matrix, Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/jailhouse'
OUT = BASE/'ruin-source-v003'
BRIEF = BASE/'ruin-brief-v002.json'
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
points = [o.matrix_world @ v.co for o in original for v in o.data.vertices]
lo = Vector([min(p[k] for p in points) for k in range(3)])
hi = Vector([max(p[k] for p in points) for k in range(3)])
scale = 5.5/max(hi.x-lo.x, hi.y-lo.y)
shift = Vector((-(hi.x+lo.x)/2, -(hi.y+lo.y)/2, -lo.z))
normalize = Matrix.Scale(scale,4) @ Matrix.Translation(shift)
material = original[0].data.materials[0]
kept, removed = [], []

# Divide the source wall boxes at brick-sized intervals before taking away
# upper courses. This makes actual stepped breaks instead of smooth cutaways.
split_original = []
for obj in original:
    if obj.name.startswith('Grey stone water table'):
        # The healthy exterior band used a solid hidden box. Open its centre
        # when the roof is absent; it must not become an invented stone floor
        # or bury the debris resting on the original lower foundation.
        width,depth,height = obj.dimensions
        for dims,offset in [((.14,depth,height),(-width/2+.07,0,0)),
                            ((.14,depth,height),(width/2-.07,0,0)),
                            ((width-.28,.14,height),(0,-depth/2+.07,0)),
                            ((width-.28,.14,height),(0,depth/2-.07,0))]:
            part=obj.copy();part.data=obj.data.copy()
            bpy.context.collection.objects.link(part)
            for v in part.data.vertices:
                for k in range(3):v.co[k]*=dims[k]/obj.dimensions[k]
            part.location += Vector(offset)
            split_original.append(part)
        bpy.data.objects.remove(obj,do_unlink=True)
    elif obj.name.startswith(('Brick long wall','Front brick wall','Reconstructed closed rear wall')):
        axis = 1 if obj.name.startswith('Brick long wall') else 0
        width = obj.dimensions[axis]
        count = max(1,math.ceil(width/.215))
        for i in range(count):
            part = obj.copy();part.data=obj.data.copy()
            bpy.context.collection.objects.link(part)
            for v in part.data.vertices:
                v.co[axis] /= count
            part.location[axis] += -width/2+(i+.5)*width/count
            split_original.append(part)
        bpy.data.objects.remove(obj,do_unlink=True)
    else:
        split_original.append(obj)
original=split_original
bpy.context.view_layer.update()

def top_height(x,y):
    # Disclosed uneven damage profile, not an assertion about an actual fire.
    if y < -2.5:
        nominal = 1.04 if x < 0 else 1.55
    elif y > 2.5:
        nominal = 1.83 if x < 0 else 1.26
    else:
        step = min(5,max(0,int((y+2.7)/.9)))
        nominal = ([1.15,.84,1.62,1.28,1.78,1.45] if x < 0 else
                   [1.54,1.08,.91,1.44,1.91,1.66])[step]
    loss = .075*(1+int(abs(math.sin(x*39+y*31))*4))
    return max(.57,round((nominal-loss)/.075)*.075)

def brick_uv(obj):
    obj.data.update()
    uv = obj.data.uv_layers.active
    for face in obj.data.polygons:
        normal = max(range(3),key=lambda k:abs(face.normal[k]))
        for loop in face.loop_indices:
            p = obj.matrix_world @ obj.data.vertices[obj.data.loops[loop].vertex_index].co
            a = 1 if normal == 0 else 0
            vv = p.z if normal != 2 else p.y+3
            uv.data[loop].uv = ((p[a]+3)/8,1-vv/8)

for obj in original:
    name = obj.name
    keep = name.startswith(('White-painted raised brick foundation','Grey stone water table','Stone doorstep'))
    wall = name.startswith(('Brick long wall','Front brick wall','Reconstructed closed rear wall'))
    stone = name.startswith(('Rough limestone window quoin','Stone window lintel or sill','Door stone jamb'))
    iron = name.startswith(('Iron window bar','Iron bar cross tie'))
    band = name.startswith('Brick corbel band') and obj.location.z < .6
    if wall or stone or iron:
        cap = top_height(obj.location.x,obj.location.y)
        world = [obj.matrix_world @ v.co for v in obj.data.vertices]
        keep = min(p.z for p in world) < cap-.035
        if keep:
            inverse = obj.matrix_world.inverted()
            for vertex,p in zip(obj.data.vertices,world):
                if p.z > cap:
                    p.z = cap
                    vertex.co = inverse @ p
            if wall:
                brick_uv(obj)
    keep |= band
    if keep:
        if name.startswith('White-painted raised brick foundation'):
            # The newly exposed interior face is soot-covered game debris
            # ground, not a pristine white invented prison floor.
            for face in obj.data.polygons:
                if face.normal.z > .9:
                    for loop in face.loop_indices:
                        obj.data.uv_layers.active.data[loop].uv=(.81,.44)
        kept.append(obj)
    else:
        removed.append(name)
        bpy.data.objects.remove(obj,do_unlink=True)

# Reconstructed debris uses only the documented exterior materials. There is
# no invented cell-block interior or unsupported timber framing in this view.
rng = random.Random(1888)
for i in range(220):
    slate = i >= 170
    dims = (.19,.13,.023) if slate else (.18+rng.random()*.06,.10,.065)
    bpy.ops.mesh.primitive_cube_add(size=1,location=(rng.uniform(-1.1,1.1),rng.uniform(-2.35,2.35),.30))
    obj = bpy.context.object
    obj.name = 'Fallen slate fragment' if slate else 'Fallen brick fragment'
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.rotation_euler = (rng.uniform(-.4,.4),rng.uniform(-.3,.3),rng.uniform(-math.pi,math.pi))
    obj.data.materials.append(material)
    bpy.context.view_layer.update()
    bottom = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
    obj.location.z += .27-bottom
    bpy.context.view_layer.update()
    if slate:
        for uv in obj.data.uv_layers.active.data:
            uv.uv = ((1548+uv.uv.x*480)/2048,1-(528+uv.uv.y*472)/2048)
    else:
        brick_uv(obj)
    kept.append(obj)
bpy.context.view_layer.update()
for obj in kept:
    obj.matrix_world = normalize @ obj.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for obj in kept:
    obj.select_set(True)
bpy.context.view_layer.objects.active = kept[0]
bpy.ops.object.join()
ruin = bpy.context.object
ruin.name = 'SM_HoldingRuin_Jailhouse'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
ruin.data.calc_loop_triangles()
triangles = len(ruin.data.loop_triangles)
assert 0 < triangles < 30000
assert len(ruin.data.materials)==1 and not bpy.data.actions
assert not any(o.type=='ARMATURE' for o in bpy.data.objects)
assert all(math.isfinite(c) for v in ruin.data.vertices for c in v.co)
assert all(math.isfinite(c) for uv in ruin.data.uv_layers.active.data for c in uv.uv)
points = [v.co.copy() for v in ruin.data.vertices]
bounds = {'min':[min(p[k] for p in points) for k in range(3)],
          'max':[max(p[k] for p in points) for k in range(3)]}
assert abs(bounds['min'][2]) < .0001
assert bounds['max'][2] < 2.1
assert bounds['max'][0]-bounds['min'][0] <= 3.0
assert bounds['max'][1]-bounds['min'][1] <= 5.5+.0001
# Match the established native ruin material's local soot multiplication.
bsdf = material.node_tree.nodes.get('Principled BSDF')
socket = bsdf.inputs['Base Color']
grain = socket.links[0].from_socket
multiply = material.node_tree.nodes.new('ShaderNodeMixRGB')
multiply.blend_type = 'MULTIPLY'
multiply.inputs[0].default_value = 1
multiply.inputs[2].default_value = (.17,.165,.16,1)
material.node_tree.links.new(grain,multiply.inputs[1])
material.node_tree.links.new(multiply.outputs[0],socket)
bsdf.inputs['Roughness'].default_value = .96
project = OUT/'Jailhouse-Ruin.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
ruin.matrix_world = Matrix.Rotation(math.pi,4,'Z')
fbx = OUT/'SM_HoldingRuin_Jailhouse.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
    bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_tspace=True,
    path_mode='STRIP',embed_textures=False)
ruin.matrix_world = Matrix.Identity(4)
with bpy.data.libraries.load(str(base_project),link=False) as (src,dst):
    dst.objects = ['Holding_Base_Ground','Holding_Base_Tuft']
for obj in dst.objects:
    bpy.context.collection.objects.link(obj)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.resolution_x,scene.render.resolution_y = 1024,768
scene.render.resolution_percentage = 100
scene.world.color = (.25,.30,.36)
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = .7
sun_data = bpy.data.lights.new('Clear warm sunlight','SUN')
sun_data.energy=2.2;sun_data.angle=math.radians(12);sun_data.color=(1,.93,.83)
sun = bpy.data.objects.new('Clear warm sunlight',sun_data);scene.collection.objects.link(sun)
sun.rotation_euler=(math.radians(25),math.radians(-20),math.radians(-30))
for name,pos,power,size in [('Warm daylight',(-5,-6,9),1700,6),('Sky fill',(5,3,8),1200,7)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
    obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj)
    obj.location=pos;obj.rotation_euler=(-obj.location).to_track_quat('-Z','Y').to_euler()
views={}
for name,pos in [('front',(7,-11,7)),('rear',(-7,11,7)),('right',(12,2,6)),('overhead',(0,-.01,15))]:
    data=bpy.data.cameras.new(name);data.type='ORTHO';data.ortho_scale=11
    camera=bpy.data.objects.new('Review_'+name,data);scene.collection.objects.link(camera)
    camera.location=pos;camera.rotation_euler=(Vector((0,0,.5))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera=camera;scene.render.filepath=str(OUT/(name+'.png'))
    bpy.ops.render.render(write_still=True)
    visible=[o for o in scene.objects if o.type=='MESH']
    projected=[world_to_camera_view(scene,camera,o.matrix_world@v.co) for o in visible for v in o.data.vertices]
    assert all(0<=p.x<=1 and 0<=p.y<=1 and p.z>0 for p in projected),name
    views[name]=sha(OUT/(name+'.png'))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Jailhouse-Ruin-Review.blend'))
assert sha(source)==brief['preservation']['sha256']
assert sha(base_project)==brief['preservation']['base_sha256']
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',
    brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,
    normalization=dict(scale=scale,shift=list(shift)),triangles=triangles,bounds_m=bounds,
    removed_parts=removed,project_sha256=sha(project),base_project_sha256=sha(base_project),
    fbx_sha256=sha(fbx),views=views,imported=False,
    limitations=['Fictional game damage, not a historical event','Native conditions and repair restoration pending']),indent=2)+'\n')
print('JAILHOUSE_RUIN_AUTHORED',flush=True)
