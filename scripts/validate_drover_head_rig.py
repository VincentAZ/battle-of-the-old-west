"""Stress-test locally recovered Drover neck/head; temporary poses are not saved."""
import bpy,json,math,hashlib,sys
from pathlib import Path
from mathutils import Matrix,Vector,Quaternion
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from weather_drifter_review import geometry_hash
p=ROOT/'art/western/crew/playable-v001/drover';q=p/'head-rig-qa';q.mkdir(exist_ok=True)
s=json.loads((p/'rig-settings.json').read_text());sel=json.loads((p/'head-weight-selection.json').read_text());project=p/'Drover-Rigged.blend'
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
o=bpy.data.objects['drover_Appearance_Review'];arm=bpy.data.objects['Armature'];m=o.data
assert geometry_hash(o)==s['source_geometry_uv_sha256']
for side in ('Left','Right'):
 foot=arm.data.bones[side+'Foot'];toe=arm.data.bones[side+'ToeBase']
 assert (foot.tail_local-toe.head_local).length<1e-6
 assert .02<toe.head_local.z<.06 and -.13<toe.head_local.y<-.07
for name in ('Head','Neck'):
 group=o.vertex_groups[name].index
 assert sum(any(g.group==group and g.weight>.01 for g in v.groups) for v in m.vertices)>50
orig=[o.matrix_world@v.co for v in m.vertices];rigid=set(sel['rigid_head_vertices']);affected=set(rigid)|set(sel['blend_vertices']);positions={}
for i,c in enumerate(orig):positions.setdefault(tuple(round(v,6) for v in c),[]).append(i)
seams=[(group[0],i) for group in positions.values() if any(i in affected for i in group) for i in group[1:]]
edges=[(a,b,(orig[a]-orig[b]).length) for e in m.edges for a,b in [e.vertices] if a in affected and b in affected and (orig[a]-orig[b]).length>.001]
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.render.threads_mode='FIXED';scene.render.threads=4;scene.render.resolution_x=960;scene.render.resolution_y=960;scene.render.resolution_percentage=100
cam=scene.camera;cam.location=(-2.6,-4,1.9);target=Vector((0,0,1.53));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=.72
records=[]
for name,rotations in [('rest',[]),('look-left',[('Head','Z',30)]),('look-right',[('Head','Z',-30)]),('nod',[('Neck','X',12),('Head','X',12)]),('tilt',[('Neck','Y',10),('Head','Y',12)])]:
 for b in arm.pose.bones:b.matrix_basis=Matrix.Identity(4)
 for bone,axis,angle in rotations:
  worldaxis=Vector(tuple(1 if a==axis else 0 for a in 'XYZ'));localaxis=arm.data.bones[bone].matrix_local.to_3x3().inverted()@worldaxis
  arm.pose.bones[bone].rotation_quaternion=Quaternion(localaxis,math.radians(angle))
 bpy.context.view_layer.update();evaluated=o.evaluated_get(bpy.context.evaluated_depsgraph_get());tmp=evaluated.to_mesh();actual=[evaluated.matrix_world@v.co for v in tmp.vertices]
 xf=arm.matrix_world@arm.pose.bones['Head'].matrix@arm.data.bones['Head'].matrix_local.inverted()@arm.matrix_world.inverted()
 error=max((actual[i]-xf@orig[i]).length for i in rigid);gap=max((actual[a]-actual[b]).length for a,b in seams);ratios=[(actual[a]-actual[b]).length/l for a,b,l in edges]
 records.append({'pose':name,'head_rigid_max_error_m':error,'seam_max_gap_m':gap,'edge_stretch_min':min(ratios),'edge_stretch_max':max(ratios)});evaluated.to_mesh_clear()
 if '--no-render' not in sys.argv:
  scene.render.filepath=str(q/(name+'.png'));bpy.ops.render.render(write_still=True)
report={'status':'quantitative_pass_pending_visual_review' if all(r['head_rigid_max_error_m']<1e-5 and r['seam_max_gap_m']<1e-4 and r['edge_stretch_max']<2 for r in records) else 'needs_review','project_sha256':hashlib.sha256(project.read_bytes()).hexdigest(),'source_geometry_uv_sha256':s['source_geometry_uv_sha256'],'rigid_head_vertices':len(rigid),'affected_vertices':len(affected),'seam_pairs':len(seams),'tests':records,'saved_pose_or_animation':False}
(q/'head-stress-review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
