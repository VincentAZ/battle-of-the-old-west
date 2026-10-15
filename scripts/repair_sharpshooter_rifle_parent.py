"""Version the approved Sharpshooter rig with Rifle following RightHand."""
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Quaternion

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from rig_crew_mixar import appearance

OUT = ROOT/'art/western/crew/attachments-v001/sharpshooter'
SOURCE = ROOT/'art/western/crew/playable-v001/sharpshooter/Sharpshooter-Rigged.blend'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads((OUT/'render-brief.json').read_text())
for path, digest in brief['sources'].items():
    assert sha(ROOT/path) == digest, path
project = OUT/'Sharpshooter-Rigged.blend'
assert not project.exists(), 'Preserve prior source revisions'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE), use_scripts=False)
arm = bpy.data.objects['Armature']
obj = bpy.data.objects['sharpshooter_Appearance_Review']
assert not bpy.data.actions
before_appearance = appearance(obj)
weights = [[(g.group, g.weight) for g in v.groups] for v in obj.data.vertices]
rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
parents = {b.name: b.parent.name if b.parent else None for b in arm.data.bones}
assert parents['Rifle'] == 'root'
group = obj.vertex_groups['Rifle'].index
indices = [v.index for v in obj.data.vertices if any(g.group == group for g in v.groups)]
assert indices
for i in indices:
    assert len(weights[i]) == 1 and weights[i][0] == (group, 1.)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
bone = arm.data.edit_bones['Rifle']
matrix = bone.matrix.copy()
bone.parent = arm.data.edit_bones['RightHand']
bone.use_connect = False
bone.matrix = matrix
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.update()
rest_error = max(abs(b.matrix_local[i][j]-rest[b.name][i][j])
                 for b in arm.data.bones for i in range(4) for j in range(4))
assert rest_error < 1e-6
assert all((b.parent.name if b.parent else None) == ('RightHand' if b.name == 'Rifle' else parents[b.name])
           for b in arm.data.bones)
assert appearance(obj) == before_appearance
assert weights == [[(g.group, g.weight) for g in v.groups] for v in obj.data.vertices]
relative = arm.data.bones['RightHand'].matrix_local.inverted() @ arm.data.bones['Rifle'].matrix_local
stress = []
for angle in (0., .7, -1.2, 2.):
    arm.pose.bones['RightHand'].rotation_mode = 'QUATERNION'
    arm.pose.bones['RightHand'].rotation_quaternion = Quaternion((1, 0, 0), angle)
    bpy.context.view_layer.update()
    actual = arm.pose.bones['RightHand'].matrix.inverted() @ arm.pose.bones['Rifle'].matrix
    error = max(abs(actual[i][j]-relative[i][j]) for i in range(4) for j in range(4))
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    transform = arm.pose.bones['Rifle'].matrix @ arm.data.bones['Rifle'].matrix_local.inverted()
    vertex_error = max((mesh.vertices[i].co-transform @ obj.data.vertices[i].co).length for i in indices)
    evaluated.to_mesh_clear()
    assert error < 1e-5 and vertex_error < 1e-5, (angle, error, vertex_error)
    stress.append(dict(wrist_angle_radians=angle,relative_transform_error=error,rigid_vertex_error_m=vertex_error))
arm.pose.bones['RightHand'].matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=str(project))
bpy.ops.wm.open_mainfile(filepath=str(project), use_scripts=False)
obj = bpy.data.objects['sharpshooter_Appearance_Review']; arm = bpy.data.objects['Armature']
assert appearance(obj) == before_appearance and arm.data.bones['Rifle'].parent.name == 'RightHand'
exports = OUT/'exports'; exports.mkdir(exist_ok=True)
unit = Matrix.Scale(100, 4)
for item in (obj, arm):
    item.data.transform(unit)
    item.location *= 100
bpy.context.scene.unit_settings.scale_length = .01
bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active = arm
fbx = exports/'SK_Sharpshooter.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'ARMATURE', 'MESH'},
    add_leaf_bones=False, bake_anim=False, use_armature_deform_only=True, use_mesh_modifiers=False,
    mesh_smooth_type='FACE', apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
    axis_forward='-Y', axis_up='Z', path_mode='RELATIVE')
for path, digest in brief['sources'].items():
    assert sha(ROOT/path) == digest
report = dict(ok=True,source_sha256=sha(SOURCE),project_sha256=sha(project),fbx_sha256=sha(fbx),
    appearance_sha256=before_appearance,geometry_uv_materials_weights_unchanged=True,
    rest_transform_max_error=rest_error,only_parent_change={'Rifle': ['root','RightHand']},
    rigid_vertex_count=len(indices),pose_stress=stress,saved_source_reopened=True,
    script_sha256=sha(Path(__file__)),native_validation='pending')
(OUT/'source-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('SHARPSHOOTER_ATTACHMENT_SOURCE_PASSED',len(indices),flush=True)
