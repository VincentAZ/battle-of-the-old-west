"""Author five sourced, static Trouble props locally in Mixar."""
import hashlib
import json
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import create_trouble_landscapes as geo
from create_trouble_objects import box, rod, curve

EVIDENCE=ROOT/'research/western-presentation/trouble-schemes.json'
OUT=ROOT/'art/western/trouble/schemes-v003'
COLOURS={'Earth':(.19,.083,.025),'Cloud':(.14,.19,.26),'Grass':(.12,.27,.019),
         'GrassLight':(.31,.43,.033),'Wood':(.28,.11,.027),'WoodLight':(.43,.22,.065),
         'WoodDark':(.11,.032,.009),'Olive':(.28,.29,.054),'Iron':(.022,.025,.029),
         'Steel':(.22,.25,.27),'Bronze':(.63,.34,.085),'Copper':(.66,.24,.087),
         'Gold':(.89,.53,.045),'PanMetal':(.29,.32,.34),'Rock':(.32,.28,.22),
         'Sand':(.33,.25,.13),'Paper':(.86,.77,.56),'Tar':(.025,.018,.011),
         'Glass':(.76,.90,.94),'FlameAmber':(1,.38,.012)}
METALS={'Iron','Steel','Bronze','Copper','Gold','PanMetal'}


def lathe(name,profile,material,segments=64):
    verts=[(r*math.cos(i*math.tau/segments),r*math.sin(i*math.tau/segments),z)
           for r,z in profile for i in range(segments)]
    faces=[]
    for j in range(len(profile)-1):
        for i in range(segments):
            a=j*segments+i;b=j*segments+(i+1)%segments
            faces.append((a,b,b+segments,a+segments))
    return geo.mesh(name,verts,faces,[material],smooth=True)


def ground():
    geo.base();rng=random.Random(375)
    for _ in range(45):
        a=rng.random()*math.tau;r=rng.uniform(.73,.91)
        x=r*math.cos(a);y=r*.73*math.sin(a)
        for j in range(4):
            geo.blade(x+rng.uniform(-.02,.02),y+rng.uniform(-.02,.02),.12,
                rng.uniform(.08,.17),.008,'Grass' if j%2 else 'GrassLight',rng.random()*math.tau,.04)


def beam(name,a,b,width,depth,mat):
    a,b=Vector(a),Vector(b);obj=box(name,(a+b)/2,(width,depth,(b-a).length),mat,.005)
    obj.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();return obj


def ring(name,radius,width,thickness,location,material,axis='Z'):
    obj=lathe(name,[(radius-thickness,-width/2),(radius,-width/2),(radius,width/2),
        (radius-thickness,width/2),(radius-thickness,-width/2)],material)
    if axis=='X':obj.rotation_euler[1]=math.pi/2
    obj.location=location;return obj


def cannonade():
    ground()
    # Closed exterior tube with a shallow black muzzle, no working bore.
    tube=lathe('BronzeTube',[(0,.30),(.095,.30),(.13,.24),(.15,.13),(.16,-.18),
        (.15,-.38),(.145,-.61),(.174,-.66),(.174,-.74),(.12,-.74),(.12,-.715)],'Bronze')
    tube.rotation_euler[0]=-math.pi/2;tube.location=(0,-.13,.98)
    rod('MuzzleShadow',(0,-.872,.98),(0,-.870,.98),.119,'Iron')
    geo.ellipsoid('BreechKnob',(0,.245,.98),(.058,.067,.058),'Bronze',2)
    rod('Trunnion',(-.31,-.06,.95),(.31,-.06,.95),.065,'Bronze')
    rod('Axle',(-.77,-.08,.62),(.77,-.08,.62),.057,'Iron')
    for x in (-.66,.66):
        ring('WoodFelloe',.48,.09,.065,(x,-.08,.62),'Olive','X')
        ring('IronTire',.488,.095,.018,(x,-.08,.62),'Iron','X')
        rod('WheelHub',(x-.075,-.08,.62),(x+.075,-.08,.62),.10,'Olive')
        for i in range(12):
            a=i*math.tau/12
            beam('WheelSpoke',(x,-.08+.055*math.cos(a),.62+.055*math.sin(a)),
                (x,-.08+.435*math.cos(a),.62+.435*math.sin(a)),.034,.038,'Olive')
        rod('HubIron',(x-.083,-.08,.62),(x+.083,-.08,.62),.038,'Iron')
    for x in (-.24,.24):
        beam('CarriageCheek',(x,-.32,.90),(x,.23,.74),.13,.17,'Olive')
        beam('RearTrail',(x,.23,.74),(x*.20,.69,.20),.14,.12,'Olive')
        box('TrunnionStrap',(x,-.06,.994),(.11,.16,.026),'Iron',.005)
    box('TrailShoe',(0,.68,.19),(.30,.18,.05),'Iron',.008)
    box('CarriageTransom',(0,.30,.62),(.57,.12,.11),'Olive',.005)


def polygon_stock(name,outline,depth,mat):
    verts=[(x,y,z) for y in (-depth/2,depth/2) for x,z in outline];n=len(outline)
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
    obj=geo.mesh(name,verts,faces,[mat])
    bpy.context.view_layer.objects.active=obj
    mod=obj.modifiers.new('StockEdge','BEVEL');mod.width=.007;mod.segments=3
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def ambush():
    ground()
    for loc,scale in [((-.48,.13,.41),(.27,.25,.25)),((.37,-.20,.37),(.26,.24,.28)),
                      ((-.40,.15,.18),(.24,.22,.13)),((.44,.26,.18),(.18,.20,.12))]:
        obj=geo.ellipsoid('RockSupport',loc,scale,'Rock',2)
        for p in obj.data.polygons:p.use_smooth=False
    start=len(geo.PARTS)
    polygon_stock('ShoulderStock',[(-.85,-.04),(-.82,.095),(-.49,.075),(-.29,.015),
        (-.13,.015),(-.13,-.07),(-.37,-.10),(-.47,-.16),(-.84,-.19)],.09,'Wood')
    box('Receiver',(-.06,0,.004),(.24,.115,.13),'Steel',.012)
    rod('Barrel',(.045,0,.08),(.87,0,.08),.022,'Iron')
    rod('Magazine',(.11,0,.019),(.81,0,.019),.019,'Iron')
    box('ForeEnd',(.30,0,.00),(.40,.078,.088),'Wood',.028)
    for x in (.13,.49):box('BarrelBand',(x,0,.038),(.025,.09,.12),'Iron',.006)
    box('FrontSight',(.81,0,.11),(.035,.01,.03),'Iron',.002)
    box('RearSight',(.19,0,.113),(.07,.018,.015),'Iron',.002)
    curve('LeverLoop',[(-.105+.135*math.cos(i*math.tau/40),0,-.12+.078*math.sin(i*math.tau/40)) for i in range(41)],.010,'Iron')
    beam('ButtPlate',(-.845,0,-.19),(-.835,0,.095),.017,.10,'Iron')
    bpy.context.view_layer.update()
    transform=Matrix.Translation((.01,-.09,.75))@Matrix.Rotation(math.radians(-25),4,'Z')
    for obj in geo.PARTS[start:]:obj.matrix_world=transform@obj.matrix_world


def gold_rush():
    ground()
    for x,y,r in [(-.26,.22,.18),(.31,.23,.16),(.62,-.25,.11)]:
        obj=geo.ellipsoid('RiverStone',(x,y,.17),(r,r*.85,r*.55),'Rock',2)
        for p in obj.data.polygons:p.use_smooth=False
    start=len(geo.PARTS)
    lathe('PlainMetalPan',[(0,0),(.32,0),(.53,.155),(.54,.17),(.533,.18),
        (.519,.169),(.31,.013),(0,.013)],'PanMetal',96)
    ring('PanLip',.535,.011,.010,(0,0,.173),'PanMetal')
    geo.ellipsoid('WetSand',(.02,.015,.019),(.25,.20,.01),'Sand',2)
    rng=random.Random(419)
    for _ in range(15):
        x,y=rng.uniform(-.19,.19),rng.uniform(-.13,.13)
        geo.ellipsoid('SmallPebble',(x,y,.031),(.019,.015,.009),'Rock',1)
    for x,y,r in [(-.10,-.04,.012),(.04,.07,.016),(.13,-.045,.01)]:
        geo.ellipsoid('GoldFleck',(x,y,.036),(r,r*.75,r*.30),'Gold',2)
    bpy.context.view_layer.update()
    transform=Matrix.Translation((0,0,.26))@Matrix.Rotation(math.radians(24),4,'X')
    for obj in geo.PARTS[start:]:obj.matrix_world=transform@obj.matrix_world


def dynamite_crate():
    ground()
    box('CrateFloor',(0,0,.17),(1.03,.68,.07),'WoodDark',.004)
    for i in range(3):
        z=.245+i*.145
        for y in (-.34,.34):box('SidePlank',(0,y,z),(1.10,.05,.14),'WoodLight' if i%2 else 'Wood',.003)
        for x in (-.52,.52):box('EndPlank',(x,0,z),(.05,.65,.14),'Wood',.003)
    for x in (-.44,.44):
        for y in (-.378,.378):
            box('CornerBatten',(x,y,.39),(.07,.035,.47),'WoodLight',.002)
            for z in (.24,.52):rod('Nail',(x,y-.019,z),(x,y+.019,z),.005,'Iron')
    # Closed exterior paper rolls are only partly visible beneath the offset lid.
    for i in range(4):rod('PaperWrappedCartridge',(-.35+i*.23,-.25,.47),(-.35+i*.23,.22,.47),.045,'Paper')
    for i in range(4):box('OffsetLid',(-.09,-.15+i*.16,.645),(1.12,.151,.045),'WoodLight' if i%2 else 'Wood',.003)
    for x in (-.43,.28):box('LidBatten',(x,.09,.681),(.06,.62,.024),'WoodDark',.003)
    curve('LooseFuseCoil',[(.06+( .13+.07*i/239)*math.cos(i*math.tau*2.5/239),
        .06+(.13+.07*i/239)*math.sin(i*math.tau*2.5/239),.711) for i in range(240)],.012,'Tar')
    for x in (-.30,.05,.31):
        curve('BoardGrain',[(x+.008*math.sin(i*.7),-.367,.19+i*.017) for i in range(23)],.0015,'WoodDark')


def curfew():
    ground()
    for i in range(6):box('BoardwalkPlank',(-.46+i*.17,-.13,.15),(.163,.84,.065),'WoodLight' if i%3 else 'Wood',.004)
    box('PlainPost',(0,.18,1.02),(.115,.115,1.83),'WoodDark',.006)
    box('LampSupport',(0,.18,1.95),(.39,.39,.065),'Copper',.01)
    for x in (-.20,.20):
        for y in (-.02,.38):box('CopperCorner',(x,y,2.24),(.025,.025,.56),'Copper',.003)
    for z in (1.99,2.50):box('LampFrame',(0,.18,z),(.435,.435,.03),'Copper',.007)
    for x in (-.199,.199):box('SideGlass',(x,.18,2.245),(.005,.365,.475),'Glass')
    for y in (-.019,.379):box('FrontGlass',(0,y,2.245),(.365,.005,.475),'Glass')
    cap=lathe('Reservoir',[(0,0),(.074,0),(.079,.05),(.05,.078),(.024,.078)],'Copper',48)
    cap.location=(0,.18,2.015)
    rod('Burner',(0,.18,2.09),(0,.18,2.115),.025,'Iron')
    geo.ellipsoid('SmallKeroseneFlame',(0,.18,2.16),(.014,.014,.048),'FlameAmber',2)
    geo.mesh('SlopingRainCap',[(-.26,-.08,2.52),(.26,-.08,2.52),(.26,.44,2.52),(-.26,.44,2.52),
        (-.07,.11,2.68),(.07,.11,2.68),(.07,.25,2.68),(-.07,.25,2.68)],
        [(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)],['Copper'])
    box('VentCap',(0,.18,2.705),(.14,.14,.035),'Copper',.006)


def main():
    evidence=json.loads(EVIDENCE.read_text());assert 'mixar' in Path(bpy.app.binary_path).name.lower()
    OUT.mkdir(parents=True,exist_ok=True);records=[]
    authors={'cannonade':cannonade,'ambush':ambush,'gold_rush':gold_rush,'run_out_of_town':dynamite_crate,'curfew':curfew}
    for entry in evidence['assets']:
        assert entry['sources'] and entry['render_brief']
        bpy.ops.wm.read_factory_settings(use_empty=True);geo.PARTS.clear();geo.MATS.clear()
        for name,rgb in COLOURS.items():
            mat=bpy.data.materials.new('M_Trouble_'+name);mat.use_nodes=True
            shader=mat.node_tree.nodes['Principled BSDF'];shader.inputs['Base Color'].default_value=(*rgb,1)
            shader.inputs['Roughness'].default_value=.38 if name in METALS else .78
            shader.inputs['Metallic'].default_value=.8 if name in METALS else 0
            if name=='Glass':
                shader.inputs['Transmission Weight'].default_value=1;shader.inputs['Roughness'].default_value=.08
                shader.inputs['IOR'].default_value=1.45
            if name.startswith('Flame'):
                shader.inputs['Emission Color'].default_value=(*rgb,1);shader.inputs['Emission Strength'].default_value=.7
            geo.MATS[name]=mat
        authors[entry['card_id']]();bpy.ops.object.select_all(action='DESELECT')
        for part in geo.PARTS:part.select_set(True)
        bpy.context.view_layer.objects.active=geo.PARTS[0];bpy.ops.object.join();obj=bpy.context.object
        obj.name=entry['name'];bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');obj.data.calc_loop_triangles()
        fbx=OUT/(obj.name+'.fbx');project=OUT/(obj.name+'.blend')
        bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE')
        bpy.ops.wm.save_as_mainfile(filepath=str(project))
        records.append(dict(name=obj.name,card_id=entry['card_id'],fbx=fbx.name,sha256=hashlib.sha256(fbx.read_bytes()).hexdigest(),
            project_sha256=hashlib.sha256(project.read_bytes()).hexdigest(),triangles=len(obj.data.loop_triangles),materials=[m.name for m in obj.data.materials]))
        tall=entry['card_id']=='curfew'
        geo.render(obj,OUT/(entry['card_id']+'.png'),focus=(0,0,1.3 if tall else .48),ortho_scale=3.4 if tall else 2.5)
    (OUT/'manifest.json').write_text(json.dumps(dict(evidence_sha256=hashlib.sha256(EVIDENCE.read_bytes()).hexdigest(),assets=records,
        material_linear_rgb={'M_Trouble_'+n:c for n,c in COLOURS.items()},visual_review='pending'),indent=2)+'\n')
    print('TROUBLE_SCHEMES_AUTHORED',[(r['card_id'],r['triangles']) for r in records],flush=True)


if __name__=='__main__':main()
