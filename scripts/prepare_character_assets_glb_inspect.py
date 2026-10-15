import bpy
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'art/characters/vitruvian/godot_project'
bpy.ops.wm.read_factory_settings(use_empty=True)
for name in ['vitruvian_body.glb', 'vitruvian_head.glb']:
    bpy.ops.import_scene.gltf(filepath=str(SOURCE / name))
for a in list(bpy.data.actions):
    bpy.data.actions.remove(a)
for o in bpy.data.objects:
    o.animation_data_clear()
    if o.type == 'ARMATURE':
        for b in o.pose.bones:
            b.matrix_basis.identity()
        print('BONES',[(b.name,tuple(b.head_local),tuple(b.tail_local)) for b in o.data.bones if b.name in ['mixamorig:Hips','mixamorig:Head','mixamorig:LeftFoot','mixamorig:RightFoot','mixamorig:LeftHand','mixamorig:RightHand']])
    if o.type == 'MESH':
        print('MESH', o.name, 'location',tuple(o.location),'rotation',tuple(o.rotation_euler),'scale',tuple(o.scale), 'dimensions',tuple(o.dimensions),len(o.data.vertices),len(o.data.polygons))
        print('MATERIALS',[(i,m.name) for i,m in enumerate(o.data.materials)])
        print('UV',[(u.name,len(u.data)) for u in o.data.uv_layers])
        print('SHAPEKEYS',len(o.data.shape_keys.key_blocks) if o.data.shape_keys else 0)
        print('ZSPAN',min(v.co.z for v in o.data.vertices),max(v.co.z for v in o.data.vertices))
        print('ARMATURE',o.find_armature())
print('GLB_INSPECT_DONE',flush=True)
