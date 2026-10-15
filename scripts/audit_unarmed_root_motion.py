"""Read the new clip's root trajectory without modifying any asset."""
import hashlib
import json
import math
from pathlib import Path
import unreal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'art/characters/unarmed_walk'
path=ROOT/'game/OldWest/Content/Art/Survivors/SurvivorA/Animations/RA_MF_Unarmed_Walk_Fwd.uasset'
before=hashlib.sha256(path.read_bytes()).hexdigest()
anim=unreal.EditorAssetLibrary.load_asset('/Game/Art/Survivors/SurvivorA/Animations/RA_MF_Unarmed_Walk_Fwd')
assert anim
mesh=unreal.EditorAssetLibrary.load_asset('/Game/Art/Survivors/SurvivorA/SKM_Survivor_A_Cm')
component=unreal.SkeletalMeshComponent()
component.set_skeletal_mesh_asset(mesh)
names=[str(component.get_bone_name(i)) for i in range(component.get_num_bones())]
def resolve(name):
    matches=[n for n in names if n in (name,'mixamorig:'+name,'mixamorig_'+name)]
    assert len(matches)==1,(name,matches)
    return matches[0]
identities={bone:resolve(bone) for bone in ('root','Hips','LeftHand','RightHand','LeftFoot','RightFoot')}
rows=[]
for i in range(34):
    time=anim.get_play_length()*i/33
    pose=unreal.AnimPoseExtensions.get_anim_pose_at_time(anim,time,unreal.AnimPoseEvaluationOptions())
    row={'time':time}
    for bone,identity in identities.items():
        t=unreal.AnimPoseExtensions.get_bone_pose(pose,identity,unreal.AnimPoseSpaces.WORLD)
        row[bone]=[t.translation.x,t.translation.y,t.translation.z,t.rotation.x,t.rotation.y,t.rotation.z,t.rotation.w]
    rows.append(row)
start,end=rows[0],rows[-1]
root_travel=math.dist(start['root'][:2],end['root'][:2])
relative={bone:max(math.dist([r[bone][a]-r['root'][a] for a in range(3)],
                            [s[bone][a]-s['root'][a] for a in range(3)]) for r in rows for s in rows)
          for bone in ('Hips','LeftHand','RightHand','LeftFoot','RightFoot')}
assert root_travel>10
assert relative['Hips']<20, relative
assert all(relative[b]>2 for b in relative if b!='Hips')
assert hashlib.sha256(path.read_bytes()).hexdigest()==before
report={'status':'numeric_pass_native_in_place_review_pending','sha256':before,'duration':anim.get_play_length(),
        'enable_root_motion':anim.get_editor_property('enable_root_motion'),
        'force_root_lock':anim.get_editor_property('force_root_lock'),
        'root_travel_cm':root_travel,'stride_speed_cm_s':root_travel/anim.get_play_length(),
        'bone_identities':identities,'root_relative_motion_ranges_cm':relative,'samples':rows}
(OUT/'root-motion-audit.json').write_text(json.dumps(report,indent=2)+'\n')
unreal.log('OLDWEST_UNARMED_ROOT_AUDIT '+json.dumps({k:v for k,v in report.items() if k!='samples'}))
