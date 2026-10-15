"""Compare original/repaired torso deformation in memory; never save animation."""
import bpy,json,hashlib,math
from pathlib import Path
from mathutils import Matrix,Euler,Vector
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'art/western/crew/playable-v001/prospector';qa=p/'rig-mask-qa';r=json.loads((p/'rig-validation.json').read_text());poses={'torso-twist':{'Spine':(0,25,0),'Spine1':(0,15,0),'Spine2':(0,20,0)},'arm-and-torso':{'Spine':(0,25,0),'Spine1':(0,15,0),'Spine2':(5,20,0),'RightArm':(-60,0,-25),'RightForeArm':(0,30,0)}};results=[]
for stage,path in [('before',p/'before-waist-fix/Prospector-Rigged.blend'),('repaired',p/'Prospector-Rigged.blend')]:
 bpy.ops.wm.open_mainfile(filepath=str(path),use_scripts=False);o=bpy.data.objects['prospector_Appearance_Review'];arm=bpy.data.objects['Armature'];orig=[o.matrix_world@v.co for v in o.data.vertices]
 groups={}
 for i,v in enumerate(orig):groups.setdefault(tuple(round(x,6) for x in v),[]).append(i)
 seams=[(ids[0],j) for ids in groups.values() for j in ids[1:]]
 edges=[tuple(e.vertices) for e in o.data.edges if all(.94<orig[i].z<1.18 and abs(orig[i].x)<.25 for i in e.vertices)]
 for label,changes in poses.items():
  for b in arm.pose.bones:b.matrix_basis=Matrix.Identity(4)
  for n,a in changes.items():arm.pose.bones[n].rotation_quaternion=Euler([math.radians(x) for x in a]).to_quaternion()
  bpy.context.view_layer.update();eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());em=eo.to_mesh();actual=[eo.matrix_world@v.co for v in em.vertices]
  gap=max(((actual[i]-actual[j]).length for i,j in seams),default=0);ratios=sorted((actual[i]-actual[j]).length/(orig[i]-orig[j]).length for i,j in edges if (orig[i]-orig[j]).length>1e-5)
  result={'stage':stage,'pose':label,'seam_max_gap_m':gap,'waist_edge_ratio_max':max(ratios),'waist_edge_ratio_p99':ratios[int(.99*len(ratios))],'edges':len(ratios)};results.append(result);eo.to_mesh_clear()
  scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=1280;scene.render.resolution_y=960;scene.render.resolution_percentage=100;cam=scene.camera;cam.location=(-3,-4,1.7);target=Vector((0,0,1.13));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=1.15;scene.render.filepath=str(qa/(stage+'-'+label+'.png'));bpy.ops.render.render(write_still=True)
assert all(x['seam_max_gap_m']<1e-5 for x in results if x['stage']=='repaired')
report={'status':'passed_seam_check','project_sha256':r['project_sha256'],'approved_source_sha256':r['source_project_sha256'],'tests':results,'animation_saved':False,'new_motion_freezes':False}
(qa/'waist-stress-review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
