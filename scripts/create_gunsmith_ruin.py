"""Create a separate fictional fire condition from the reviewed Gunsmith timbers.

Mixar --background --factory-startup --python-exit-code 1 --python THIS
Preserves all healthy source files. Does not import or change gameplay.
"""
import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/western/holdings/expansion-review-v001/gunsmith'
OUT = BASE / 'ruin-source-v003'
BRIEF = BASE / 'ruin-brief-v001.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
source = BASE / brief['preservation']['source']
assert sha(source) == brief['preservation']['sha256']
assert not OUT.exists()
OUT.mkdir()
bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
original = [o for o in bpy.context.scene.objects if o.type == 'MESH']
points = [o.matrix_world @ v.co for o in original for v in o.data.vertices]
lo = Vector([min(p[k] for p in points) for k in range(3)])
hi = Vector([max(p[k] for p in points) for k in range(3)])
# Use the INTACT model's review normalization, not the smaller ruin bounds.
scale = 5.5 / max(hi.x - lo.x, hi.y - lo.y)
shift = Vector((-(hi.x + lo.x)/2, -(hi.y + lo.y)/2, -lo.z))
normalize = Matrix.Scale(scale, 4) @ Matrix.Translation(shift)
kept, removed, wall_logs, fallen = [], [], [], []
for obj in original:
    name, z = obj.name, obj.location.z
    keep = False
    if name.startswith(('Hewn side log', 'Rear hewn log')) and z < 1.55:
        keep = True
        wall_logs.append(obj)
        # Uneven ends above the sill courses leave open, recognisable log walls.
        if z > .65:
            if name.startswith('Hewn side'):
                obj.scale.y *= .50 + .12 * math.sin(z * 9 + obj.location.x)
                obj.location.y += .72 if obj.location.x > 0 else -.62
            else:
                obj.scale.x *= .62 + .13 * math.cos(z * 7)
                obj.location.x += .38
    elif name.startswith('Side vertical brace'):
        keep = True
        height = 1.55 + (.55 if obj.location.y > 0 else .20)
        obj.scale.z *= height / obj.dimensions.z
        obj.location.z = height / 2
    elif name.startswith('Door frame'):
        keep = True
        height = 1.62 if obj.location.x < 0 else 1.12
        obj.scale.z *= height / obj.dimensions.z
        obj.location.z = height / 2
    elif name.startswith('Timber threshold'):
        keep = True
    elif name.startswith('Hewn side log') and 1.9 < z < 2.4:
        keep = True
        fallen.append(obj)
        side = 1 if obj.location.x > 0 else -1
        obj.scale.y *= .32 + .07 * math.sin(z * 13)
        obj.location = (side * (.35 + (z-1.9)*2.3), (z-2.15)*5, .15)
        obj.rotation_euler = (0, math.radians(side*4), math.radians(side*(z*137)))
    elif name.startswith('Facade rail') and z < 3:
        keep = True
        fallen.append(obj)
        obj.location = (0, -.45, .28)
        obj.rotation_euler = (math.radians(17), 0, math.radians(21))
        obj.scale.x *= .68
    if keep:
        # Consumed ends are irregular and slightly rounded, not fresh saw cuts.
        # These small losses change only this derivative's vertices.
        longest = max(range(3), key=lambda k: obj.dimensions[k])
        span = max(abs(v.co[longest]) for v in obj.data.vertices)
        for v in obj.data.vertices:
            if abs(v.co[longest]) > span * .70:
                wave = math.sin(v.co.x*47 + v.co.y*31 + v.co.z*53 + z*3)
                v.co[longest] *= .90 + .07 * wave
        kept.append(obj)
    else:
        removed.append(name)
        bpy.data.objects.remove(obj, do_unlink=True)
bpy.context.view_layer.update()
# The healthy floor was consumed. Set the low courses on the ground as a
# connected stack, and settle each fallen beam by its actual rotated vertices.
sill_height = min((o.matrix_world @ v.co).z for o in wall_logs for v in o.data.vertices)
for obj in wall_logs:
    obj.location.z -= sill_height
for obj in fallen:
    bottom = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
    obj.location.z -= bottom
bpy.context.view_layer.update()
for obj in kept:
    obj.matrix_world = normalize @ obj.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for obj in kept:
    obj.select_set(True)
bpy.context.view_layer.objects.active = kept[0]
bpy.ops.object.join()
ruin = bpy.context.object
ruin.name = 'SM_HoldingRuin_Gunsmith'
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
ruin.data.calc_loop_triangles()
assert not bpy.data.actions and not any(o.type == 'ARMATURE' for o in bpy.data.objects)
# Keep original wood UVs. This preview shader is explicit char, not a grade of
# the whole scene; Unreal can use the already imported wood-grain ruin material.
material = ruin.data.materials[0]
bsdf = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
socket = bsdf.inputs['Base Color']
grain = socket.links[0].from_socket
multiply = material.node_tree.nodes.new('ShaderNodeMixRGB')
multiply.blend_type = 'MULTIPLY'
multiply.inputs[0].default_value = 1
multiply.inputs[2].default_value = (.10, .085, .075, 1)
material.node_tree.links.new(grain, multiply.inputs[1])
material.node_tree.links.new(multiply.outputs[0], socket)
bsdf.inputs['Roughness'].default_value = .94
noise = material.node_tree.nodes.new('ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 45
noise.inputs['Detail'].default_value = 3
bump = material.node_tree.nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = .5
bump.inputs['Distance'].default_value = .035
material.node_tree.links.new(noise.outputs['Fac'], bump.inputs['Height'])
material.node_tree.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
project = OUT / 'Gunsmith-Ruin.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
# Export only the new ruin. Same axis convention as export_holdings_mixar.py.
ruin.matrix_world = Matrix.Rotation(math.pi, 4, 'Z') @ ruin.matrix_world
bpy.ops.export_scene.fbx(filepath=str(OUT/'SM_HoldingRuin_Gunsmith.fbx'), use_selection=True,
    object_types={'MESH'}, apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
    axis_forward='-Y', axis_up='Z', bake_anim=False, add_leaf_bones=False,
    mesh_smooth_type='FACE', use_tspace=True, path_mode='STRIP', embed_textures=False)
ruin.matrix_world = Matrix.Identity(4)
base_project = BASE/'base-v003/gunsmith-Base.blend'
with bpy.data.libraries.load(str(base_project), link=False) as (src, dst):
    dst.objects = ['Holding_Base_Ground', 'Holding_Base_Tuft']
for obj in dst.objects:
    bpy.context.collection.objects.link(obj)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = 1024, 768
scene.render.resolution_percentage = 100
scene.world.color = (.25, .30, .36)
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = .7
sun_data = bpy.data.lights.new('Clear warm sunlight', 'SUN')
sun_data.energy = 2.2
sun_data.angle = math.radians(12)
sun_data.color = (1, .93, .83)
sun = bpy.data.objects.new('Clear warm sunlight', sun_data)
scene.collection.objects.link(sun)
sun.rotation_euler = (math.radians(25), math.radians(-20), math.radians(-30))
for name, pos, power, size in [('Warm daylight',(-5,-6,9),1700,6),('Sky fill',(5,3,8),1200,7)]:
    data = bpy.data.lights.new(name, 'AREA'); data.energy = power; data.shape = 'DISK'; data.size = size
    light = bpy.data.objects.new(name, data); scene.collection.objects.link(light)
    light.location = pos; light.rotation_euler = (-light.location).to_track_quat('-Z','Y').to_euler()
views = {}
for name, pos in [('front', (7,-11,7)), ('rear',(-7,11,7)), ('right',(12,2,6)), ('overhead',(0,-.01,15))]:
    data = bpy.data.cameras.new(name); data.type = 'ORTHO'; data.ortho_scale = 12
    camera = bpy.data.objects.new('Review_'+name, data); scene.collection.objects.link(camera)
    camera.location = pos; camera.rotation_euler = (Vector((0,0,.35))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera = camera; scene.render.filepath = str(OUT/(name+'.png'))
    bpy.ops.render.render(write_still=True)
    views[name] = sha(OUT/(name+'.png'))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Gunsmith-Ruin-Review.blend'))
assert sha(source) == brief['preservation']['sha256']
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',
    brief_sha256=sha(BRIEF), source_sha256=sha(source), source_unchanged=True,
    normalization=dict(scale=scale, shift=list(shift)), triangles=len(ruin.data.loop_triangles),
    removed_parts=removed, project_sha256=sha(project), base_project_sha256=sha(base_project),
    fbx_sha256=sha(OUT/'SM_HoldingRuin_Gunsmith.fbx'), views=views, imported=False,
    limitations=['Fictional fire condition, not a historical event','Native material, scale, camera, repair restoration and gameplay remain']),indent=2)+'\n')
print('GUNSMITH_RUIN_AUTHORED', flush=True)
