"""CPU-only actual-rifle holster/return study on the unchanged Survivor rig.

Uses the exported native idle pose, original rifle geometry and accepted work
entry stance. Writes a separate candidate; no Unreal import or runtime edit.
"""
import argparse
import ast
import hashlib
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'art/characters/scientist_gesture/candidate-v11'
REF=ROOT/'art/characters/scientist_gesture/holster-reference/cpu-study'
parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,default=ROOT/'art/characters/scientist_gesture/holster-v3')
parser.add_argument('--render',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=args.output.resolve();OUT.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
protected={str(p):sha(p) for directory in [SOURCE,REF] for p in directory.iterdir() if p.is_file()}
protected.update({str(p):sha(p) for p in (ROOT/'game/OldWest/Content/Art/Survivors').rglob('*.uasset')})
blend_path=OUT/'Scientist_Holster_Candidate.blend'
assert not blend_path.exists(),'Preserve prior candidates; use a new output directory.'
bpy.ops.wm.open_mainfile(filepath=str(REF/'Scientist_ActualRifleIdle.blend'),use_scripts=False)
arm=bpy.data.objects['Survivor_Rig'];scene=bpy.context.scene;scene.frame_set(1)
rifle=bpy.data.objects['ActualNativeRifle_CPUReference']
source_rows=json.loads((SOURCE/'pose-and-prop-samples.json').read_text())
reference=json.loads((REF/'reference-study.json').read_text())
for obj in bpy.data.objects:obj.animation_data_clear()
for action in list(bpy.data.actions):bpy.data.actions.remove(action)

def smooth(t):t=max(0,min(1,t));return t*t*(3-2*t)
def mix(a,b,frame,first,last):return Vector(a).lerp(Vector(b),smooth((frame-first)/(last-first)))
def native_basis():
    return {b.name:(b.location.copy(),b.rotation_quaternion.copy(),b.scale.copy()) for b in arm.pose.bones}
def basis_from(row):
    return {n:(Vector(d['location']),Quaternion((d['rotation_xyzw'][3],*d['rotation_xyzw'][:3])),Vector(d['scale'])) for n,d in row['bones'].items()}
def apply_basis(rows):
    for name,(p,q,s) in rows.items():
        bone=arm.pose.bones[name];bone.rotation_mode='QUATERNION';bone.location=p;bone.rotation_quaternion=q;bone.scale=s
    bpy.context.view_layer.update()
idle=native_basis();idle_world={bone.name:bone.matrix.copy() for bone in arm.pose.bones}
work=basis_from(source_rows[0]);apply_basis(work)
work_world={bone.name:bone.matrix.copy() for bone in arm.pose.bones}
def current_palm(side):
    hand=arm.pose.bones['mixamorig:'+side+'Hand'].head;middle=arm.pose.bones['mixamorig:'+side+'HandMiddle1'].head
    along=(middle-hand).normalized();bend=arm.pose.bones['mixamorig:'+side+'HandMiddle2'].head-middle
    return hand.lerp(middle,.58)+(bend-along*bend.dot(along)).normalized()*.009
right_ready=current_palm('Right');left_ready=current_palm('Left');apply_basis(idle)
gun_start=Matrix(reference['rifle_matrix']);gun_q0=gun_start.to_quaternion()
gun_vertical=Quaternion((1,0,0),math.pi/2)
right_grip=Vector(reference['rifle_right_grip_local_m']);left_grip=Vector(reference['rifle_left_grip_local_m'])
right_start=Vector(reference['runtime_right_palm_m']);left_start=Vector(reference['runtime_left_palm_m'])
right_bone=arm.pose.bones['mixamorig:RightHand'];left_bone=arm.pose.bones['mixamorig:LeftHand']
right_local=right_bone.matrix.inverted()@right_start
left_local=left_bone.matrix.inverted()@left_start
right_gun_rotation=gun_q0.inverted()@right_bone.matrix.to_quaternion()
left_q0=left_bone.matrix.to_quaternion()
holster_palm=Vector((-.35,.25,1.02))
gun_end=Matrix.LocRotScale(holster_palm-gun_vertical@right_grip,gun_vertical,Vector((1,1,1)))

def solve_two_bones(first_name,middle_name,end_name,target,end_rotation,twist=.25):
    first,middle,end=[arm.pose.bones['mixamorig:'+n] for n in (first_name,middle_name,end_name)]
    origin=first.head.copy();target=Vector(target);delta=target-origin;distance=delta.length
    length1=first.bone.length;length2=middle.bone.length
    assert abs(length1-length2)+.00001<distance<length1+length2-.00001,(frame,end_name,distance,length1+length2)
    along=delta/distance
    across=middle.head-origin-along*(middle.head-origin).dot(along)
    if across.length<.0001:across=Vector((0,-1,0))-along*along.dot(Vector((0,-1,0)))
    across.normalize();a=(length1*length1-length2*length2+distance*distance)/(2*distance)
    elbow=origin+along*a+across*math.sqrt(max(0,length1*length1-a*a))
    def aim(bone,toward):
        rotation=(bone.bone.tail_local-bone.bone.head_local).rotation_difference(toward.normalized())
        bone.matrix=Matrix.Translation(bone.head)@rotation.to_matrix().to_4x4()@bone.bone.matrix_local.to_3x3().to_4x4()
        bpy.context.view_layer.update()
    aim(first,elbow-origin);aim(middle,target-middle.head)
    relative=middle.bone.matrix_local.to_quaternion().inverted()@end.bone.matrix_local.to_quaternion()
    rotated=end_rotation@relative.inverted()
    rotated=(rotated@Vector((0,1,0))).rotation_difference((target-middle.head).normalized())@rotated
    middle.matrix=Matrix.Translation(middle.head)@middle.matrix.to_quaternion().slerp(rotated,twist).to_matrix().to_4x4()
    bpy.context.view_layer.update()
    end.matrix=Matrix.Translation(end.head)@end_rotation.to_matrix().to_4x4()
    bpy.context.view_layer.update()

def position_hand(side,palm,q,palm_local):
    target=Vector(palm)-q@palm_local
    solve_two_bones(side+'Arm',side+'ForeArm',side+'Hand',target,q)

def key_object(obj,frame):
    for channel in ('location','rotation_quaternion','scale'):obj.keyframe_insert(channel,frame=frame)

# A visible receiver shoe, leather backing and short straps connect the rifle
# to the coat-side waist. This new prop stays separate from all source assets.
holster=bpy.data.objects.new('RifleHolster_Receiver',None);bpy.context.collection.objects.link(holster)
holster.location=gun_end.translation;holster.rotation_mode='QUATERNION'
def box(name,position,dimensions,material,bevel=.004):
    bpy.ops.mesh.primitive_cube_add(size=1,location=position);obj=bpy.context.object;obj.name=name;obj.dimensions=dimensions
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    mod=obj.modifiers.new('Fitted_rounded_edges','BEVEL');mod.width=bevel;mod.segments=4;bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.data.materials.append(bpy.data.materials[material]);obj.parent=holster
    for face in obj.data.polygons:face.use_smooth=True
    return obj
box('Holster_leather_body_pad',(.065,-.035,-.155),(.013,.15,.17),'M_ScientistAnalysis_Rubber')
box('Holster_inner_steel_cheek',(.039,-.005,-.17),(.008,.068,.045),'M_ScientistAnalysis_Steel')
box('Holster_outer_steel_cheek',(-.041,-.005,-.17),(.008,.068,.045),'M_ScientistAnalysis_Steel')
box('Holster_receiver_bridge',(-.002,.034,-.17),(.088,.009,.045),'M_ScientistAnalysis_Steel')
for title,height in [('upper',-.10),('lower',-.21)]:
    strap=box('Holster_'+title+'_webbing',(.12,-.078,height),(.15,.039,.018),'M_ScientistAnalysis_Rubber')
    strap.rotation_euler.z=math.radians(-42)
for height in (-.10,-.21):
    for y in (-.025,.025):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=.004,location=(.055,y,height))
        rivet=bpy.context.object;rivet.name='Holster_brass_rivet';rivet.scale.x=.35;rivet.parent=holster
        rivet.data.materials.append(bpy.data.materials['M_ScientistAnalysis_Brass'])

rows=[]
for frame in range(1,92):
    t=smooth((frame-1)/64)
    apply_basis({n:(idle[n][0].lerp(work[n][0],t),idle[n][1].slerp(work[n][1],t),idle[n][2].lerp(work[n][2],t)) for n in idle})
    if 1<frame<65:
        hip=arm.pose.bones['mixamorig:Hips'];pose=hip.matrix.copy()
        pose.translation.z-=.035*math.sin(math.pi*(frame-1)/64);hip.matrix=pose
        bpy.context.view_layer.update()
    # Each foot lifts and places independently; the support foot stays planted.
    if 1<frame<65:
        for side,first,last in [('Left',15,39),('Right',41,65)]:
            begin=idle_world['mixamorig:'+side+'Foot'];end=work_world['mixamorig:'+side+'Foot']
            phase=max(0,min(1,(frame-first)/(last-first)))
            target=begin.translation.lerp(end.translation,smooth(phase));target.z+=.05*math.sin(math.pi*phase)
            rotation=begin.to_quaternion().slerp(end.to_quaternion(),smooth(phase))
            solve_two_bones(side+'UpLeg',side+'Leg',side+'Foot',target,rotation,twist=0)
    right=mix(right_start,(-.47,.0,1.23),frame,1,25) if frame<=25 else (Vector((-.47,.0,1.23)) if frame<=43 else mix((-.47,.0,1.23),holster_palm,frame,43,65))
    gun_q=gun_q0.slerp(gun_vertical,smooth((frame-22)/21))
    if frame<=65:rifle.matrix_world=Matrix.LocRotScale(right-gun_q@right_grip,gun_q,Vector((1,1,1)))
    else:rifle.matrix_world=gun_end
    right_q=gun_q@right_gun_rotation
    if frame>65:
        # Clear the fixed receiver before moving the hand into work stance.
        right=mix(holster_palm,(-.49,.055,1.11),frame,65,76) if frame<=76 else mix((-.49,.055,1.11),right_ready,frame,76,91)
        right_q=right_q.slerp(work_world['mixamorig:RightHand'].to_quaternion(),smooth((frame-68)/23))
    left=mix(left_start,(.34,-.005,1.21),frame,1,25) if frame<=25 else mix((.34,-.005,1.21),left_ready,frame,25,53)
    left_q=left_q0.slerp(work_world['mixamorig:LeftHand'].to_quaternion(),smooth((frame-10)/43))
    if frame not in (1,91):
        for side,start,end in [('Right',65,91),('Left',1,35)]:
            for name in idle:
                if name.startswith('mixamorig:'+side+'Hand') and name!='mixamorig:'+side+'Hand':
                    arm.pose.bones[name].rotation_quaternion=idle[name][1].slerp(work[name][1],smooth((frame-start)/(end-start)))
        bpy.context.view_layer.update()
        right_local=arm.pose.bones['mixamorig:RightHand'].matrix.inverted()@current_palm('Right')
        left_local=arm.pose.bones['mixamorig:LeftHand'].matrix.inverted()@current_palm('Left')
        position_hand('Right',right,right_q,right_local)
        position_hand('Left',left,left_q,left_local)
    elif frame==1:apply_basis(idle);rifle.matrix_world=gun_start
    else:apply_basis(work)
    bpy.context.view_layer.update()
    def palm(side):
        hand=arm.pose.bones['mixamorig:'+side+'Hand'].head;middle=arm.pose.bones['mixamorig:'+side+'HandMiddle1'].head
        along=(middle-hand).normalized();bend=arm.pose.bones['mixamorig:'+side+'HandMiddle2'].head-middle
        return hand.lerp(middle,.58)+(bend-along*bend.dot(along)).normalized()*.009
    gap=(palm('Right')-rifle.matrix_world@right_grip).length*100
    for bone in arm.pose.bones:
        for channel in ('location','rotation_quaternion','scale'):bone.keyframe_insert(channel,frame=frame)
    rifle.rotation_mode='QUATERNION';key_object(rifle,frame)
    rows.append({'frame':frame,'seconds':(frame-1)/30,'rifle_held':frame<=65,'right_native_palm_gap_cm':gap,
        'rifle_matrix_m':[list(row) for row in rifle.matrix_world],
        'bones':{b.name:{'location':list(b.location),'rotation_xyzw':[b.rotation_quaternion.x,b.rotation_quaternion.y,b.rotation_quaternion.z,b.rotation_quaternion.w],'scale':list(b.scale)} for b in arm.pose.bones}})
scene.frame_start=1;scene.frame_end=91;scene.render.fps=30;scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
(OUT/'pose-and-rifle-samples.json').write_text(json.dumps(rows,indent=2)+'\n')
if args.render:
    source=(ROOT/'scripts/author_scientist_decision_branches.py').read_text().replace('(2.8,-2.4,2.25)','(-2.8,-2.4,2.25)').replace('(1.3,-1.8,2.4)','(-1.7,-1.8,2.0)')
    tree=ast.parse(source);exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='studio'],type_ignores=[]),'studio','exec'),globals())
    images=studio(blend_path,OUT,[1,25,43,65,76,91])
else:images=[]
assert all(sha(p)==v for p,v in protected.items()),'Original/reference/native source changed'
(OUT/'manifest.json').write_text(json.dumps({'status':'CPU_holster_candidate_requires_visual_review',
    'blend':str(blend_path),'blend_sha256':sha(blend_path),'frames':91,'seconds':3,
    'source_idle':str(REF),'source_work':str(SOURCE),'images':images,
    'maximum_held_native_right_palm_gap_cm':max(r['right_native_palm_gap_cm'] for r in rows if r['rifle_held']),
    'originals_unchanged':True,'limitations':['No native import, gameplay or return clip yet.','Receiver fitting, fingers, garment clearance and two stepping feet need actual rendered review.']},indent=2)+'\n')
print('SCIENTIST_HOLSTER_CPU_STUDY_COMPLETE',flush=True)
