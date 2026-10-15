"""Verify tangent bases and wheel radius before Unreal import; safe to rerun."""
import bpy,bmesh,json,math,hashlib,os,sys
from mathutils import Vector, Matrix
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'art/vehicles/raiders/redesign/game-export'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Raider-Game.blend'))
report=json.loads((OUT/'export.json').read_text())
for record in report['assets']:
 ob=bpy.data.objects[record['name']];ob.hide_set(False);ob.hide_render=False
 ob.data.transform(ob.matrix_world);ob.matrix_world=Matrix.Identity(4)
 bm=bmesh.new();bm.from_mesh(ob.data)
 degenerate=[face for face in bm.faces if face.calc_area()<1e-10]
 if degenerate:bmesh.ops.delete(bm,geom=degenerate,context='FACES_ONLY')
 bm.to_mesh(ob.data);bm.free();ob.data.update()
 uv=ob.data.uv_layers.active
 if 'Chassis' in ob.name:
  slots={i for i,m in enumerate(ob.data.materials) if m.name=='M_Raider_Glass'}
  for face in ob.data.polygons:
   if face.material_index in slots:
    axis=max(range(3),key=lambda a:abs(face.normal[a]));axes=(1,2) if axis==0 else (0,2) if axis==1 else (0,1)
    for index in face.loop_indices:
     v=ob.data.vertices[ob.data.loops[index].vertex_index].co;uv.data[index].uv=(v[axes[0]],v[axes[1]])
 if 'Wheel' in ob.name:
  radius=max(math.hypot(v.co.x,v.co.y) for v in ob.data.vertices)
  for v in ob.data.vertices:v.co*=.44/radius
 # MikkTSpace's geometric tolerance is more stable in centimetres for the
 # sub-millimetre cast/bevel details. Object scale preserves the exact world size.
 ob.data.transform(Matrix.Scale(100,4));ob.scale=(.01,.01,.01);ob.data.update()
 ob.data.calc_tangents(uvmap=uv.name)
 invalid_faces=[list(f.loop_indices) for f in ob.data.polygons if any(ob.data.loops[i].tangent.length<.99 for i in f.loop_indices)]
 for indices in invalid_faces:
  center=sum((uv.data[i].uv.copy() for i in indices),Vector((0,0)))/3
  for index,offset in zip(indices,((-.00004,-.00004),(.00004,-.00004),(0,.00004))):uv.data[index].uv=center+Vector(offset)
 if invalid_faces:
  ob.data.free_tangents();ob.data.update();ob.data.calc_tangents(uvmap=uv.name)
 invalid=sum(loop.tangent.length<.99 for loop in ob.data.loops)
 if invalid:
  # Extremely thin bevel faces can carry weighted normals parallel to their
  # UV tangent. Use their geometric face normals rather than discard geometry.
  bad=[f for f in ob.data.polygons if any(ob.data.loops[i].tangent.length<.99 for i in f.loop_indices)]
  for f in bad:f.use_smooth=False
  ob.data.normals_split_custom_set([(0,0,0)]*len(ob.data.loops))
  ob.data.update();ob.data.calc_tangents(uvmap=uv.name)
  invalid=sum(loop.tangent.length<.99 for loop in ob.data.loops)
 for attempt in range(3):
  if not invalid:break
  bad=[f.index for f in ob.data.polygons if any(ob.data.loops[i].tangent.length<.99 for i in f.loop_indices)]
  print('Removing ill-conditioned export slivers',len(bad),'largest area cm2',max(ob.data.polygons[i].area for i in bad),flush=True)
  bm=bmesh.new();bm.from_mesh(ob.data);bm.faces.ensure_lookup_table()
  bmesh.ops.delete(bm,geom=[bm.faces[i] for i in bad],context='FACES_ONLY')
  bm.to_mesh(ob.data);bm.free();ob.data.update();uv=ob.data.uv_layers.active
  ob.data.calc_tangents(uvmap=uv.name)
  invalid=sum(loop.tangent.length<.99 for loop in ob.data.loops)
 print('TANGENTS',ob.name,'degenerate faces removed',len(degenerate),'repaired UV faces',len(invalid_faces),'invalid',invalid,flush=True)
 assert invalid==0,(ob.name,'invalid tangent loops',invalid)
 bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
 path=OUT/record['file']
 bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',mesh_smooth_type='FACE',bake_anim=False,add_leaf_bones=False,use_tspace=True,axis_forward='-Y',axis_up='Z')
 ob.data.calc_loop_triangles()
 record.update({'triangles':len(ob.data.loop_triangles),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bounds_min_m':[min(v.co[i]*.01 for v in ob.data.vertices) for i in range(3)],'bounds_max_m':[max(v.co[i]*.01 for v in ob.data.vertices) for i in range(3)],'invalid_tangent_loops':invalid})
 ob.hide_set(True);ob.hide_render=True
report['wheel_radius_cm']=44
(OUT/'export.json').write_text(json.dumps(report,indent=2)+'\n');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Raider-Game.blend'))
print('RAIDER_GAME_EXPORT_VALIDATED',flush=True)
sys.stdout.flush();sys.stderr.flush();os._exit(0)
