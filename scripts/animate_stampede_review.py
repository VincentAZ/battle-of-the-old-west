"""Author the approved longhorn's Stage B rig and in-place loops inside Mixar.

Uses Mixar's quadruped rig as a weight/joint guide. The approved mesh and packed
2K material are retained verbatim. Run with Mixar --background --factory-startup
--python-exit-code 1 --python scripts/animate_stampede_review.py.
"""
import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector, Quaternion
from mathutils.kdtree import KDTree
from mixar.modules.hunyuan.constants import ANIMATE_IMPORT_OPTIONS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/western/stampede/animation-v001'
APPROVED = OUT.parent / 'review-v001/review/Longhorn-Review.blend'
FPS = 30


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def smooth(t):
    return t*t*(3-2*t)


def bone_map(name):
    if name == 'tripo::Root' or name in [f'bone_{i}' for i in range(45,51)]:
        return 'Body'
    if name.startswith('tripo::Spine_'):
        return name.replace('tripo::', '')
    if 'Head_' in name or name in ['bone_21','bone_23','bone_25']:
        return 'Head'
    if name in ['bone_6','bone_12']:
        return 'Shoulder_L' if name == 'bone_6' else 'Shoulder_R'
    if '_Limb_' in name:
        prefix, side, _, index = name.replace('tripo::','').split('_')
        return ('Front' if prefix=='0' else 'Hind') + ['Upper','Lower','Foot'][min(int(index),2)] + '_' + side[0]
    if name.startswith('bone_') and 38 <= int(name[5:]) <= 44:
        return 'Tail_'+str(int(name[5:])-38)
    raise ValueError(name)


def main():
    assert 'mixar' in Path(bpy.app.binary_path).name.lower()
    approval=json.loads((OUT/'appearance-approval.json').read_text())
    # Approval record records the immutable source, even across authoring retries.
    assert sha(APPROVED) in json.dumps(approval)
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(OUT/'longhorn-rigged-original.glb'), **ANIMATE_IMPORT_OPTIONS)
    raw_arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    raw_mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
    # Provider normalized length to one meter. Restore the approved three meters.
    raw_world=Matrix.Scale(3,4) @ raw_arm.matrix_world
    guide={b.name: {'head':raw_world@b.head_local, 'tail':raw_world@b.tail_local,
                   'parent':b.parent.name if b.parent else None,
                   'matrix':raw_world@b.matrix_local} for b in raw_arm.data.bones}
    tree=KDTree(len(raw_mesh.data.vertices))
    for v in raw_mesh.data.vertices:
        tree.insert(3*(raw_mesh.matrix_world@v.co),v.index)
    tree.balance()
    raw_weights=[]
    for v in raw_mesh.data.vertices:
        weights={}
        for item in v.groups:
            name=bone_map(raw_mesh.vertex_groups[item.group].name)
            weights[name]=weights.get(name,0)+item.weight
        raw_weights.append(weights)
    # Append the approved studio, mesh and exact material; discard provider mesh.
    with bpy.data.libraries.load(str(APPROVED),link=False) as (src,dst):
        dst.objects=list(src.objects)
        dst.worlds=list(src.worlds)
    for obj in dst.objects:
        bpy.context.scene.collection.objects.link(obj)
    animal=next(o for o in dst.objects if o.name.startswith('Longhorn_Appearance'))
    animal.name='Longhorn'
    scene=bpy.context.scene
    scene.world=dst.worlds[0]
    scene.camera=next(o for o in dst.objects if o.type=='CAMERA' and 'three-quarter' in o.name)
    bpy.data.objects.remove(raw_mesh,do_unlink=True)
    bpy.data.objects.remove(raw_arm,do_unlink=True)
    data=bpy.data.armatures.new('Longhorn_Skeleton')
    arm=bpy.data.objects.new('Armature',data)
    scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active=arm;arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    root=data.edit_bones.new('Root');root.head=(0,0,0);root.tail=(0,0,.25)
    body=data.edit_bones.new('Body');body.head=(.0527,.9,1.5);body.tail=(.0527,.9,1.8);body.parent=root
    created={'Root','Body'}
    for name,g in guide.items():
        mapped=bone_map(name)
        if mapped in created:continue
        b=data.edit_bones.new(mapped)
        b.head=g['head']; b.tail=g['tail']
        if mapped=='Head': b.tail=b.head+Vector((0,-.35,0))
        if 'Foot' in mapped: b.tail=b.head+Vector((0,-.16,-.15))
        parent=bone_map(g['parent']) if g['parent'] else 'Body'
        b.parent=data.edit_bones[parent]
        b.align_roll(g['matrix'].to_3x3()@Vector((0,0,1)))
        created.add(mapped)
    bpy.ops.object.mode_set(mode='OBJECT')
    distances=[]; corrections=0
    for name in created:animal.vertex_groups.new(name=name)
    # Geometric filtering removes remote hoof/horn weights from the auto-rigger.
    for v in animal.data.vertices:
        co=animal.matrix_world@v.co
        _,index,distance=tree.find(co);distances.append(distance)
        weights=raw_weights[index].copy()
        leg=('Front' if co.y < .35 else 'Hind')
        side='L' if co.x>.075 else 'R'
        if co.z < .55 and co.y < 1.32:
            allowed={leg+part+'_'+side for part in ('Upper','Lower','Foot')}
            weights={k:w for k,w in weights.items() if k in allowed}
            if not weights:weights={leg+'Foot_'+side:1}
            # Rigid hoof below the fetlock; blend to the lower leg above it.
            rigid=1-smooth(max(0,min(1,(co.z-.17)/.20)))
            total=sum(weights.values())
            weights={k:w/total*(1-rigid) for k,w in weights.items()}
            weights[leg+'Foot_'+side]=weights.get(leg+'Foot_'+side,0)+rigid
            corrections+=1
        if co.y < -.96 and co.z>1.53 or co.y< -1.20:
            weights={'Head':1.0};corrections+=1
        weights={k:w for k,w in weights.items() if w>.001}
        weights=dict(sorted(weights.items(),key=lambda x:x[1],reverse=True)[:4])
        total=sum(weights.values());assert total>0
        for name,w in weights.items():animal.vertex_groups[name].add([v.index],w/total,'REPLACE')
    assert max(distances)<.00001,max(distances)
    animal.parent=arm;animal.matrix_parent_inverse=Matrix.Identity(4)
    modifier=animal.modifiers.new('Longhorn skin','ARMATURE');modifier.object=arm
    modifier.use_deform_preserve_volume=False
    arm.show_in_front=True;arm.data.display_type='STICK'
    for p in arm.pose.bones:p.rotation_mode='QUATERNION'
    rest={b.name:b.matrix_local.copy() for b in arm.data.bones}
    # Exact first/last pose is authored, plus a static origin Root for Unreal.
    clips=[('Idle',120),('Run',24)]
    validation={}
    for clip,end in clips:
        arm.animation_data_create()
        action=bpy.data.actions.new('Longhorn_'+clip);action.use_fake_user=True
        arm.animation_data.action=action
        scene.frame_start=0;scene.frame_end=end
        samples=[];contact_error=[];underfloor=[]
        for frame in range(end+1):
            scene.frame_set(frame)
            phase=frame/end if frame<end else 0
            for p in arm.pose.bones:p.matrix_basis=Matrix.Identity(4)
            if clip=='Idle':
                bob=-.005+.005*math.sin(2*math.pi*phase)
                pitch=0
            else:
                bob=-.14+.025*math.cos(4*math.pi*(phase-.18))
                pitch=math.radians(1.8)*math.sin(2*math.pi*phase)
            body_pose=Matrix.Translation((0,0,bob)) @ Matrix.Translation(rest['Body'].translation) @ Matrix.Rotation(pitch,4,'X') @ Matrix.Translation(-rest['Body'].translation) @ rest['Body']
            arm.pose.bones['Body'].matrix=body_pose
            bpy.context.view_layer.update()
            # Breathing is subtle; skull/horns remain one rigid segment.
            p=arm.pose.bones['Spine_5']
            p.rotation_quaternion=Quaternion((1,0,0), math.radians(.7 if clip=='Idle' else 1.8)*math.sin(2*math.pi*(phase+.15)))
            p=arm.pose.bones['Head']
            p.rotation_quaternion=Quaternion((0,1,0), math.radians(1.8 if clip=='Idle' else .7)*math.sin(2*math.pi*phase))
            for i in range(7):
                arm.pose.bones['Tail_'+str(i)].rotation_quaternion=Quaternion((1,0,0), math.radians(2.0 if clip=='Idle' else 3.5)*math.sin(2*math.pi*phase-i*.35))
            bpy.context.view_layer.update()
            contacts={}
            for leg,offset in [('Hind_L',0),('Hind_R',.12),('Front_L',.44),('Front_R',.56)]:
                family,side=leg.split('_')
                a=arm.pose.bones[family+'Upper_'+side]
                b=arm.pose.bones[family+'Lower_'+side]
                foot=arm.pose.bones[family+'Foot_'+side]
                base=rest[foot.name].translation.copy()
                t=(phase-offset)%1
                stance=clip=='Idle' or t<=.40
                if clip=='Idle':dy=height=0
                elif stance:
                    dy=-.36+.72*t/.40; height=0
                else:
                    swing=(t-.40)/.60
                    dy=.36-.72*smooth(swing)
                    height=.32*math.sin(math.pi*swing)**1.5
                target=base+Vector((0,dy,height))
                shoulder=a.head.copy()
                delta=target-shoulder
                l1=arm.data.bones[a.name].length
                l2=(rest[foot.name].translation-rest[b.name].translation).length
                distance=delta.length;unit=delta.normalized()
                assert distance<l1+l2+.0002,(clip,frame,leg,distance,l1+l2)
                # Carpal joints fold toward the head; hocks point toward the tail.
                pole=Vector((0,-1 if family=='Front' else 1,0))
                pole=(pole-unit*pole.dot(unit)).normalized()
                along=(l1*l1-l2*l2+distance*distance)/(2*distance)
                bend=math.sqrt(max(0,l1*l1-along*along))
                knee=shoulder+unit*along+pole*bend
                for pb,head,tail in [(a,shoulder,knee),(b,knee,target)]:
                    old_dir=arm.data.bones[pb.name].tail_local-arm.data.bones[pb.name].head_local
                    rot=old_dir.rotation_difference(tail-head).to_matrix().to_4x4()
                    matrix=rot@rest[pb.name];matrix.translation=head
                    pb.matrix=matrix
                    bpy.context.view_layer.update()
                matrix=rest[foot.name].copy();matrix.translation=target
                foot.matrix=matrix
                bpy.context.view_layer.update()
                contacts[leg]={'stance':stance,'target':list(target),'actual':list(foot.head)}
                if stance:contact_error.append((foot.head-target).length)
            for p in arm.pose.bones:
                p.keyframe_insert(data_path='location',frame=frame,group=p.name)
                p.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=p.name)
                p.keyframe_insert(data_path='scale',frame=frame,group=p.name)
            deps=bpy.context.evaluated_depsgraph_get()
            evaluated=animal.evaluated_get(deps).to_mesh()
            low=min(v.co.z for v in evaluated.vertices)
            underfloor.append(low)
            animal.evaluated_get(deps).to_mesh_clear()
            samples.append({'frame':frame,'phase':phase,'contacts':contacts,
                            'root_matrix':[list(row) for row in arm.pose.bones['Root'].matrix],
                            'min_vertex_z_m':low})
        # Linear subframe interpolation; densely sampled quaternion curves.
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:key.interpolation='LINEAR'
        poses=[]
        for frame in [0,end]:
            scene.frame_set(frame);bpy.context.view_layer.update()
            poses.append({p.name:p.matrix.copy() for p in arm.pose.bones})
        loop_error=max(abs(poses[0][n][i][j]-poses[1][n][i][j]) for n in poses[0] for i in range(4) for j in range(4))
        assert loop_error<.00001,loop_error
        validation[clip]={'frames_including_duplicate_endpoint':end+1,'fps':FPS,'duration_seconds':end/FPS,
                          'loop_matrix_error':loop_error,'max_stance_target_error_m':max(contact_error),
                          'minimum_vertex_z_m':min(underfloor),'samples':samples}
    scene.render.fps=FPS;scene.frame_start=0;scene.frame_end=120
    arm.animation_data.action=bpy.data.actions['Longhorn_Idle'];scene.frame_set(0)
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24;scene.cycles.use_denoising=True
    scene.render.threads_mode='FIXED';scene.render.threads=12
    scene.render.resolution_x=960;scene.render.resolution_y=720;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
    animal['review_status']='Stage B: animation review; appearance approved'
    arm['animation_notes']='In-place. Root fixed at origin. Run reference speed 2.25 m/s; presentation controls actor movement.'
    bpy.ops.object.select_all(action='DESELECT');animal.select_set(True);arm.select_set(True);bpy.context.view_layer.objects.active=arm
    project=OUT/'Longhorn-Animated.blend'
    bpy.data.orphans_purge(do_recursive=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(project))
    animal.data.calc_loop_triangles()
    manifest={'stage':'B: animated single-animal review','status':'awaiting_animation_review',
              'authoring_application':bpy.app.binary_path,'application_version':bpy.app.version_string,
              'approved_source_sha256':sha(APPROVED),'rig_source_sha256':sha(OUT/'longhorn-rigged-original.glb'),
              'project':project.name,'project_sha256':sha(project),'triangles':len(animal.data.loop_triangles),
              'vertices':len(animal.data.vertices),'materials':1,'bones':len(arm.data.bones),'max_weights_per_vertex':4,
              'rig_scale_restoration':3,'weight_transfer_max_distance_m':max(distances),
              'geometric_weight_cleanup_vertices':corrections,'root_motion':False,
              'heading':'-Y','up':'Z','units':'meters','run_reference_speed_mps':2.25,
              'animations':{k:{a:b for a,b in v.items() if a!='samples'} for k,v in validation.items()},
              'textures':[{'name':i.name,'size':list(i.size),'packed':bool(i.packed_file)} for i in bpy.data.images if i.users and i.type=='IMAGE'],
              'unreal_imported':False}
    (OUT/'animation-validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('STAMPEDE_ANIMATED',json.dumps(manifest),flush=True)


if __name__=='__main__':main()
