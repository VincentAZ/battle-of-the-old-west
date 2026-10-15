"""Rig an approved Native preview mesh in Mixar; preserve its exact geometry and textures."""
import bpy,json,hashlib,sys,math,shutil
from pathlib import Path
from mathutils import Matrix,Vector
from mathutils.kdtree import KDTree
from mixar.modules.hunyuan.constants import ANIMATE_IMPORT_OPTIONS
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from weather_drifter_review import geometry_hash
SLUG=sys.argv[sys.argv.index('--')+1]
NAME={'lozen':'Lozen','sarah-winnemucca':'Sarah'}[SLUG]
OUT=ROOT/'art/western/native/trio-animation-v001'/SLUG
SOURCE=OUT.parent.parent/'review-v001'/SLUG/'review'/(SLUG+'-Review.blend')
HEIGHT=json.loads((SOURCE.parent.parent/'character.json').read_text())['height_m']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
assert sha(SOURCE)==json.loads((OUT.parent.parent/'review-v001/appearance-approval.json').read_text())['projects'][SLUG]['sha256']
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(OUT/'rigged-original.glb'),**ANIMATE_IMPORT_OPTIONS)
raw_arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');raw=next(o for o in bpy.context.scene.objects if o.type=='MESH')
# The inspected provider result is the exact mesh normalized to one-meter height.
scale=Matrix.Scale(HEIGHT,4);world=scale@raw_arm.matrix_world
if SLUG=='lozen':
 mapping={'tripo::Root':'Hips','tripo::0_Right_Limb_0':'Spine','tripo::Spine_0':'Spine1',
          'tripo::Head_0':'Neck','tripo::Head_1':'Head','tripo::0_Left_Limb_0':'Hips'}
 shoulders=[('Left',5,9),('Right',24,28)]
 legs=[('Left',['bone_'+str(i) for i in range(43,47)]),('Right',['tripo::0_Right_Limb_'+str(i) for i in range(1,5)])]
else:
 mapping={'tripo::Root':'Hips','tripo::0_Left_Limb_0':'Spine','tripo::Spine_0':'Spine1','tripo::Spine_1':'Spine2',
          'tripo::Head_0':'Neck','bone_5':'Head'}
 shoulders=[('Left',6,10),('Right',25,29)]
 legs=[('Left',['bone_'+str(i) for i in range(44,48)]),('Right',['tripo::0_Left_Limb_'+str(i) for i in range(1,5)])]
for side,offset,fingers in shoulders:
 for index,part in enumerate(['Shoulder','Arm','ForeArm','Hand']):
  key='tripo::Head_1' if SLUG=='sarah-winnemucca' and offset+index==25 else 'bone_'+str(offset+index)
  mapping[key]=side+part
 for index,finger in enumerate(['Thumb','Index','Middle','Ring','Pinky']):
  for digit in range(3):mapping['bone_'+str(fingers+index*3+digit)]=side+'Hand'+finger+str(digit+1)
for side,names in legs:
 for key,part in zip(names,['UpLeg','Leg','Foot','ToeBase']):mapping[key]=side+part
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
obj=bpy.data.objects[SLUG.replace('-','_')+'_Appearance_Review'];approved_geometry=geometry_hash(obj)
arm_data=bpy.data.armatures.new(NAME+'_Skeleton');arm=bpy.data.objects.new('Armature',arm_data);bpy.context.scene.collection.objects.link(arm)
bpy.ops.object.select_all(action='DESELECT');arm.select_set(True);bpy.context.view_layer.objects.active=arm
bpy.ops.object.mode_set(mode='EDIT')
root=arm_data.edit_bones.new('root');root.head=(0,0,0);root.tail=(0,0,.15)
created={'root'}
# Standard anatomical hierarchy, corrected from the provider's arbitrary names.
rest={}
for original,g in guide.items():
 name=mapping[original]
 if name not in rest:rest[name]=g.copy()
rest['Hips']['head']=(rest['LeftUpLeg']['head']+rest['RightUpLeg']['head'])/2
rest['Hips']['tail']=rest['Spine']['head']
if 'Spine2' not in rest:
 rest['Spine2']=dict(head=rest['Spine1']['head'].lerp(rest['Neck']['head'],.55),tail=rest['Neck']['head'],matrix=rest['Spine1']['matrix'])
parents={'Hips':'root','Spine':'Hips','Spine1':'Spine','Spine2':'Spine1','Neck':'Spine2','Head':'Neck'}
for side in ['Left','Right']:
 for part,parent in [('Shoulder','Spine2'),('Arm',side+'Shoulder'),('ForeArm',side+'Arm'),('Hand',side+'ForeArm'),('UpLeg','Hips'),('Leg',side+'UpLeg'),('Foot',side+'Leg'),('ToeBase',side+'Foot')]:parents[side+part]=parent
 for finger in ['Thumb','Index','Middle','Ring','Pinky']:
  for digit in range(1,4):parents[side+'Hand'+finger+str(digit)]=side+'Hand'+finger+str(digit-1) if digit>1 else side+'Hand'
for name,parent in parents.items():
 g=rest[name];b=arm_data.edit_bones.new(name);b.head=g['head'];b.tail=g['tail']
 if name=='Head':b.tail=b.head+Vector((0,0,.17))
 if name.endswith('ToeBase'):b.tail=b.head+Vector((0,-.06,0))
 b.align_roll(g['matrix'].to_3x3()@Vector((0,0,1)))
 created.add(name)
for name,parent in parents.items():arm_data.edit_bones[name].parent=arm_data.edit_bones[parent]
bpy.ops.object.mode_set(mode='OBJECT')
for name in created:obj.vertex_groups.new(name=name)
distances=[];rigid_head=0;max_influences=0
for v in obj.data.vertices:
 co=obj.matrix_world@v.co;_,i,distance=tree.find(co);distances.append(distance)
 w=weights[i].copy()
 if co.z>rest['Head']['head'].z-.015:w={'Head':1};rigid_head+=1
 # Preserve the provider's cross-leg cloth blends for the long skirts.
 w={n:a for n,a in w.items() if a>.001};w=dict(sorted(w.items(),key=lambda x:x[1],reverse=True)[:4])
 total=sum(w.values());assert total>0
 max_influences=max(max_influences,len(w))
 for name,value in w.items():obj.vertex_groups[name].add([v.index],value/total,'REPLACE')
assert max(distances)<.00002,max(distances)
obj.parent=arm;obj.matrix_parent_inverse=Matrix.Identity(4)
mod=obj.modifiers.new(NAME+' skin','ARMATURE');mod.object=arm;mod.use_deform_preserve_volume=False
assert geometry_hash(obj)==approved_geometry
# Bind pose must reproduce the exact approved mesh, not only its UV coordinates.
bpy.context.view_layer.update();evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
error=max((a.co-b.co).length for a,b in zip(obj.data.vertices,evaluated.vertices));assert error<.00001,error
obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
arm.show_in_front=True
for b in arm.pose.bones:b.rotation_mode='QUATERNION'
project=OUT/(NAME+'-Rigged.blend');bpy.ops.wm.save_as_mainfile(filepath=str(project))
exports=OUT/'exports';exports.mkdir(exist_ok=True)
for path in (SOURCE.parent/'textures').glob('*.png'):shutil.copy2(path,exports/path.name.replace(SLUG.replace('-','_'),NAME))
# Disposable centimeter export; editable Mixar project remains in meters.
unit=Matrix.Scale(100,4)
for item in (obj,arm):item.data.transform(unit);item.location*=100
bpy.context.scene.unit_settings.scale_length=.01
bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True);arm.select_set(True);bpy.context.view_layer.objects.active=arm
bpy.ops.export_scene.fbx(filepath=str(exports/('SK_'+NAME+'.fbx')),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,bake_anim=False,use_armature_deform_only=True,use_mesh_modifiers=False,mesh_smooth_type='FACE',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',path_mode='RELATIVE')
report=dict(source_sha256=sha(SOURCE),project_sha256=sha(project),source_geometry_uv_sha256=approved_geometry,rig_bones=len(created),bone_mapping=mapping,bind_pose_max_error_m=error,nearest_guide_max_error_m=max(distances),maximum_vertex_influences=max_influences,rigid_head_vertices=rigid_head,triangles=len(obj.data.polygons),files={p.name:sha(p) for p in exports.iterdir() if p.is_file()})
(OUT/'rig-validation.json').write_text(json.dumps(report,indent=2)+'\n');print('NATIVE_PREVIEW_RIGGED',json.dumps({k:v for k,v in report.items() if k not in ['bone_mapping','files']}),flush=True)
