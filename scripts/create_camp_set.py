"""Build six textured wasteland camps with damaged/ruined meshes at real scale.

Run Blender --background --factory-startup --disable-autoexec --python this_file.py
Add -- --render for six individual renders and a native 3D overview contact sheet.
All geometry is authored here; PBR source photos are the project's CC0 library.
"""
import bpy
import bmesh
import json
import math
import random
import sys
from pathlib import Path
from mathutils import Vector, Matrix, Euler, noise

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/camps'
LIB = ROOT / 'art/library/polyhaven'
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'previews').mkdir(exist_ok=True)
if '--verify' in sys.argv:
    catalog=json.loads((OUT/'camp-set-manifest.json').read_text())
    checks=[]
    for name,camp in catalog['camps'].items():
        for state,record in camp['variants'].items():
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.fbx(filepath=str(ROOT/record['fbx']))
            objects=[o for o in bpy.data.objects if o.type=='MESH']
            assert len(objects)==1,(name,state,'expected one mesh',len(objects))
            obj=objects[0]
            tris=sum(len(p.vertices)-2 for p in obj.data.polygons)
            assert tris==record['triangles'],(name,state,'triangle mismatch',tris,record['triangles'])
            assert len(obj.data.uv_layers)>=1,(name,state,'missing UVs')
            assert all(math.isfinite(c) for v in obj.data.vertices for c in v.co),(name,state,'nonfinite mesh')
            mats=[m.name for m in obj.data.materials]
            assert set(mats)==set(record['material_slots']),(name,state,'material mismatch',mats)
            checks.append({'camp':name,'state':state,'triangles':tris,'uv_layers':len(obj.data.uv_layers),
                           'materials':mats,'dimensions_m':list(obj.dimensions)})
    (OUT/'fbx-validation.json').write_text(json.dumps({'verified':True,'meshes':checks},indent=2)+'\n')
    print('CAMP_FBX_VERIFIED',len(checks),'meshes',flush=True)
    raise SystemExit(0)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1
random.seed(2219)
palette = {}
camp_objects = {}
CURRENT = 'Bunker'
ROLE = 'detail'


def texture_path(asset, suffix):
    matches = list((LIB / asset).rglob(asset + '_' + suffix + '_4k.*'))
    return matches[0] if matches else None


def material(name, color=(.2,.2,.2), rough=.75, metal=0, asset=None, tile=2,
             tint=(1,1,1), emission=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    mat['tile_m'] = tile
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Metallic'].default_value = metal
    record = dict(color=list(color), roughness=rough, metallic=metal,
                  tint=list(tint), emission=emission, textures={})
    def image(path, is_color=False):
        n = nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(str(path), check_existing=True)
        n.image.colorspace_settings.name = 'sRGB' if is_color else 'Non-Color'
        return n
    if asset:
        path = texture_path(asset,'diff')
        diff = image(path,True)
        mult = nodes.new('ShaderNodeMixRGB'); mult.blend_type='MULTIPLY'
        mult.inputs[0].default_value=1; mult.inputs[2].default_value=(*tint,1)
        links.new(diff.outputs['Color'],mult.inputs[1]); links.new(mult.outputs[0],bsdf.inputs['Base Color'])
        record['textures']['diff']=str(path.relative_to(ROOT))
        normal = texture_path(asset,'nor_gl')
        if normal:
            n=image(normal); nm=nodes.new('ShaderNodeNormalMap')
            nm.inputs['Strength'].default_value=.68
            links.new(n.outputs['Color'],nm.inputs['Color']); links.new(nm.outputs[0],bsdf.inputs['Normal'])
            dx=texture_path(asset,'nor_dx')
            record['textures']['normal']=str((dx or normal).relative_to(ROOT))
            record['normal_convention']='DirectX' if dx else 'OpenGL'
        arm=texture_path(asset,'arm'); roughmap=texture_path(asset,'rough')
        if arm:
            n=image(arm); split=nodes.new('ShaderNodeSeparateColor')
            links.new(n.outputs['Color'],split.inputs[0]); links.new(split.outputs['Green'],bsdf.inputs['Roughness'])
            record['textures']['arm']=str(arm.relative_to(ROOT))
        elif roughmap:
            n=image(roughmap); links.new(n.outputs['Color'],bsdf.inputs['Roughness'])
            record['textures']['rough']=str(roughmap.relative_to(ROOT))
    if emission:
        bsdf.inputs['Emission Color'].default_value=(*color,1)
        bsdf.inputs['Emission Strength'].default_value=emission
    palette[name]=record
    return mat


steel=material('Camp_DarkSteel',asset='rusty_metal_sheet',tile=2.1,tint=(.20,.25,.25),metal=.3)
zinc=material('Camp_Galvanized',asset='rusty_metal_sheet',tile=2.4,tint=(.80,.85,.82),metal=.3)
rust=material('Camp_CorrodedSteel',asset='rust_coarse_01',tile=1.8,tint=(.68,.67,.57),metal=.1)
concrete=material('Camp_Concrete',asset='concrete_wall_007',tile=2.7,tint=(.86,.82,.70))
pale=material('Camp_ClinicPaint',asset='rusty_metal_sheet',tile=2.0,tint=(.92,.95,.89),metal=.12)
canvas=material('Camp_DustCanvas',asset='concrete_wall_007',tile=.85,tint=(.32,.30,.20))
pink=material('Camp_FadedRose',asset='rusty_metal_sheet',tile=.8,tint=(.65,.19,.26),metal=.12)
cyan=material('Camp_FadedTurquoise',asset='rusty_metal_sheet',tile=.9,tint=(.22,.54,.51),metal=.12)
ivory=material('Camp_StencilledChalk',asset='concrete_wall_007',tile=.5,tint=(1,.95,.79))
black=material('Camp_Rubber',(.022,.025,.022),rough=.86)
glass=material('Camp_SmokedGlass',(.016,.035,.03),rough=.2,metal=.17)
wiremat=material('Camp_Cable',(.017,.019,.016),rough=.8)
copper=material('Camp_Copper',asset='rusty_metal_sheet',tile=.6,tint=(.59,.34,.18),metal=.65)
lamp=material('Camp_AmberLamp',(.96,.51,.17),rough=.38,emission=3)
led=material('Camp_StatusLight',(.20,.68,.56),rough=.25,emission=2)
char=material('Camp_Burnt',asset='rust_coarse_01',tile=1.3,tint=(.105,.105,.095))
soil=material('Camp_Ground',asset='dirt',tile=3.4,tint=(.80,.79,.68))


def tag(obj,name,mat=None,role=None):
    obj.name=CURRENT+'_'+name
    obj['camp']=CURRENT; obj['role']=role or ROLE
    if mat: obj.data.materials.append(mat)
    camp_objects.setdefault(CURRENT,[]).append(obj)
    return obj


def project_uv(obj,tile=2):
    uv=obj.data.uv_layers.active or obj.data.uv_layers.new(name='UVMap')
    ox,oy=random.uniform(0,4),random.uniform(0,4)
    for poly in obj.data.polygons:
        axis=max(range(3),key=lambda i:abs(poly.normal[i]))
        a,b=(1,2) if axis==0 else (0,2) if axis==1 else (0,1)
        for li in poly.loop_indices:
            v=obj.data.vertices[obj.data.loops[li].vertex_index].co
            uv.data[li].uv=(v[a]/tile+ox,v[b]/tile+oy)


def bevel(obj,width=.01):
    mod=obj.modifiers.new('ManufacturedEdge','BEVEL');mod.width=width;mod.segments=2


def box(name,pos,size,mat=steel,edge=.012,rot=None,role=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=pos)
    obj=bpy.context.object;obj.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    project_uv(obj,mat.get('tile_m',2))
    if edge:bevel(obj,edge)
    if rot:obj.rotation_euler=rot
    return tag(obj,name,mat,role)


def cyl(name,pos,radius,depth,mat=steel,axis=(0,0,1),vertices=40,role=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=pos)
    obj=bpy.context.object
    uv=obj.data.uv_layers.active;tile=mat.get('tile_m',2)
    for p in obj.data.polygons:
        if len(p.vertices)==4:
            p.use_smooth=True
            angles=[math.atan2(obj.data.vertices[obj.data.loops[li].vertex_index].co.y,obj.data.vertices[obj.data.loops[li].vertex_index].co.x) for li in p.loop_indices]
            if max(angles)-min(angles)>math.pi:angles=[a+2*math.pi if a<0 else a for a in angles]
            for li,a in zip(p.loop_indices,angles):
                v=obj.data.vertices[obj.data.loops[li].vertex_index].co;uv.data[li].uv=(a*radius/tile,v.z/tile)
        else:
            for li in p.loop_indices:
                v=obj.data.vertices[obj.data.loops[li].vertex_index].co;uv.data[li].uv=(v.x/tile,v.y/tile)
    obj.rotation_euler=Vector(axis).to_track_quat('Z','Y').to_euler()
    bevel(obj,min(.008,radius*.07))
    return tag(obj,name,mat,role)


def beam(name,a,b,width=.07,mat=steel,role=None):
    a,b=Vector(a),Vector(b)
    obj=box(name,(a+b)/2,(width,width,(b-a).length),mat,edge=min(.007,width*.12),role=role)
    obj.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    return obj


def pipe(name,a,b,r=.06,mat=steel,role=None):
    a,b=Vector(a),Vector(b)
    return cyl(name,(a+b)/2,r,(b-a).length,mat,b-a,role=role)


def ring(name,pos,r,t=.012,mat=steel,axis=(0,0,1),role=None):
    bpy.ops.mesh.primitive_torus_add(major_segments=40,minor_segments=8,major_radius=r,minor_radius=t,location=pos)
    obj=bpy.context.object
    for p in obj.data.polygons:p.use_smooth=True
    project_uv(obj,mat.get('tile_m',2))
    obj.rotation_euler=Vector(axis).to_track_quat('Z','Y').to_euler()
    return tag(obj,name,mat,role)


def cable(name,points,r=.016,mat=wiremat,role=None):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.resolution_u=8
    data.bevel_depth=r;data.bevel_resolution=2
    spline=data.splines.new('BEZIER');spline.bezier_points.add(len(points)-1)
    for point,co in zip(spline.bezier_points,points):
        point.co=co;point.handle_left_type='AUTO';point.handle_right_type='AUTO'
    obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj)
    return tag(obj,name,mat,role)


def mesh(name,verts,faces,mat=steel,role=None):
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
    obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj)
    project_uv(obj,mat.get('tile_m',2))
    return tag(obj,name,mat,role)


def text(name,body,pos,size=.18,mat=ivory):
    data=bpy.data.curves.new(name,'FONT');data.body=body;data.align_x='CENTER';data.align_y='CENTER'
    data.size=size;data.extrude=.0007
    data.font=bpy.data.fonts.load('/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf')
    obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj)
    obj.location=pos;obj.rotation_euler=(math.pi/2,0,0)
    return tag(obj,name,mat)


def sheet(name,pos,width,depth,mat=zinc,slope=0,vertical=False,role='roof'):
    count=max(8,int(width/.06));verts=[];faces=[]
    for j in range(2):
        for i in range(count+1):
            u=(i/count-.5)*width;v=(j-.5)*depth
            corr=.023*math.cos(u*math.pi/.075)
            verts.append((pos[0]+u,pos[1]+corr if vertical else pos[1]+v,
                          pos[2]+v if vertical else pos[2]+corr+slope*v))
    for i in range(count):faces.append((i,i+1,count+i+2,count+i+1))
    obj=mesh(name,verts,faces,mat,role)
    solid=obj.modifiers.new('SheetThickness','SOLIDIFY');solid.thickness=.006
    return obj


def panel_wall(name,y,width,height,mat=zinc,base=.16):
    parts=max(3,int(width/.58))
    for i in range(parts):
        x=(i-(parts-1)/2)*width/parts
        sheet(name,(x,y,base+height/2),width/parts+.018,height,mat,vertical=True,role='wall')


def footing(pos,size):
    return box('Footing',pos,size,concrete,.035,role='foundation')


def bollard(x,y,z=0):
    cyl('GuardPost',(x,y,z+.43),.072,.86,rust,role='detail')
    cyl('PostStripe',(x,y,z+.64),.074,.065,cyan)


def crate(pos,size=(.64,.52,.52),mat=steel):
    x,y,z=pos;w,d,h=size
    box('SupplyCrate',(x,y,z+h/2),(w,d,h),mat,.018)
    for sx in [-1,1]:
        for sy in [-1,1]:box('CrateCorner',(x+sx*(w/2-.025),y+sy*(d/2-.025),z+h/2),(.05,.05,h+.015),rust,.005)
    for yy in [-1,1]:box('CrateLatch',(x,y+yy*(d/2+.008),z+h*.72),(.10,.022,.14),zinc,.006)


def sandbag(pos,angle=0):
    obj=box('FilledSandbag',pos,(.70,.32,.23),canvas,.09,rot=(0,random.uniform(-.06,.06),angle))
    # Uneven filled fabric silhouette, not perfectly identical boxes.
    for v in obj.data.vertices:
        v.co.z+=random.uniform(-.018,.018)
    return obj


def flange(pos,axis=(0,1,0),radius=.14):
    cyl('PipeFlange',pos,radius,.065,rust,axis)
    axis=Vector(axis).normalized();right=axis.cross(Vector((0,0,1)))
    if right.length<.1:right=Vector((1,0,0))
    right.normalize();up=axis.cross(right).normalized()
    for i in range(8):
        a=i*math.pi/4;p=Vector(pos)+(right*math.cos(a)+up*math.sin(a))*radius*.78+axis*.039
        cyl('FlangeBolt',p,.013,.035,zinc,axis,vertices=6)


def wall_lamp(pos):
    x,y,z=pos
    box('LampBack',(x,y,z),(.25,.10,.14),steel,.014)
    box('AmberPractical',(x,y-.060,z),(.17,.023,.071),lamp,.01)
    for xx in [-.06,0,.06]:box('LampCage',(x+xx,y-.079,z),(.01,.013,.105),steel,.002)


def vent(pos,width=.6,height=.45):
    x,y,z=pos
    box('VentFrame',pos,(width,.075,height),steel,.01)
    for i in range(7):box('VentLouvre',(x,y-.052,z+(i-3)*height/8),(width-.06,.05,.016),zinc,.003,rot=(.3,0,0))


def ladder(x,y,top,base=.15):
    for sx in [-1,1]:pipe('LadderRail',(x+sx*.24,y,base),(x+sx*.24,y,top),.025,rust)
    for i in range(int((top-base)/.29)+1):pipe('LadderRung',(x-.24,y-.006,base+i*.29),(x+.24,y-.006,base+i*.29),.022,zinc)


def bunker():
    footing((0,0,.09),(4.9,4.0,.18))
    for x in [-1.63,1.63]:box('BlastWall',(x,-1.70,1.25),(1.35,.58,2.34),concrete,.07,role='wall')
    box('DoorLintel',(0,-1.7,2.43),(2.12,.67,.44),concrete,.05,role='wall')
    for x in [-2.05,2.05]:box('FlankWall',(x,.03,1.22),(.59,3.1,2.28),concrete,.055,rot=(0,(-.11 if x>0 else .11),0),role='wall')
    box('RearWall',(0,1.49,1.20),(4.08,.51,2.23),concrete,.045,role='wall')
    for x in [-1.6,-.8,0,.8,1.6]:box('RoofSlab',(x,0,2.52),(.83,3.8,.27),concrete,.026,role='roof')
    box('ArmouredDoor',(0,-1.43,1.22),(1.17,.13,2.22),steel,.025)
    for x in [-.42,.42]:box('DoorReinforcement',(x,-1.52,1.22),(.09,.052,2.10),rust,.008)
    box('DoorVisionSlit',(0,-1.514,1.75),(.44,.03,.10),glass,.006)
    cyl('DoorWheel',(0,-1.62,1.10),.15,.04,rust,(0,1,0),vertices=8)
    for x in [-1.61,1.61]:box('DefenceSlit',(x,-2.001,1.72),(.75,.024,.12),glass,.003)
    for i in range(5):sandbag((-1.5+i*.71,-1.54,2.77),random.uniform(-.05,.05))
    for i in range(4):sandbag((-1.16+i*.71,-1.54,2.98),random.uniform(-.06,.06))
    pipe('Exhaust',(-1.4,.72,2.7),(-1.4,.72,3.40),.13,rust)
    cyl('ExhaustRainCap',(-1.4,.72,3.42),.23,.06,steel)
    pipe('RadioMast',(1.52,.99,2.6),(1.52,.99,4.35),.029,steel)
    for z in [3.71,4.04]:pipe('AntennaArm',(1.13,.99,z),(1.90,.99,z),.013,zinc)
    cable('MastCable',[(1.5,1,3.3),(.6,1.1,2.7),(.5,.2,2.66)],.015)
    text('BunkerStencil','HOLD FAST',(0,-2.039,2.43),.16)
    box('IdentityStripe',(-2.0,-2.01,.71),(.09,.019,1.17),pink,.003)
    wall_lamp((.84,-1.96,2.27))
    for x in [-1.78,1.82]:bollard(x,-2.18)
    crate((2.30,.97,.02),(.56,.52,.56),rust)


def workshop():
    footing((0,.05,.07),(5.35,4.43,.14))
    for x in [-2.36,2.36]:
        for y in [-1.84,1.87]:beam('IColumn',(x,y,.16),(x,y,2.87),.14,steel,role='wall')
        box('SideWall',(x,.1,1.30),(.085,3.88,2.38),steel,.008,role='wall')
        for y in [-1.54,-.91,-.28,.35,.98,1.61]:box('WallRib',(x-.05 if x>0 else x+.05,y,1.33),(.095,.043,2.36),rust,.006,role='wall')
    panel_wall('RearSheet',1.92,4.69,2.6,steel)
    for x in [-1.57,0,1.57]:sheet('CorrugatedRoof',(x,0,2.91),1.63,4.47,zinc,slope=.065)
    box('FrontBeam',(0,-1.87,2.80),(5.05,.19,.24),rust,.012,role='roof')
    box('WorkshopFascia',(0,-2.025,2.64),(3.7,.06,.33),steel,.012)
    text('WorkshopSign','SOUTHPOINT  WORKS',(0,-2.064,2.65),.20)
    box('FadedTrim',(-1.84,-2.065,2.65),(.10,.012,.3),cyan,.002)
    box('WorkbenchTop',(-.48,1.18,1.01),(2.69,.79,.09),zinc,.012)
    for x in [-1.65,.67]:
        for y in [.91,1.43]:beam('BenchLeg',(x,y,.15),(x,y,.99),.067,rust)
    box('ViceBase',(.38,.92,1.1),(.25,.20,.11),steel,.012)
    box('ViceJaw',(.38,.91,1.2),(.25,.045,.14),rust,.004)
    pipe('ViceHandle',(.25,.82,1.08),(.54,.82,1.08),.013,zinc)
    for i in range(7):
        x=-1.4+i*.26
        pipe('HangingTool',(x,1.855,1.45),(x,1.855,1.84),.022,zinc)
        ring('ToolHandle',(x,1.844,1.90),.045,.012,rust,(0,1,0))
    box('Generator',(1.46,.83,.69),(1.15,1.19,.89),steel,.045)
    for z in [.4,.54,.68,.82,.96]:box('GeneratorCoolingFin',(1.47,.208,z),(.93,.12,.048),rust,.005)
    pipe('GeneratorExhaust',(1.86,1.12,1.17),(1.86,1.12,2.27),.065,rust)
    for z in [.35,.61,.87]:ring('StackedTyre',(-1.77,-.91,z),.30,.10,black)
    cyl('TyreRim',(-1.77,-.91,.91),.21,.09,rust)
    beam('HoistTrack',(-1.83,-1.45,2.53),(1.83,-1.45,2.53),.16,steel,role='roof')
    ring('HoistPulley',(.59,-1.43,2.27),.12,.035,rust,(0,1,0))
    cable('HoistCable',[(.57,-1.43,2.31),(.54,-1.43,1.44),(.60,-1.43,1.23)],.014)
    ring('HoistHook',(.60,-1.43,1.17),.07,.017,zinc,(0,1,0))
    crate((-2.74,.33,.02),(.62,.70,.53),rust)
    wall_lamp((-.42,-2.08,2.30));wall_lamp((1.51,-2.08,2.30))
    cable('PowerLead',[(2.36,1.26,2.24),(2.7,.2,.64),(2.57,-1.42,.09)],.025)


def supply():
    footing((0,.08,.09),(5.6,4.33,.18))
    for x in [-1.56,0,1.56]:
        cyl('TankPlinth',(x,.59,.26),.69,.30,concrete)
        cyl('WaterTank',(x,.59,1.74),.64,2.68,zinc,vertices=64,role='wall')
        cyl('TankBottom',(x,.59,.47),.66,.10,rust)
        cyl('TankLid',(x,.59,3.10),.69,.13,steel,vertices=64,role='roof')
        for z in [.85,1.67,2.58]:ring('TankStrap',(x,.59,z),.649,.025,steel)
        for z in [1.11,1.35,1.59,1.83,2.07,2.31,2.55]:box('FillGaugeMark',(x-.28,-.05,z),(.09,.016,.025),ivory,.003)
        box('TankColourBand',(x+.28,-.034,1.93),(.10,.013,1.18),cyan,.003)
        pipe('TankOutlet',(x,-.04,.69),(x,-.70,.69),.068,rust)
        flange((x,-.50,.69));ring('ValveWheel',(x,-.76,.70),.13,.019,cyan,(0,1,0))
    pipe('Collector',(-1.92,-.94,.48),(1.9,-.94,.48),.09,steel)
    for x in [-1.57,0,1.57]:pipe('CollectorDrop',(x,-.64,.69),(x,-.94,.48),.059,rust)
    for x in [-2.50,2.5]:
        for y in [-1.7,1.74]:beam('AwningPost',(x,y,.17),(x,y,3.55),.086,rust,role='wall')
    for x in [-1.67,0,1.67]:sheet('SupplyCanopy',(x,0,3.60),1.73,4.10,steel,slope=.055)
    box('SupplySign',(0,-2.09,3.32),(2.45,.067,.31),steel,.012)
    text('SupplyLettering','WATER  /  RATIONS',(0,-2.13,3.32),.19)
    crate((-2.02,-1.46,.19),(.84,.66,.58),steel);crate((-2.02,-1.46,.78),(.60,.56,.43),rust)
    for x in [.75,1.18,1.61]:
        box('JerryCan',(x,-1.47,.55),(.32,.19,.59),steel,.038)
        box('CanHandle',(x,-1.47,.885),(.19,.075,.065),rust,.011)
        cyl('CanCap',(x+.09,-1.47,.865),.036,.045,zinc)
    for x in [-2.52,2.52]:bollard(x,-2.15,.14)
    wall_lamp((1.8,-2.10,3.25))


def clinic():
    footing((0,0,.09),(5.03,4.40,.18))
    for x in [-2.17,2.17]:box('ClinicSide',(x,.05,1.17),(.15,3.92,2.12),pale,.019,role='wall')
    box('ClinicRear',(0,1.92,1.24),(4.44,.15,2.24),pale,.019,role='wall')
    # Rolled arched roof, with separate repeated ribs and actual curvature.
    for j in range(7):
        y=-1.79+j*.60;verts=[];faces=[]
        for row in range(2):
            for i in range(33):
                a=i*math.pi/32
                verts.append((2.26*math.cos(a),y+(row-.5)*.64,2.1+1.12*math.sin(a)))
        for i in range(32):faces.append((i,i+1,i+34,i+33))
        obj=mesh('ArchedClinicRoof',verts,faces,pale,'roof')
        solid=obj.modifiers.new('RolledSheetThickness','SOLIDIFY');solid.thickness=.01
        cable('RoofSeam',[(2.275*math.cos(i*math.pi/32),y-.31,2.1+1.13*math.sin(i*math.pi/32)) for i in range(33)],.018,steel,'roof')
    for y in [-1.985,1.985]:
        points=[(2.255*math.cos(i*math.pi/32),y,2.1+1.115*math.sin(i*math.pi/32)) for i in range(33)]
        cap=mesh('SealedArchGable',points,[tuple(range(33))],pale,'wall')
        solid=cap.modifiers.new('GableSheetThickness','SOLIDIFY');solid.thickness=.04
    box('ClinicGableVent',(0,-2.015,2.70),(.54,.056,.24),steel,.008)
    for i in range(4):box('GableLouvre',(0,-2.055,2.63+i*.048),(.46,.027,.014),zinc,.003)
    for x,w in [(-1.57,1.28),(.72,2.59)]:box('ClinicFront',(x,-1.93,1.16),(w,.15,2.11),pale,.016,role='wall')
    box('SealedDoor',(-.66,-1.985,1.20),(1.04,.12,2.11),steel,.021)
    box('DoorWindow',(-.66,-2.056,1.55),(.58,.018,.42),glass,.017)
    box('DoorHandle',(-.27,-2.10,1.12),(.043,.055,.24),zinc,.009)
    box('ClinicWindow',(1.01,-2.024,1.48),(1.50,.025,.59),glass,.009)
    for x in [.29,1.01,1.73]:box('WindowMullion',(x,-2.043,1.48),(.035,.03,.65),steel,.006)
    box('WindowTop',(1.01,-2.047,1.81),(1.52,.10,.045),zinc,.007)
    box('AidPanel',(-1.59,-2.036,1.61),(.64,.035,.64),steel,.008)
    box('AidCrossV',(-1.59,-2.061,1.61),(.11,.016,.43),pink,.002)
    box('AidCrossH',(-1.59,-2.063,1.61),(.43,.016,.11),pink,.002)
    text('ClinicLabel','FIELD MEDIC',(.18,-2.037,2.22),.19)
    vent((1.41,-2.024,.63),.85,.43)
    for x in [-1.24,.25,1.60]:
        cyl('AirFilter',(x,.53,3.10),.19,.52,steel)
        cyl('FilterTop',(x,.53,3.39),.27,.09,rust)
    box('MedicalCase',(-2.52,.68,.56),(.55,1.31,.98),pale,.038)
    cable('ExternalAirPipe',[(-2.47,.52,.86),(-2.6,.51,1.42),(-2.39,.5,2.20),(-2.13,.5,2.53)],.061,steel)
    beam('CanopySupport',(-1.23,-2.03,2.18),(-1.23,-2.70,2.0),.045,rust)
    sheet('DoorRainCover',(-.66,-2.34,2.18),1.34,.94,steel,slope=.14)
    box('OutsideBench',(1.16,-2.63,.55),(1.6,.36,.065),steel,.012)
    for x in [.51,1.81]:beam('BenchSupport',(x,-2.63,.10),(x,-2.63,.53),.055,rust)
    wall_lamp((-.64,-2.13,2.07))


def railgun():
    cyl('WeaponFoundation',(0,.10,.20),2.18,.38,concrete,vertices=64,role='foundation')
    for x in [-1.71,1.71]:
        for y in [-1.13,1.34]:footing((x,y,.21),(.76,.84,.38))
    cyl('TraverseRing',(0,.12,.50),1.25,.24,rust,vertices=64)
    cyl('TurretPedestal',(0,.12,.98),.93,.78,steel,vertices=64,role='wall')
    for x in [-.75,.75]:box('GunCradle',(x,.14,1.43),(.26,1.38,.93),steel,.06,role='wall')
    cyl('ElevationAxle',(0,.13,1.76),.27,1.94,zinc,(1,0,0),vertices=48)
    for x in [-.95,.95]:cyl('AxleCap',(x,.13,1.76),.32,.12,rust,(1,0,0))
    box('Receiver',(0,.28,1.98),(1.19,1.47,.62),steel,.06)
    for x in [-.31,.31]:
        box('AcceleratorRail',(x,-1.47,2.06),(.20,2.74,.23),zinc,.018)
        for y in [-.51,-.94,-1.37,-1.80,-2.23]:
            box('MagneticCoil',(x,y,2.06),(.27,.16,.35),copper,.026)
    box('MuzzleBridge',(0,-2.88,2.06),(.94,.14,.51),steel,.04)
    box('MuzzleBore',(0,-2.96,2.06),(.38,.02,.11),black,.005)
    box('UpperArmour',(0,.48,2.39),(1.41,1.62,.10),steel,.024,rot=(.05,0,0),role='roof')
    for x in [-.38,.38]:
        box('CapacitorBank',(x,1.17,1.79),(.56,.68,.87),rust,.035)
        for y in [.94,1.10,1.26,1.42]:box('CapacitorFin',(x,y,1.90),(.67,.046,.69),steel,.008)
        cable('PowerCable',[(x,1.45,1.81),(x*1.8,1.45,1.30),(x*2.1,.98,.64)],.051,wiremat)
    for angle in [i*math.pi/6 for i in range(12)]:
        cyl('TurretBolt',(1.08*math.cos(angle),.12+1.08*math.sin(angle),.655),.026,.035,zinc,vertices=6)
    box('TargetConsole',(-1.45,.94,1.14),(.56,.43,.93),steel,.035)
    box('ConsoleScreen',(-1.45,.69,1.42),(.37,.03,.24),glass,.012,rot=(.18,0,0))
    for x in [-1.61,-1.46,-1.31]:cyl('ConsoleKey',(x,.663,1.20),.015,.015,cyan,(0,1,0),vertices=16)
    text('GunSerial','RX / 07',(0,-.487,2.17),.15)
    box('WeaponRoseMark',(.52,-.479,1.96),(.085,.015,.29),pink,.002)
    for x in [-1.76,1.76]:
        for j in range(3):sandbag((x,-.35+j*.61,.55),math.pi/2)


def watchtower():
    for x in [-1.44,1.44]:
        for y in [-1.27,1.27]:
            footing((x,y,.16),(.65,.65,.32))
            beam('TowerLeg',(x,y,.28),(x*.86,y*.86,4.05),.14,rust,role='wall')
    for x in [-1.4,1.4]:
        beam('SideCrossBrace',(x,-1.21,.59),(x*.89,1.11,3.90),.064,steel,role='wall')
        beam('SideCrossBrace',(x,1.21,.59),(x*.89,-1.11,3.90),.064,steel,role='wall')
    for y in [-1.22,1.22]:
        beam('RearCrossBrace',(-1.37,y,.6),(1.27,y*.90,3.88),.064,steel,role='wall')
        beam('RearCrossBrace',(1.37,y,.6),(-1.27,y*.90,3.88),.064,steel,role='wall')
    for x in [-1.32,-.44,.44,1.32]:box('PlatformDeck',(x,0,4.01),(.87,3.25,.14),zinc,.018,role='wall')
    for x in [-1.49,1.49]:
        for y in [-1.40,1.40]:beam('UpperPost',(x,y,4.05),(x,y,5.85),.075,steel,role='wall')
    for x in [-1.5,1.5]:box('LookoutShield',(x,0,4.41),(.10,2.79,.73),steel,.014,role='wall')
    box('RearShield',(0,1.41,4.4),(2.98,.09,.70),rust,.014,role='wall')
    for x in [-1.05,-.35,.35,1.05]:sandbag((x,-1.43,4.19))
    for x in [-.66,.02,.70]:sandbag((x,-1.43,4.41))
    for x in [-1.03,0,1.03]:sheet('LookoutRoof',(x,0,5.91),1.1,3.46,zinc,slope=.09)
    beam('RoofRidge',(-1.6,.95,6.00),(1.6,.95,6.00),.08,rust,role='roof')
    ladder(-.91,-1.82,4.29)
    for z in [2.1,2.75,3.4,4.05]:
        points=[(-.91+.43*math.cos(a),-1.79-.43*math.sin(a),z) for a in [i*math.pi/16 for i in range(17)]]
        cable('LadderSafetyCage',points,.017,rust)
    box('RadioCabinet',(.72,.91,4.47),(.62,.36,.71),steel,.025)
    pipe('RadioAntenna',(.76,.94,4.91),(.76,.94,6.69),.020,zinc)
    cyl('BeaconBase',(-1.18,1.20,6.08),.13,.18,steel)
    cyl('Beacon',(-1.18,1.20,6.23),.085,.15,lamp)
    text('TowerNumber','WATCH  04',(0,-1.49,4.67),.17)
    box('TowerRoseStripe',(1.37,-1.465,4.50),(.07,.018,.77),pink,.003)
    crate((.35,.03,.01),(.83,.79,.60),rust)
    crate((.35,.03,.62),(.59,.61,.41),steel)


BUILDERS={'Bunker':bunker,'Workshop':workshop,'Supply':supply,'Clinic':clinic,'Gatling Emplacement':railgun,'Mountain Hideout':watchtower}
for CURRENT, builder in BUILDERS.items():
    builder()
    print('CAMP_BUILT',CURRENT,len(camp_objects[CURRENT]),flush=True)

# Mesh-copy conversion applies bevels and curve geometry while retaining editable
# originals. Every game mesh exports around the same camp origin at ground level.
depsgraph=bpy.context.evaluated_depsgraph_get()
manifest={'units':'meters','up_axis':'Z','front_axis':'-Y (Blender)','materials':palette,'camps':{},
          'license':'Original geometry; texture sources CC0, see CREDITS.md',
          'scope':'Six reusable archetypes, not 66 individually authored camps'}
source_collection=scene.collection.children.get('Collection')


def merged_variant(name, originals, state):
    rng=random.Random(name+state)
    copies=[]
    for index,orig in enumerate(originals):
        role=orig['role']
        if state=='Damaged' and role=='roof' and index%3==0:continue
        if state=='Ruined' and (role=='roof' or orig.location.z>3):continue
        evaluated=orig.evaluated_get(depsgraph)
        data=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=depsgraph)
        ob=bpy.data.objects.new(orig.name+'_'+state,data);scene.collection.objects.link(ob)
        ob.matrix_world=orig.matrix_world.copy()
        if not ob.data.uv_layers:project_uv(ob,2)
        if state=='Damaged' and role=='roof':
            ob.rotation_euler.y+=rng.uniform(-.19,.19)
            ob.location.z-=rng.uniform(.08,.30)
        if state=='Ruined' and role!='foundation':
            # Work in world coordinates: curves/arch meshes and primitive boxes
            # have different origins. Uniform object scaling left floating gables.
            ob.data.transform(ob.matrix_world)
            ob.matrix_world=Matrix.Identity(4)
            world=[v.co.copy() for v in ob.data.vertices]
            low=min(v.z for v in world);high=max(v.z for v in world)
            if role=='wall':
                cutoff=rng.uniform(.73,1.12)
                if low>cutoff:
                    bpy.data.objects.remove(ob,do_unlink=True)
                    continue
                bm=bmesh.new();bm.from_mesh(ob.data)
                bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                    dist=.0001,plane_co=(0,0,cutoff),plane_no=(0,0,1),clear_outer=True)
                for vert in bm.verts:
                    if abs(vert.co.z-cutoff)<.002:
                        vert.co.z-=rng.uniform(0,.12)
                bm.to_mesh(ob.data);bm.free()
                if not ob.data.polygons:
                    bpy.data.objects.remove(ob,do_unlink=True)
                    continue
            elif high>1.12:
                center=sum(world,Vector())/len(world)
                rotation=Euler((rng.uniform(1.15,1.45) if high-low>1.1 else rng.uniform(-.28,.28),
                    rng.uniform(-.20,.20),rng.uniform(-.24,.24))).to_matrix().to_4x4()
                transform=Matrix.Translation(center)@rotation@Matrix.Translation(-center)
                ob.data.transform(transform)
                bottom=min(v.co.z for v in ob.data.vertices)
                ob.data.transform(Matrix.Translation((0,0,rng.uniform(.13,.30)-bottom)))
            ob.data.materials.clear();ob.data.materials.append(char)
            for p in ob.data.polygons:p.material_index=0
        elif state=='Damaged' and index%5==0 and role!='foundation':
            ob.data.materials.clear();ob.data.materials.append(char)
            for p in ob.data.polygons:p.material_index=0
        copies.append(ob)
    if state=='Ruined':
        for i in range(22):
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1,
                location=(rng.uniform(-2.0,2.0),rng.uniform(-1.70,1.65),rng.uniform(.10,.23)))
            rubble=bpy.context.object;rubble.name=name+'_ConcreteRubble'
            rubble.scale=(rng.uniform(.10,.34),rng.uniform(.08,.25),rng.uniform(.07,.20))
            rubble.rotation_euler=(rng.random(),rng.random(),rng.random()*math.pi)
            bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
            rubble.data.materials.append(concrete if i%3 else char)
            project_uv(rubble,.6);copies.append(rubble)
        for i in range(8):
            x,y=rng.uniform(-1.75,1.75),rng.uniform(-1.55,1.55)
            w,d=rng.uniform(.32,.81),rng.uniform(.24,.60)
            data=bpy.data.meshes.new('FoldedScrap')
            data.from_pydata([(x-w/2,y-d/2,.18),(x+w/2,y-d/2,.21),
                (x-w/2,y,.27),(x+w/2,y,.40),(x-w/2,y+d/2,.14),(x+w/2,y+d/2,.19)],[],
                [(0,1,3,2),(2,3,5,4)])
            data.update();scrap=bpy.data.objects.new(name+'_FoldedScrap',data);scene.collection.objects.link(scrap)
            data.materials.append(rust);project_uv(scrap,1.2);copies.append(scrap)
    bpy.ops.object.select_all(action='DESELECT')
    for ob in copies:ob.select_set(True)
    bpy.context.view_layer.objects.active=copies[0]
    bpy.ops.object.join()
    result=copies[0];result.name='SM_Camp_'+name+('' if state=='Healthy' else '_'+state)
    scene.cursor.location=(0,0,0)
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    bpy.ops.export_scene.fbx(filepath=str(OUT/(result.name+'.fbx')),use_selection=True,
        object_types={'MESH'},apply_unit_scale=True,bake_anim=False,add_leaf_bones=False,
        axis_forward='-Y',axis_up='Z',path_mode='RELATIVE')
    record={'fbx':str((OUT/(result.name+'.fbx')).relative_to(ROOT)),
            'unreal_name':result.name,'triangles':sum(len(p.vertices)-2 for p in result.data.polygons),
            'dimensions_m':list(result.dimensions),'material_slots':[m.name for m in result.data.materials]}
    result.hide_render=True;result.hide_set(True)
    return result,record


game_meshes=[]
for name, originals in camp_objects.items():
    manifest['camps'][name]={'variants':{}}
    for state in ['Healthy','Damaged','Ruined']:
        obj,record=merged_variant(name,originals,state)
        game_meshes.append(obj);manifest['camps'][name]['variants'][state]=record
    print('CAMP_EXPORTED',name,flush=True)

manifest['camps']['Workshop']['suggested_point_lights']=[
    {'position_m':[0,.20,2.37],'color':[1,.78,.51],'lumens':1300,'attenuation_radius_m':4.5}]
manifest['camps']['Supply']['suggested_point_lights']=[
    {'position_m':[0,-.80,3.26],'color':[1,.81,.58],'lumens':650,'attenuation_radius_m':3.6}]

(OUT/'camp-set-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

# Place sources in separate editing collections. Exports above remain centred.
for name, objects in camp_objects.items():
    collection=bpy.data.collections.new('Camp_'+name);scene.collection.children.link(collection)
    for obj in objects:
        for old in list(obj.users_collection):old.objects.unlink(obj)
        collection.objects.link(obj)
exports=bpy.data.collections.new('ExportMeshes');scene.collection.children.link(exports)
for obj in game_meshes:
    for old in list(obj.users_collection):old.objects.unlink(obj)
    exports.objects.link(obj)
exports.hide_render=True;exports.hide_viewport=True

scene.render.engine='CYCLES'
scene.cycles.samples=32
scene.cycles.use_denoising=True
scene.world=bpy.data.worlds.new('CampStudioWorld');scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.18,.22,.25,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.40
scene.view_settings.view_transform='AgX'

def area(name,position,energy,color,size):
    data=bpy.data.lights.new(name,'AREA');obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj)
    obj.location=position;obj.rotation_euler=(Vector((0,0,1.8))-obj.location).to_track_quat('-Z','Y').to_euler()
    data.energy=energy;data.color=color;data.size=size
    return obj

lights=[area('WarmKey',(-5,-8,11),1800,(1,.81,.63),8),
        area('CoolFill',(7,-2,7),1150,(.63,.77,1),7),area('Rim',(3,6,10),2400,(1,.78,.50),7)]
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.055))
floor=bpy.context.object;floor.name='StudioGround';floor.data.materials.append(soil)
project_uv(floor,3.4)
data=bpy.data.cameras.new('CampCamera');camera=bpy.data.objects.new('CampCamera',data);scene.collection.objects.link(camera)
camera.location=(8,-11,7.8);target=Vector((0,0,2.3))
camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
data.type='ORTHO';data.ortho_scale=8.4;scene.camera=camera
scene.render.resolution_x=1200;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
for name,objects in camp_objects.items():
    for obj in objects:
        obj.hide_render=(name!='Bunker')
        obj.hide_set(name!='Bunker')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'CampSet.blend'))

if '--render' in sys.argv:
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX'
    for device in prefs.get_devices_for_type('OPTIX'):device.use=device.type=='OPTIX'
    scene.cycles.device='GPU'
    for name in BUILDERS:
        for other,objects in camp_objects.items():
            for obj in objects:
                obj.hide_render=(other!=name)
                obj.hide_set(other!=name)
        data.ortho_scale=8.4 if name=='Mountain Hideout' else 7.8
        target=Vector((0,0,2.5 if name=='Mountain Hideout' else 1.65))
        camera.location=(8,-11,8.0 if name=='Mountain Hideout' else 7.2)
        camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        practicals=[]
        for spec in manifest['camps'][name].get('suggested_point_lights',[]):
            pd=bpy.data.lights.new('PreviewPractical','POINT');po=bpy.data.objects.new('PreviewPractical',pd)
            scene.collection.objects.link(po);po.location=spec['position_m']
            pd.color=spec['color'];pd.energy=spec['lumens']/9;pd.shadow_soft_size=.16
            practicals.append(po)
        scene.render.filepath=str(OUT/'previews'/f'{name}.png')
        bpy.ops.render.render(write_still=True)
        for po in practicals:bpy.data.objects.remove(po,do_unlink=True)
        print('CAMP_PREVIEW_RENDERED',name,flush=True)
    # One actual 3D scene makes the overview, with camera-plane arrangement.
    # Every model retains its real proportions; there are no AI redraws or
    # substituted illustrations in the contact sheet.
    floor.hide_render=True
    camera.location=(0,-30,16)
    camera.rotation_euler=(Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()
    quat=camera.rotation_euler.to_quaternion();right=quat @ Vector((1,0,0));up=quat @ Vector((0,1,0))
    offsets={}
    for index,(name,objects) in enumerate(camp_objects.items()):
        col=index%3;row=index//3
        offset=right*((col-1)*8.0)+up*((.5-row)*9.6)
        offsets[name]=offset
        for obj in objects:obj.hide_render=False;obj.hide_set(False);obj.location+=offset
        # A small isolated floor receives real contact shadows for each camp.
        bpy.ops.mesh.primitive_plane_add(size=1,location=offset+Vector((0,0,-.055)))
        pad=bpy.context.object;pad.name='OverviewGround_'+name;pad.dimensions=(7.2,6.6,1)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        pad.data.materials.append(soil);project_uv(pad,3.4)
        # Labels face the orthographic overview camera, as native text geometry.
        label=bpy.data.curves.new('OverviewLabel','FONT');label.body=name.upper()
        label.align_x='CENTER';label.size=.31;label.extrude=0
        ob=bpy.data.objects.new('OverviewLabel_'+name,label);scene.collection.objects.link(ob)
        ob.location=offset-up*2.4;ob.rotation_euler=camera.rotation_euler
        labelmat=bpy.data.materials.get('ContactSheetLabel')
        if labelmat is None:labelmat=material('ContactSheetLabel',(.76,.82,.87),rough=1,emission=1)
        ob.data.materials.append(labelmat)
        for spec in manifest['camps'][name].get('suggested_point_lights',[]):
            pd=bpy.data.lights.new('OverviewPractical','POINT');po=bpy.data.objects.new('OverviewPractical',pd)
            scene.collection.objects.link(po);po.location=offset+Vector(spec['position_m'])
            pd.color=spec['color'];pd.energy=spec['lumens']/9;pd.shadow_soft_size=.16
    # Broad uniform daylight gives the six locations comparable material values.
    for light in lights:light.hide_render=True
    sun_data=bpy.data.lights.new('OverviewSun','SUN');sun=bpy.data.objects.new('OverviewSun',sun_data);scene.collection.objects.link(sun)
    sun.rotation_euler=(.42,-.55,-.30);sun_data.energy=2.0;sun_data.angle=.12
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.35,.40,.47,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=1.5
    data.ortho_scale=25.8
    camera.location=- (quat @ Vector((0,0,-1)))*35 + up*1.1
    scene.render.resolution_x=3600;scene.render.resolution_y=2500
    scene.render.filepath=str(OUT/'CampSet_ContactSheet.png')
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'CampSet_Overview.blend'))
    # Inspect the actual exported wreck geometry under the same overview camera.
    for objects in camp_objects.values():
        for obj in objects:obj.hide_render=True
    for obj in list(bpy.data.objects):
        if obj.name.startswith('OverviewPractical'):obj.hide_render=True
    exports.hide_render=False;exports.hide_viewport=False
    for obj in game_meshes:
        obj.hide_render=not obj.name.endswith('_Ruined')
        obj.hide_set(obj.hide_render)
        if not obj.hide_render:
            name=obj.name.removeprefix('SM_Camp_').removesuffix('_Ruined')
            obj.location=offsets[name]
    scene.render.filepath=str(OUT/'CampSet_Ruins.png')
    bpy.ops.render.render(write_still=True)
    print('CAMP_CONTACT_SHEET_RENDERED',flush=True)
print('CAMP_SET_COMPLETE',flush=True)
