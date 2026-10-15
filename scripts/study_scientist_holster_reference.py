"""CPU-only study of the actual native Prospector rifle pose and mesh.

No original mesh, animation, material or Unreal asset is changed.
"""
import ast
import hashlib
import json
import math
from pathlib import Path
import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'art/characters/scientist_gesture/candidate-v11'
REF=ROOT/'art/characters/scientist_gesture/holster-reference'
OUT=ROOT/'art/characters/scientist_gesture/holster-reference/cpu-study'
OUT.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
protected={str(p):sha(p) for directory in [SOURCE,REF] for p in directory.iterdir() if p.is_file() and p.name!='cpu-study.log'}
reference=json.loads((REF/'native-reference.json').read_text())
bpy.ops.wm.open_mainfile(filepath=str(SOURCE/'Scientist_Analysis_Candidate.blend'),use_scripts=False)
arm=bpy.data.objects['Survivor_Rig'];scene=bpy.context.scene
scene.frame_set(1)
for obj in bpy.data.objects:obj.animation_data_clear()

def converted_transform(row):
    x,y,z=row['translation_cm'];qx,qy,qz,qw=row['rotation_xyzw']
    return Matrix.LocRotScale(Vector((x/100,-y/100,z/100)),Quaternion((qw,-qx,qy,-qz)),Vector(row['scale']))

for row in reference['pose_samples'][0]['bones']:
    if row['name']=='Survivor_Rig':continue
    name='root' if row['name']=='root' else 'mixamorig:'+row['name']
    arm.pose.bones[name].matrix=converted_transform(row['component'])
    bpy.context.view_layer.update()
before=set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=reference['rifle_fbx'],use_anim=False)
meshes=[obj for obj in bpy.data.objects if obj not in before and obj.type=='MESH']
assert len(meshes)==1
rifle=meshes[0];rifle.name='ActualNativeRifle_CPUReference'
raw={'object_matrix':[list(r) for r in rifle.matrix_world],
     'bounds_m':[[min((rifle.matrix_world@v.co)[i] for v in rifle.data.vertices) for i in range(3)],
                 [max((rifle.matrix_world@v.co)[i] for v in rifle.data.vertices) for i in range(3)]]}
# Exported static FBX source axes are converted to Blender by its importer.
# Preserve that complete transform in mesh coordinates before placing it.
rifle.data.transform(rifle.matrix_world);rifle.matrix_world=Matrix.Identity(4)
rifle.data.materials.clear();rifle.data.materials.append(bpy.data.materials['M_ScientistAnalysis_Dark'])

def palm(side):
    def head(suffix):return arm.pose.bones['mixamorig:'+side+suffix].head.copy()
    start=head('Hand');middle=head('HandMiddle1');along=(middle-start).normalized()
    bend=head('HandMiddle2')-middle;into=(bend-along*bend.dot(along)).normalized()
    return start.lerp(middle,.58)+into*.009

right,left=palm('Right'),palm('Left')
# Runtime native coordinates reflected to Blender. Native +Y muzzle -> -Y.
right_grip=Vector((-.018,.01,-.007))
span=(left-right).length
rail=max(.228,min(.369,-.01+math.sqrt(max(0,span*span-.036**2-.035**2))))
left_grip=Vector((.018,-rail,.028))
def yz(y,z):
    y=y.normalized();z=(z-y*z.dot(y)).normalized();x=y.cross(z)
    return Matrix((x,y,z)).transposed().to_quaternion()
q=yz(left-right,Vector((0,0,1)))@yz(left_grip-right_grip,Vector((0,0,1))).inverted()
rifle.rotation_mode='QUATERNION';rifle.rotation_quaternion=q;rifle.location=right-q@right_grip
bpy.context.view_layer.update()
rows={'reference_sha256':sha(REF/'native-reference.json'),'rifle_import':raw,
      'runtime_right_palm_m':list(right),'runtime_left_palm_m':list(left),
      'rifle_right_grip_local_m':list(right_grip),'rifle_left_grip_local_m':list(left_grip),
      'rifle_matrix':[list(row) for row in rifle.matrix_world],
      'bone_heads_m':{bone.name:list(bone.head) for bone in arm.pose.bones},
      'bone_basis':{bone.name:{'location':list(bone.location),'rotation_xyzw':[bone.rotation_quaternion.x,bone.rotation_quaternion.y,bone.rotation_quaternion.z,bone.rotation_quaternion.w],'scale':list(bone.scale)} for bone in arm.pose.bones}}
for bone in arm.pose.bones:
    bone.rotation_mode='QUATERNION'
    for channel in ('location','rotation_quaternion','scale'):bone.keyframe_insert(channel,frame=1)
path=OUT/'Scientist_ActualRifleIdle.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
# Reuse only the reviewed CPU studio function, not the authoring entrypoint.
tree=ast.parse((ROOT/'scripts/author_scientist_decision_branches.py').read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='studio'],type_ignores=[]),'studio-helper','exec'),globals())
rows['images']=studio(path,OUT,[1])
assert all(sha(p)==value for p,value in protected.items())
rows['originals_unchanged']=True
(OUT/'reference-study.json').write_text(json.dumps(rows,indent=2)+'\n')
print('SCIENTIST_ACTUAL_RIFLE_REFERENCE_STUDY_COMPLETE',flush=True)
