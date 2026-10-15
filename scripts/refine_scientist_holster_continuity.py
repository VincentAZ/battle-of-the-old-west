"""Isolated CPU candidate: continuous left elbow/twist, exact existing endpoints.

Uses the actual currently imported Prospector costume source for all previews.
Only the three left Arm/ForeArm/Hand pose channels change. No live assets or
runtime code are edited; accepted v3 files are hash protected.
"""
import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
import bpy
from mathutils import Matrix,Quaternion,Vector

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/characters/scientist_gesture'
SOURCE=BASE/'holster-v3/Scientist_Holster_Candidate.blend'
COSTUME=ROOT/'art/characters/survivor_variants/deformation-v3/scientist/Scientist.blend'
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--render',action='store_true')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);OUT=a.output.resolve();OUT.mkdir(parents=True,exist_ok=True)
assert not (OUT/'Scientist_Holster_Candidate.blend').exists(),'Preserve previous candidate'
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
protected={str(f):sha(f) for directory in (BASE/'holster-v3',ROOT/'game/OldWest/Content/Art/Survivors') for f in directory.rglob('*') if f.is_file()}
protected[str(COSTUME)]=sha(COSTUME)
bpy.ops.wm.open_mainfile(filepath=str(COSTUME),use_scripts=False)
native_arm=bpy.data.objects['Survivor_Rig']
native_names=[o.name for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==native_arm]
bpy.ops.wm.open_mainfile(filepath=str(SOURCE),use_scripts=False)
arm=bpy.data.objects['Survivor_Rig'];scene=bpy.context.scene
old_meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm]
for obj in old_meshes:bpy.data.objects.remove(obj,do_unlink=True)
with bpy.data.libraries.load(str(COSTUME),link=False) as (available,loaded):loaded.objects=native_names
for obj in loaded.objects:
    if obj.name not in scene.objects:scene.collection.objects.link(obj)
    matrix=obj.matrix_world.copy()
    if obj.parent and obj.parent.type=='ARMATURE':obj.parent=arm;obj.matrix_world=matrix
    for mod in obj.modifiers:
        if mod.type=='ARMATURE':mod.object=arm
for other in list(bpy.data.objects):
    if other.type=='ARMATURE' and other!=arm:bpy.data.objects.remove(other,do_unlink=True)
assert len(arm.data.bones)==53
NAMES=['mixamorig:Left'+n for n in ('Arm','ForeArm','Hand')]
original=[];world=[]
for frame in range(1,92):
    scene.frame_set(frame);bpy.context.view_layer.update()
    original.append({b.name:(b.location.copy(),b.rotation_quaternion.copy(),b.scale.copy()) for b in arm.pose.bones})
    world.append({b.name:b.matrix.copy() for b in arm.pose.bones})

def smooth(t):t=max(0.,min(1.,t));return t*t*(3-2*t)
def apply_basis(data):
    for n,(t,q,s) in data.items():
        b=arm.pose.bones[n];b.rotation_mode='QUATERNION';b.location=t;b.rotation_quaternion=q;b.scale=s
    bpy.context.view_layer.update()
def projected(p,d):
    value=p-d*p.dot(d);assert value.length>1e-7;return value.normalized()
def set_oriented(bone,origin,direction,previous,preferred,restore):
    direction=direction.normalized()
    q=(previous@Vector((0,1,0))).rotation_difference(direction)@previous
    q=q.slerp(preferred,restore)
    q=(q@Vector((0,1,0))).rotation_difference(direction)@q
    bone.matrix=Matrix.Translation(origin)@q.to_matrix().to_4x4()
    bpy.context.view_layer.update()
    return bone.matrix.to_quaternion()

FIRST,LAST=1,53
first,last=world[FIRST-1],world[LAST-1]
origin=first[NAMES[0]].translation;target=first[NAMES[2]].translation
initial_pole=projected(first[NAMES[1]].translation-origin,(target-origin).normalized())
origin=last[NAMES[0]].translation;target=last[NAMES[2]].translation
final_pole=projected(last[NAMES[1]].translation-origin,(target-origin).normalized())
previous=[world[0][n].to_quaternion() for n in NAMES[:2]]
rows=[]
for frame in range(1,92):
    scene.frame_set(frame);apply_basis(original[frame-1]);w=world[frame-1]
    if FIRST<frame<LAST:
        upper,lower,hand=[arm.pose.bones[n] for n in NAMES]
        shoulder=w[NAMES[0]].translation;wrist=w[NAMES[2]].translation.copy()
        # Once released, keep the free hand in front of the body rather than
        # passing through the sleeve/backpack on its way to the resting hip.
        front_weight=smooth((frame-FIRST)/(25-FIRST)) if frame<=25 else 1-smooth((frame-25)/(LAST-25))
        wrist.y-=.18*front_weight
        delta=wrist-shoulder;distance=delta.length;axis=delta.normalized()
        l1,l2=upper.bone.length,lower.bone.length
        assert abs(l1-l2)<distance<l1+l2
        restore=smooth((frame-FIRST)/(LAST-FIRST))
        natural_pole=projected(Vector((1.,-.3,-.8)),axis)
        endpoint_pole=projected(initial_pole.lerp(final_pole,restore),axis)
        weight=math.sin(math.pi*(frame-FIRST)/(LAST-FIRST))**2
        plane=projected(endpoint_pole.lerp(natural_pole,weight),axis)
        along=(l1*l1-l2*l2+distance*distance)/(2*distance)
        elbow=shoulder+axis*along+plane*math.sqrt(max(0.,l1*l1-along*along))
        upper_q=first[NAMES[0]].to_quaternion().slerp(last[NAMES[0]].to_quaternion(),restore)
        lower_q=first[NAMES[1]].to_quaternion().slerp(last[NAMES[1]].to_quaternion(),restore)
        previous[0]=set_oriented(upper,shoulder,elbow-shoulder,upper_q,upper_q,1.)
        previous[1]=set_oriented(lower,elbow,wrist-elbow,lower_q,lower_q,1.)
        hand_pose=w[NAMES[2]].copy();hand_pose.translation=wrist
        hand.matrix=hand_pose;bpy.context.view_layer.update()
    else:previous=[arm.pose.bones[n].matrix.to_quaternion() for n in NAMES[:2]]
    for name in NAMES:
        if rows and arm.pose.bones[name].rotation_quaternion.dot(rows[-1][name][1])<0:
            arm.pose.bones[name].rotation_quaternion.negate()
        for channel in ('location','rotation_quaternion','scale'):arm.pose.bones[name].keyframe_insert(channel,frame=frame)
    rows.append({b.name:(b.location.copy(),b.rotation_quaternion.copy(),b.scale.copy()) for b in arm.pose.bones})

# Blender evaluates linear quaternion channels by normalization, corresponding
# to the native shortest local-key interpolation checked below. FBX export will
# retain the same 30 Hz integer samples as the accepted timing contract.
for action in bpy.data.actions:
    for layer in action.layers:
        for strip in layer.strips:
            for slot in action.slots:
                try:bag=strip.channelbag(slot)
                except RuntimeError:continue
                if bag:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:key.interpolation='LINEAR'

max_other=0.;max_end=0.
for i in range(91):
    for name in original[i]:
        old,new=original[i][name],rows[i][name]
        angle=old[1].rotation_difference(new[1]).angle
        error=max((old[0]-new[0]).length,min(angle,2*math.pi-angle),(old[2]-new[2]).length)
        if name not in NAMES or not FIRST<i+1<LAST:max_other=max(max_other,error)
        if i in (0,90):max_end=max(max_end,error)
assert max_other<1e-6 and max_end<1e-6,(max_other,max_end)
max_step=max(math.degrees(2*math.acos(min(1.,abs(rows[i][n][1].normalized().dot(rows[i+1][n][1].normalized()))))) for i in range(90) for n in NAMES)
right_grip=Vector((-.018,.01,-.007));rifle=bpy.data.objects['ActualNativeRifle_CPUReference']
def palm(side):
    wrist=arm.pose.bones['mixamorig:'+side+'Hand'].head;middle=arm.pose.bones['mixamorig:'+side+'HandMiddle1'].head
    nextjoint=arm.pose.bones['mixamorig:'+side+'HandMiddle2'].head;along=(middle-wrist).normalized();bend=nextjoint-middle
    return wrist.lerp(middle,.58)+(bend-along*bend.dot(along)).normalized()*.009
samples=[]
for tick in range(361):
    frame=1+tick/4;scene.frame_set(int(frame),subframe=frame-int(frame));bpy.context.view_layer.update()
    samples.append({'frame':frame,'seconds':(frame-1)/30,'left_palm_body_m':list(palm('Left')),
        'right_held_grip_gap_cm':(palm('Right')-rifle.matrix_world@right_grip).length*100 if frame<=65 else None})
scene.frame_set(1);path=OUT/'Scientist_Holster_Candidate.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
report={'status':'isolated CPU candidate; dense surface and native review required','source':str(SOURCE),'source_sha256':protected[str(SOURCE)],
        'costume':str(COSTUME),'costume_sha256':protected[str(COSTUME)],'candidate':str(path),'candidate_sha256':sha(path),
        'authoring_script_sha256':sha(__file__),'modified_bones':NAMES,'modified_frames':[FIRST+1,LAST-1],
        'maximum_other_local_pose_change':max_other,'maximum_endpoint_local_pose_change':max_end,
        'maximum_adjacent_left_local_degrees':max_step,'maximum_dense_held_right_gap_cm':max(s['right_held_grip_gap_cm'] or 0 for s in samples),
        'quarter_frame_samples':samples,'protected_originals_unchanged':all(sha(p)==h for p,h in protected.items())}
assert report['protected_originals_unchanged']
(OUT/'continuity-preflight.json').write_text(json.dumps(report,indent=2)+'\n')

if a.render:
    for obj in list(bpy.data.objects):
        if obj.type in {'CAMERA','LIGHT'}:bpy.data.objects.remove(obj,do_unlink=True)
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32
    scene.cycles.use_denoising=True;scene.render.threads_mode='FIXED';scene.render.threads=4
    scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
    if scene.world is None:scene.world=bpy.data.worlds.new('CPU_Review_World')
    scene.world.color=(.15,.15,.15)
    for name,where,power,size in [('Key',(2,-3,4),900,4),('Fill',(-3,-1,2.8),500,3)]:
        data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
        light=bpy.data.objects.new(name,data);scene.collection.objects.link(light);light.location=where
        light.rotation_euler=(Vector((0,0,1.0))-light.location).to_track_quat('-Z','Y').to_euler()
    camera=bpy.data.objects.new('Native_side_review',bpy.data.cameras.new('Native_side_review'));scene.collection.objects.link(camera)
    scene.camera=camera;camera.location=(2.8,-2.8,2.5);camera.data.lens=75
    camera.rotation_euler=(Vector((0,0,1.20))-camera.location).to_track_quat('-Z','Y').to_euler()
    for frame in (10.,11.,12.,12.5,13.,14.,25.,65.,91.):
        scene.frame_set(int(frame),subframe=frame-int(frame));bpy.context.view_layer.update()
        scene.render.filepath=str(OUT/f'{frame:05.1f}-front-right.png');bpy.ops.render.render(write_still=True)
assert all(sha(p)==h for p,h in protected.items())
print('SCIENTIST_HOLSTER_CONTINUITY_STAGED '+json.dumps({k:v for k,v in report.items() if k!='quarter_frame_samples'}),flush=True)
# These CPU background jobs previously hung in Blender's PulseAudio shutdown
# after completing all work. All outputs are synchronously saved above.
sys.stdout.flush();sys.stderr.flush();os._exit(0)
