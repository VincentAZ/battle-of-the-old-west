"""Read-only hand motion isolation checks; exact geometry preserved by rig binder."""
import bpy,json,math,hashlib,sys
from pathlib import Path
from mathutils import Matrix,Euler,Vector
ROOT=Path(__file__).resolve().parents[1];base=ROOT/'art/western/crew/playable-v001'
for slug,name in [('buffalo-soldier-veteran','BuffaloSoldierVeteran'),('gatling-gunner','GatlingGunner')]:
 if '--' in sys.argv and slug not in sys.argv[sys.argv.index('--')+1:]:continue
 p=base/slug;qa=p/'rig-mask-qa';rig=json.loads((p/'rig-validation.json').read_text());project=p/(name+'-Rigged.blend');assert hashlib.sha256(project.read_bytes()).hexdigest()==rig['project_sha256'];bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False);o=bpy.data.objects[slug.replace('-','_')+'_Appearance_Review'];arm=bpy.data.objects['Armature'];orig=[o.matrix_world@v.co for v in o.data.vertices];groups={}
 for i,v in enumerate(orig):groups.setdefault(tuple(round(x,6) for x in v),[]).append(i)
 if slug=='gatling-gunner':
  settings=json.loads((p/'rig-settings.json').read_text());carriage={i for region in settings['rigid_regions'] for i in region['vertex_indices']};boots={i for i,v in enumerate(orig) if v.z<.2 and i not in carriage};stationary=boots|carriage
 else:
  top=json.loads((qa/'topology-before-hand-fix.json').read_text());stationary={i for c in [2,19] for i in top['components'][c]['indices']};carriage=set()
 tests=[]
 for label,angle in [('positive',40),('negative',-40)]:
  for b in arm.pose.bones:b.matrix_basis=Matrix.Identity(4)
  for side,sign in [('Left',1),('Right',-1)]:
   arm.pose.bones[side+'Hand'].rotation_quaternion=Euler((0,0,math.radians(sign*angle))).to_quaternion()
   if slug=='gatling-gunner':
    arm.pose.bones[side+'Arm'].rotation_quaternion=Euler((math.radians(sign*30),0,math.radians(sign*20))).to_quaternion();arm.pose.bones[side+'ForeArm'].rotation_quaternion=Euler((0,math.radians(sign*25),0)).to_quaternion()
  bpy.context.view_layer.update();eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());em=eo.to_mesh();pos=[eo.matrix_world@v.co for v in em.vertices];gap=max(((pos[ids[0]]-pos[i]).length for ids in groups.values() for i in ids[1:]),default=0);motion=max((pos[i]-orig[i]).length for i in stationary);assert gap<1e-5,(slug,gap);assert motion<1e-5,(slug,motion);tests.append({'pose':label,'welded_seam_max_gap_m':gap,'unrelated_geometry_max_motion_m':motion,'stationary_test_vertices':len(stationary)});eo.to_mesh_clear()
  if angle==40:
   scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=1280;scene.render.resolution_y=960;scene.render.resolution_percentage=100;cam=scene.camera
   for view in (['human-detail','whole-assembly'] if slug=='gatling-gunner' else ['hands-and-trousers']):
    if view=='human-detail':cam.location=(-1.5,-4,1.5);target=Vector((-.74,.2,1.0));scale=2.25
    elif view=='whole-assembly':cam.location=(-3,-4,2.5);target=Vector((-.5,-.3,.9));scale=3.2
    else:cam.location=(0,-4,1.4);target=Vector((0,0,.85));scale=1.55
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=scale;scene.render.filepath=str(qa/('corrected-'+view+'.png'));bpy.ops.render.render(write_still=True)
 report={'status':'passed','project_sha256':rig['project_sha256'],'approved_source_sha256':rig['source_project_sha256'],'tests':tests,'carriage_vertices_preserved':len(carriage),'new_motion_constraints':False,'animation_saved':False};(qa/'hand-motion-isolation-review.json').write_text(json.dumps(report,indent=2)+'\n');print('ISOLATION_CHECK',slug,flush=True)
