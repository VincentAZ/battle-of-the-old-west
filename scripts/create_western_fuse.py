"""Locally author a tarred, twine-wrapped fuse segment in Mixar; no service calls.

One metre along X, centred at the origin; radial size is deliberately enlarged
for game readability. Evidence is recorded before this script renders anything.
"""
import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/western/trouble/fuse-v001'
EVIDENCE = ROOT / 'research/western-presentation/fuse-line.json'


def main():
    evidence = json.loads(EVIDENCE.read_text())
    assert evidence['sources'] and evidence['render_brief']
    assert 'mixar' in Path(bpy.app.binary_path).name.lower()
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    mat = bpy.data.materials.new('M_WesternFuseCord'); mat.use_nodes = True
    shader = mat.node_tree.nodes['Principled BSDF']
    shader.inputs['Base Color'].default_value = (.025, .012, .004, 1)
    shader.inputs['Roughness'].default_value = .66
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=.017, depth=1, rotation=(0, math.pi/2, 0))
    core = bpy.context.object; core.name = 'FuseCore'; core.data.materials.append(mat)
    curve = bpy.data.curves.new('TwineWrapping', 'CURVE')
    curve.dimensions = '3D'; curve.resolution_u = 1; curve.bevel_depth = .0025; curve.bevel_resolution = 1
    spline = curve.splines.new('POLY'); count = 641; spline.points.add(count-1)
    for i, point in enumerate(spline.points):
        t = i / (count-1); angle = t * math.tau * 40
        point.co = (t-.5, math.cos(angle)*.017, math.sin(angle)*.017, 1)
    wrap = bpy.data.objects.new('TwineWrapping', curve); scene.collection.objects.link(wrap)
    wrap.data.materials.append(mat)
    bpy.ops.object.select_all(action='DESELECT'); wrap.select_set(True); bpy.context.view_layer.objects.active = wrap
    bpy.ops.object.convert(target='MESH')
    core.select_set(True); bpy.ops.object.join(); obj = bpy.context.object
    obj.name = 'SM_WesternFuseCord'; bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for polygon in obj.data.polygons: polygon.use_smooth = True
    obj.data.calc_loop_triangles()
    fbx = OUT / 'SM_WesternFuseCord.fbx'
    bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'MESH'},
                            apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
                            axis_forward='-Y', axis_up='Z', bake_anim=False, add_leaf_bones=False,
                            mesh_smooth_type='FACE')
    # Editable mesh source stays at the authored origin; studio is separate.
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'WesternFuse.blend'))
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 24
    scene.render.resolution_x = 1200; scene.render.resolution_y = 420; scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new('World'); scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.35, .4, .5, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .5
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0,0,-.021))
    floor = bpy.context.object; floor_mat = bpy.data.materials.new('StudioFloor'); floor_mat.diffuse_color=(.22,.24,.27,1)
    floor.data.materials.append(floor_mat)
    light = bpy.data.objects.new('WarmKey', bpy.data.lights.new('WarmKey','AREA')); scene.collection.objects.link(light)
    light.location=(0,-.6,1.2); light.data.energy=120; light.data.size=1.5; light.data.color=(1,.86,.68)
    camera = bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera')); scene.collection.objects.link(camera); scene.camera=camera
    camera.location=(.12,-.7,.42); camera.rotation_euler=(-camera.location).to_track_quat('-Z','Y').to_euler()
    camera.data.type='ORTHO'; camera.data.ortho_scale=1.15
    scene.render.filepath=str(OUT/'fuse-detail.png'); bpy.ops.render.render(write_still=True)
    report = {'evidence_sha256': hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),
              'fbx': fbx.name, 'fbx_sha256': hashlib.sha256(fbx.read_bytes()).hexdigest(),
              'project_sha256': hashlib.sha256((OUT/'WesternFuse.blend').read_bytes()).hexdigest(),
              'triangles': len(obj.data.loop_triangles), 'length_cm': 100,
              'axis': 'X', 'diameter_cm': 3.9, 'material_linear_rgb': [.025,.012,.004],
              'visual_review': 'pending', 'scope': 'Local geometry only, no paid jobs or external payloads'}
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('WESTERN_FUSE_AUTHORED', report['triangles'], flush=True)


if __name__ == '__main__': main()
