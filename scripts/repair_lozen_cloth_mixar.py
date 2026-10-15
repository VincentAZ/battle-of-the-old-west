"""Revise Lozen's skirt skinning while preserving approved geometry and textures.

Run inside Mixar. Writes an isolated cloth-v004 source/export checkpoint; does
not overwrite the approved appearance or the original animation preview.
"""
import bpy
import hashlib
import json
import shutil
import sys
from pathlib import Path
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from weather_drifter_review import geometry_hash

SOURCE = ROOT / 'art/western/native/trio-animation-v001/lozen'
OUT = ROOT / 'art/western/native/lozen-cloth-v004'
OUT.mkdir(parents=True, exist_ok=True)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def smooth(value):
    value = max(0., min(1., value))
    return value * value * (3. - 2. * value)

assert 'mixar' in Path(bpy.app.binary_path).name.lower()
bpy.ops.wm.open_mainfile(filepath=str(SOURCE / 'Lozen-Rigged.blend'), use_scripts=False)
obj = bpy.data.objects['lozen_Appearance_Review']
arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
original_geometry = geometry_hash(obj)
original_report = json.loads((SOURCE / 'rig-validation.json').read_text())
assert original_geometry == original_report['source_geometry_uv_sha256']
changed = []
for vertex in obj.data.vertices:
    x, y, z = obj.matrix_world @ vertex.co
    # Provider skinning pins almost the entire skirt to Hips, while the knees
    # swing independently underneath. Transfer only that pelvis contribution
    # to the adjacent leg, smoothly across the waist and the center seam.
    # The approved geometry and textures remain intact.
    falloff = smooth((.91 - z) / .22) * smooth((.32 - abs(x)) / .05)
    if z < .23 or falloff <= 0:
        continue
    weights = {obj.vertex_groups[g.group].name: g.weight for g in vertex.groups}
    lower_names = ['Hips', 'LeftUpLeg', 'RightUpLeg', 'LeftLeg', 'RightLeg', 'LeftFoot', 'RightFoot']
    lower_total = sum(weights.get(name, 0.) for name in lower_names)
    if lower_total < .95:
        continue
    # Use the same smooth anatomical field for the covered leg and cloth.
    # The provider's residual opposite-leg weights at the hem pull fabric
    # through the trailing calf even after correcting its pelvis weights.
    left = smooth((x + .045) / .09)
    calf = smooth((.60 - z) / .22)
    for name in lower_names:
        weights[name] = weights.get(name, 0.) * (1. - falloff)
    amount = lower_total * falloff
    for side, fraction in [('Left', left), ('Right', 1. - left)]:
        for bone, share in [('UpLeg', 1. - calf), ('Leg', calf)]:
            name = side + bone
            weights[name] = weights.get(name, 0.) + amount * fraction * share
    weights = dict(sorted(weights.items(), key=lambda item: item[1], reverse=True)[:4])
    total = sum(weights.values())
    for group in obj.vertex_groups:
        group.remove([vertex.index])
    for name, weight in weights.items():
        if weight > 0:
            obj.vertex_groups[name].add([vertex.index], weight / total, 'REPLACE')
    changed.append(vertex.index)
assert len(changed) > 1000
assert geometry_hash(obj) == original_geometry
bpy.context.view_layer.update()
evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
mesh = evaluated.to_mesh()
bind_error = max((a.co - b.co).length for a, b in zip(obj.data.vertices, mesh.vertices))
evaluated.to_mesh_clear()
assert bind_error < .00001
project = OUT / 'Lozen-Rigged.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
exports = OUT / 'exports'
exports.mkdir(exist_ok=True)
for path in (SOURCE / 'exports').glob('*.png'):
    shutil.copy2(path, exports / path.name)
unit = Matrix.Scale(100, 4)
for item in (obj, arm):
    item.data.transform(unit)
    item.location *= 100
bpy.context.scene.unit_settings.scale_length = .01
bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.export_scene.fbx(filepath=str(exports / 'SK_Lozen.fbx'), use_selection=True,
    object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False, bake_anim=False,
    use_armature_deform_only=True, use_mesh_modifiers=False, mesh_smooth_type='FACE',
    apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y',
    axis_up='Z', path_mode='RELATIVE')
report = dict(source_sha256=sha(SOURCE / 'Lozen-Rigged.blend'),
    project_sha256=sha(project), source_geometry_uv_sha256=original_geometry,
    bind_pose_max_error_m=bind_error, changed_vertices=len(changed),
    rig_bones=len(arm.data.bones), visual_qa_passed=False,
    files={p.name: sha(p) for p in exports.iterdir() if p.is_file()})
(OUT / 'rig-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print('LOZEN_CLOTH_REVISION', json.dumps(report), flush=True)
