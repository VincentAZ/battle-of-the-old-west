"""Read-only coordinated editor export of the actual rifle/idle reference.

Run only in a granted native commandlet slot. Does not save any Unreal asset.
"""
import hashlib
import json
import math
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/characters/scientist_gesture/holster-reference'
OUT.mkdir(parents=True, exist_ok=True)
sha = lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
protected = {str(p):sha(p) for root in (ROOT/'game/OldWest/Content/Art/Survivors',
                                      ROOT/'game/OldWest/Content/Weapons/Rifle') for p in root.rglob('*.uasset')}
assert protected
lib = unreal.EditorAssetLibrary
mesh = lib.load_asset('/Game/Art/Survivors/Variants/SKM_Prospector_Cm')
idle = lib.load_asset('/Game/Art/Survivors/SurvivorA/Animations/RA_MF_Rifle_Idle_ADS')
rifle = lib.load_asset('/Game/Weapons/Rifle/Meshes/SM_Rifle')
assert isinstance(mesh,unreal.SkeletalMesh) and isinstance(idle,unreal.AnimSequence) and isinstance(rifle,unreal.StaticMesh)
assert idle.get_editor_property('skeleton')==mesh.get_editor_property('skeleton')
component = unreal.SkeletalMeshComponent()
component.set_skeletal_mesh_asset(mesh)
names = [str(component.get_bone_name(i)) for i in range(component.get_num_bones())]
assert len(names)==54
options = unreal.AnimPoseEvaluationOptions()
options.set_editor_property('optional_skeletal_mesh',mesh)
rows=[]
for seconds in (0.,.25,.5,1.):
    assert seconds<=idle.get_play_length()
    pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(idle,seconds,options)
    assert unreal.AnimPoseExtensions.is_valid(pose)
    bones=[]
    for name in names:
        values={}
        for space,label in ((unreal.AnimPoseSpaces.WORLD,'component'),(unreal.AnimPoseSpaces.LOCAL,'parent_relative')):
            tr=unreal.AnimPoseExtensions.get_bone_pose(pose,name,space)
            p,q,s=tr.translation,tr.rotation,tr.scale3d
            data={'translation_cm':[p.x,p.y,p.z],'rotation_xyzw':[q.x,q.y,q.z,q.w],'scale':[s.x,s.y,s.z]}
            assert all(math.isfinite(x) for group in data.values() for x in group)
            assert all(abs(x-1.)<.001 for x in data['scale'])
            values[label]=data
        bones.append({'name':name,'parent':str(component.get_parent_bone(name)),**values})
    rows.append({'seconds':seconds,'bones':bones})
file=OUT/'SM_Rifle_native_reference.fbx'
assert not file.exists(), 'Preserve earlier reference export; choose a new directory for another export.'
task=unreal.AssetExportTask()
for key,value in {'object':rifle,'filename':str(file),'automated':True,'replace_identical':False,
                  'prompt':False,'exporter':unreal.StaticMeshExporterFBX()}.items():task.set_editor_property(key,value)
task.set_editor_property('options',unreal.FbxExportOption())
assert unreal.Exporter.run_asset_export_task(task)
assert file.is_file() and file.stat().st_size>10000
assert all(sha(p)==value for p,value in protected.items()),'Existing survivor/rifle asset changed'
report={'status':'read_only_reference_export_complete_CPU_holster_not_authored',
        'mesh':mesh.get_path_name(),'idle_clip':idle.get_path_name(),'idle_duration_seconds':idle.get_play_length(),
        'rifle':rifle.get_path_name(),'rifle_fbx':str(file),'rifle_fbx_sha256':sha(file),
        'bones':54,'pose_samples':rows,'original_assets_unchanged':True,'protected_sha256':protected,
        'native_runtime_source':{'path':'game/OldWest/Source/OldWestGame/Private/OldWestBattlefield.cpp',
                                 'sha256':sha(ROOT/'game/OldWest/Source/OldWestGame/Private/OldWestBattlefield.cpp'),
                                 'functions':['PalmContact','AlignWeaponToHands']},
        'coordinates':'Unreal centimeters, model faces+Y. To original Blender frame use(x,-y,z)/100 and quaternion(-x,y,-z,w).',
        'limitations':['No animation or mesh import, native source edit or asset save was performed.',
                       'The FBX is the exact source mesh, not the runtime material override or a fitted world weapon transform.',
                       'Pose samples are the real idle clip; runtime idle phase varies, so an authored holster needs a validated entry blend.']}
(OUT/'native-reference.json').write_text(json.dumps(report,indent=2)+'\n')
unreal.log('SCIENTIST_HOLSTER_REFERENCE_EXPORTED '+str(OUT))
