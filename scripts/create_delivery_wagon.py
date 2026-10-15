"""Author the sourced straight-box wagon locally, preserving previous assets."""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import create_trouble_landscapes as geo
from create_trouble_objects import box,rod,curve
from create_trouble_schemes import ring,beam

OUT=ROOT/'art/western/delivery/wagon-v004'
EVIDENCE=ROOT/'research/western-presentation/delivery-wagon.json'
PALETTE={'Blue':(.008,.065,.38),'BlueEdge':(.006,.035,.16),'Red':(.52,.009,.004),
         'Wood':(.43,.23,.08),'WoodLight':(.63,.40,.18),'Iron':(.025,.03,.034),
         'Canvas':(.87,.84,.75),'Rope':(.39,.23,.09)}


def wheel(name,radius,spokes,location):
    start=len(geo.PARTS)
    ring('Felloe',radius-.012,.09,.09,(0,0,0),'Red','X')
    ring('IronTire',radius,.098,.017,(0,0,0),'Iron','X')
    rod('Hub',(-.14,0,0),(.14,0,0),.105,'Red')
    for a in (-.115,.115):ring('HubBand',.111,.025,.014,(a,0,0),'Iron','X')
    for i in range(spokes):
        a=i*math.tau/spokes
        # Shallow dish follows the timber wheel's spokes from hub to felloe.
        beam('Spoke',(-math.copysign(.025,location[0]),.075*math.cos(a),.075*math.sin(a)),
            (0,(radius-.07)*math.cos(a),(radius-.07)*math.sin(a)),.039,.044,'Red')
    rod('AxleEnd',(-.16,0,0),(.16,0,0),.034,'Iron')
    for obj in geo.PARTS[start:]:obj.location+=Vector(location)
    return join(name,geo.PARTS[start:],location)


def join(name,parts,origin=(0,0,0)):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:obj.select_set(True)
    bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();obj=bpy.context.object
    obj.name=name;bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bpy.context.scene.cursor.location=origin;bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    obj.data.calc_loop_triangles();return obj


def wagon():
    # The ground pivot is centred under the box. Front is authored negative Y.
    for i in range(9):
        box('FloorPlank',(-.496+i*.124,0,.93),(.121,3.66,.06),'WoodLight',.004)
        for y in (-1.46,-.72,0,.72,1.46):
            rod('FloorNail',(-.496+i*.124,y,.961),(-.496+i*.124,y,.963),.004,'Iron')
    for x in (-.59,.59):
        for i in range(4):box('BoxSide',(x,0,1.02+i*.142),(.065,3.70,.137),'Blue',.004)
        for y in (-1.79,-.90,0,.90,1.79):
            box('SideStake',(x*1.057,y,1.21),(.044,.085,.65),'BlueEdge',.003)
            for z in (.99,1.40):rod('StakeBolt',(x*1.07,y,z),(x*1.12,y,z),.010,'Iron')
        box('TopRail',(x,0,1.54),(.09,3.75,.06),'Blue',.005)
        box('BoxRunner',(x*.76,0,.84),(.13,3.63,.14),'Wood',.005)
    for y in (-1.83,1.83):
        for i in range(4):box('EndBoard',(0,y,1.02+i*.142),(1.11,.06,.137),'Blue',.004)
        for x in (-.44,.44):box('EndBatten',(x,y*1.025,1.22),(.08,.035,.59),'BlueEdge',.003)
    # Front axle turns under a kingpin; rear axle and reach stay fixed.
    for y,z in ((-1.25,.55),(1.10,.70)):
        box('TimberAxle',(0,y,z),(1.59,.13,.14),'Red',.014)
        rod('AxleStub',(-.96,y,z),(.96,y,z),.035,'Iron')
        box('Bolster',(0,y,.79),(1.33,.16,.15),'Red',.007)
        for x in (-.55,.55):box('AxleStrap',(x,y,z),(.065,.147,.155),'Iron',.004)
    box('Reach',(0,.02,.65),(.14,2.69,.13),'Red',.010)
    box('FrontAxleBed',(0,-1.25,.66),(.62,.17,.14),'Red',.007)
    ring('FifthWheel',.25,.05,.065,(0,-1.25,.715),'Iron')
    rod('KingPin',(0,-1.25,.48),(0,-1.25,.91),.025,'Iron')
    for x in (-.42,.42):
        beam('Hound',(x,-1.19,.65),(x*.30,-2.15,.73),.075,.10,'Red')
        beam('RearBrace',(x,1.1,.70),(0,.12,.65),.075,.09,'Red')
    beam('Tongue',(0,-1.30,.68),(0,-4.20,.99),.11,.105,'Wood')
    for y in (-1.5,-2.10,-4.02):box('TongueBand',(0,y,.68+(-y-1.3)/2.9*.31),(.125,.065,.12),'Iron',.003)
    # Reconstructed goose stop and chain attachment, separately represented.
    box('GooseStop',(0,-3.94,.885),(.08,.065,.13),'Iron',.006)
    box('DraftCrossTimber',(0,-1.72,.84),(1.1,.14,.12),'Red',.006)
    rod('DraftEyeBolt',(-.065,-1.782,.88),(.065,-1.782,.88),.017,'Iron')
    ring('DraftAttachment',.045,.020,.012,(0,-1.82,.85),'Iron','X')
    # Six bows; visible bare wood on the open loading end.
    def bow_point(y,t):return (.61*math.cos(t),y,1.54+1.20*math.sin(t))
    for y in (-1.74,-1.05,-.35,.35,1.05,1.74):
        curve('BentWoodBow',[bow_point(y,i*math.pi/64) for i in range(65)],.020,'WoodLight')
        for x in (-.60,.60):box('BowSocket',(x,y,1.46),(.054,.06,.20),'Iron',.003)
    # The cover is gathered toward the front for loading. No zipper or snaps.
    na,ny=64,96;verts=[]
    def canvas_point(y,a):
        # Cloth sits outside the complete bow tube, including at its crown.
        normal=Vector((math.cos(a)/.61,0,math.sin(a)/1.20)).normalized()
        phase=(y+1.82)/.92*math.tau*12
        gather=.032+.016*(1+.18*math.sin(phase*.31+a*2))*(1-math.cos(phase+.22*math.sin(a*3)))
        return Vector((.61*math.cos(a),y,1.54+1.20*math.sin(a)))+normal*gather
    for j in range(ny+1):
        y=-1.82+j*.92/ny
        for i in range(na+1):
            verts.append(canvas_point(y,i*math.pi/na))
    faces=[(j*(na+1)+i,j*(na+1)+i+1,(j+1)*(na+1)+i+1,(j+1)*(na+1)+i) for j in range(ny) for i in range(na)]
    canvas=geo.mesh('GatheredCanvas',verts,faces,['Canvas'],smooth=True)
    bpy.context.view_layer.objects.active=canvas
    mod=canvas.modifiers.new('CanvasThickness','SOLIDIFY');mod.thickness=.003
    bpy.ops.object.modifier_apply(modifier=mod.name)
    for y in (-1.80,-.91):
        curve('CanvasHem',[canvas_point(y,i*math.pi/64) for i in range(65)],.009,'Canvas')
    for x in (-.63,.63):
        for y in (-1.73,-1.3,-.95):
            curve('CanvasTie',[(x,y,1.56),(x*1.03,y+.025,1.39),(x,y+.045,1.38),(x,y,1.56)],.006,'Rope')


def main():
    evidence=json.loads(EVIDENCE.read_text());assert evidence['sources'] and evidence['render_brief']
    assert 'mixar' in Path(bpy.app.binary_path).name.lower()
    OUT.mkdir(parents=True,exist_ok=True);bpy.ops.wm.read_factory_settings(use_empty=True)
    for name,rgb in PALETTE.items():
        m=bpy.data.materials.new('M_Delivery_'+name);m.use_nodes=True
        p=m.node_tree.nodes['Principled BSDF'];p.inputs['Base Color'].default_value=(*rgb,1)
        p.inputs['Roughness'].default_value=.38 if name=='Iron' else .78
        p.inputs['Metallic'].default_value=.8 if name=='Iron' else 0
        geo.MATS[name]=m
    wagon();body=join('SM_Delivery_Wagon',list(geo.PARTS));geo.PARTS.clear()
    objects=[body]
    for side,x in [('Left',-.85),('Right',.85)]:
        for axle,y,r,n in [('Front',-1.25,.55,12),('Rear',1.1,.70,14)]:
            objects.append(wheel('SM_Delivery_'+axle+side,r,n,(x,y,r)));geo.PARTS.clear()
    records=[]
    for obj in objects:
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
        # Each rotating wheel is exported at its own axle-centred origin.
        saved=obj.location.copy();obj.location=(0,0,0)
        fbx=OUT/(obj.name+'.fbx')
        bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},
            apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
            bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE')
        obj.location=saved
        records.append(dict(name=obj.name,fbx=fbx.name,sha256=hashlib.sha256(fbx.read_bytes()).hexdigest(),
            triangles=len(obj.data.loop_triangles),placement_m=list(saved),size_m=list(obj.dimensions),
            materials=[m.name for m in obj.data.materials]))
    project=OUT/'Delivery-Wagon.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=48
    scene.cycles.use_denoising=True;scene.render.resolution_x=1400;scene.render.resolution_y=1000
    scene.render.resolution_percentage=100;scene.view_settings.view_transform='Standard'
    scene.view_settings.look='None';scene.view_settings.exposure=-1.5
    scene.world=bpy.data.worlds.new('ClearDay');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.55,.70,1,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.35
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.008))
    floor=bpy.data.materials.new('ReviewFloor');floor.diffuse_color=(.16,.20,.24,1)
    bpy.context.object.data.materials.append(floor)
    for pos,power,size in [((4,-3,7),1200,5),((-4,1,5),700,4),((1,6,6),900,4)]:
        bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=power;o.data.size=size
        o.data.color=(1,.96,.88)
        o.rotation_euler=(Vector((0,-.7,1.1))-o.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';scene.camera=cam
    for name,pos,target,scale in [('rear',(5,7,4),(0,-.8,1.1),7.5),('front',(5,-8,4),(0,-.8,1.1),7.5),
        ('side',(8,-.5,3.2),(0,-.8,1.1),7.3),('undercarriage',(4,-5,1.0),(0,-.6,.7),6.7)]:
        cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()
        cam.data.ortho_scale=scale;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
    (OUT/'manifest.json').write_text(json.dumps(dict(assets=records,project_sha256=hashlib.sha256(project.read_bytes()).hexdigest(),
        evidence_sha256=hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),author_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        material_linear_rgb={'M_Delivery_'+n:c for n,c in PALETTE.items()},visual_review='pending'),indent=2)+'\n')
    print('DELIVERY_WAGON_AUTHORED',flush=True)


if __name__=='__main__':main()
