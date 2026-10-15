"""Bake one existing unarmed walk through the reviewed survivor retargeter.

Creates only RA_MF_Unarmed_Walk_Fwd. The source clip, shared skeleton, rig,
physics and existing animations are hash-protected. Run in the coordinated
Unreal commandlet lane; numeric checks do not replace an actual motion review.
"""
import hashlib
import json
import math
from pathlib import Path
import shutil
import unreal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/characters/unarmed_walk'
OUT.mkdir(parents=True, exist_ok=True)
BASE = '/Game/Art/Survivors/SurvivorA'
CLIP = '/Game/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd'
DEST = BASE+'/Animations/RA_MF_Unarmed_Walk_Fwd'
FILE = ROOT/'game/OldWest/Content/Art/Survivors/SurvivorA/Animations/RA_MF_Unarmed_Walk_Fwd.uasset'
LIB = unreal.EditorAssetLibrary

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

protected = {str(path): digest(path) for path in (ROOT/'game/OldWest/Content/Art/Survivors/SurvivorA').rglob('*.uasset') if path != FILE}
source_file = ROOT/'game/OldWest/Content/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Fwd.uasset'
protected[str(source_file)] = digest(source_file)
if FILE.exists() and not (OUT/'before-rebake.uasset').exists():
    shutil.copy2(FILE, OUT/'before-rebake.uasset')
source = LIB.load_asset('/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple')
target = LIB.load_asset(BASE+'/SKM_Survivor_A_Cm')
retargeter = LIB.load_asset(BASE+'/Rig/RTG_Manny_Survivor_A')
assert source and target and retargeter

inputs = unreal.IKRetargetBatchOperationInputs()
inputs.assets_to_retarget = [LIB.find_asset_data(CLIP)]
assert inputs.assets_to_retarget[0].is_valid()
inputs.source_mesh = source
inputs.target_mesh = target
inputs.ik_retarget_asset = retargeter
inputs.prefix = 'RA_'
inputs.target_path = BASE+'/Animations'
inputs.use_source_path = False
inputs.include_referenced_assets = False
inputs.overwrite_existing_files = True
inputs.retain_additive_flags = False
results = unreal.IKRetargetBatchOperation.run_batch_retarget(inputs)
assert len(results) == 1
anim = results[0].get_asset()
assert anim.get_path_name() == DEST+'.RA_MF_Unarmed_Walk_Fwd'
assert anim.get_editor_property('skeleton') == target.get_editor_property('skeleton')
assert anim.get_editor_property('additive_anim_type') == unreal.AdditiveAnimationType.AAT_NONE
assert LIB.save_loaded_asset(anim, only_if_is_dirty=False)
length = anim.get_play_length()
assert 0 < length < 10
component = unreal.SkeletalMeshComponent()
component.set_skeletal_mesh_asset(target)
names = [str(component.get_bone_name(i)) for i in range(component.get_num_bones())]

def bone(name):
    found = [x for x in names if x in (name, 'mixamorig_'+name, 'mixamorig:'+name)]
    assert len(found) == 1, (name, found)
    return found[0]

bones = {name: bone(name) for name in ('Hips','Head','LeftHand','RightHand','LeftFoot','RightFoot')}
samples = []
for frame in range(33):
    time = length*frame/33
    pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(anim, time, unreal.AnimPoseEvaluationOptions())
    assert unreal.AnimPoseExtensions.is_valid(pose)
    row = {}
    for name, identity in bones.items():
        transform = unreal.AnimPoseExtensions.get_bone_pose(pose, identity, unreal.AnimPoseSpaces.WORLD)
        p, q = transform.translation, transform.rotation
        values = [p.x,p.y,p.z,q.x,q.y,q.z,q.w]
        assert all(math.isfinite(v) for v in values)
        row[name] = values
    assert 20 < math.dist(row['Head'][:3], row['Hips'][:3]) < 120
    samples.append({'time': time, 'bones': row})
motion = {name: max(math.dist(a['bones'][name][:3], b['bones'][name][:3]) for a in samples for b in samples)
          for name in ('LeftHand','RightHand','LeftFoot','RightFoot')}
assert all(v > 2 for v in motion.values()), ('Expected actual arm and foot movement', motion)
assert all(digest(Path(path)) == sha for path, sha in protected.items()), 'An existing survivor/source asset changed'
report = {'status': 'baked_numeric_checks_pass_render_review_pending', 'asset': anim.get_path_name(),
          'asset_sha256': digest(FILE), 'source': CLIP, 'source_sha256': digest(source_file),
          'retargeter': retargeter.get_path_name(), 'duration': length, 'full_pose': True,
          'motion_ranges_cm': motion, 'samples': samples, 'protected_sha256': protected,
          'limitations': ['Native unarmed travel, hand pose, foot contact and loop still require actual visual review.',
                         'This is a human walk; Blacksmith needs its own mechanical gait review.']}
(OUT/'retarget.json').write_text(json.dumps(report, indent=2)+'\n')
unreal.log('OLDWEST_UNARMED_WALK_BAKED '+json.dumps({'asset': DEST, 'duration': length, 'motion_ranges_cm': motion}))
