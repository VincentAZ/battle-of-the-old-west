"""Independent counter-rotating wrist checks for confirmed cross-hand repairs."""
import bpy,hashlib,json,math
from pathlib import Path
from mathutils import Matrix,Euler,Vector
ROOT=Path(__file__).resolve().parents[1];base=ROOT/'art/western/crew/playable-v001';approval=json.loads((ROOT/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects']
for slug in ['blacksmith','bounty-hunter','poker-alice']:
 p=base/slug;qa=p/'rig-mask-qa';rig=json.loads((p/'rig-validation.json').read_text());project=p/(approval[slug]['asset_name']+'-Rigged.blend');assert hashlib.sha256(project.read_bytes()).hexdigest()==rig['project_sha256'];bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False);o=bpy.data.objects[slug.replace('-','_')+'_Appearance_Review'];arm=bpy.data.objects['Armature'];changed=json.loads((qa/'cross-hand-correction.json').read_text())['changed_vertices'];groups={}
 for v in o.data.vertices:groups.setdefault(tuple(round(x,6) for x in o.matrix_world@v.co),[]).append(v.index)
 for c in changed:
  v=o.data.vertices[c['vertex']];wrong='Right' if c['correct_hand']=='LeftHand' else 'Left';assert not any(o.vertex_groups[g.group].name.startswith(wrong+'Hand') and g.weight>1e-6 for g in v.groups)
 tests=[]
 for label,angle in [('wrists-positive',40),('wrists-negative',-40)]:
  for b in arm.pose.bones:b.matrix_basis=Matrix.Identity(4)
  for side,sign in [('Left',1),('Right',-1)]:arm.pose.bones[side+'Hand'].rotation_quaternion=Euler((0,0,math.radians(sign*angle))).to_quaternion()
  bpy.context.view_layer.update();eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());em=eo.to_mesh();pos=[eo.matrix_world@v.co for v in em.vertices];gap=max(((pos[ids[0]]-pos[i]).length for ids in groups.values() for i in ids[1:]),default=0);assert gap<1e-5;tests.append({'pose':label,'all_welded_seam_max_gap_m':gap});eo.to_mesh_clear()
  if angle==40:
   scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=1280;scene.render.resolution_y=960;scene.render.resolution_percentage=100;cam=scene.camera;cam.location=(0,-4,1.25);target=Vector((0,0,.98));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.35;scene.render.filepath=str(qa/'corrected-wrist-stress.png');bpy.ops.render.render(write_still=True)
 (qa/'cross-hand-stress-review.json').write_text(json.dumps({'status':'passed','project_sha256':rig['project_sha256'],'approved_source_sha256':rig['source_project_sha256'],'corrected_vertices':len(changed),'new_motion_constraints':False,'tests':tests,'animation_saved':False},indent=2)+'\n');print('HAND_CHECK',slug,flush=True)
