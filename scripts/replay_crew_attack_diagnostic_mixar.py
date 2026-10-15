"""Replay measured Unreal component-world attack on source rig in memory; no saved asset edits."""
import bpy,json,sys,hashlib,os
from pathlib import Path
from mathutils import Matrix,Quaternion,Vector
ROOT=Path(__file__).resolve().parents[1];path=ROOT/'art/western/crew/playable-v001/integration/attack-pose-diagnostic.json';data=json.loads(path.read_text());approval=json.loads((ROOT/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects'];slugs=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['claim-jumper','jesse-james'];C=Matrix.Diagonal((.01,-.01,.01,1));Ci=C.inverted()
def matrix(t):
 x,y,z,w=t['quaternion_xyzw'];return Matrix.LocRotScale(Vector(t['translation_cm']),Quaternion((w,x,y,z)),Vector(t['scale']))
for slug in slugs:
 r=next(x for x in data['characters'] if x['slug']==slug);p=ROOT/'art/western/crew/playable-v001'/slug;project=p/(approval[slug]['asset_name']+'-Rigged.blend');assert hashlib.sha256(project.read_bytes()).hexdigest()==r['imported_rig_project_sha256'];bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False);arm=bpy.data.objects['Armature'];qa=p/'rig-mask-qa';qa.mkdir(exist_ok=True);ref_errors=[];expected={}
 for b in arm.data.bones:
  if b.name not in r['bones']:continue
  x=r['bones'][b.name];ref=C@matrix(x['reference']['world']);posed=C@matrix(x['attack02']['world']);ref_errors.append((ref.translation-b.head_local).length);expected[b.name]=posed@ref.inverted()@b.matrix_local
 assert max(ref_errors)<.0001,('Reference frame mismatch',max(ref_errors))
 for b in sorted(arm.pose.bones,key=lambda x:len(x.parent_recursive)):
  if b.name in expected:b.matrix=expected[b.name];bpy.context.view_layer.update()
 pose_error=max((arm.pose.bones[n].head-x.translation).length for n,x in expected.items());assert pose_error<.0001,pose_error
 upper_alpha=float(os.environ.get('CREW_REPLAY_UPPER_ALPHA','1'));hips_alpha=float(os.environ.get('CREW_REPLAY_HIPS_ALPHA','1'))
 alpha=float(os.environ.get('CREW_REPLAY_SPINE_ALPHA','1'));neck_alpha=float(os.environ.get('CREW_REPLAY_NECK_ALPHA','1'));suffix='' if alpha==1 and neck_alpha==1 else f'-spine{alpha}-neck{neck_alpha}'
 if upper_alpha!=1 or hips_alpha!=1:suffix=f'-upper{upper_alpha}-hips{hips_alpha}'
 rotation_changes={}
 freeze=set(json.loads((p/'rig-validation.json').read_text()).get('freeze_bones',[]))
 for name in ('Spine','Spine1','Spine2','Neck','Head','LeftShoulder','RightShoulder','LeftArm','RightArm','LeftForeArm','RightForeArm','LeftHand','RightHand','Hips'):
  b=arm.pose.bones[name];a=(hips_alpha if name=='Hips' else upper_alpha) if (upper_alpha!=1 or hips_alpha!=1) else (neck_alpha if name=='Neck' else alpha if name in ('Spine','Spine1','Spine2') else 1);a=1 if name in freeze else a;t,q,s=b.matrix_basis.decompose();adjusted=Quaternion().slerp(q,a);rotation_changes[name]={'fraction':a,'before_basis_quaternion_wxyz':list(q),'after_basis_quaternion_wxyz':list(adjusted),'translation_preserved':list(t),'scale_preserved':list(s)};b.matrix_basis=Matrix.LocRotScale(t,adjusted,s)
 bpy.context.view_layer.update()
 scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=1280;scene.render.resolution_y=960;scene.render.resolution_percentage=100;cam=scene.camera;target=(arm.pose.bones['Head'].head+arm.pose.bones['Hips'].head)/2;cam.location=target+Vector((-3,-3,1));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.65;scene.render.filepath=str(qa/('replayed-unreal-attack02'+suffix+'.png'));
 if os.environ.get('CREW_REPLAY_AUDIT_ONLY')!='1':bpy.ops.render.render(write_still=True)
 report={'status':'replayed_measured_pose','project_sha256':r['imported_rig_project_sha256'],'diagnostic_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'reference_head_max_error_m':max(ref_errors),'posed_head_max_error_m':pose_error,'basis':'Exact imported geometry audit established source→Unreal axis[+X,-Y,+Z], centimeters. Per-bone reference matrices cancel FBX bone-axis corrections.','asset_modified':False,'spine_bind_fraction':alpha,'neck_bind_fraction':neck_alpha,'upper_body_bind_fraction':upper_alpha,'hips_bind_fraction':hips_alpha,'existing_frozen_bones_preserved':sorted(freeze),'rotation_changes':rotation_changes,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'image_sha256':hashlib.sha256(Path(scene.render.filepath).read_bytes()).hexdigest()};(qa/('replayed-unreal-attack02'+suffix+'.json')).write_text(json.dumps(report,indent=2)+'\n');assert hashlib.sha256(project.read_bytes()).hexdigest()==r['imported_rig_project_sha256'];print('REPLAY',slug,pose_error,flush=True)
