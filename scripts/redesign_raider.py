"""Author an editable Raider assault-truck look-development scene.

blender -b -t 8 --python scripts/redesign_raider.py -- --render
Outputs art/vehicles/raiders/redesign/Raider.blend and photographic review views.
Original game FBX assets are preserved. All dimensions are metres, nose -Y.
"""
import argparse
import math
import random
import sys
from pathlib import Path
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/vehicles/raiders/redesign'
OUT.mkdir(parents=True, exist_ok=True)
p = argparse.ArgumentParser()
p.add_argument('--render', action='store_true')
p.add_argument('--samples', type=int, default=48)
a = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
bpy.ops.wm.read_factory_settings(use_empty=True)
s = bpy.context.scene
s.unit_settings.system = 'METRIC'
random.seed(73)
col = None

def group(name):
    global col
    print('BUILDING', name, flush=True)
    col = bpy.data.collections.new(name)
    s.collection.children.link(col)

def own(o, name, mat):
    o.name = name
    for c in list(o.users_collection): c.objects.unlink(o)
    col.objects.link(o)
    if mat: o.data.materials.append(mat)
    return o

def bevel(o, width=.008):
    m=o.modifiers.new('Machined / folded edge', 'BEVEL'); m.width=width; m.segments=3
    m=o.modifiers.new('Weighted corner normals', 'WEIGHTED_NORMAL'); m.keep_sharp=True
    return o

def box(name, loc, size, mat, width=.008):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o=own(bpy.context.object,name,mat);o.dimensions=size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return bevel(o,width)

def cyl(name, loc, radius, depth, mat, axis=(0,0,1), n=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=n, radius=radius, depth=depth, location=loc)
    o=own(bpy.context.object,name,mat);o.rotation_euler=Vector(axis).to_track_quat('Z','Y').to_euler()
    for f in o.data.polygons:f.use_smooth=True
    return bevel(o,.002)

def tube(name, pts, r, mat):
    c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.resolution_u=1;c.bevel_depth=r;c.bevel_resolution=3
    sp=c.splines.new('POLY');sp.points.add(len(pts)-1)
    for p,co in zip(sp.points,pts):p.co=(*co,1)
    o=bpy.data.objects.new(name,c);col.objects.link(o);c.materials.append(mat);return o

def panel(name, verts, mat, thick=.022):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],[tuple(range(len(verts)))]);me.update()
    o=bpy.data.objects.new(name,me);col.objects.link(o);me.materials.append(mat)
    m=o.modifiers.new('Actual plate gauge','SOLIDIFY');m.thickness=thick
    return bevel(o,.005)

def ring(name, loc, major, minor, mat, axis=(0,0,1)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=minor,major_segments=64,minor_segments=12,location=loc)
    o=own(bpy.context.object,name,mat);o.rotation_euler=Vector(axis).to_track_quat('Z','Y').to_euler()
    for f in o.data.polygons:f.use_smooth=True
    return o

def bolt(loc,axis=(0,0,1),r=.012):
    cyl('Bolt washer',loc,r*1.45,.004,metal,axis,24)
    return cyl('Hex fastener',Vector(loc)+Vector(axis)*.006,r,.014,metal,axis,6)

def material(name, color, metallic=0, rough=.5, wear=False):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    n=m.node_tree.nodes;l=m.node_tree.links;b=n.get('Principled BSDF')
    b.inputs['Base Color'].default_value=(*color,1);b.inputs['Metallic'].default_value=metallic;b.inputs['Roughness'].default_value=rough
    tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=125;tex.inputs['Detail'].default_value=3
    bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.22;bump.inputs['Distance'].default_value=.00065
    l.new(tex.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],b.inputs['Normal'])
    ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(rough*.65,)*3+(1,);ramp.color_ramp.elements[1].color=(min(.98,rough*1.3),)*3+(1,)
    l.new(tex.outputs['Fac'],ramp.inputs[0]);l.new(ramp.outputs[0],b.inputs['Roughness'])
    if wear:
        coord=n.new('ShaderNodeTexCoord')
        image=n.new('ShaderNodeTexImage');image.image=bpy.data.images.load(str(ROOT/'art/library/polyhaven/rusty_metal_sheet/textures/rusty_metal_sheet_diff_4k.jpg'),check_existing=True)
        image.projection='BOX';image.projection_blend=.2;l.new(coord.outputs['Object'],image.inputs['Vector'])
        mix=n.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=.96;mix.inputs[2].default_value=(*color,1)
        l.new(image.outputs[0],mix.inputs[1]);l.new(mix.outputs[0],b.inputs['Base Color'])
    return m

paint=material('01 | sun-faded military olive / oxidized paint',(.11,.145,.085),.25,.58,True)
rust=material('02 | salvaged oxide armor',(.23,.07,.022),.45,.63,True)
metal=material('03 | exposed brushed steel',(.19,.21,.20),.85,.38)
black=material('04 | parkerized gunmetal',(.043,.054,.055),.8,.43)
rubber=material('05 | dusty vulcanized rubber',(.012,.015,.012),0,.88)
canvas=material('06 | weathered canvas',(.21,.18,.12),0,.92)
cream=material('07 | faded bone-white stencil',(.71,.68,.51),0,.73)
red=material('08 | red oxide primer',(.25,.032,.015),.35,.52)
glass=material('09 | smoked laminated glass',(.34,.43,.40),0,.065)
glass.node_tree.nodes.get('Principled BSDF').inputs['Coat Weight'].default_value=.22
glass.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].default_value=.94
glass.node_tree.nodes.get('Principled BSDF').inputs['IOR'].default_value=1.48
lamp=material('10 | headlamp glass',(.65,.51,.30),.12,.18)
b=lamp.node_tree.nodes.get('Principled BSDF');b.inputs['Emission Color'].default_value=(1,.67,.30,1);b.inputs['Emission Strength'].default_value=.45

group('01 CHASSIS • drivetrain and suspension')
for x in (-.58,.58):box('Box-section ladder rail',(x,.02,.49),(.12,3.85,.17),black)
for y in (-1.25,-.4,.55,1.24,1.75):box('Crossmember',(0,y,.49),(1.3,.10,.13),black)
for y in (-1.24,1.24):
    cyl('Live axle',(0,y,.44),.065,2.05,black,(1,0,0))
    cyl('Differential casing',(0,y,.44),.17,.3,black,(1,0,0))
    for x in (-.67,.67):
        for i in range(4):
            tube('Layered leaf spring',[(x,y-.50+j*.05,.43+i*.012+.10*((j-10)/10)**2) for j in range(21)],.012,black)
        tube('Damper piston',[(x,y-.17,.43),(x,y+.13,.88)],.022,metal)
        tube('Shock absorber',[(x,y-.17,.43),(x,y+.02,.72)],.041,red)
        tube('Coil spring',[(x+.061*math.cos(t*.23),y+.10+.061*math.sin(t*.23),.54+t*.003) for t in range(100)],.009,metal)
tube('Propeller shaft',[(0,-1.24,.44),(0,1.24,.44)],.042,metal)
box('Floor pan',(0,.02,.74),(1.65,3.62,.09),black)

group('02 BODY • formed hood and armored cab')
# Sloping bonnet built as sheet metal, with a separate removable centre panel.
panel('Bonnet crown',[(-.73,-1.83,1.13),(.73,-1.83,1.13),(.80,-.64,1.36),(-.80,-.64,1.36)],paint)
for sign in (-1,1):
    panel('Bonnet cheek',[(sign*.73,-1.83,.79),(sign*.73,-1.83,1.13),(sign*.80,-.64,1.36),(sign*.80,-.64,.82)],paint)
    tube('Bonnet panel seam',[(sign*.52,-1.81,1.138),(sign*.57,-.66,1.368)],.004,black)
    for y in (-1.58,-.85):
        box('Hood latch',(sign*.78,y,1.08),(.045,.075,.13),black)
        bolt((sign*.808,y,1.07),(sign,0,0))
    for j in range(7):
        o=box('Side cooling louvre',(sign*.805,-1.08+j*.051,1.20),(.022,.022,.11),black,.002);o.rotation_euler.x=-.18
# Radiator face and fine grille behind the vertical bars.
box('Radiator surround',(0,-1.835,.98),(1.48,.065,.34),paint)
box('Recessed radiator core',(0,-1.875,.985),(1.15,.02,.255),black)
for i in range(31):box('Radiator cooling fin',(-.55+i*.037,-1.894,.985),(.008,.013,.24),metal,.001)
for z in (.90,.98,1.06):box('Grille protection',(0,-1.905,z),(1.15,.024,.023),black)
# True window openings: no opaque solid block behind glazing.
box('Cab lower rear bulkhead',(0,.58,1.13),(1.62,.07,.68),paint)
box('Roof',(0,.06,1.96),(1.70,1.12,.065),paint,.02)
for sign in (-1,1):
    x=sign*.83
    panel('Door armor',[(x,-.64,.81),(x,.57,.81),(x,.57,1.43),(x,-.63,1.43)],paint)
    panel('Armored side window',[(x,-.58,1.46),(x,-.40,1.91),(x,.50,1.91),(x,.50,1.46)],glass,.015)
    for ya,yb,za,zb in [(-.64,-.40,1.39,1.95),(.55,.55,1.39,1.95)]:tube('Cab structural pillar',[(x,ya,za),(x,yb,zb)],.035,paint)
    tube('Window lower channel',[(x,-.61,1.44),(x,.55,1.44)],.022,black)
    panel('Salvaged door reinforcement',[(x+sign*.018,-.46,.87),(x+sign*.018,.43,.87),(x+sign*.018,.43,1.29),(x+sign*.018,-.40,1.35)],rust,.012)
    for y in (-.38,.35):
        for z in (.94,1.25):bolt((x+sign*.04,y,z),(sign,0,0))
    box('Recessed door handle',(x+sign*.036,.30,1.37),(.035,.15,.03),black)
    for z in (.93,1.24):box('External door hinge',(x+sign*.046,-.55,z),(.045,.12,.045),metal)
    box('Serrated side step',(sign*.98,.01,.67),(.30,.95,.055),metal)
    for j in range(13):box('Step tread groove',(sign*.98,-.39+j*.062,.701),(.22,.016,.012),black,.001)
    tube('Side impact rail',[(sign*1.12,-.52,.72),(sign*1.12,.60,.72)],.035,black)
    tube('Mirror arm',[(x,-.39,1.62),(sign*1.13,-.55,1.70)],.016,metal)
    box('Wing mirror housing',(sign*1.17,-.56,1.73),(.16,.075,.24),black,.025)
    box('Reflective mirror',(sign*1.17,-.514,1.73),(.134,.01,.206),glass)
# Windscreen is a sloped continuous frame with two separately inset panes.
tube('Windscreen outer frame',[(-.84,-.662,1.39),(.84,-.662,1.39),(.84,-.402,1.94),(-.84,-.402,1.94),(-.84,-.662,1.39)],.038,black)
tube('Windscreen central mullion',[(0,-.662,1.39),(0,-.402,1.94)],.025,black)
for sign in (-1,1):
    x0,x1=sorted((sign*.045,sign*.755))
    panel('Laminated windshield',[(x0,-.655,1.45),(x1,-.655,1.45),(x1,-.439,1.88),(x0,-.439,1.88)],glass,.008)
    tube('Windshield wiper',[(sign*.66,-.676,1.46),(sign*.20,-.571,1.66)],.008,black)
    tube('Wiper blade',[(sign*.15,-.589,1.63),(sign*.39,-.517,1.78)],.012,rubber)
    # Eyebrow armor overhang.
    panel('Windscreen armored visor',[(sign*.02,-.44,1.91),(sign*.86,-.44,1.91),(sign*.86,-.67,1.91),(sign*.02,-.67,1.91)],rust)
    for z in (1.47,1.61,1.75,1.87):bolt((sign*.795,-.67+(z-1.43)*.473,z),(0,-1,.47),.008)
# Dashboard and seats visible through side glass at glancing angles.
box('Dashboard',(0,-.42,1.35),(1.49,.28,.13),black)
for x in (-.43,.43):
    box('Canvas seat cushion',(x,.10,.94),(.56,.50,.14),canvas,.07)
    seat=box('Canvas seat back',(x,.35,1.24),(.56,.15,.56),canvas,.07);seat.rotation_euler.x=.08
ring('Steering wheel',(-.43,-.26,1.45),.16,.016,black,(0,-.6,.8))

group('03 RECOVERY • ram bumper, winch and lighting')
box('Heavy bumper centre',(0,-2.03,.65),(1.40,.23,.23),black,.024)
for sign in (-1,1):
    panel('Tapered bumper wing',[(sign*.65,-2.15,.54),(sign*1.10,-2.02,.64),(sign*1.08,-1.93,.84),(sign*.65,-2.15,.78)],rust,.07)
    tube('Bull bar',[(sign*.66,-2.10,.69),(sign*.66,-2.10,1.22),(sign*.51,-2.10,1.29),(0,-2.10,1.29)],.036,black)
    box('Recovery tab',(sign*.53,-2.19,.63),(.065,.15,.17),rust)
    ring('Forged recovery shackle',(sign*.53,-2.26,.58),.062,.016,metal,(1,0,0))
    # Metal headlamp bucket, sealed lens and guard.
    cyl('Headlamp housing',(sign*.66,-1.90,1.06),.119,.11,black,(0,1,0))
    cyl('Reflector lens',(sign*.66,-1.962,1.06),.095,.012,lamp,(0,1,0))
    ring('Headlight bezel',(sign*.66,-1.976,1.06),.104,.012,metal,(0,1,0))
    for d in (-.052,0,.052):tube('Lamp protection wire',[(sign*.66+d,-1.99,.98),(sign*.66+d,-1.99,1.14)],.004,black)
cyl('Winch cable drum',(0,-2.02,.86),.079,.46,black,(1,0,0))
for j in range(32):ring('Wound steel recovery cable',(-.215+j*.014,-2.02,.86),.077,.006,metal,(1,0,0))
for x in (-.27,.27):cyl('Winch drum flange',(x,-2.02,.86),.115,.035,black,(1,0,0))
cyl('Winch motor',(.40,-2.02,.86),.068,.19,black,(1,0,0))
box('Roller fairlead',(0,-2.175,.78),(.36,.055,.086),metal)
# Layered skid plate, with paired bolt heads and diagonal danger stripes.
panel('Front skid armor',[(-.62,-2.13,.52),(.62,-2.13,.52),(.51,-1.78,.30),(-.51,-1.78,.30)],rust,.018)
for x in (-.50,.50):bolt((x,-2.145,.48),(0,-1,-.4))

group('04 WHEELS • radial tires and beadlock rims')
def wheel(cx,cy,cz, spare=False):
    # Tire surface revolved around X. Tread crests stay at the original 44cm radius.
    prof=[(-.19,.245),(-.20,.30),(-.175,.365),(-.135,.412),(-.09,.425),(.09,.425),(.135,.412),(.175,.365),(.20,.30),(.19,.245)]
    vs=[];fs=[];N=96
    for x,r in prof:
        for i in range(N):
            t=i*math.tau/N;vs.append((cx+x,cy+r*math.cos(t),cz+r*math.sin(t)))
    for j in range(len(prof)):
        for i in range(N):fs.append((j*N+i,j*N+(i+1)%N,((j+1)%len(prof))*N+(i+1)%N,((j+1)%len(prof))*N+i))
    me=bpy.data.meshes.new('Radial tire carcass');me.from_pydata(vs,[],fs);me.update()
    o=bpy.data.objects.new('Rounded all-terrain carcass',me);col.objects.link(o);me.materials.append(rubber)
    for f in me.polygons:f.use_smooth=True
    for i in range(44):
        t=i*math.tau/44
        for side in (-1,1):
            o=box('Alternating chevron tread',(cx+side*.087,cy+.423*math.cos(t),cz+.423*math.sin(t)),(.15,.048,.031),rubber,.006)
            o.rotation_euler.x=t-math.pi/2;o.rotation_euler.z=side*.18
    for side in (-1,1):
        xx=cx+side*.19
        ring('Molded sidewall ridge',(xx,cy,cz),.337,.004,rubber,(1,0,0))
        ring('Bead lock ring',(xx,cy,cz),.244,.018,paint,(1,0,0))
        cyl('Deep steel wheel dish',(cx+side*.12,cy,cz),.239,.08,black,(1,0,0))
        cyl('Axle hub',(xx,cy,cz),.080,.075,metal,(1,0,0))
        for j in range(12):
            t=j*math.tau/12
            bolt((xx+side*.015,cy+.244*math.cos(t),cz+.244*math.sin(t)),(side,0,0),.008)
        for j in range(6):
            t=j*math.tau/6
            bolt((xx+side*.03,cy+.111*math.cos(t),cz+.111*math.sin(t)),(side,0,0),.012)
            # Recessed circular vent openings, dark centres inside metal collars.
            ring('Wheel ventilation lip',(cx+side*.164,cy+.173*math.cos(t),cz+.173*math.sin(t)),.037,.007,metal,(1,0,0))
for x in (-1.02,1.02):
    for y in (-1.24,1.24):wheel(x,y,.44)

group('05 FENDERS • folded armor and mud flaps')
for sign in (-1,1):
    for y in (-1.24,1.24):
        x0,x1=sign*.78,sign*1.27
        panel('Wheel arch top',[(x0,y-.27,.995),(x1,y-.27,.995),(x1,y+.27,.995),(x0,y+.27,.995)],paint)
        for d in (-1,1):
            panel('Sloped fender wing',[(x0,y+d*.27,.995),(x1,y+d*.27,.995),(x1,y+d*.53,.79),(x0,y+d*.53,.79)],paint)
        for dy in (-.19,.19):bolt((sign*1.22,y+dy,1.015),r=.008)
        box('Flexible trailing mudflap',(sign*1.025,y+.49,.56),(.40,.019,.41),rubber)
        for dx in (-.13,.13):bolt((sign*1.025+dx,y+.508,.73),(0,1,0),.008)

group('06 BED • roll cage, fuel and field stowage')
box('Bed floor',(0,1.20,.80),(1.65,1.3,.055),paint)
for j in range(12):box('Bed floor rib',(-.72+j*.13,1.2,.838),(.017,1.23,.015),metal,.002)
for sign in (-1,1):
    box('Bed armored side',(sign*.83,1.23,1.03),(.04,1.29,.40),paint)
    for y in (.65,1.22,1.80):box('Bed reinforcing stake',(sign*.86,y,1.02),(.055,.055,.43),black)
    tube('Rear roll hoop',[(sign*.80,1.68,.88),(sign*.80,1.68,1.74),(sign*.64,1.68,1.91),(0,1.68,1.91)],.043,black)
    tube('Roll cage diagonal',[(sign*.8,.64,1.94),(sign*.8,1.68,1.12)],.032,black)
    tube('Upper cage rail',[(sign*.80,.53,1.94),(sign*.64,1.68,1.91)],.038,black)
box('Tailgate',(0,1.88,1.03),(1.72,.055,.40),rust)
for x in (-.62,.62):box('Tailgate hinge',(x,1.92,.86),(.18,.06,.055),metal)
for sign in (-1,1):
    box('Taillight guard',(sign*.69,1.935,1.08),(.20,.045,.10),black)
    box('Red taillight',(sign*.69,1.963,1.08),(.14,.016,.063),red)
    for y in (.96,1.44):
        box('Pressed fuel can',(sign*.56,y,1.08),(.29,.34,.45),paint,.032)
        tube('Can handle',[(sign*.56-.095,y,1.315),(sign*.56-.095,y,1.38),(sign*.56+.095,y,1.38),(sign*.56+.095,y,1.315)],.012,metal)
        cyl('Fuel cap',(sign*.56,y-.105,1.315),.035,.027,black)
        for d in (-1,1):tube('Pressed jerrycan X',[(sign*.56-.105,y-.18,1.08+d*.14),(sign*.56+.105,y-.18,1.08-d*.14)],.008,metal)
# Soft tied bedroll, irregular profile instead of a smooth featureless box.
for i in range(8):
    o=box('Folded canvas bedroll',(0,1.21,.93+i*.042),(.62+random.uniform(-.03,.03),.65+random.uniform(-.03,.03),.085),canvas,.038)
for x in (-.22,.22):tube('Stowage tie-down',[(x,.85,.88),(x,.85,1.29),(x,1.55,1.29),(x,1.55,.88)],.014,black)
# Exhaust with an open mouth and perforated heat shield.
for sign in (-1,1):
    tube('Exhaust downpipe',[(sign*.68,.50,.47),(sign*.94,.59,.73),(sign*.94,.59,1.87)],.040,black)
    for j in range(13):ring('Exhaust heat-shield rib',(sign*.94,.59,1.03+j*.055),.060,.006,metal)
    ring('Open exhaust rim',(sign*.94,.59,1.90),.041,.005,metal)
    cyl('Dark exhaust bore',(sign*.94,.59,1.88),.035,.008,black)
tube('Flexible whip aerial',[(.70,1.62,1.65),(.72,1.63,2.05),(.78,1.67,2.47),(.89,1.73,2.83)],.0035,black)

group('07 TURRET • heavy machine gun and splinter shield')
cyl('Roof bearing',(0,.1,2.01),.23,.06,black)
for j in range(12):
    t=j*math.tau/12;bolt((.19*math.cos(t),.1+.19*math.sin(t),2.047),r=.009)
cyl('Pintle mount',(0,.1,2.16),.055,.30,metal)
box('Receiver',(0,-.16,2.33),(.19,.51,.16),black)
box('Receiver top cover',(0,-.16,2.42),(.20,.40,.035),metal)
for x in (-.13,.13):
    box('Pivot yoke',(x,.03,2.29),(.035,.14,.24),black)
    bolt((x,.03,2.32),(1 if x>0 else -1,0,0),.022)
cyl('Barrel',(0,-.88,2.34),.026,.94,black,(0,1,0))
for j in range(12):ring('Barrel cooling fins',(0,-.46-j*.037,2.34),.038,.008,black,(0,1,0))
cyl('Muzzle brake',(0,-1.40,2.34),.048,.17,metal,(0,1,0))
cyl('Recessed muzzle bore',(0,-1.49,2.34),.023,.004,black,(0,1,0))
for y in (-1.35,-1.40,-1.45):
    for sign in (-1,1):box('Muzzle brake port',(sign*.046,y,2.34),(.004,.020,.026),black,.002)
box('Ammo box',(-.24,-.08,2.32),(.22,.27,.21),paint)
for j in range(8):
    cyl('Visible linked cartridge',(-.20+j*.026,-.20,2.46+.018*math.sin(j*.5)),.009,.08,metal,(0,1,0),16)
for sign in (-1,1):
    panel('Angled gun shield',[(sign*.14,-.37,2.13),(sign*.51,-.29,2.13),(sign*.48,-.27,2.57),(sign*.22,-.34,2.62),(sign*.14,-.37,2.49)],rust,.018)
    for z in (2.20,2.49):bolt((sign*.40,-.305,z),(0,-1,0),.010)
    tube('Spade grip',[(sign*.10,.15,2.35),(sign*.16,.25,2.35),(sign*.16,.25,2.23)],.018,black)
# Gunsight.
box('Front sight post',(0,-1.14,2.405),(.018,.025,.12),black,.002)
ring('Front sight aperture',(0,-1.14,2.48),.028,.004,black,(0,1,0))

group('08 FINISH • chipped edges, welds and markings')
# Localized scratches: concentrate on exposed fender and door edges, keep broad
# panels quieter so the surface does not read as uniformly noisy procedural rust.
for sign in (-1,1):
    for j in range(42):
        y=random.uniform(-.43,.41);z=random.choice((.91,1.26))+random.uniform(-.025,.025)
        tube('Door chipped paint',[(sign*.878,y,z),(sign*.879,y+random.uniform(.012,.065),z+random.uniform(-.003,.003))],random.uniform(.0009,.002),metal)
    for y in (-1.24,1.24):
        for j in range(25):
            yy=y+random.uniform(-.26,.24)
            tube('Fender edge scuff',[(sign*1.274,yy,1.00),(sign*1.274,yy+random.uniform(.01,.05),1.00)],.0018,metal)
    for j in range(25):
        y=-.39+j*.032
        cyl('Door plate weld bead',(sign*.87,y,.875),.006,.005,metal,(sign,0,0),12)
def label(text,loc,size,rot,mat):
    c=bpy.data.curves.new('Stencil '+text,'FONT');c.body=text;c.size=size;c.extrude=.00015
    o=bpy.data.objects.new('Stencil '+text,c);col.objects.link(o);o.location=loc;o.rotation_euler=rot;c.materials.append(mat)
    return o
label('RAIDER / 07',(.48,1.916,1.05),.13,(math.pi/2,0,math.pi),cream)

sys.path.insert(0, str(ROOT / 'scripts'))
from raider_battle_wear import apply_battle_wear, apply_battle_refinements
apply_battle_wear()
apply_battle_refinements()
from raider_exposed_engine import apply_exposed_engine
apply_exposed_engine()

vehicle_objects=[o for o in s.objects]
for o in vehicle_objects:o['asset']='Raider redesign';o['units']='metres'
group('09 STUDIO • cameras and lighting')
ground=material('Studio charcoal concrete',(.070,.076,.076),0,.83)
box('Ground',(0,0,-.065),(2000,2000,.12),ground,.001)
world=bpy.data.worlds.new('Neutral studio');s.world=world;world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.32,.38,.45,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.22

def aim(o,at):o.rotation_euler=(Vector(at)-o.location).to_track_quat('-Z','Y').to_euler()
def area(name,loc,power,size,color,at=(0,0,1)):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;d.color=color
    o=bpy.data.objects.new(name,d);col.objects.link(o);o.location=loc;aim(o,at)
area('Large warm key',(-3,-4,6),1100,4,(1,.84,.66))
area('Cool edge strip',(4,2,5),1700,3,(.65,.80,1))
area('Front fill',(4,-5,2.5),280,3,(1,.96,.87))
area('Roof sheen',(-1,3,6),750,3,(1,.90,.74))
def camera(name,loc,at,lens):
    d=bpy.data.cameras.new(name);o=bpy.data.objects.new(name,d);col.objects.link(o);o.location=loc;d.lens=lens;aim(o,at);return o
hero=camera('01 HERO front three-quarter',(6.2,-8.6,4.2),(0,-.10,1.16),54)
rear=camera('02 REAR mechanical detail',(-5.5,7,3.4),(0,.2,1.15),54)
close=camera('03 FRONT low angle',(4.7,-7.3,2.15),(0,-.35,1.17),58)
s.camera=hero;s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=a.samples;s.cycles.use_denoising=True
s.render.resolution_x=1600;s.render.resolution_y=1200;s.render.resolution_percentage=100
s.view_settings.view_transform='AgX'
s.render.image_settings.file_format='PNG'
from raider_punk_crew import apply_punk_crew
apply_punk_crew()
from raider_layout_revision import apply_layout_revision
apply_layout_revision()
# Relative references and packed textures make the delivered blend portable.
bpy.ops.file.pack_all()
for screen in bpy.data.screens:
    for ar in screen.areas:
        if ar.type=='VIEW_3D':
            ar.spaces.active.region_3d.view_perspective='CAMERA'
bpy.ops.object.select_all(action='DESELECT')
s['Design']='Raider 07 | armored desert recovery / assault truck'
s['Delivery']='Blender look development; original game meshes unchanged. Runtime import and performance verification pending.'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Raider.blend'))
if a.render:
    for cam,filename in [(hero,'raider-hero.png'),(rear,'raider-rear.png'),(close,'raider-low.png'),(bpy.data.objects['04 CREW driver and gunner'],'raider-crew-detail.png')]:
        s.camera=cam;s.render.filepath=str(OUT/filename);bpy.ops.render.render(write_still=True)
print('RAIDER_REDESIGN_SAVED',OUT/'Raider.blend',len(vehicle_objects))
# This Linux installation can stall in PulseAudio teardown even with -noaudio.
# All synchronous saves/renders are complete before bypassing that shutdown.
if bpy.app.background:
    import os
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
