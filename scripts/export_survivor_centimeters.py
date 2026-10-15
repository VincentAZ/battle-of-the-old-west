"""Export a UE skeleton with centimeter bone lengths and unit root scale.

The editable Blender source stays in meters. Scaling the actual mesh/bone data
in this disposable export process avoids a 100x armature-node scale that IK
retargeting otherwise normalizes away. No source .blend is overwritten.
"""
import bpy
import json
from pathlib import Path
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/characters/oldwest_survivor'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Survivor_A.blend'))
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == arm]
assert meshes
scale = Matrix.Scale(100, 4)
objects = [arm]+meshes
before = {o.name: {'scale': list(o.scale), 'dimensions': list(o.dimensions)} for o in objects}
assert all(abs(v-1) < .0001 for o in objects for v in o.scale), 'Apply source object scales before unit conversion'
for obj in objects:
    if obj.type == 'MESH':
        obj.data.transform(scale, shape_keys=True)
    else:
        obj.data.transform(scale)
    obj.location *= 100
    matrix = obj.matrix_parent_inverse.copy()
    matrix.translation *= 100
    obj.matrix_parent_inverse = matrix
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = .01
bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
for obj in objects:
    obj.select_set(True)
bpy.context.view_layer.objects.active = arm
bpy.ops.export_scene.fbx(filepath=str(OUT/'Survivor_A_Cm.fbx'), use_selection=True,
    object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False, bake_anim=False,
    use_armature_deform_only=True, use_mesh_modifiers=False, mesh_smooth_type='FACE',
    apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
    axis_forward='-Y', axis_up='Z', path_mode='RELATIVE')
report = {'unit': 'centimeter', 'root_object_scale': list(arm.scale), 'bones': len(arm.data.bones),
          'mesh_count': len(meshes), 'before': before,
          'after': {o.name: {'scale': list(o.scale), 'dimensions': list(o.dimensions)} for o in objects}}
(OUT/'centimeter-export.json').write_text(json.dumps(report, indent=2)+'\n')
print('SURVIVOR_CENTIMETER_EXPORT', len(meshes), len(arm.data.bones))
