"""Read-only native poses for checking cloth skinning against Unreal motion."""
import json
from pathlib import Path
import unreal
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/western/native/lozen-cloth-v003'
DEST = '/Game/Art/Western/Lozen'
mesh = unreal.load_asset(DEST + '/SK_Lozen')
skeleton = mesh.get_editor_property('skeleton')
reference = unreal.AnimPoseExtensions.get_reference_pose(skeleton)
component = unreal.SkeletalMeshComponent()
component.set_skeletal_mesh_asset(mesh)
names = [str(component.get_bone_name(i)) for i in range(component.get_num_bones())]
def transforms(pose):
    result = {}
    for name in names:
        t = unreal.AnimPoseExtensions.get_bone_pose(pose, name, unreal.AnimPoseSpaces.WORLD)
        p,q,s = t.translation,t.rotation,t.scale3d
        result[name] = [p.x,p.y,p.z,q.x,q.y,q.z,q.w,s.x,s.y,s.z]
    return result
result = dict(reference=transforms(reference), clips={})
for clip in ['MM_Idle','MF_Unarmed_Walk_Fwd','MM_Attack_01','MM_HitReact_Front_Lgt_01']:
    anim = unreal.load_asset(DEST+'/Animations/RA_'+clip)
    length = anim.get_play_length()
    result['clips'][clip] = [dict(seconds=length*i/48, bones=transforms(
        unreal.AnimPoseExtensions.get_anim_pose_at_time(anim,length*i/48,unreal.AnimPoseEvaluationOptions()))) for i in range(48)]
(OUT/'native-poses.json').write_text(json.dumps(result)+'\n')
