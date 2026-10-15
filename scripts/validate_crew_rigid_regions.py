"""Stress rigid prop/grip weights in memory; never save poses into source projects."""
import bpy, hashlib, json, math, sys
from pathlib import Path
from mathutils import Matrix, Euler
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
from weather_drifter_review import geometry_hash
slug=sys.argv[sys.argv.index('--')+1];out=root/'art/western/crew/playable-v001'/slug
s=json.loads((out/'rig-settings.json').read_text());r=json.loads((out/'rig-validation.json').read_text())
approval=json.loads((root/'art/western/crew/review-v003/appearance-approval.json').read_text())['projects'][slug]
project=out/(approval['asset_name']+'-Rigged.blend');assert hashlib.sha256(project.read_bytes()).hexdigest()==r['project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
o=bpy.data.objects[slug.replace('-','_')+'_Appearance_Review'];arm=bpy.data.objects['Armature'];assert geometry_hash(o)==r['source_geometry_uv_sha256']
orig=[o.matrix_world@v.co for v in o.data.vertices];indices={i for region in s['rigid_regions'] for i in region['vertex_indices']};groups={}
for i,v in enumerate(orig):groups.setdefault(tuple(round(x,6) for x in v),[]).append(i)
seams=[(i,j) for ids in groups.values() for i in ids if i in indices for j in ids if j not in indices]
scenarios=[('rest',{}),('head-turn',{'Head':(0,0,20),'Neck':(10,0,0)}),('free-arm',{'LeftArm':(20,0,15),'LeftForeArm':(0,15,0),'LeftHand':(0,0,10)}),('carrying-arm',{'RightArm':(25,0,-30),'RightForeArm':(0,35,0),'RightHand':(0,0,15)}),('body',{'Spine':(0,0,12),'Spine2':(10,0,-15),'RightArm':(0,0,20),'LeftUpLeg':(5,0,0),'RightUpLeg':(-5,0,0)})]
results=[]
for label,changes in scenarios:
 for bone in arm.pose.bones:bone.matrix_basis=Matrix.Identity(4)
 applied={n:a for n,a in changes.items() if n not in r['freeze_bones']}
 for n,a in applied.items():arm.pose.bones[n].rotation_quaternion=Euler([math.radians(x) for x in a]).to_quaternion()
 bpy.context.view_layer.update();eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());em=eo.to_mesh();actual=[eo.matrix_world@v.co for v in em.vertices]
 error=0
 for region in s['rigid_regions']:
  n=region['name'];xf=arm.matrix_world@arm.pose.bones[n].matrix@arm.data.bones[n].matrix_local.inverted()@arm.matrix_world.inverted()
  error=max(error,max((actual[i]-xf@orig[i]).length for i in region['vertex_indices']))
 gap=max(((actual[i]-actual[j]).length for i,j in seams),default=0)
 results.append(dict(pose=label,applied_rotations_degrees=applied,rigid_max_error_m=error,wrist_seam_max_gap_m=gap))
 eo.to_mesh_clear()
report=dict(status='passed' if all(t['rigid_max_error_m']<1e-5 and t['wrist_seam_max_gap_m']<1e-4 for t in results) else 'needs_weight_adjustment',project_sha256=r['project_sha256'],selected_vertices=len(indices),wrist_seam_pairs=len(seams),tests=results,saved_pose_or_animation=False)
qa=out/'rig-mask-qa';qa.mkdir(exist_ok=True);(qa/'pose-stress-review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
assert report['status']=='passed'
