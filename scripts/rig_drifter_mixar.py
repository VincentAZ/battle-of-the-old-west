"""Preserve approved Drifter geometry/textures; author its Mixar biped rig and FBX."""
import bpy,json,hashlib,sys,math,shutil
from pathlib import Path
from mathutils import Matrix,Vector
from mathutils.kdtree import KDTree
from mixar.modules.hunyuan.constants import ANIMATE_IMPORT_OPTIONS
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from weather_drifter_review import geometry_hash
OUT=ROOT/'art/western/drifter/animation-v001';SOURCE=OUT.parent/'review-v003/review/Drifter-Review.blend'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
assert sha(SOURCE)==json.loads((OUT/'approval.json').read_text())['source_sha256']
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(OUT/'drifter-rigged-original.glb'),**ANIMATE_IMPORT_OPTIONS)
raw_arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');raw=next(o for o in bpy.context.scene.objects if o.type=='MESH')
# The inspected provider result is the exact mesh normalized to one-meter height.
scale=Matrix.Scale(1.85,4);world=scale@raw_arm.matrix_world
mapping={'tripo::Root':'Hips','tripo::0_Left_Limb_0':'Spine','tripo::0_Left_Limb_1':'Spine1','tripo::0_Left_Limb_2':'Spine2',
 'tripo::Head_0':'Neck','tripo::Head_1':'Head','tripo::Head_2':'Head',
 'tripo::Spine_0':'LeftShoulder','bone_8':'LeftArm','bone_9':'LeftForeArm','bone_10':'LeftHand',
 'tripo::0_Left_Limb_3':'RightShoulder','tripo::0_Left_Limb_4':'RightArm','tripo::0_Left_Limb_5':'RightForeArm','tripo::0_Left_Limb_6':'RightHand'}
for side,offset in [('Left',11),('Right',30)]:
 for index,finger in enumerate(['Thumb','Index','Middle','Ring','Pinky']):
  for digit in range(3):
   rawname='bone_'+str(offset+index*3+digit)
   if side=='Right' and finger=='Pinky':rawname='tripo::0_Left_Limb_'+str(7+digit)
   mapping[rawname]=side+'Hand'+finger+str(digit+1)
for side,prefix in [('Left','tripo::1_Left_Limb_'),('Right','tripo::0_Right_Limb_')]:
 for i,name in enumerate(['UpLeg','Leg','Foot','ToeBase']):mapping[prefix+str(i)]=side+name
mapping['tripo::0_Right_Limb_4']='RightToeBase'
assert set(mapping)==set(b.name for b in raw_arm.data.bones)
guide={b.name:dict(head=world@b.head_local,tail=world@b.tail_local,matrix=world@b.matrix_local,parent=b.parent.name if b.parent else None) for b in raw_arm.data.bones}
tree=KDTree(len(raw.data.vertices));weights=[]
for v in raw.data.vertices:
 tree.insert(scale@(raw.matrix_world@v.co),v.index)
 w={}
 for g in v.groups:
  name=mapping[raw.vertex_groups[g.group].name];w[name]=w.get(name,0)+g.weight
 weights.append(w)
tree.balance()
bpy.ops.wm.open_mainfile(filepath=str(SOURCE),use_scripts=False)
obj=bpy.data.objects['Drifter_Appearance_Review'];approved_geometry=geometry_hash(obj)
arm_data=bpy.data.armatures.new('Drifter_Skeleton');arm=bpy.data.objects.new('Armature',arm_data);bpy.context.scene.collection.objects.link(arm)
bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);bpy.context.view_layer.objects.active=arm
bpy.ops.object.mode_set(mode='EDIT')
root=arm_data.edit_bones.new('root');root.head=(0,0,0);root.tail=(0,0,.15)
created={'root'}
for original,g in guide.items():
 name=mapping[original]
 if name in created:continue
 b=arm_data.edit_bones.new(name);b.head=g['head'];b.tail=g['tail']
 if name=='Hips':
  b.head=(guide['tripo::1_Left_Limb_0']['head']+guide['tripo::0_Right_Limb_0']['head'])/2
  b.tail=guide['tripo::0_Left_Limb_0']['head']
 if name=='Head':b.tail=b.head+Vector((0,0,.19))
 if name.endswith('ToeBase'):b.tail=b.head+Vector((0,-.065,0))
 b.parent=arm_data.edit_bones[mapping[g['parent']] if g['parent'] else 'root']
 b.align_roll(g['matrix'].to_3x3()@Vector((0,0,1)))
 created.add(name)
bpy.ops.object.mode_set(mode='OBJECT')
for name in created:obj.vertex_groups.new(name=name)
distances=[];rigid_head=0;max_influences=0
for v in obj.data.vertices:
 co=obj.matrix_world@v.co;_,i,distance=tree.find(co);distances.append(distance)
 w=weights[i].copy()
 if co.z>1.53:w={'Head':1};rigid_head+=1
 # Prevent remote fingers/other leg influences. Keep generated local skin blends.
 if co.z<.75:
  side='Left' if co.x>0 else 'Right';w={n:a for n,a in w.items() if n.startswith(side) and 'Hand' not in n}
  if not w:w={side+('Foot' if co.z<.18 else 'Leg'):1}
 w={n:a for n,a in w.items() if a>.001};w=dict(sorted(w.items(),key=lambda x:x[1],reverse=True)[:4])
 total=sum(w.values());assert total>0
 max_influences=max(max_influences,len(w))
 for name,value in w.items():obj.vertex_groups[name].add([v.index],value/total,'REPLACE')
assert max(distances)<.00002,max(distances)
obj.parent=arm;obj.matrix_parent_inverse=Matrix.Identity(4)
mod=obj.modifiers.new('Drifter skin','ARMATURE');mod.object=arm;mod.use_deform_preserve_volume=False
assert geometry_hash(obj)==approved_geometry
# Bind pose must reproduce the exact approved mesh, not only its UV coordinates.
bpy.context.view_layer.update();evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
error=max((a.co-b.co).length for a,b in zip(obj.data.vertices,evaluated.vertices));assert error<.00001,error
obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
arm.show_in_front=True
for b in arm.pose.bones:b.rotation_mode='QUATERNION'
project=OUT/'Drifter-Rigged.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
exports=OUT/'exports';exports.mkdir(exist_ok=True)
for path in (SOURCE.parent/'textures').glob('*.png'):shutil.copy2(path,exports/path.name)
# Disposable centimeter export; editable Mixar project remains in meters.
unit=Matrix.Scale(100,4)
for item in (obj,arm):item.data.transform(unit);item.location*=100
bpy.context.scene.unit_settings.scale_length=.01
bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True);arm.select_set(True);bpy.context.view_layer.objects.active=arm
bpy.ops.export_scene.fbx(filepath=str(exports/'SK_Drifter.fbx'),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,bake_anim=False,use_armature_deform_only=True,use_mesh_modifiers=False,mesh_smooth_type='FACE',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',path_mode='RELATIVE')
report=dict(source_sha256=sha(SOURCE),project_sha256=sha(project),source_geometry_uv_sha256=approved_geometry,rig_bones=len(created),bone_mapping=mapping,bind_pose_max_error_m=error,nearest_guide_max_error_m=max(distances),maximum_vertex_influences=max_influences,rigid_head_vertices=rigid_head,triangles=len(obj.data.polygons),files={p.name:sha(p) for p in exports.iterdir() if p.is_file()})
(OUT/'rig-validation.json').write_text(json.dumps(report,indent=2)+'\n');print('DRIFTER_RIGGED',json.dumps({k:v for k,v in report.items() if k not in ['bone_mapping','files']}),flush=True)
