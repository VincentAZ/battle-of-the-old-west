"""Editable exposed V8 and large turbo assembly for the battle-worn Raider."""
import bpy
import math
from mathutils import Vector


def apply_exposed_engine():
    s=bpy.context.scene
    for o in list(s.objects):
        if (o.type=='FONT' and o.data.body=='NO STEP') or o.name.startswith('Faded hood recognition stripe'):
            bpy.data.objects.remove(o,do_unlink=True)
    if bpy.data.collections.get('11 EXPOSED TURBO ENGINE'):return
    col=bpy.data.collections.new('11 EXPOSED TURBO ENGINE');s.collection.children.link(col)
    def material(name,color,metal=.65,rough=.55):
        m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
        n=m.node_tree.nodes;l=m.node_tree.links;b=n.get('Principled BSDF')
        b.inputs['Metallic'].default_value=metal;b.inputs['Roughness'].default_value=rough
        noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=32;noise.inputs['Detail'].default_value=4
        mix=n.new('ShaderNodeMixRGB');mix.inputs[1].default_value=(*color,1);mix.inputs[2].default_value=(*(v*.25 for v in color),1)
        l.new(noise.outputs['Fac'],mix.inputs[0]);l.new(mix.outputs[0],b.inputs['Base Color'])
        bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.28;bump.inputs['Distance'].default_value=.001
        l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],b.inputs['Normal']);return m
    alloy=material('Engine | greasy cast aluminum',(.34,.36,.32),.78,.48)
    steel=material('Engine | aged steel',(.12,.13,.115),.80,.48)
    cast=material('Engine | heat oxidized turbine',(.14,.055,.018),.7,.78)
    rubber=material('Engine | oil-dark hoses and belts',(.013,.016,.014),0,.86)
    red=material('Engine | chipped red rocker covers',(.22,.035,.017),.45,.62)
    inside=material('Engine | intake interior',(.008,.009,.007),.1,.93)
    def own(o,name,mat):
        o.name=name
        for c in list(o.users_collection):c.objects.unlink(o)
        col.objects.link(o);o.data.materials.append(mat);o['asset']='Raider redesign';return o
    def bevel(o,w=.008):
        b=o.modifiers.new('Rounded casting edges','BEVEL');b.width=w;b.segments=3
        b=o.modifiers.new('Casting corner normals','WEIGHTED_NORMAL');b.keep_sharp=True;return o
    def box(name,loc,size,mat):
        bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=own(bpy.context.object,name,mat);o.dimensions=size
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return bevel(o)
    def cyl(name,loc,r,d,mat,axis=(0,0,1),n=48):
        bpy.ops.mesh.primitive_cylinder_add(vertices=n,radius=r,depth=d,location=loc)
        o=own(bpy.context.object,name,mat);o.rotation_euler=Vector(axis).to_track_quat('Z','Y').to_euler()
        for f in o.data.polygons:f.use_smooth=True
        return bevel(o,.002)
    def tube(name,pts,r,mat):
        c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=r;c.bevel_resolution=4
        p=c.splines.new('POLY');p.points.add(len(pts)-1)
        for a,v in zip(p.points,pts):a.co=(*v,1)
        o=bpy.data.objects.new(name,c);col.objects.link(o);c.materials.append(mat);o['asset']='Raider redesign';return o
    def ring(name,loc,r,minor,mat,axis=(0,-1,0)):
        bpy.ops.mesh.primitive_torus_add(major_radius=r,minor_radius=minor,major_segments=64,minor_segments=12,location=loc)
        o=own(bpy.context.object,name,mat);o.rotation_euler=Vector(axis).to_track_quat('Z','Y').to_euler()
        for f in o.data.polygons:f.use_smooth=True
        return o
    # Cut a physical opening through the existing dented hood, retaining its wear.
    hood=bpy.data.objects.get('Bonnet crown')
    bpy.ops.object.select_all(action='DESELECT');hood.select_set(True);bpy.context.view_layer.objects.active=hood
    for mod in list(hood.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)
    cutter=box('Temporary engine aperture',(.115,-1.26,1.35),(1.11,.94,1.1),inside)
    bpy.context.view_layer.objects.active=hood
    boolean=hood.modifiers.new('Cut through hood for exposed engine','BOOLEAN');boolean.operation='DIFFERENCE';boolean.solver='EXACT';boolean.object=cutter
    bpy.ops.object.modifier_apply(modifier=boolean.name);bpy.data.objects.remove(cutter,do_unlink=True)
    for o in list(s.objects):
        if o.name.startswith(('Field-welded hood repair','Rough field weld')):bpy.data.objects.remove(o,do_unlink=True)
    # Raw cut edges follow the slope of the surviving sheet metal.
    def hz(y):return 1.13+(y+1.83)*(.23/1.19)
    for x in (-.44,.67):tube('Raw hood aperture side',[(x,-1.73,hz(-1.73)),(x,-.79,hz(-.79))],.006,steel)
    for y in (-1.73,-.79):tube('Raw hood aperture end',[(-.44,y,hz(y)),(.67,y,hz(y))],.006,steel)
    # Block and two inclined cylinder heads form a recognizable V configuration.
    box('V8 crankcase',(0,-1.23,1.15),(.48,.72,.32),steel)
    for side in (-1,1):
        head=box('Cylinder head',(side*.21,-1.23,1.39),(.23,.73,.23),alloy);head.rotation_euler.y=side*.34
        cover=box('Rocker cover',(side*.255,-1.23,1.51),(.19,.71,.10),red);cover.rotation_euler.y=side*.34
        for j in range(5):tube('Rocker cover raised cooling rib',[(side*.245+(j-2)*.027,-1.54,1.577),(side*.245+(j-2)*.027,-.94,1.577)],.005,alloy)
        for y in (-1.54,-1.34,-1.14,-.94):
            cyl('Rocker cover fastener',(side*.32,y,1.56),.011,.014,steel,n=6)
            cyl('Spark plug boot',(side*.36,y,1.43),.016,.075,rubber,(side,.0,.3))
            tube('Ignition lead',[(side*.39,y,1.44),(side*.39,y+.04,1.54),(side*.10,-.91,1.57)],.006,rubber)
            tube('Exhaust header runner',[(side*.32,y,1.34),(side*.43,y,1.31),(side*.47,y+.06,1.22),(side*.48,-1.11,1.22)],.022,cast)
    box('Intake plenum',(0,-1.22,1.57),(.23,.52,.16),alloy)
    for y in (-1.44,-1.28,-1.12,-.98):
        for side in (-1,1):tube('Intake runner',[(0,y,1.59),(side*.12,y,1.56),(side*.17,y,1.43)],.025,alloy)
    cyl('Oil filler cap',(-.25,-1.02,1.60),.035,.035,steel)
    # Front accessory drive, visible between grille and engine.
    for x,z,r in [(0,1.12,.09),(-.23,1.29,.065),(.19,1.30,.055)]:
        cyl('Accessory drive pulley',(x,-1.625,z),r,.037,steel,(0,-1,0))
        ring('Pulley belt groove',(x,-1.652,z),r*.88,.010,rubber)
        cyl('Pulley hub',(x,-1.659,z),.020,.023,alloy,(0,-1,0),6)
    tube('Accessory serpentine belt',[(-.28,-1.65,1.31),(-.04,-1.65,1.035),(.065,-1.65,1.06),(.24,-1.65,1.29),(.20,-1.65,1.35),(-.23,-1.65,1.35),(-.28,-1.65,1.31)],.011,rubber)
    cyl('Alternator body',(-.23,-1.52,1.29),.066,.14,alloy,(0,1,0))
    # Large turbo: asymmetric spiral volute, recessed compressor bellmouth,
    # separate exhaust turbine housing and visible impeller blades.
    center=Vector((.48,-1.37,1.70))
    verts=[];faces=[];steps=100;sides=16
    for i in range(steps):
        t=i/(steps-1)*math.tau
        pathr=.118+.040*i/(steps-1);section=.037+.017*i/(steps-1)
        radial=Vector((math.cos(t),0,math.sin(t)))
        c=center+radial*pathr
        for j in range(sides):
            angle=j*math.tau/sides
            verts.append(c+radial*(math.cos(angle)*section)+Vector((0,math.sin(angle)*section,0)))
        if i:
            for j in range(sides):faces.append(((i-1)*sides+j,(i-1)*sides+(j+1)%sides,i*sides+(j+1)%sides,i*sides+j))
    data=bpy.data.meshes.new('Spiral compressor volute');data.from_pydata(verts,[],faces);data.update()
    ob=bpy.data.objects.new('Turbocharger cast snail housing',data);col.objects.link(ob);data.materials.append(alloy);ob['asset']='Raider redesign'
    for f in data.polygons:f.use_smooth=True
    cyl('Compressor back plate',(.48,-1.346,1.70),.134,.03,alloy,(0,1,0))
    cyl('Dark recessed compressor intake',(.48,-1.414,1.70),.090,.01,inside,(0,1,0))
    ring('Turbo bellmouth rim',(.48,-1.447,1.70),.092,.014,alloy)
    for j in range(12):
        t=j*math.tau/12
        vv=[]
        for r,offset in [(.018,0),(.079,.33),(.077,.49),(.020,.13)]:vv.append((.48+r*math.cos(t+offset),-1.429,1.70+r*math.sin(t+offset)))
        me=bpy.data.meshes.new('Impeller vane');me.from_pydata(vv,[],[(0,1,2,3)]);me.update()
        oo=bpy.data.objects.new('Compressor impeller vane',me);col.objects.link(oo);me.materials.append(steel)
    cyl('Impeller center spindle',(.48,-1.444,1.70),.020,.034,alloy,(0,1,0),12)
    cyl('Turbo bearing cartridge',(.48,-1.22,1.70),.065,.19,steel,(0,1,0))
    ring('Exhaust turbine housing',(.48,-1.11,1.70),.095,.046,cast)
    tube('Turbo exhaust up-pipe',[(.48,-1.11,1.22),(.57,-1.03,1.30),(.59,-1.03,1.55),(.55,-1.11,1.68)],.037,cast)
    tube('Turbine exhaust downpipe',[(.48,-1.055,1.70),(.48,-.91,1.70),(.57,-.86,1.60),(.59,-.86,1.24)],.048,cast)
    # Charge outlet leaves the volute tangentially and feeds the intake plenum.
    tube('Boost charge pipe',[(.64,-1.37,1.70),(.66,-1.37,1.87),(.57,-1.37,1.94),(.24,-1.37,1.94),(.09,-1.37,1.85),(.09,-1.37,1.68)],.039,alloy)
    for x in (.27,.34):
        ring('Charge pipe hose clamp',(x,-1.37,1.94),.043,.006,steel,(1,0,0))
    cyl('Charge pipe rubber coupler',(.305,-1.37,1.94),.042,.087,rubber,(1,0,0))
    cyl('Wastegate actuator',(.67,-1.16,1.77),.042,.062,steel,(1,0,0))
    tube('Wastegate linkage',[(.67,-1.16,1.76),(.61,-1.10,1.64)],.006,alloy)
    tube('Turbo oil supply',[(.48,-1.22,1.76),(.33,-1.14,1.78),(.13,-1.00,1.46)],.005,steel)
    tube('Oil drain return',[(.48,-1.22,1.65),(.41,-1.22,1.44),(.25,-1.20,1.17)],.012,rubber)
    s['Engine revision']='Hood stripes and NO STEP removed; cut-open hood, exposed V8, large snail turbo, impeller, charge piping, exhaust headers and accessory drive.'
    assert not any(o.type=='FONT' and o.data.body=='NO STEP' for o in s.objects)
    assert not any(o.name.startswith('Faded hood recognition stripe') for o in s.objects)
    print('EXPOSED_ENGINE_APPLIED',len(col.objects),flush=True)
