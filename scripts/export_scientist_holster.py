"""Export accepted CPU holster/return clips and the fitted receiver prop.

This writes FBXs and an expected-native contract only. It never imports into
Unreal or changes an original character, weapon, rig or native asset.
"""
import argparse
import ast
import copy
import hashlib
import json
import sys
from pathlib import Path
import bpy
from mathutils import Matrix,Quaternion,Vector

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);SOURCE=args.source.resolve()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
review=json.loads((SOURCE/'manual-review.json').read_text())
assert review['accepted_for_native_candidate_validation']
blend=SOURCE/'Scientist_Holster_Candidate.blend';before=sha(blend)
forward=json.loads((SOURCE/'pose-and-rifle-samples.json').read_text())
core=json.loads((ROOT/'art/characters/scientist_gesture/candidate-v11/pose-and-prop-samples.json').read_text())
assert core[0]['bones']==core[-1]['bones'],'Reverse entry must match actual work exit, not just its beginning.'
reverse=[]
for frame,source in enumerate(reversed(forward),1):
    row=copy.deepcopy(source);row['frame']=frame;row['seconds']=(frame-1)/30;row['source_holster_frame']=source['frame'];reverse.append(row)

def activate(obj):
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
def convert(matrix):
    p,q,s=matrix.decompose()
    return {'translation_cm':[100*p.x,-100*p.y,100*p.z],
            'rotation_xyzw':[-q.x,q.y,-q.z,q.w],'scale':list(s)}
tree=ast.parse((ROOT/'scripts/author_scientist_decision_branches.py').read_text())
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='export_animation'],type_ignores=[]),'animation-export-helper','exec'),globals())
exports=[];dense={}
for name,rows in [('Holster',forward),('Unholster',reverse)]:
    path=SOURCE/f'A_Scientist_{name}_Cm.fbx';assert not path.exists(),'Preserve prior export.'
    bpy.ops.wm.open_mainfile(filepath=str(blend),use_scripts=False)
    arm=bpy.data.objects['Survivor_Rig'];scene=bpy.context.scene;rifle=bpy.data.objects['ActualNativeRifle_CPUReference']
    for obj in bpy.data.objects:obj.animation_data_clear()
    for action in list(bpy.data.actions):bpy.data.actions.remove(action)
    expected=[]
    for row in rows:
        for bone_name,data in row['bones'].items():
            bone=arm.pose.bones[bone_name];bone.rotation_mode='QUATERNION';bone.location=data['location'];bone.scale=data['scale']
            x,y,z,w=data['rotation_xyzw'];bone.rotation_quaternion=Quaternion((w,x,y,z))
            for channel in ('location','rotation_quaternion','scale'):bone.keyframe_insert(channel,frame=row['frame'])
        rifle.matrix_world=Matrix(row['rifle_matrix_m']);rifle.rotation_mode='QUATERNION'
        for channel in ('location','rotation_quaternion','scale'):rifle.keyframe_insert(channel,frame=row['frame'])
        scene.frame_set(row['frame'])
        bpy.context.view_layer.update()
        expected.append({'frame':row['frame'],'seconds':row['seconds'],'rifle_held':row['rifle_held'],
            'rifle_body_relative':convert(rifle.matrix_world),
            'bones':{b.name.removeprefix('mixamorig:'):convert(arm.matrix_world@b.matrix) for b in arm.pose.bones}})
    dense[name]=expected
    if name=='Unholster':
        scene.frame_start=1;scene.frame_end=91;scene.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE/'Scientist_Unholster_Candidate.blend'))
    exports.append(export_animation(name,rows,SOURCE))

# New static receiver assembly, using its authored local origin and materials.
bpy.ops.wm.open_mainfile(filepath=str(blend),use_scripts=False)
root=bpy.data.objects['RifleHolster_Receiver'];copies=[];root_world=root.matrix_world.copy()
for child in list(root.children):
    if child.type!='MESH':continue
    obj=child.copy();obj.data=child.data.copy();bpy.context.collection.objects.link(obj)
    obj.parent=None;obj.matrix_world=root_world.inverted()@child.matrix_world;copies.append(obj)
assert copies
bpy.ops.object.select_all(action='DESELECT')
for obj in copies:obj.select_set(True)
bpy.context.view_layer.objects.active=copies[0];bpy.ops.object.join();obj=bpy.context.object
bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
obj.data.transform(Matrix.Scale(100,4));bpy.context.scene.unit_settings.scale_length=.01
prop_path=SOURCE/'SM_Scientist_RifleHolster_Cm.fbx';assert not prop_path.exists()
activate(obj)
bpy.ops.export_scene.fbx(filepath=str(prop_path),use_selection=True,object_types={'MESH'},bake_anim=False,
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z')
prop={'source_fbx':str(prop_path),'sha256':sha(prop_path),
    'asset':'/Game/Art/Survivors/ScientistAnalysis/Props/SM_Scientist_RifleHolster_Cm',
    'body_relative_transform':convert(root_world),'material_slots':[m.name for m in obj.data.materials]}
assert sha(blend)==before
contract={'schema':'oldwest.scientist.holster.v1','status':'CPU accepted candidate; expected native transforms only',
    'source_blend':str(blend),'source_blend_sha256':before,'frames':91,'fps':30,'seconds_per_clip':3,
    'clips':[dict(item,asset='/Game/Art/Survivors/ScientistAnalysis/Animations/'+Path(item['path']).stem) for item in exports],
    'prop':prop,'rifle_asset':'/Game/Weapons/Rifle/Meshes/SM_Rifle',
    'rifle_material':'/Game/Art/CardPortraits/M_Portrait_Weapon',
    'rig':'Unchanged53 authoring bones; expected54 imported including Survivor_Rig; same native skeleton and physics asset.',
    'entry_reference':'Exact exported RA_MF_Rifle_Idle_ADS pose at0seconds; blend from the actual current native pose before switching to the authored attachment clock. Verify this transition in native playback; do not teleport the held rifle.',
    'holster_events':[{'frames':[1,25],'event':'Left hand releases foregrip; right hand carries rifle away from case while left foot places.'},
        {'frames':[22,43],'event':'Right hand turns rifle muzzle-down outside the case.'},
        {'frames':[43,65],'event':'Right hand places rifle at rear-hip receiver; right foot places into work stance.'},
        {'frames':[65,66],'event':'Rifle is seated at65; detach held relationship at66 and retain exact body-relative receiver transform.'},
        {'frames':[66,91],'event':'Release trigger grip, clear the stock and move into exact core1/core271 work-ready pose.'}],
    'return_events':[{'frames':[1,26],'event':'Rifle stays parked while right hand approaches and closes around the grip.'},
        {'frames':[27,28],'event':'Establish held transform at27 before rifle begins moving at28.'},
        {'frames':[28,91],'event':'Reverse the reviewed placement/turn/stepping path into actual native rifle idle; left hand rejoins foregrip.'}],
    'work':'Keep rifle at the exact Holster91 body-relative transform through every work/choice/recovery branch. Core1 and271 pose dictionaries are exactly equal, so reversed Unholster1 matches either work exit.',
    'attachment':'Dense body-relative transforms preserve actual hand grips. Do not call ordinary AlignWeaponToHands during the bespoke clock or SnapToTarget a hand socket. Preserve the existing collisionless weapon.',
    'cleanup':'On interruption, actor removal or match change stop the bespoke clip, clear receiver/work props, and restore the existing ordinary weapon/idle policy only for a living armed person. Death must preserve the existing physics handoff.',
    'coordinates':'Same reflection/unit conversion as core contract: Blender meters(x,y,z) to Body cm(100x,-100y,100z), quaternion(-x,y,-z,w). No additional Actor yaw.',
    'dense_expected_native_samples':dense,
    'limits':['CPU meshes/poses are candidates, not native visual acceptance.','Existing stiff coat/lapel and exposed collar texture limits remain documented.','Native clip duration,54bone pose fidelity,prop pivots,blend/weapon contact and actual all-branch gameplay must be tested.']}
(SOURCE/'runtime-integration-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
print('SCIENTIST_HOLSTER_EXPORT_COMPLETE',flush=True)
