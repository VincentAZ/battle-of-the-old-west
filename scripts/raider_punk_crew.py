"""Append two library Punk rigs and fit seated gunner/driver poses to the Raider."""
from pathlib import Path
import math
import bpy
from mathutils import Matrix, Vector, Quaternion

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'art/characters/identity-punk-equipment-v2/punk/Punk.blend'


def apply_punk_crew():
    s=bpy.context.scene
    if bpy.data.collections.get('12 PUNK CREW'):return
    crew=bpy.data.collections.new('12 PUNK CREW');s.collection.children.link(crew)
    def bone(arm,name):return arm.pose.bones['mixamorig:'+name]
    def update():bpy.context.view_layer.update()
    def point(arm,name):return bone(arm,name).head.copy()
    def orient(arm,name,head,direction):
        pb=bone(arm,name);rest=pb.bone
        q=(rest.tail_local-rest.head_local).normalized().rotation_difference(Vector(direction).normalized())
        pb.matrix=Matrix.Translation(Vector(head)) @ q.to_matrix().to_4x4() @ rest.matrix_local.to_quaternion().to_matrix().to_4x4()
        update()
    def rotate_world(arm,name,rotation):
        pb=bone(arm,name);mat=pb.matrix.copy();head=mat.translation.copy()
        mat=rotation.to_matrix().to_4x4()@mat;mat.translation=head;pb.matrix=mat;update()
    def limb(arm,upper,lower,end,target,pole):
        start=point(arm,upper);target=Vector(target)
        l1=bone(arm,upper).bone.length;l2=bone(arm,lower).bone.length
        axis=(target-start).normalized();d=min((target-start).length,l1+l2-.001)
        target=start+axis*d
        a=(l1*l1-l2*l2+d*d)/(2*d);h=math.sqrt(max(0,l1*l1-a*a))
        bend=Vector(pole)-start;bend=(bend-axis*bend.dot(axis)).normalized()
        elbow=start+axis*a+bend*h
        orient(arm,upper,start,elbow-start);orient(arm,lower,elbow,target-elbow)
        return target
    def character(role):
        with bpy.data.libraries.load(str(SOURCE),link=False) as (src,dst):dst.objects=src.objects
        objects=[o for o in dst.objects if o and o.type in {'ARMATURE','MESH','CURVE'}]
        for o in objects:
            crew.objects.link(o);o.name=role+' | '+o.name;o.hide_render=False;o.hide_set(False)
            o.animation_data_clear();o['asset']='Raider punk crew';o['library_source']=str(SOURCE.relative_to(ROOT))
            if o.type=='MESH' and o.data.shape_keys:
                o.data.shape_keys.animation_data_clear()
                for key in o.data.shape_keys.key_blocks:
                    if key.name!='Basis':key.value=0
        arm=next(o for o in objects if o.type=='ARMATURE');arm.animation_data_clear()
        for pb in arm.pose.bones:
            pb.matrix_basis=Matrix.Identity(4)
            for c in list(pb.constraints):pb.constraints.remove(c)
        # Make imported image paths independent of the output blend directory.
        for o in objects:
            if o.type!='MESH':continue
            for material in o.data.materials:
                if not material or not material.use_nodes:continue
                for node in material.node_tree.nodes:
                    if node.type=='TEX_IMAGE' and node.image and not node.image.packed_file:
                        image=node.image
                        path=Path(bpy.path.abspath(image.filepath))
                        if not path.is_file():
                            path=SOURCE.parent/'textures'/Path(image.filepath).name
                        if not path.is_file():raise FileNotFoundError(image.filepath)
                        image.filepath=str(path);image.pack()
        update();return arm,objects

    gunner,go=character('Punk 1 — roof gunner')
    hips=bone(gunner,'Hips');mat=hips.matrix.copy();mat.translation=Vector((0,.45,2.12));hips.matrix=mat;update()
    # Small forward lean keeps the shoulders over the gun grips.
    rotate_world(gunner,'Spine',Quaternion((1,0,0),.12))
    rotate_world(gunner,'Head',Quaternion((1,0,0),.10))
    for side,sign in [('Left',1),('Right',-1)]:
        wrist=limb(gunner,side+'Arm',side+'ForeArm',side+'Hand',(sign*.16,.31,2.33),(sign*.40,.47,2.27))
        orient(gunner,side+'Hand',wrist,(0,-1,-.20))
        ankle=limb(gunner,side+'UpLeg',side+'Leg',side+'Foot',(sign*.34,-.27,2.09),(sign*.35,.05,2.65))
        orient(gunner,side+'Foot',ankle,(0,-.128,-.085))
        for finger in ('Index','Middle','Ring','Pinky'):
            for joint in (1,2,3):
                pb=bone(gunner,side+'Hand'+finger+str(joint));pb.rotation_mode='XYZ';pb.rotation_euler.x=.65 if joint>1 else .35
    update()

    driver,do=character('Punk 2 — driver')
    hips=bone(driver,'Hips');mat=hips.matrix.copy();mat.translation=Vector((-.68,.02,1.12));hips.matrix=mat;update()
    rotate_world(driver,'Spine',Quaternion((0,1,0),-.65))
    # Return the face upright: both eyes look along the direction of travel (-Y).
    head=bone(driver,'Head');orient(driver,'Head',head.head,(0,0,1))
    for side,sign in [('Left',1),('Right',-1)]:
        ankle=limb(driver,side+'UpLeg',side+'Leg',side+'Foot',(-.49+sign*.13,-.49,.84),(-.49+sign*.18,-.24,1.20))
        orient(driver,side+'Foot',ankle,(0,-.128,-.085))
    wrist=limb(driver,'LeftArm','LeftForeArm','LeftHand',(-.33,-.26,1.45),(-.31,.10,1.30))
    orient(driver,'LeftHand',wrist,(-.3,-1,-.15))
    wrist=limb(driver,'RightArm','RightForeArm','RightHand',(-.94,-.26,1.48),(-1.09,.02,1.47))
    orient(driver,'RightHand',wrist,(0,-1,0))
    for side in ('Left','Right'):
        for finger in ('Index','Middle','Ring','Pinky'):
            for joint in (1,2,3):
                pb=bone(driver,side+'Hand'+finger+str(joint));pb.rotation_mode='XYZ';pb.rotation_euler.x=.50 if side=='Left' else .18
    update()
    # Pose-specific clothing/body correction keeps the seated torso inside the
    # closed lower door while shoulders and the outside arm pass through the
    # open window. Store it as an editable corrective shape, not a mesh bake.
    for ob in do:
        if ob.type!='MESH' or not ('Survivor_Body' in ob.name or 'Punk_Outfit_Assembly' in ob.name):continue
        deform={g.index:driver.pose.bones.get(g.name) for g in ob.vertex_groups}
        transforms={i:pb.matrix @ pb.bone.matrix_local.inverted() for i,pb in deform.items() if pb}
        corrected=[]
        for vertex in ob.data.vertices:
            torso=sum(g.weight for g in vertex.groups if deform.get(g.group) and any(k in deform[g.group].name for k in ('Spine','Hips')))
            if torso<.4:continue
            influences=[g for g in vertex.groups if g.group in transforms]
            total=sum(g.weight for g in influences)
            if total<.01:continue
            skin=Matrix(((0,0,0,0),)*4)
            for g in influences:
                tm=transforms[g.group];weight=g.weight/total
                for row in range(4):
                    for c in range(4):skin[row][c]+=tm[row][c]*weight
            posed=skin @ vertex.co
            t=max(0,min(1,(posed.z-1.43)/.10));limit=-.795-.30*t*t
            if posed.z<1.53 and -.60<posed.y<.56 and posed.x<limit:
                posed.x=limit;corrected.append((vertex.index,skin.inverted_safe() @ posed))
        if corrected:
            if not ob.data.shape_keys:ob.shape_key_add(name='Basis')
            key=ob.shape_key_add(name='Seated torso clearance at door');key.value=1
            for index,co in corrected:key.data[index].co=co
    # Extend the driver's mirror forward so it does not hide his face.
    for ob in s.objects:
        if ob.name.startswith(('Wing mirror housing','Reflective mirror')) and ob.location.x<0:ob.location.y-=.36
        if ob.name.startswith('Mirror arm') and ob.type=='CURVE':
            for spline in ob.data.splines:
                if spline.points[0].co.x<0:spline.points[-1].co.y-=.36
    update()
    # The driver's side is -X, matching the existing wheel and seat location.
    for o in list(s.objects):
        if o.name.startswith('Armored side window') and o.type=='MESH':
            avg=sum((o.matrix_world@v.co).x for v in o.data.vertices)/len(o.data.vertices)
            if avg<0:
                o.hide_render=True;o.hide_set(True);o['state']='Window rolled fully down for driver'
    # Reframe to show the open driver's window and complete seated roof silhouette.
    for name,loc,target,lens in [
        ('01 HERO front three-quarter',(-6.6,-8.8,4.5),(0,0,1.48),52),
        ('03 FRONT low angle',(-5.0,-7.8,2.9),(0,-.1,1.53),54),
    ]:
        cam=bpy.data.objects.get(name)
        if cam:cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=lens
    data=bpy.data.cameras.new('Crew detail');cam=bpy.data.objects.new('04 CREW driver and gunner',data);s.collection.objects.link(cam)
    cam.location=(-3.8,-4.4,3.05);cam.rotation_euler=(Vector((-.25,.0,2.03))-cam.location).to_track_quat('-Z','Y').to_euler();data.lens=63
    s['Crew source']=str(SOURCE.relative_to(ROOT));s['Crew staging']='Punk 1 seated on roof at gun; Punk 2 seated driving, left window down, head out and facing forward.'
    update()
    report={}
    for role,arm in [('gatling_gunner',gunner),('driver',driver)]:
        report[role]={name:list(point(arm,name)) for name in ('Hips','Head','LeftHand','RightHand','LeftFoot','RightFoot')}
    print('PUNK_CREW_POSE',report,flush=True)
    return report
