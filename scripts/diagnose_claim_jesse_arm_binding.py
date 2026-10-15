"""Read-only controlled forward arm raise isolates source binding from retargeting."""
import bpy,json,math,hashlib
from pathlib import Path
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1];base=ROOT/'art/western/crew/playable-v001';reports=[]
for slug,name in [('claim-jumper','ClaimJumper'),('jesse-james','JesseJames')]:
 p=base/slug;qa=p/'rig-mask-qa';qa.mkdir(exist_ok=True);project=p/(name+'-Rigged.blend');bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False);o=bpy.data.objects[slug.replace('-','_')+'_Appearance_Review'];arm=bpy.data.objects['Armature'];b=arm.data.bones['RightArm'];original_dir=(b.tail_local-b.head_local).normalized();target=Vector((0,-1,0));world_delta=original_dir.rotation_difference(target);basis=b.matrix_local.to_quaternion();arm.pose.bones['RightArm'].rotation_quaternion=basis.inverted()@world_delta@basis;bpy.context.view_layer.update()
 actualdir=(arm.pose.bones['RightArm'].tail-arm.pose.bones['RightArm'].head).normalized();assert actualdir.dot(target)>.999
 scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=1280;scene.render.resolution_y=960;scene.render.resolution_percentage=100;cam=scene.camera;cam.location=(-3,-3,1.5);focus=Vector((0,-.15,1.13));cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.45;scene.render.filepath=str(qa/'controlled-forward-arm-source-binding.png');bpy.ops.render.render(write_still=True)
 # Skin influence anatomy in the central lower torso, beyond the actual arm envelope.
 low=[]
 for v in o.data.vertices:
  pos=o.matrix_world@v.co
  if abs(pos.x)<.16 and .95<pos.z<1.18:
   amount=sum(g.weight for g in v.groups if 'Arm' in o.vertex_groups[g.group].name or 'Hand' in o.vertex_groups[g.group].name)
   if amount>.15:low.append({'vertex':v.index,'position':list(pos),'arm_hand_weight':amount})
 rec={'slug':slug,'project_sha256':hashlib.sha256(project.read_bytes()).hexdigest(),'test':'RightArm aligned to world negativeY; every other local bone transform remains bind. No Unreal/retarget involved.','right_arm_world_direction':list(actualdir),'central_lower_torso_arm_weight_candidates':low,'preview':'rig-mask-qa/controlled-forward-arm-source-binding.png','source_modified':False};(qa/'controlled-forward-arm-diagnosis.json').write_text(json.dumps(rec,indent=2)+'\n');reports.append(rec);print('BIND_DIAG',slug,len(low),flush=True)
