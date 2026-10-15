"""Make a separate, sourced draft-cattle derivative and grounded walk in Mixar."""
import hashlib
import json
import math
from pathlib import Path
import bpy
from mathutils import Matrix, Quaternion, Vector

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'art/western/stampede/animation-v001/Longhorn-Animated.blend'
EVIDENCE=ROOT/'research/western-presentation/delivery-oxen.json'
OUT=ROOT/'art/western/delivery/oxen-v002'
FPS=30
STANCE=.70
STRIDE=.50
END=36


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def smooth(t):return t*t*(3-2*t)
def clamp(t):return max(0,min(1,t))


def main():
    assert 'mixar' in Path(bpy.app.binary_path).name.lower()
    brief=json.loads(EVIDENCE.read_text())
    before=sha(SOURCE);assert before==brief['render_brief']['preserved_source_sha256']
    OUT.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    scene=bpy.context.scene
    animal=bpy.data.objects['Longhorn'];animal.name='DraftOx'
    arm=next(o for o in scene.objects if o.type=='ARMATURE');arm.name='DraftOxArmature'
    arm.animation_data_clear()
    for p in arm.pose.bones:p.matrix_basis=Matrix.Identity(4)
    center=.052734
    changed_horn=0
    for v in animal.data.vertices:
        x,y,z=v.co;dx=x-center
        # Only the upper, lateral horn region is shortened; smooth transitions
        # retain the original closed topology and separate ear silhouette.
        weight=smooth(clamp((z-1.66)/.10))*smooth(clamp((-y-.60)/.10))
        excess=max(0,abs(dx)-.25)
        if excess and weight:
            dx-=math.copysign(excess*.66*weight,dx)
            z-=max(0,z-1.76)*.48*weight
            changed_horn+=1
        v.co=(center+dx*1.22,y,z)
    # The whole torso/limb spread is widened with the skeleton. This is an
    # explicitly reconstructed draft-cattle appearance, not a breed conversion.
    bpy.context.view_layer.objects.active=arm
    bpy.ops.object.mode_set(mode='EDIT')
    for b in arm.data.edit_bones:
        if b.name=='Root':continue
        b.head.x=center+(b.head.x-center)*1.22
        b.tail.x=center+(b.tail.x-center)*1.22
    bpy.ops.object.mode_set(mode='OBJECT')
    rest={b.name:b.matrix_local.copy() for b in arm.data.bones}
    validation={};actions={}
    for clip,end in [('Idle',90),('Walk',END)]:
        action=bpy.data.actions.new('DraftOx_'+clip);action.use_fake_user=True
        arm.animation_data_create();arm.animation_data.action=action;actions[clip]=action
        samples=[];contact_error=[];world_stance_error=[];lows=[]
        last_contacts={}
        for frame in range(end+1):
            scene.frame_set(frame);phase=frame/end if frame<end else 0
            for p in arm.pose.bones:p.matrix_basis=Matrix.Identity(4)
            bob=-.065+.004*math.cos(4*math.pi*phase) if clip=='Walk' else -.004+.003*math.cos(2*math.pi*phase)
            arm.pose.bones['Body'].matrix=Matrix.Translation((0,0,bob))@rest['Body']
            for i in range(7):
                arm.pose.bones['Tail_'+str(i)].rotation_quaternion=Quaternion((1,0,0),math.radians(1.2)*math.sin(2*math.pi*phase-i*.3))
            bpy.context.view_layer.update();contacts={}
            for leg,offset in [('Hind_L',0),('Front_L',.25),('Hind_R',.5),('Front_R',.75)]:
                family,side=leg.split('_')
                a=arm.pose.bones[family+'Upper_'+side];b=arm.pose.bones[family+'Lower_'+side]
                foot=arm.pose.bones[family+'Foot_'+side]
                t=(phase-offset)%1;stance=clip=='Idle' or t<=STANCE
                if clip=='Idle':dy=height=0
                elif stance:dy=-STRIDE/2+STRIDE*t/STANCE;height=0
                else:
                    swing=(t-STANCE)/(1-STANCE)
                    dy=STRIDE/2-STRIDE*smooth(swing);height=.095*math.sin(math.pi*swing)**1.5
                target=rest[foot.name].translation+Vector((0,dy,height))
                shoulder=a.head.copy();delta=target-shoulder;distance=delta.length;unit=delta.normalized()
                l1=arm.data.bones[a.name].length;l2=(rest[foot.name].translation-rest[b.name].translation).length
                assert distance<l1+l2+.0002,(clip,frame,leg,distance,l1+l2)
                pole=Vector((0,-1 if family=='Front' else 1,0));pole=(pole-unit*pole.dot(unit)).normalized()
                along=(l1*l1-l2*l2+distance*distance)/(2*distance)
                knee=shoulder+unit*along+pole*math.sqrt(max(0,l1*l1-along*along))
                for pb,head,tail in [(a,shoulder,knee),(b,knee,target)]:
                    old=arm.data.bones[pb.name].tail_local-arm.data.bones[pb.name].head_local
                    matrix=old.rotation_difference(tail-head).to_matrix().to_4x4()@rest[pb.name]
                    matrix.translation=head;pb.matrix=matrix;bpy.context.view_layer.update()
                matrix=rest[foot.name].copy();matrix.translation=target;foot.matrix=matrix;bpy.context.view_layer.update()
                actual=foot.head.copy()
                if stance:contact_error.append((actual-target).length)
                # For the authored constant-speed walk, planted feet must not
                # slide in world space between consecutive stance samples.
                world_y=actual.y-frame/end*STRIDE/STANCE if clip=='Walk' else actual.y
                previous=last_contacts.get(leg)
                if stance and previous and previous['stance'] and t>previous['t']:
                    world_stance_error.append(abs(world_y-previous['world_y']))
                last_contacts[leg]=dict(stance=stance,t=t,world_y=world_y)
                contacts[leg]=dict(stance=stance,target=list(target),actual=list(actual))
            for p in arm.pose.bones:
                for data_path in ['location','rotation_quaternion','scale']:
                    p.keyframe_insert(data_path=data_path,frame=frame,group=p.name)
            deps=bpy.context.evaluated_depsgraph_get();obj=animal.evaluated_get(deps);mesh=obj.to_mesh()
            low=min(v.co.z for v in mesh.vertices);lows.append(low);obj.to_mesh_clear()
            samples.append(dict(frame=frame,contacts=contacts,min_vertex_z_m=low))
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:key.interpolation='LINEAR'
        poses=[]
        for frame in [0,end]:
            scene.frame_set(frame);bpy.context.view_layer.update();poses.append({p.name:p.matrix.copy() for p in arm.pose.bones})
        loop=max(abs(poses[0][n][i][j]-poses[1][n][i][j]) for n in poses[0] for i in range(4) for j in range(4))
        assert loop<.00001 and max(contact_error)<.00001
        assert max(world_stance_error,default=0)<.00001 and min(lows)>-.002
        validation[clip]=dict(duration_seconds=end/FPS,loop_matrix_error=loop,
            max_stance_target_error_m=max(contact_error),max_world_stance_step_error_m=max(world_stance_error,default=0),
            minimum_vertex_z_m=min(lows),samples=samples)
    scene.render.fps=FPS;scene.frame_start=0;scene.frame_end=END
    arm.animation_data.action=actions['Walk'];scene.frame_set(0)
    animal['review_status']='Draft cattle derivative: appearance and walk require visual review'
    animal['historical_identity']='Reconstructed generic red-and-white draft cattle; no exact breed claimed'
    arm['walk_reference_speed_mps']=STRIDE/STANCE/(END/FPS)
    project=OUT/'Draft-Ox.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
    # Source views use a new neutral studio, independent of the saved rig.
    for obj in list(scene.objects):
        if obj not in [animal,arm]:bpy.data.objects.remove(obj,do_unlink=True)
    scene.world=bpy.data.worlds.new('DraftReview');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.6,.72,1,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.3
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.01))
    floor=bpy.context.object;mat=bpy.data.materials.new('DraftReviewFloor');mat.use_nodes=True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.18,.22,.28,1)
    floor.data.materials.append(mat)
    for pos,power,size in [((3,-4,5),700,4),((-3,1,4),500,4),((0,4,5),700,3)]:
        bpy.ops.object.light_add(type='AREA',location=pos);light=bpy.context.object;light.data.energy=power;light.data.size=size
        light.rotation_euler=(Vector((0,0,1))-light.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=4.3;scene.camera=cam
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=32;scene.cycles.use_denoising=True
    scene.render.resolution_x=1200;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=0
    views=[('front',(0,-6,2.5),'Idle',0),('side',(6,0,2.5),'Idle',0),('quarter',(4,-5,3),'Idle',0)]
    views += [('walk-%02d'%f,(6,-.5,2.1),'Walk',f) for f in [0,9,18,27]]
    for name,pos,clip,frame in views:
        arm.animation_data.action=actions[clip];scene.frame_set(frame)
        cam.location=pos;cam.rotation_euler=(Vector((0,0,1))-cam.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
    assert sha(SOURCE)==before
    (OUT/'animation-validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    (OUT/'manifest.json').write_text(json.dumps(dict(source_sha256=before,source_preserved=True,
        project_sha256=sha(project),evidence_sha256=sha(EVIDENCE),author_sha256=sha(Path(__file__)),
        horn_region_vertices=changed_horn,walk_reference_speed_mps=STRIDE/STANCE/(END/FPS),
        visual_review='pending',native_imported=False),indent=2)+'\n')
    print('DELIVERY_OXEN_AUTHORED',flush=True)


if __name__=='__main__':main()
