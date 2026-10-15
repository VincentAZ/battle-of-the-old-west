"""Author distinct Survivor costumes without changing the original asset or rig.

blender -b --factory-startup --disable-autoexec --threads 8 \
  --python scripts/author_survivor_variants.py -- --render

New costumes use real sewn silhouettes, articulated equipment and baked PBR
surfaces. Costume-only variants retain the source facial geometry. Identity
callbacks may sculpt facial surfaces while preserving topology and expressions.
Skin geometry and UVs stay intact; the inherited isolated finger weight is repaired.
The 53-bone rest rig and the Survivor_Rig FBX root remain exactly unchanged.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
SOURCE = ROOT / 'art/characters/oldwest_survivor/Survivor_A.blend'
OUT = ROOT / 'art/characters/survivor_variants'
SOURCE_SHA = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
HEAD, CHEST, HIPS = 'mixamorig:Head', 'mixamorig:Spine2', 'mixamorig:Hips'
NAMES = {'prospector': 'Prospector', 'gatling_gunner': 'Gatling Gunner', 'bounty_hunter': 'Bounty Hunter'}
arm = None
parts = []
specs = {}


def activate(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def signature():
    return [{'name': b.name, 'parent': b.parent.name if b.parent else None,
             'matrix': [[float(v) for v in row] for row in b.matrix_local],
             'deform': b.use_deform} for b in arm.data.bones]


def material(name, color, rough=.65, metal=0, fabric=False):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    n, links = mat.node_tree.nodes, mat.node_tree.links
    p = n.get('Principled BSDF'); p.inputs['Metallic'].default_value = metal
    p.inputs['Roughness'].default_value = rough
    coord = n.new('ShaderNodeTexCoord')
    grain = n.new('ShaderNodeTexNoise'); grain.inputs['Scale'].default_value = 65
    grain.inputs['Detail'].default_value = 4
    links.new(coord.outputs['Object'], grain.inputs['Vector'])
    ramp = n.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*(v * .52 for v in color), 1)
    ramp.color_ramp.elements[1].color = (*(min(.95, v * 1.2) for v in color), 1)
    links.new(grain.outputs['Fac'], ramp.inputs[0]); links.new(ramp.outputs[0], p.inputs['Base Color'])
    roughness = n.new('ShaderNodeMapRange')
    roughness.inputs['To Min'].default_value = max(.13, rough-.12)
    roughness.inputs['To Max'].default_value = min(.98, rough+.12)
    links.new(grain.outputs['Fac'], roughness.inputs['Value']); links.new(roughness.outputs[0], p.inputs['Roughness'])
    bump = n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = .30
    bump.inputs['Distance'].default_value = .00065 if fabric else .00016
    if fabric:
        # Existing CC0 photographic weave, used as small-scale surface relief.
        weave = n.new('ShaderNodeTexImage')
        weave.image = bpy.data.images.load(str(ROOT/'art/characters/oldwest_survivor/textures/fabric_pattern_05_rough_2k.jpg'), check_existing=True)
        weave.image.colorspace_settings.name = 'Non-Color'
        scale = n.new('ShaderNodeVectorMath'); scale.operation = 'SCALE'; scale.inputs[3].default_value = 7
        links.new(coord.outputs['Generated'], scale.inputs[0]); links.new(scale.outputs[0], weave.inputs['Vector'])
        links.new(weave.outputs['Color'], bump.inputs['Height'])
    else:
        fine = n.new('ShaderNodeTexNoise'); fine.inputs['Scale'].default_value = 360
        links.new(coord.outputs['Object'], fine.inputs['Vector']); links.new(fine.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], p.inputs['Normal'])
    specs[name] = {'base': color, 'roughness': rough, 'metallic': metal,
                   'photographic_fabric_relief': fabric, 'baked_normal_convention': 'OpenGL'}
    return mat


def finish(obj, name, mat, bone=CHEST, bevel=0, already_skinned=False):
    obj.name = name; obj.data.materials.clear(); obj.data.materials.append(mat)
    activate(obj); bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new('Physical_edge_radius', 'BEVEL'); mod.width=bevel; mod.segments=3
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for poly in obj.data.polygons: poly.use_smooth=True
    if not already_skinned:
        obj.vertex_groups.clear(); obj.vertex_groups.new(name=bone).add(list(range(len(obj.data.vertices))),1,'REPLACE')
        obj.parent=arm
        skin=obj.modifiers.new('Preserved_survivor_skin','ARMATURE');skin.object=arm
    parts.append(obj)
    return obj


def box(name,p,size,mat,bone=CHEST,bevel=.009):
    bpy.ops.mesh.primitive_cube_add(size=1, location=p)
    obj=bpy.context.object;obj.dimensions=size
    return finish(obj,name,mat,bone,bevel)


def cylinder(name,p,radius,depth,mat,bone=CHEST,axis=(0,0,1),vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=p)
    obj=bpy.context.object;obj.rotation_euler=Vector(axis).to_track_quat('Z','Y').to_euler()
    return finish(obj,name,mat,bone,min(.002,radius*.08))


def ellipsoid(name,p,size,mat,bone=CHEST):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=24,radius=1,location=p)
    obj=bpy.context.object;obj.scale=size
    return finish(obj,name,mat,bone)


def tube(name,points,radius,mat,bone=CHEST):
    curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D';curve.bevel_depth=radius;curve.bevel_resolution=2
    spline=curve.splines.new('POLY');spline.points.add(len(points)-1)
    for point,co in zip(spline.points,points):point.co=(*co,1)
    obj=bpy.data.objects.new(name,curve);bpy.context.collection.objects.link(obj)
    activate(obj);bpy.ops.object.convert(target='MESH')
    return finish(bpy.context.object,name,mat,bone)


def sheet(name,rows,mat,bone=CHEST,thickness=.004):
    verts=[tuple(v) for row in rows for v in row];cols=len(rows[0])
    faces=[(r*cols+c,r*cols+c+1,(r+1)*cols+c+1,(r+1)*cols+c)
           for r in range(len(rows)-1) for c in range(cols-1)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    activate(obj)
    solid=obj.modifiers.new('Real_fabric_thickness','SOLIDIFY');solid.thickness=thickness
    bpy.ops.object.modifier_apply(modifier=solid.name)
    return finish(obj,name,mat,bone)


def loft(name,rings,mat,bone=CHEST,start=0,end=2*math.pi,segments=64):
    # Rings: z, x center, y center, x radius, y radius, physical fold amplitude.
    # Interpolate the silhouette rather than leaving visibly faceted cone bands
    # at the crown of a helmet/hood or across a garment's shoulder transition.
    dense=[]
    for index in range(len(rings)-1):
        a,b,c,d=[rings[max(0,min(len(rings)-1,j))] for j in [index-1,index,index+1,index+2]]
        for step in range(4):
            t=step/4
            dense.append(tuple(.5*((2*y)+(-x+z)*t+(2*x-5*y+4*z-w)*t*t+(-x+3*y-3*z+w)*t*t*t)
                               for x,y,z,w in zip(a,b,c,d)))
    dense.append(rings[-1])
    rows=[]
    for z,cx,cy,rx,ry,wave in dense:
        row=[]
        for i in range(segments+1):
            a=start+(end-start)*i/segments
            fold=1+wave*(math.sin(a*11+z*29)+.25*math.sin(a*23-z*19))
            row.append((cx+rx*math.cos(a)*fold,cy+ry*math.sin(a)*fold,z))
        rows.append(row)
    return sheet(name,rows,mat,bone)


def sleeve(name,bone,mat,radius_a,radius_b,start=.03,end=.94):
    b=arm.data.bones[bone];a=b.head_local.lerp(b.tail_local,start);z=b.head_local.lerp(b.tail_local,end)
    direction=(z-a).normalized();u=direction.cross(Vector((0,1,0))).normalized();v=direction.cross(u).normalized()
    rows=[]
    for j in range(13):
        t=j/12;center=a.lerp(z,t);r=radius_a+(radius_b-radius_a)*t
        rows.append([center+(u*math.cos(i*math.tau/48)+v*math.sin(i*math.tau/48))*r*(1+.035*math.sin(i*math.tau/48*9+j*1.4)) for i in range(49)])
    return sheet(name,rows,mat,bone)


def replace_cloth(source_name,name,mat):
    obj=bpy.data.objects[source_name]
    return finish(obj,name,mat,already_skinned=True)


def remove_equipment(extra=()):
    prefixes=('Survivor_Bedroll','Survivor_Goggle','Survivor_Harness','Survivor_ChestPatch',
              'Survivor_LeftShoulder','Survivor_ArmourRivet','Survivor_DustScarf','Survivor_ScarfFold')+tuple(extra)
    for obj in list(bpy.data.objects):
        if obj.type=='MESH' and obj.name.startswith(prefixes):bpy.data.objects.remove(obj,do_unlink=True)


def coat_skin(obj):
    """Matching deformation for the coat, its sewn pockets and edge stitches."""
    obj.vertex_groups.clear()
    for vertex in obj.data.vertices:
        position=obj.matrix_world@vertex.co;z=position.z;x=position.x
        if z>1.08:weights={CHEST:min(1,(z-1.08)/.24),HIPS:1-min(1,(z-1.08)/.24)}
        else:
            leg='mixamorig:LeftUpLeg' if x>=0 else 'mixamorig:RightUpLeg';t=min(.82,max(0,(1.04-z)/.4))
            weights={leg:t,HIPS:1-t}
        for bone,weight in weights.items():
            if weight>0:(obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)).add([vertex.index],weight,'REPLACE')
    return obj


def scientist(m):
    remove_equipment(('Survivor_HairCards','Survivor_Canteen','Survivor_BeltPouch','Survivor_Pouch',
                      'Survivor_Left_Cargo','Survivor_Right_Cargo','Survivor_Left_Pocket','Survivor_Right_Pocket'))
    replace_cloth('Survivor_FieldShirt','Scientist_Long_Coat_Shirt',m['ivory'])
    coat=loft('Scientist_Open_Split_Coat',[(.67,0,.03,.224,.183,.035),(.76,0,.03,.217,.177,.025),
        (.91,0,.025,.209,.165,.024),(1.02,0,.022,.194,.151,.018),(1.16,0,.03,.182,.165,.016),
        (1.32,0,.04,.178,.172,.012),(1.40,0,.065,.165,.137,.012)],m['ivory'],start=-1.32,end=math.pi+1.32)
    # Keep lower coat panels attached to the corresponding moving thigh; the
    # center blends to pelvis and upper fabric follows the original spine.
    coat_skin(coat)
    for side,s in [('Left',1),('Right',-1)]:
        sleeve('Scientist_'+side+'_Full_Sleeve','mixamorig:'+side+'ForeArm',m['ivory'],.064,.043,-.30,.94)
        sleeve('Scientist_'+side+'_Rubber_Cuff','mixamorig:'+side+'ForeArm',m['rubber'],.047,.048,.83,.99)
        rows=[[(s*.016,-.176,1.07),(s*.095,-.181,1.09)],[(s*.018,-.184,1.25),(s*.128,-.17,1.24)],[(s*.063,-.106,1.46),(s*.135,-.108,1.38)]]
        sheet('Scientist_'+side+'_Folded_Lapel',rows,m['ivory'])
        tube('Scientist_'+side+'_Lapel_Stitch',[(s*.096,-.187,1.11),(s*.123,-.182,1.24),(s*.129,-.115,1.38)],.0016,m['thread'])
        coat_skin(box('Scientist_'+side+'_Coat_Pocket',(s*.142,-.117,.895),(.088,.023,.125),m['ivory'],HIPS,.011))
    for z in [1.04,1.12,1.20]:cylinder('Scientist_Coat_Button',(.037,-.182,z),.007,.004,m['steel'],axis=(0,-1,0))
    for s in [-1,1]:
        # Actual narrow seam piping and spaced stitches define construction.
        tube('Scientist_Shoulder_Seam',[(s*.052,-.097,1.437),(s*.113,-.10,1.417),(s*.172,-.056,1.398)],.0015,m['thread'])
        for i in range(15):
            z=.745+i*.022
            coat_skin(tube('Scientist_Coat_Edge_Stitch',[(s*.052,-.153,z),(s*.052,-.153,z+.010)],.0011,m['thread'],HIPS))
    box('Scientist_Chest_Pocket',(-.112,-.166,1.288),(.082,.022,.09),m['ivory'])
    for x in [-.137,-.120,-.102]:
        cylinder('Scientist_Pocket_Instrument',(x,-.183,1.322),.006,.077,m['brass'])
        cylinder('Scientist_Instrument_Cap',(x,-.183,1.363),.008,.013,m['teal'])
    # A field-research cap and twin optical goggles change the head silhouette.
    loft('Scientist_Fitted_Field_Cap',[(1.69,0,.025,.091,.105,.014),(1.720,0,.028,.095,.102,.009),
        (1.745,0,.033,.083,.085,.007),(1.770,0,.036,.060,.062,.005),(1.782,0,.038,.028,.032,.003),
        (1.787,0,.038,.002,.002,0)],m['charcoal'],HEAD)
    for x in [-.043,.043]:
        cylinder('Scientist_Optic_Frame',(x,-.099,1.659),.036,.028,m['brass'],HEAD,axis=(0,-1,0))
        cylinder('Scientist_Optic_Glass',(x,-.116,1.659),.027,.007,m['lens'],HEAD,axis=(0,-1,0))
        for a in [0,math.pi/2,math.pi,3*math.pi/2]:cylinder('Scientist_Optic_Screw',(x+.031*math.cos(a),-.118,1.659+.031*math.sin(a)),.003,.005,m['steel'],HEAD,axis=(0,-1,0),vertices=12)
    tube('Scientist_Optic_Bridge',[(-.012,-.112,1.664),(0,-.120,1.668),(.012,-.112,1.664)],.004,m['steel'],HEAD)
    for s in [-1,1]:tube('Scientist_Goggle_Strap',[(s*.079,-.10,1.66),(s*.104,.015,1.68),(s*.076,.119,1.67)],.009,m['leather'],HEAD)
    box('Scientist_Instrument_Backpack',(0,.183,1.239),(.248,.124,.32),m['leather'],bevel=.032)
    for s in [-1,1]:
        cylinder('Scientist_Field_Canister',(s*.085,.262,1.242),.043,.274,m['steel'])
        for z in [1.133,1.348]:cylinder('Scientist_Canister_Collar',(s*.085,.262,z),.047,.018,m['brass'])
        tube('Scientist_Canister_Feed',[(s*.085,.262,1.388),(s*.114,.24,1.43),(s*.162,.20,1.37)],.008,m['rubber'])
    box('Scientist_Belt_Meter',(.177,-.103,.99),(.086,.059,.116),m['teal'],HIPS,.012)
    cylinder('Scientist_Analog_Dial',(.177,-.137,1.014),.027,.006,m['ivory'],HIPS,axis=(0,-1,0))
    tube('Scientist_Dial_Needle',[(.177,-.142,1.014),(.191,-.142,1.032)],.0014,m['rubber'],HIPS)


def gunner(m):
    remove_equipment(('Survivor_HairCards',))
    replace_cloth('Survivor_FieldShirt','Gunner_Quilted_Undershirt',m['ochre'])
    # Curved overlapping torso plates have bevelled edges and fasteners, rather
    # than a single box used as the entire armour silhouette.
    for j,(z,w,h) in enumerate([(1.305,.325,.118),(1.19,.294,.091),(1.085,.277,.082)]):
        rows=[]
        for r in range(13):
            t=r/12;half=w*.5*(.87+.13*math.sin(t*math.pi))
            rows.append([(half*(i/24*2-1),-.153-.050*(1-(i/24*2-1)**2),z+(t-.5)*h) for i in range(25)])
        sheet('Gunner_Curved_Cuirass_'+str(j),rows,m['steel'],thickness=.010)
        for side in [0,-1]:tube('Gunner_Rolled_Plate_Edge',rows[side],.0035,m['steel'])
        for s in [-1,1]:cylinder('Gunner_Cuirass_Rivet',(s*w*.37,-.185,z),.007,.009,m['brass'],axis=(0,-1,0))
    loft('Gunner_Armoured_Collar',[(1.372,0,.043,.143,.114,.015),(1.442,0,.042,.117,.096,.009)],m['rubber'])
    for side,s in [('Left',1),('Right',-1)]:
        bone='mixamorig:'+side+'Arm'
        for j in range(3):
            a=arm.data.bones[bone];p=a.head_local.lerp(a.tail_local,.05+j*.17)+Vector((s*.027,0,.035))
            plate=ellipsoid('Gunner_'+side+'_Pauldron_'+str(j),p,(.099,.131,.044),m['steel'],bone)
            plate.rotation_euler.y=s*.55
        sleeve('Gunner_'+side+'_Forearm_Guard','mixamorig:'+side+'ForeArm',m['rubber'],.065,.049,.18,.87)
        b=arm.data.bones['mixamorig:'+side+'ForeArm'];p=b.head_local.lerp(b.tail_local,.5)+Vector((0,-.047,.02))
        guard=box('Gunner_'+side+'_Bracer_Plate',p,(.076,.037,.159),m['steel'],'mixamorig:'+side+'ForeArm',.013)
        guard.rotation_euler=Vector(b.tail_local-b.head_local).to_track_quat('Z','Y').to_euler()
        leg='mixamorig:'+side+'Leg'
        ellipsoid('Gunner_'+side+'_Knee_Guard',(s*.116,-.027,.518),(.071,.052,.085),m['steel'],leg)
        for z in [.476,.552]:
            loft('Gunner_'+side+'_Knee_Strap',[(z-.007,s*.116,.046,.074,.071,0),(z+.007,s*.116,.046,.074,.071,0)],m['rubber'],leg)
    # Helmet shell with an actual open underside, brow rim and separate ears.
    loft('Gunner_Ballistic_Helmet',[(1.661,0,.032,.106,.115,.0),(1.708,0,.030,.114,.121,.004),
        (1.77,0,.035,.096,.102,.0),(1.812,0,.039,.060,.064,.0),(1.83,0,.04,.003,.003,0)],m['steel'],HEAD)
    tube('Gunner_Helmet_Brow',[(.106*math.cos(a),.032+.12*math.sin(a),1.668) for a in [math.pi+i*math.pi/48 for i in range(49)]],.011,m['rubber'],HEAD)
    for s in [-1,1]:
        ellipsoid('Gunner_Ear_Defender',(s*.108,.027,1.643),(.029,.069,.062),m['rubber'],HEAD)
        cylinder('Gunner_Ear_Steel_Cap',(s*.133,.027,1.643),.041,.015,m['steel'],HEAD,axis=(1,0,0))
        tube('Gunner_Chin_Strap',[(s*.099,.045,1.62),(s*.059,-.077,1.55),(s*.027,-.08,1.541)],.006,m['leather'],HEAD)
    box('Gunner_Ammo_Pack',(0,.205,1.255),(.302,.168,.286),m['ochre'],bevel=.030)
    for s in [-1,1]:
        tube('Gunner_Pack_Frame',[(s*.165,.22,1.105),(s*.165,.28,1.14),(s*.165,.28,1.39),(s*.14,.21,1.42)],.011,m['steel'])
        box('Gunner_Pack_Buckle',(s*.093,.299,1.255),(.045,.014,.05),m['brass'],bevel=.004)
    # A true diagonal belt of individually collared cartridges.
    points=[(-.132,-.196,1.386),(-.052,-.205,1.277),(.031,-.201,1.167),(.121,-.177,1.055)]
    for side in [-1,1]:tube('Gunner_Bandolier_Edge',[(x+side*.028,y,z) for x,y,z in points],.006,m['leather'])
    for i in range(11):
        t=i/10;x=-.132+.253*t;z=1.385-.331*t;y=-.214+.031*t
        cylinder('Gunner_Cartridge_Case',(x,y,z),.010,.047,m['brass'])
        cylinder('Gunner_Cartridge_Base',(x,y,z-.024),.012,.005,m['steel'])
        ellipsoid('Gunner_Cartridge_Tip',(x,y,z+.032),(.009,.009,.018),m['copper'])


def assassin(m):
    remove_equipment(('Survivor_HairCards','Survivor_Canteen','Survivor_BeltPouch','Survivor_Pouch','Survivor_Left_Cargo','Survivor_Right_Cargo','Survivor_Left_Pocket','Survivor_Right_Pocket'))
    replace_cloth('Survivor_FieldShirt','Assassin_Fitted_Charcoal_Jacket',m['charcoal'])
    replace_cloth('Survivor_CargoTrousers','Assassin_Charcoal_Trousers',m['charcoal'])
    hood=loft('Assassin_Deep_Panelled_Hood',[(1.48,0,.040,.125,.128,.038),(1.57,0,.037,.132,.139,.03),
        (1.69,0,.030,.128,.148,.022),(1.76,0,.034,.105,.130,.02),(1.79,0,.04,.056,.080,.013),
        (1.81,0,.042,.007,.012,0)],m['charcoal'],HEAD,start=-.95,end=math.pi+.95)
    hood.vertex_groups.clear()
    for vertex in hood.data.vertices:
        t=min(1,max(0,(vertex.co.z-1.48)/.13))
        for bone,weight in [(HEAD,t),(CHEST,1-t)]:
            if weight:(hood.vertex_groups.get(bone) or hood.vertex_groups.new(name=bone)).add([vertex.index],weight,'REPLACE')
    for a in [-.95,math.pi+.95]:
        tube('Assassin_Hood_Stitched_Rim',[(rx*math.cos(a),cy+ry*math.sin(a),z) for z,cy,rx,ry in
            [(1.48,.04,.125,.128),(1.57,.037,.132,.139),(1.69,.03,.128,.148),(1.76,.034,.105,.13),(1.79,.04,.056,.08)]],.0035,m['leather'],HEAD)
    loft('Assassin_Wrapped_Face_Mask',[(1.53,0,.009,.087,.119,.07),(1.556,0,.008,.092,.120,.08),
        (1.58,0,.005,.092,.124,.06),(1.612,0,.004,.087,.120,.025)],m['charcoal'],HEAD,start=math.pi,end=math.tau)
    # The shoulder cowl is asymmetric and folds into an open split short cape.
    loft('Assassin_Shoulder_Cowl',[(1.28,0,.05,.244,.201,.065),(1.36,0,.052,.247,.188,.036),
        (1.437,0,.055,.181,.133,.025),(1.486,0,.049,.117,.099,.025)],m['charcoal'],start=-.7,end=math.pi+.7)
    rows=[]
    for j in range(21):
        t=j/20;z=1.425-.68*t
        rows.append([(-.195+.39*i/32, .162+.053*t+.012*math.sin(i*.75+t*12), z+.027*math.sin(i*.6)*t) for i in range(33)])
    cape=sheet('Assassin_Folded_Short_Cape',rows,m['charcoal'])
    # Cape blends to pelvis below the waist; there is no new cloth simulation or
    # dangling rigid extension that could break existing cinematic handoffs.
    cape.vertex_groups.clear()
    for v in cape.data.vertices:
        t=min(1,max(0,(v.co.z-1.0)/.35))
        for b,w in [(CHEST,t),(HIPS,1-t)]:
            if w:(cape.vertex_groups.get(b) or cape.vertex_groups.new(name=b)).add([v.index],w,'REPLACE')
    for s in [-1,1]:
        strap=[(s*.093,-.156,1.35),(s*.065,-.172,1.21),(s*.106,-.141,1.04)]
        sheet('Assassin_Harness_Leather',[[(x-.017,y,z),(x+.017,y,z)] for x,y,z in strap],m['leather'])
        for edge in [-1,1]:tube('Assassin_Harness_Stitch',[(x+edge*.012,y-.004,z) for x,y,z in strap],.0012,m['thread'])
        cylinder('Assassin_Cowl_Clasp',(s*.104,-.146,1.349),.019,.012,m['steel'],axis=(0,-1,0))
    for side,s in [('Left',1),('Right',-1)]:
        sleeve('Assassin_'+side+'_Forearm_Wrap','mixamorig:'+side+'ForeArm',m['leather'],.054,.043,.22,.90)
        b=arm.data.bones['mixamorig:'+side+'ForeArm']
        for i in range(5):
            p=b.head_local.lerp(b.tail_local,.32+i*.1)
            cylinder('Assassin_Bracer_Stud',p+Vector((0,-.051,0)),.004,.006,m['steel'],'mixamorig:'+side+'ForeArm',axis=(0,-1,0),vertices=12)
    sheath=box('Assassin_Thigh_Knife_Sheath',(-.186,.023,.75),(.046,.052,.215),m['leather'],'mixamorig:RightUpLeg',.017)
    tube('Assassin_Thigh_Knife_Handle',[(-.186,.023,.848),(-.184,.023,.92)],.015,m['rubber'],'mixamorig:RightUpLeg')
    for z in [.734,.812]:tube('Assassin_Thigh_Strap',[(-.189,-.03,z),(-.21,.043,z),(-.168,.115,z)],.010,m['leather'],'mixamorig:RightUpLeg')


def bake_atlas(mesh,name,texdir):
    activate(mesh);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.10,island_margin=.003)
    bpy.ops.object.mode_set(mode='OBJECT')
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=8
    scene.render.bake.margin=10;scene.render.bake.use_clear=True
    images={}
    for channel in ['BaseColor','Roughness','Metallic','Normal']:
        image=bpy.data.images.new('T_'+name+'_Outfit_'+channel,width=2048,height=2048,alpha=False)
        image.colorspace_settings.name='sRGB' if channel=='BaseColor' else 'Non-Color'
        swaps=[]
        for mat in mesh.data.materials:
            n,links=mat.node_tree.nodes,mat.node_tree.links;p=n.get('Principled BSDF');out=next(v for v in n if v.type=='OUTPUT_MATERIAL')
            target=n.new('ShaderNodeTexImage');target.image=image;n.active=target
            if channel!='Normal':
                emission=n.new('ShaderNodeEmission');socket=p.inputs[{'BaseColor':'Base Color','Roughness':'Roughness','Metallic':'Metallic'}[channel]]
                if socket.is_linked:links.new(socket.links[0].from_socket,emission.inputs['Color'])
                else:
                    value=socket.default_value
                    emission.inputs['Color'].default_value=(*value[:3],1) if hasattr(value,'__len__') else (value,value,value,1)
                links.new(emission.outputs[0],out.inputs['Surface']);swaps.append((mat,p,out,emission))
        bpy.ops.object.bake(type='NORMAL' if channel=='Normal' else 'EMIT')
        for mat,p,out,emission in swaps:mat.node_tree.links.new(p.outputs[0],out.inputs['Surface']);mat.node_tree.nodes.remove(emission)
        image.filepath_raw=str(texdir/(image.name+'.png'));image.file_format='PNG';image.save();images[channel]=image
    atlas=bpy.data.materials.new('M_'+name+'_Outfit');atlas.use_nodes=True
    n,links=atlas.node_tree.nodes,atlas.node_tree.links;p=n.get('Principled BSDF')
    for channel in ['BaseColor','Roughness','Metallic']:
        tex=n.new('ShaderNodeTexImage');tex.image=images[channel]
        links.new(tex.outputs['Color'],p.inputs[{'BaseColor':'Base Color','Roughness':'Roughness','Metallic':'Metallic'}[channel]])
    tex=n.new('ShaderNodeTexImage');tex.image=images['Normal'];normal=n.new('ShaderNodeNormalMap')
    links.new(tex.outputs['Color'],normal.inputs['Color']);links.new(normal.outputs[0],p.inputs['Normal'])
    mesh.data.materials.clear();mesh.data.materials.append(atlas)
    for face in mesh.data.polygons:face.material_index=0
    return images


def render_studio(path,name):
    bpy.ops.wm.open_mainfile(filepath=str(path),use_scripts=False)
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=48
    scene.render.resolution_x=1200;scene.render.resolution_y=1400;scene.render.resolution_percentage=100
    scene.world=bpy.data.worlds.new(name+'_Studio');scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.12,.16,.18,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.35
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.017))
    floor=bpy.context.object;floor.data.materials.append(material('Studio_floor',(.025,.034,.038),.8))
    for label,position,energy,size,color in [('Key',(-3,-4,5),650,4,(1,.86,.69)),('Fill',(3,-2,3),350,3,(.58,.79,1)),('Rim',(1,3,4),850,3,(.81,.93,1))]:
        data=bpy.data.lights.new(label,'AREA');data.energy=energy;data.shape='DISK';data.size=size;data.color=color
        obj=bpy.data.objects.new(label,data);bpy.context.collection.objects.link(obj);obj.location=position
        obj.rotation_euler=(Vector((0,0,1))-obj.location).to_track_quat('-Z','Y').to_euler()
    data=bpy.data.cameras.new(name+'_Review');camera=bpy.data.objects.new(name+'_Review',data);bpy.context.collection.objects.link(camera)
    scene.camera=camera;data.lens=68
    for label,position in [('front',(0,-4.8,1.8)),('three-quarter',(-3.0,-4.0,2.15)),('back',(2.7,4.0,2.1))]:
        camera.location=position;camera.rotation_euler=(Vector((0,0,.93))-camera.location).to_track_quat('-Z','Y').to_euler()
        scene.render.filepath=str(path.parent/(name+'_'+label+'.png'));bpy.ops.render.render(write_still=True)


def author(card, designer=None):
    global arm,parts,specs
    name=NAMES[card];out=OUT/card;texdir=out/'textures';texdir.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE),use_scripts=False)
    arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
    assert arm.name=='Survivor_Rig' and len(arm.data.bones)==53
    arm.animation_data_clear()
    for action in list(bpy.data.actions):bpy.data.actions.remove(action)
    for bone in arm.pose.bones:bone.matrix_basis.identity()
    # Existing image links must remain absolute after saving into a new folder.
    for image in bpy.data.images:
        if image.filepath:image.filepath=bpy.path.abspath(image.filepath)
    for obj in list(bpy.data.objects):
        if obj.type not in {'ARMATURE','MESH'}:bpy.data.objects.remove(obj,do_unlink=True)
    before=signature();parts=[];specs={}
    from character_hands import correct_isolated_ring_vertex
    hand_repairs=correct_isolated_ring_vertex(bpy.data.objects['Survivor_Body'])
    m={key:material('M_'+name+'_'+key,color,rough,metal,fabric) for key,color,rough,metal,fabric in [
        ('ivory',(.57,.55,.42),.76,0,True),('charcoal',(.036,.048,.050),.84,0,True),
        ('ochre',(.25,.17,.070),.78,0,True),('teal',(.038,.20,.18),.47,.12,False),
        ('leather',(.068,.045,.027),.65,0,False),('steel',(.18,.215,.21),.49,.83,False),
        ('brass',(.34,.22,.074),.39,.90,False),('copper',(.30,.11,.039),.40,.88,False),
        ('rubber',(.018,.023,.022),.85,0,False),('thread',(.32,.30,.22),.9,0,True),
        ('lens',(.032,.16,.19),.16,.18,False)]}
    (designer or {'prospector':scientist,'gatling_gunner':gunner,'bounty_hunter':assassin}[card])(m)
    assert signature()==before,'Authoring changed the preserved rest rig'
    part_specs=[{'name':p.name,'vertices':len(p.data.vertices),'bones':[g.name for g in p.vertex_groups]} for p in parts]
    # New garments retain their existing skin weights; rigid equipment carries
    # explicit per-bone weights. Join only the new outfit, preserving skin/eyes.
    activate(parts[0])
    for p in parts:p.select_set(True)
    bpy.ops.object.join();outfit=bpy.context.object;outfit.name=name+'_Outfit_Assembly'
    for v in outfit.data.vertices:
        total=sum(g.weight for g in v.groups)
        assert abs(total-1)<.001 and all(outfit.vertex_groups[g.group].name in arm.data.bones for g in v.groups)
    images=bake_atlas(outfit,name,texdir)
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    scene.view_settings.view_transform='AgX';scene.render.fps=30
    path=out/(name+'.blend');bpy.ops.wm.save_as_mainfile(filepath=str(path))
    meshes=[o for o in bpy.data.objects if o.type=='MESH' and o.find_armature()==arm]
    assert outfit in meshes
    report={'card_id':card,'name':name,'status':'authored costume candidate; studio and native motion review required',
        'source_blend':str(SOURCE),'source_sha256':SOURCE_SHA,'source_mesh_license':'CC0-1.0',
        'source_credits':'art/characters/oldwest_survivor/CREDITS.md','source_animation_actions_included':False,
        'rig_bones':53,'expected_unreal_reference_bones':54,'armature_object_name':arm.name,'rig_reference':before,
        'original_rig_unchanged':signature()==before,'parts':part_specs,'materials':specs,
        'hand_weight_corrections':hand_repairs,
        'total_triangles':sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons),
        'outfit_triangles':sum(len(p.vertices)-2 for p in outfit.data.polygons),
        'outfit_material':'M_'+name+'_Outfit','textures':{channel:{'path':str(Path(image.filepath)),
        'sha256':hashlib.sha256(Path(image.filepath).read_bytes()).hexdigest()} for channel,image in images.items()},
        'material_names':sorted({m.name for o in meshes for m in o.data.materials if m})}
    body=bpy.data.objects.get('Survivor_Body');face=bpy.data.objects.get('Survivor_Face_27Shapes')
    if face and face.get('identity_face_report'):
        report['facial_identity']=json.loads(face['identity_face_report'])
    if body and body.get('neck_seam_vertices_fitted'):
        report['neck_correction']={
            'body_vertices_fitted':body['neck_seam_vertices_fitted'],
            'body_weights_preserved':bool(body.get('neck_body_weights_preserved')),
            'face_vertices_weight_transferred':face.get('neck_body_weight_transfer_vertices',0),
            'native_deformation_review_required':True}
    # Export the same proven unit conversion, without overwriting meter source.
    scale=Matrix.Scale(100,4)
    for obj in [arm]+meshes:
        if obj.type=='MESH':obj.data.transform(scale,shape_keys=True)
        else:obj.data.transform(scale)
        obj.location*=100;inverse=obj.matrix_parent_inverse.copy();inverse.translation*=100;obj.matrix_parent_inverse=inverse
    scene.unit_settings.scale_length=.01;bpy.context.view_layer.update();activate(arm)
    for obj in meshes:obj.select_set(True)
    fbx=out/(name+'_Cm.fbx')
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,
        bake_anim=False,use_armature_deform_only=True,use_mesh_modifiers=False,mesh_smooth_type='FACE',
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',path_mode='RELATIVE')
    report['fbx_sha256']=hashlib.sha256(fbx.read_bytes()).hexdigest()
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_SHA
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('VARIANT_AUTHORED',card,report['total_triangles'],flush=True)
    if '--render' in sys.argv:render_studio(path,name)


if __name__=='__main__':
    requested=[x for x in sys.argv[sys.argv.index('--')+1:] if x in NAMES] if '--' in sys.argv else []
    for card in requested or NAMES:author(card)
