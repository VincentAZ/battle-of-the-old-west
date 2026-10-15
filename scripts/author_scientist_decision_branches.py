"""CPU-only decision/choice-wait variants on the reviewed Prospector layout.

Uses the preserved original53-bone rig and the accepted v11 solver; writes a
new directory. These studies never read a private deck or alter game state.
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
parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,default=ROOT/'art/characters/scientist_gesture/candidate-v11')
parser.add_argument('--output',type=Path,default=ROOT/'art/characters/scientist_gesture/decision-branches-v3')
parser.add_argument('--render',action='store_true')
parser.add_argument('--branches',nargs='+',choices=['SortLeft','SortRight','SkipRecover','WorkHold'],
                    default=['SortLeft','SortRight','SkipRecover','WorkHold'])
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
SOURCE=args.source.resolve();OUT=args.output.resolve();OUT.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert json.loads((SOURCE/'manual-review.json').read_text())['accepted_for_native_candidate_import']
source_blend=SOURCE/'Scientist_Analysis_Candidate.blend'
source_frames=json.loads((SOURCE/'pose-and-prop-samples.json').read_text())
protected={str(p):sha(p) for p in SOURCE.iterdir() if p.is_file()}
protected.update({str(p):sha(p) for p in (ROOT/'game/OldWest/Content/Art/Survivors').rglob('*.uasset')})
# Import only known pure solver functions from the immutable reviewed source.
tree=ast.parse((SOURCE/'authoring-script.py').read_text())
wanted={'smooth','blend','hand_rotation','pose_arm','key','activate'}
definitions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in wanted]
assert {node.name for node in definitions}==wanted
exec(compile(ast.Module(body=definitions,type_ignores=[]),str(SOURCE/'authoring-script.py'),'exec'),globals())


def reset_study():
    global arm,scene,roots
    bpy.ops.wm.open_mainfile(filepath=str(source_blend),use_scripts=False)
    arm=bpy.data.objects['Survivor_Rig'];scene=bpy.context.scene
    roots={name:bpy.data.objects[name] for name in source_frames[134]['props']}
    for obj in bpy.data.objects:obj.animation_data_clear()
    for action in list(bpy.data.actions):bpy.data.actions.remove(action)
    assert len(arm.data.bones)==53


def apply_pose(frame):
    for name,data in source_frames[frame-1]['bones'].items():
        bone=arm.pose.bones[name];bone.rotation_mode='QUATERNION'
        bone.location=data['location'];bone.scale=data['scale']
        x,y,z,w=data['rotation_xyzw'];bone.rotation_quaternion=Quaternion((w,x,y,z))
    for name,data in source_frames[frame-1]['props'].items():
        obj=roots[name];obj.location=data['location_m'];obj.rotation_mode='QUATERNION'
        x,y,z,w=data['rotation_xyzw'];obj.rotation_quaternion=Quaternion((w,x,y,z))
    bpy.context.view_layer.update()


def turn_torso(radians,axis=(0,0,1)):
    bone=arm.pose.bones['mixamorig:Spine'];point=bone.head.copy()
    bone.matrix=Matrix.Translation(point) @ Quaternion(axis,radians).to_matrix().to_4x4() @ Matrix.Translation(-point) @ bone.matrix
    bpy.context.view_layer.update()


def record(frame,contacts):
    for bone in arm.pose.bones:
        bone.rotation_mode='QUATERNION'
        for channel in ('location','rotation_quaternion','scale'):bone.keyframe_insert(channel,frame=frame)
    for obj in roots.values():key(obj,frame)
    return {'frame':frame,'seconds':(frame-1)/30,'contacts':contacts,
            'bones':{bone.name:{'location':list(bone.location),'scale':list(bone.scale),
                               'rotation_xyzw':[bone.rotation_quaternion.x,bone.rotation_quaternion.y,bone.rotation_quaternion.z,bone.rotation_quaternion.w]}
                     for bone in arm.pose.bones},
            'props':{name:{'location_m':list(obj.location),'rotation_xyzw':[obj.rotation_quaternion.x,obj.rotation_quaternion.y,obj.rotation_quaternion.z,obj.rotation_quaternion.w]}
                     for name,obj in roots.items()}}


def export_animation(name,frames,directory):
    arm.animation_data_clear();arm.data.transform(Matrix.Scale(100,4))
    scene.unit_settings.scale_length=.01
    for frame in frames:
        for name_bone,data in frame['bones'].items():
            bone=arm.pose.bones[name_bone];bone.rotation_mode='QUATERNION';bone.location=Vector(data['location'])*100;bone.scale=data['scale']
            x,y,z,w=data['rotation_xyzw'];bone.rotation_quaternion=Quaternion((w,x,y,z))
            for channel in ('location','rotation_quaternion','scale'):bone.keyframe_insert(channel,frame=frame['frame'])
    arm.animation_data.action.name='Scientist_'+name+'_Cm'
    activate(arm);scene.frame_start=1;scene.frame_end=len(frames)
    path=directory/f'A_Scientist_{name}_Cm.fbx'
    bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,object_types={'ARMATURE'},add_leaf_bones=False,
        use_armature_deform_only=True,bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True,bake_anim_simplify_factor=0.,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z')
    return {'path':str(path),'sha256':sha(path),'frames':[1,len(frames)],'duration_seconds':(len(frames)-1)/30}


def studio(blend_path,directory,frames):
    bpy.ops.wm.open_mainfile(filepath=str(blend_path),use_scripts=False)
    scene=bpy.context.scene;scene.unit_settings.scale_length=1;scene.render.engine='CYCLES';scene.cycles.device='CPU'
    scene.cycles.samples=32;scene.cycles.use_denoising=True
    if hasattr(scene.cycles,'denoising_use_gpu'):scene.cycles.denoising_use_gpu=False
    scene.render.resolution_x=1280;scene.render.resolution_y=1080;scene.render.resolution_percentage=100
    world=bpy.data.worlds.new('Decision_CPU_Studio');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.1,.13,.15,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.3;scene.world=world
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.025))
    bpy.context.object.data.materials.append(bpy.data.materials['M_ScientistAnalysis_Dark'])
    for name,pos,power,size,color in [('Key',(-3,-4,5),700,3.5,(1,.88,.72)),('Fill',(3,-2,3),450,3,(.65,.8,1)),('Rim',(0,3,4),850,3,(.8,.93,1))]:
        data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;data.color=color
        obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj);obj.location=pos
        obj.rotation_euler=(Vector((0,-.15,1))-obj.location).to_track_quat('-Z','Y').to_euler()
    data=bpy.data.cameras.new('Decision_CPU_Camera');camera=bpy.data.objects.new('Decision_CPU_Camera',data)
    bpy.context.collection.objects.link(camera);scene.camera=camera;data.lens=64
    images=[]
    for frame in frames:
        scene.frame_set(frame)
        for view,pos,target in [('three-quarter',(2.8,-2.4,2.25),(0,-.24,1.04)),('contact',(1.3,-1.8,2.4),(0,-.34,1.15))]:
            camera.location=pos;camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
            path=directory/f'{frame:03d}-{view}.png';scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
            images.append({'frame':frame,'view':view,'path':str(path),'sha256':sha(path)})
    return images


reports=[]
for name in args.branches:
    directory=OUT/name;directory.mkdir(parents=True,exist_ok=True)
    blend_path=directory/f'Scientist_{name}_Candidate.blend'
    assert not blend_path.exists(), 'Preserve previous candidate; use a new output directory.'
    reset_study();rows=[];frame_count=87 if name=='SkipRecover' else 61
    right_base=Vector(source_frames[134]['contacts']['right']['palm_world_m'])
    left_base=Vector(source_frames[134]['contacts']['left']['palm_world_m'])
    output=Vector(source_frames[175]['contacts']['left']['palm_world_m'])
    offset=Vector((0,-.055,-.035))
    for frame in range(1,frame_count+1):
        apply_pose(frame+184 if name=='SkipRecover' else 135)
        if name in ('SortLeft','SortRight'):
            selected=0 if name=='SortLeft' else 2
            sample=Vector(source_frames[134]['props'][f'AnonymousSalvageSample_{selected+1}']['location_m'])
            pickup=sample-offset
            if name=='SortLeft':turn_torso(math.radians(-40)*smooth((frame-1)/22)*(1-smooth((frame-32)/21)))
            if frame<=23:
                t=(frame-1)/22;left=blend(left_base,pickup,frame,1,23)+Vector((0,0,.075*math.sin(math.pi*t)))
            elif frame<=38:left=blend(pickup,Vector((.10,-.385,1.23)),frame,23,38)
            elif frame<=53:left=blend(Vector((.10,-.385,1.23)),output,frame,38,53)
            else:left=output.copy()
            curl=1.3*smooth((frame-17)/6)*(1-smooth((frame-53)/8))
            right=right_base.copy()
            if name=='SortLeft':
                # Lift the held scanner clear before the other hand crosses
                # beneath it; retain an above-sample pickup approach.
                right.z+=.08*smooth((frame-1)/13)*(1-smooth((frame-38)/23))
                roots['HandScanner_GripAnchor'].location=right
            contacts={'right':pose_arm('Right',right,1.35),'left':pose_arm('Left',left,curl)}
            if 23<frame<=53:roots[f'AnonymousSalvageSample_{selected+1}'].location=left+offset
            elif frame>53:roots[f'AnonymousSalvageSample_{selected+1}'].location=output+offset
        elif name=='SkipRecover':
            # Same reviewed scanner/lid recovery, but no sample is selected.
            for index in range(3):roots[f'AnonymousSalvageSample_{index+1}'].location=source_frames[134]['props'][f'AnonymousSalvageSample_{index+1}']['location_m']
            if frame<=14:
                target=Vector(source_frames[197]['contacts']['left']['palm_world_m'])
                left=blend(left_base,target,frame,1,14)
                left_contact=pose_arm('Left',left,.12)
            else:left_contact=source_frames[frame+183]['contacts']['left']
            contacts={'right':source_frames[frame+183]['contacts']['right'],'left':left_contact}
        else:
            turn_torso(math.radians(.3)*math.sin((frame-1)/60*math.tau),(1,0,0))
            contacts={'right':pose_arm('Right',right_base,1.35),'left':pose_arm('Left',left_base,.12)}
        # Re-running the finite-iteration thumb solver on an already posed
        # hand must not alter a parked grip at every branch boundary.
        if name!='SkipRecover':
            for bone_name,data in source_frames[134]['bones'].items():
                if bone_name.startswith('mixamorig:RightHand') and bone_name!='mixamorig:RightHand':
                    bone=arm.pose.bones[bone_name];x,y,z,w=data['rotation_xyzw']
                    bone.rotation_quaternion=Quaternion((w,x,y,z))
        if frame in (1,frame_count):
            saved_props={key:(obj.location.copy(),obj.rotation_quaternion.copy()) for key,obj in roots.items()}
            apply_pose(135 if frame==1 or name=='WorkHold' else (271 if name=='SkipRecover' else 185))
            for prop_name,(location,rotation) in saved_props.items():
                roots[prop_name].location=location;roots[prop_name].rotation_quaternion=rotation
        rows.append(record(frame,contacts))
    arm.animation_data.action.name='Scientist_'+name+'_Candidate'
    scene.frame_start=1;scene.frame_end=frame_count;scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    (directory/'pose-and-prop-samples.json').write_text(json.dumps(rows,indent=2)+'\n')
    exported=export_animation(name,rows,directory)
    review_frames=[23,38,53] if name.startswith('Sort') else ([1,35,72] if name=='SkipRecover' else[1,16,46])
    report={'name':name,'status':'CPU_branch_candidate_visual_review_pending','source_blend_sha256':sha(source_blend),
            'blend':str(blend_path),'blend_sha256':sha(blend_path),'animation_export':exported,
            'selected_index':0 if name=='SortLeft' else (2 if name=='SortRight' else None),
            'loop':name=='WorkHold','bones':53,'expected_native_bones':54,
            'first_pose_source_frame':135,'final_pose_source_frame':271 if name=='SkipRecover' else (135 if name=='WorkHold' else 185),
            'props':'Same10 meshes/pivots/materials as reviewed core; use this branch dense prop transforms.',
            'renders':studio(blend_path,directory,review_frames) if args.render else[],
            'limitations':['CPU branch only; no native import or gameplay validation.','Unrevealed/absent samples must be hidden using actual public count.','Holster and actual effect/discard reactions are separate work.']}
    assert all(sha(p)==value for p,value in protected.items()),'Protected source/native asset changed'
    report['protected_source_and_native_assets_unchanged']=True
    (directory/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    reports.append(report)
    (OUT/'branches.json').write_text(json.dumps({'status':'CPU_candidates_native_pending','branches':reports,'protected_sha256':protected},indent=2)+'\n')
    print('SCIENTIST_DECISION_BRANCH_COMPLETE',name,flush=True)
