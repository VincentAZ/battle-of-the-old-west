"""In-memory pose stress test; never saves a posed/animated source asset."""
import bpy,json,math,hashlib,sys
from pathlib import Path
from mathutils import Matrix,Euler
root=Path(__file__).resolve().parents[1];p=root/'art/western/crew/playable-v001/coach-guard'
s=json.loads((p/'rig-settings.json').read_text());path=p/'CoachGuard-Rigged.blend'
sys.path.insert(0,str(root/'scripts'))
from weather_drifter_review import geometry_hash
bpy.ops.wm.open_mainfile(filepath=str(path),use_scripts=False)
mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH' and len(o.data.vertices)==14277)
assert geometry_hash(mesh)==s['source_geometry_uv_sha256'], 'Approved mesh geometry or UV changed'
arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
idx=set(s['rigid_regions'][0]['vertex_indices']);orig=[mesh.matrix_world@v.co for v in mesh.data.vertices]
spine=arm.pose.bones['Spine2'];rest=arm.data.bones['Spine2'].matrix_local.copy()
bypos={}
for i,v in enumerate(orig):bypos.setdefault(tuple(round(q,6) for q in v),[]).append(i)
seams=[(i,j) for group in bypos.values() for i in group if i in idx for j in group if j not in idx]
assert seams,'Need seam pairs for contact continuity test'
scenarios=[('rest',{}),('twist',{'Spine2':(0,0,20)}),('bend',{'Spine2':(15,0,0)}),('recoil',{'Spine1':(-12,0,0),'Spine2':(8,0,-15)}),('countertwist',{'Spine':(0,0,10),'Spine1':(0,0,-10),'Spine2':(0,0,-20)})]
results=[]
for name,changes in scenarios:
 for b in arm.pose.bones:b.matrix_basis=Matrix.Identity(4)
 for bone,angles in changes.items():arm.pose.bones[bone].rotation_quaternion=Euler([math.radians(x) for x in angles]).to_quaternion()
 bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();em=mesh.evaluated_get(deps);temp=em.to_mesh();actual=[em.matrix_world@v.co for v in temp.vertices]
 xf=arm.matrix_world@spine.matrix@rest.inverted()@arm.matrix_world.inverted()
 rigid=max((actual[i]-xf@orig[i]).length for i in idx)
 seam=max((actual[i]-actual[j]).length for i,j in seams)
 results.append({'pose':name,'rigid_max_error_m':rigid,'wrist_seam_max_gap_m':seam})
 em.to_mesh_clear()
report={'status':'passed' if all(r['rigid_max_error_m']<.00001 and r['wrist_seam_max_gap_m']<.0001 for r in results) else 'needs_weight_adjustment','project_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_geometry_uv_sha256':s['source_geometry_uv_sha256'],'selected_vertices':len(idx),'wrist_seam_pairs':len(seams),'tests':results,'saved_pose_or_animation':False}
(p/'rig-mask-qa/pose-stress-review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
