"""Read-only source replay of Gatling bind versus upright-idle rotation baselines."""
import bpy,json,hashlib,math
from pathlib import Path
from mathutils import Matrix,Quaternion,Vector
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'art/western/crew/playable-v001/gatling-gunner'
project=p/'GatlingGunner-Rigged.blend';project_hash=hashlib.sha256(project.read_bytes()).hexdigest()
validation=json.loads((p/'rig-validation.json').read_text());assert validation['project_sha256']==project_hash
source_path=p/'attack-gesture-baseline-v001/attack-source-keys.json';source=json.loads(source_path.read_text())
cap_path=p/'unreal-pose-captures.json';cap=json.loads(cap_path.read_text());assert cap['rig_project_sha256']==project_hash
idle=next(x for x in cap['captures'] if x['clip']=='MM_Idle' and x['fraction']==0)['component_local_pose']
current=next(x for x in cap['captures'] if x['clip']=='MM_Attack_01' and x['fraction']==.5)['component_local_pose']
upper=('Spine','Spine1','Spine2','Neck','Head')+tuple(s+n for s in ('Left','Right') for n in ('Shoulder','Arm','ForeArm','Hand'))
frozen=set(validation['freeze_bones']);C=Matrix.Diagonal((.01,-.01,.01,1));qa=p/'rig-mask-qa';qa.mkdir(exist_ok=True)
def quat(a):return Quaternion((a[3],a[0],a[1],a[2]))
def mat(t):return Matrix.LocRotScale(Vector(t['translation']),quat(t['rotation']),Vector(t['scale']))
def xyzw(q):return [q.x,q.y,q.z,q.w]
report={'rig_project_sha256':project_hash,'archived_attack_keys_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),'capture_manifest_sha256':hashlib.sha256(cap_path.read_bytes()).hexdigest(),'asset_modified':False,'variants':[]}
for variant in ['original','bind035','idle035']:
 bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
 arm=bpy.data.objects['Armature'];order=sorted(arm.data.bones,key=lambda b:len(b.parent_recursive));refs={};poses={};worlds={};basis_errors=[];rotation_changes={};frame=(source['count']-1)//2
 for b in order:
  n=b.name;refs[n]=(refs[b.parent.name] if b.parent else Matrix.Identity(4))@mat(source['reference'][n])
  t=dict(source['bones'][n][frame]);t['rotation']=list(t['rotation'])
  if variant!='original' and n in upper and n not in frozen:
   if variant=='bind035':q0=quat(source['reference'][n]['rotation'])
   else:
    # Pose capture covers all moving upper bones except hands. Hands retain the
    # original rotation until an all-bone idle readback is available.
    q0=quat(idle[n][3:7]) if n in idle else quat(t['rotation'])
   q=q0.slerp(quat(t['rotation']),.35);t['rotation']=xyzw(q);rotation_changes[n]={'baseline':xyzw(q0),'result':xyzw(q)}
  poses[n]=t;worlds[n]=(worlds[b.parent.name] if b.parent else Matrix.Identity(4))@mat(t)
  basis_errors.append(((C@refs[n]).translation-b.head_local).length)
 print('REFERENCE_HEAD_CHECK',[(b.name,list((C@refs[b.name]).translation),list(b.head_local),round(e,5)) for b,e in zip(order,basis_errors) if e>.001],flush=True)
 print('BONE_FRAME_OFFSETS',[(n,[list(row) for row in (C@refs[n]).inverted()@arm.data.bones[n].matrix_local]) for n in ['LeftArm','RightArm','Head','LeftFoot','Spine2']],flush=True)
 # Stale USkeleton references are the defect: unchanged joints establish the exact axis conversion.
 for n in ['LeftArm','RightArm','Head','LeftFoot','Spine2']:
  offset=(C@refs[n]).inverted()@arm.data.bones[n].matrix_local
  assert max(abs(offset[i][j]-C.inverted()[i][j]) for i in range(4) for j in range(4))<.001
 desired={n:C@worlds[n]@C.inverted() for n in worlds}
 for b in sorted(arm.pose.bones,key=lambda b:len(b.parent_recursive)):
  b.matrix=desired[b.name];bpy.context.view_layer.update()
 pose_error=max((arm.pose.bones[n].head-m.translation).length for n,m in desired.items());assert pose_error<.0001
 if variant=='bind035':
  errors=[min((quat(poses[n]['rotation'])-quat(v[3:7])).magnitude,(quat(poses[n]['rotation'])+quat(v[3:7])).magnitude) for n,v in current.items()]
  assert max(errors)<.002,('Current rotation mismatch',max(errors))
 scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=1280;scene.render.resolution_y=960;scene.render.resolution_percentage=100
 cam=scene.camera;target=Vector((-.35,-.3,1.));cam.location=target+Vector((4,-6,2.8));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=3.3;scene.render.filepath=str(qa/f'gatling-attack-reference-{variant}.png');bpy.ops.render.render(write_still=True)
 report['variants'].append({'variant':variant,'frame':frame,'reference_head_max_error_m':max(basis_errors),'posed_head_max_error_m':pose_error,'local_transforms':poses,'changed_rotations':rotation_changes,'image':scene.render.filepath,'image_sha256':hashlib.sha256(Path(scene.render.filepath).read_bytes()).hexdigest()})
 print('GATLING_REFERENCE_REPLAY',variant,pose_error,flush=True)
assert hashlib.sha256(project.read_bytes()).hexdigest()==project_hash
(qa/'gatling-attack-reference-diagnostic.json').write_text(json.dumps(report,indent=2)+'\n')
