"""Verify the exported survivor by importing its FBX in a fresh Blender scene."""
import bpy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/characters/oldwest_survivor'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(OUT / 'Survivor_A.fbx'))
arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
assert len(arms) == 1, f'Expected one armature: {[o.name for o in arms]}'
arm = arms[0]
assert 'root' in arm.data.bones
assert 'mixamorig:Hips' in arm.data.bones
assert len(bpy.data.actions) == 0, 'Source motion clips leaked into the export'
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
report = {'fbx': str(OUT / 'Survivor_A.fbx'), 'blender': bpy.app.version_string,
          'armatures': len(arms), 'bones': len(arm.data.bones), 'actions': len(bpy.data.actions),
          'mesh_count': len(meshes), 'materials': sorted({m.name for o in meshes for m in o.data.materials}),
          'vertices': sum(len(o.data.vertices) for o in meshes),
          'triangles': sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons),
          'weights': [], 'shape_keys': {}}
for obj in meshes:
    assert obj.find_armature() == arm, f'{obj.name} is not skinned'
    assert len(obj.data.uv_layers) >= 1, f'{obj.name} has no UVs'
    weights = [sum(g.weight for g in v.groups) for v in obj.data.vertices]
    bad = sum(w < .98 or w > 1.02 for w in weights)
    report['weights'].append({'mesh': obj.name, 'vertices': len(weights), 'unweighted_or_unnormalized': bad})
    assert bad == 0, f'{obj.name} has {bad} unnormalized vertices'
    if obj.data.shape_keys:
        keys = [k.name for k in obj.data.shape_keys.key_blocks]
        report['shape_keys'][obj.name] = keys
        assert len(keys) == 27, f'Expected base plus26 facial shapes, got {len(keys)}'
body = next(o for o in meshes if o.name.startswith('Survivor_Body'))
def world_vertices(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return [evaluated.matrix_world @ v.co for v in evaluated.data.vertices]
bpy.context.view_layer.update()
before = world_vertices(body)
bone = arm.pose.bones['mixamorig:LeftArm']
bone.rotation_mode = 'XYZ'
bone.rotation_euler.y = math.radians(22)
bpy.context.view_layer.update()
after = world_vertices(body)
movement = max((a-b).length for a,b in zip(before,after))
assert movement > .01, f'Skinning did not deform the body: {movement}'
report['left_arm_rotation_deforms_body_m'] = movement
report['verified'] = True
(OUT / 'fbx-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print('SURVIVOR_FBX_VERIFIED', json.dumps({k:v for k,v in report.items() if k not in ['weights','materials','shape_keys']}), flush=True)
