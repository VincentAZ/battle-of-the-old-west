"""Static fictional canvas/timber ruin; never modify the healthy tent or base."""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
from mathutils import Matrix, Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/army-surgeons-tent'
OUT = BASE/'ruin-source-v004'
BRIEF = BASE/'ruin-brief-v001.json'
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
scale = 5/max(hi.x-lo.x, hi.y-lo.y)
shift = Vector((-(hi.x+lo.x)/2, -(hi.y+lo.y)/2, -lo.z))
normalize = Matrix.Scale(scale, 4)@Matrix.Translation(shift)
material = original[0].data.materials[0]
kept, removed = [], []
for obj in original:
    if obj.name.startswith(('Wood guy peg', 'Ridge guy peg')):
        kept.append(obj)
    else:
        removed.append(obj.name)
        bpy.data.objects.remove(obj, do_unlink=True)


def finish(obj):
    obj.data.materials.clear()
    obj.data.materials.append(material)
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name='UVMap')
    # The warm dark timber area of the preserved atlas, further darkened by
    # the existing ruin material. Canvas remnants deliberately lose white.
    for item in uv.data:
        item.uv = (.82+(item.uv.x % 1)*.08, .72+(item.uv.y % 1)*.08)
    kept.append(obj)


def rod(name, a, b, radius):
    a, b = Vector(a), Vector(b)
    axis = b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=radius,
                                       depth=axis.length, location=(a+b)/2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = axis.to_track_quat('Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    bottom = min((obj.matrix_world@v.co).z for v in obj.data.vertices)
    obj.location.z += max(0, -bottom)
    finish(obj)


# A few broken poles remain identifiable; no unsupported high roof survives.
rod('Front upright stump', (0, -2.18, 0), (.035, -2.18, .51), .048)
rod('Rear upright stump', (0, 2.18, 0), (-.06, 2.16, .37), .048)
for i, (a, b, radius) in enumerate([
    ((-.80, -1.82, .085), (.62, .14, .15), .048),
    ((.46, .85, .10), (-.98, 1.95, .09), .048),
    ((-1.12, -1.28, .085), (-.71, .84, .11), .055),
    ((.67, -.91, .08), (1.35, .83, .10), .055),
    ((-.44, .38, .09), (.30, 1.73, .08), .048),
]):
    rod('Fallen charred pole %02d' % i, a, b, radius)

rng = random.Random(1864)
for index, (cx, cy, width, length) in enumerate([
    (-.79, -1.05, 1.30, 1.65), (.68, -.63, 1.37, 1.70),
    (-.54, 1.10, 1.55, 1.35), (.73, 1.43, 1.15, .93),
    (.28, -1.72, 1.08, .66), (-1.19, .11, .64, 1.1),
]):
    nu, nv = 16, 19
    vertices, faces = [], []
    phase = rng.uniform(0, math.tau)
    for j in range(nv+1):
        v = j/nv
        for i in range(nu+1):
            u = i/nu
            x = cx+(u-.5)*width+.032*math.sin(v*21+phase)
            y = cy+(v-.5)*length+.025*math.sin(u*19+phase)
            z = .067+.11*math.sin(u*math.pi)**2+.075*math.sin(v*math.pi*3+phase)**2
            vertices.append((x, y, z))
    for j in range(nv):
        for i in range(nu):
            # Torn, partly consumed edges and internal holes, not an intact
            # tent merely compressed vertically.
            boundary = i in (0, nu-1) or j in (0, nv-1)
            hole = math.sin(i*.72+phase)*math.cos(j*.63-phase) > .57
            if hole or (boundary and rng.random() < .48):
                continue
            k = j*(nu+1)+i
            faces.append((k, k+1, k+nu+2, k+nu+1))
    mesh = bpy.data.meshes.new('Collapsed canvas fragment')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new('Collapsed canvas %02d' % index, mesh)
    bpy.context.collection.objects.link(obj)
    finish(obj)
    bpy.context.view_layer.objects.active = obj
    solid = obj.modifiers.new('Cloth thickness', 'SOLIDIFY')
    solid.thickness = .004
    bpy.ops.object.modifier_apply(modifier=solid.name)

bpy.context.view_layer.update()
for obj in kept:
    obj.matrix_world = normalize@obj.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for obj in kept:
    obj.select_set(True)
bpy.context.view_layer.objects.active = kept[0]
bpy.ops.object.join()
ruin = bpy.context.object
ruin.name = 'SM_HoldingRuin_ArmySurgeonsTent'
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
ruin.data.calc_loop_triangles()
triangles = len(ruin.data.loop_triangles)
assert 0 < triangles < 30000 and len(ruin.data.materials) == 1
assert not bpy.data.actions and not any(o.type == 'ARMATURE' for o in bpy.data.objects)
coords = [v.co.copy() for v in ruin.data.vertices]
bounds = {'min': [min(p[k] for p in coords) for k in range(3)],
          'max': [max(p[k] for p in coords) for k in range(3)]}
assert abs(bounds['min'][2]) < .0001 and bounds['max'][2] < .6, bounds
bsdf = material.node_tree.nodes['Principled BSDF']
socket = bsdf.inputs['Base Color']
grain = socket.links[0].from_socket
multiply = material.node_tree.nodes.new('ShaderNodeMixRGB')
multiply.blend_type = 'MULTIPLY'
multiply.inputs[0].default_value = 1
multiply.inputs[2].default_value = (.015, .035, .09, 1)
material.node_tree.links.new(grain, multiply.inputs[1])
material.node_tree.links.new(multiply.outputs[0], socket)
bsdf.inputs['Roughness'].default_value = .96
project = OUT/'ArmySurgeonsTent-Ruin.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
ruin.matrix_world = Matrix.Rotation(math.pi, 4, 'Z')
fbx = OUT/'SM_HoldingRuin_ArmySurgeonsTent.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'MESH'},
    apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y', axis_up='Z',
    bake_anim=False, add_leaf_bones=False, mesh_smooth_type='FACE', use_tspace=True,
    path_mode='STRIP', embed_textures=False)
ruin.matrix_world = Matrix.Identity(4)
with bpy.data.libraries.load(str(base_project), link=False) as (src, dst):
    dst.objects = ['Holding_Base_Ground', 'Holding_Base_Tuft']
for obj in dst.objects:
    bpy.context.collection.objects.link(obj)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.threads_mode = 'FIXED'
scene.render.threads = 8
scene.render.resolution_x, scene.render.resolution_y = 1024, 768
scene.render.resolution_percentage = 100
if scene.world is None:
    scene.world = bpy.data.worlds.new('Review daylight')
scene.world.color = (.25, .30, .36)
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = .7
data = bpy.data.lights.new('Clear warm sunlight', 'SUN')
data.energy, data.angle, data.color = 2.2, math.radians(12), (1, .93, .83)
sun = bpy.data.objects.new('Clear warm sunlight', data)
scene.collection.objects.link(sun)
sun.rotation_euler = (math.radians(25), math.radians(-20), math.radians(-30))
for name, pos, power, size in [('Warm daylight', (-5, -6, 9), 1700, 6), ('Sky fill', (5, 3, 8), 1200, 7)]:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.shape, data.size = power, 'DISK', size
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = pos
    obj.rotation_euler = (-obj.location).to_track_quat('-Z', 'Y').to_euler()
views = {}
for name, pos in [('front', (7, -11, 7)), ('rear', (-7, 11, 7)), ('right', (12, 2, 6)), ('overhead', (0, -.01, 15))]:
    data = bpy.data.cameras.new(name)
    data.type, data.ortho_scale = 'ORTHO', 12.5
    camera = bpy.data.objects.new('Review_'+name, data)
    scene.collection.objects.link(camera)
    camera.location = pos
    camera.rotation_euler = (Vector((0, 0, .2))-camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera, scene.render.filepath = camera, str(OUT/(name+'.png'))
    bpy.ops.render.render(write_still=True)
    projected = [world_to_camera_view(scene, camera, o.matrix_world@v.co)
                 for o in scene.objects if o.type == 'MESH' for v in o.data.vertices]
    assert all(0 <= p.x <= 1 and 0 <= p.y <= 1 and p.z > 0 for p in projected), name
    views[name] = sha(OUT/(name+'.png'))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'ArmySurgeonsTent-Ruin-Review.blend'))
assert sha(source) == brief['preservation']['sha256']
assert sha(base_project) == brief['preservation']['base_sha256']
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',
    brief_sha256=sha(BRIEF), source_sha256=sha(source), source_unchanged=True,
    normalization=dict(scale=scale, shift=list(shift)), triangles=triangles, bounds_m=bounds,
    removed_parts=removed, project_sha256=sha(project), base_project_sha256=sha(base_project),
    fbx_sha256=sha(fbx), views=views, imported=False, char_tint_linear=[.015, .035, .09],
    limitations=['Fictional game damage, not a documented tent fire', 'Native condition lifecycle pending']), indent=2)+'\n')
print('ARMY_SURGEONS_TENT_RUIN_AUTHORED', flush=True)
