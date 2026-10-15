"""Deterministic physical damage and layered dirt for the authored Raider scene.
Called by redesign_raider.py; also supports an existing scene with --python.
"""
import bpy
import bmesh
import math
import random
from mathutils import Vector


def apply_battle_wear():
    if bpy.data.collections.get('10 BATTLE WEAR'): return
    rng=random.Random(1947)
    scene=bpy.context.scene
    collection=bpy.data.collections.new('10 BATTLE WEAR');scene.collection.children.link(collection)
    def mat(name,color,rough=1,metal=0):
        m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
        n=m.node_tree.nodes;l=m.node_tree.links;b=n.get('Principled BSDF');b.inputs['Base Color'].default_value=(*color,1);b.inputs['Roughness'].default_value=rough;b.inputs['Metallic'].default_value=metal
        t=n.new('ShaderNodeTexNoise');t.inputs['Scale'].default_value=180;t.inputs['Detail'].default_value=3
        bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.6;bump.inputs['Distance'].default_value=.002
        l.new(t.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],b.inputs['Normal']);return m
    oxide=mat('Wear | dark exposed oxide',(.075,.027,.009),.94,.15)
    edge=mat('Wear | freshly gouged steel',(.14,.15,.14),.65,.7)
    mud=mat('Wear | baked desert mud',(.14,.088,.043))
    soot=mat('Wear | carbon and oil',(.006,.004,.003),.96)
    pale=mat('Wear | fractured laminated glass',(.42,.46,.42),.45)

    # Use world-space noise so chips stay the same physical size across panels,
    # fasteners, tires and letters. Three separate scales avoid uniform speckle.
    for material in list(bpy.data.materials):
        if material.name.startswith(('Wear |','Studio')) or not material.use_nodes:continue
        n=material.node_tree.nodes;l=material.node_tree.links;b=n.get('Principled BSDF')
        if not b:continue
        glass='glass' in material.name.lower();rubber='rubber' in material.name.lower()
        geo=n.new('ShaderNodeNewGeometry')
        def noise(scale,detail=3,vector=None):
            t=n.new('ShaderNodeTexNoise');t.inputs['Scale'].default_value=scale;t.inputs['Detail'].default_value=detail
            l.new(vector or geo.outputs['Position'],t.inputs['Vector']);return t.outputs['Fac']
        def ramp(source,low,high):
            t=n.new('ShaderNodeValToRGB');t.color_ramp.elements[0].position=low;t.color_ramp.elements[1].position=high
            l.new(source,t.inputs[0]);return t.outputs['Color']
        def mathnode(op,x,y):
            t=n.new('ShaderNodeMath');t.operation=op
            for val,inp in zip((x,y),t.inputs):
                if isinstance(val,(int,float)):inp.default_value=val
                else:l.new(val,inp)
            return t.outputs[0]
        def mix(source,fac,color):
            t=n.new('ShaderNodeMixRGB');l.new(fac,t.inputs[0])
            if hasattr(source,'node'):l.new(source,t.inputs[1])
            else:t.inputs[1].default_value=source
            if hasattr(color,'node'):l.new(color,t.inputs[2])
            else:t.inputs[2].default_value=(*color,1)
            return t.outputs[0]
        source=b.inputs['Base Color'].links[0].from_socket if b.inputs['Base Color'].links else tuple(b.inputs['Base Color'].default_value)
        # Fractal, ragged paint loss and different dark/light oxide colors.
        chips=ramp(noise(24,5),.49,.64)
        oxide_color=mix((.026,.012,.006,1),noise(62),(.24,.083,.017))
        if not glass and not rubber:
            source=mix(source,mathnode('MULTIPLY',chips,.78),oxide_color)
        # Vertical rain trails have narrow horizontal width and long downflow.
        stretch=n.new('ShaderNodeVectorMath');stretch.operation='MULTIPLY';stretch.inputs[1].default_value=(15,15,.65)
        l.new(geo.outputs['Position'],stretch.inputs[0])
        streak=ramp(noise(3,3,stretch.outputs[0]),.50,.72)
        source=mix(source,mathnode('MULTIPLY',streak,.35 if glass else .62),(.038,.026,.012))
        sep=n.new('ShaderNodeSeparateXYZ');l.new(geo.outputs['Position'],sep.inputs[0])
        height=mathnode('SUBTRACT',1.30,sep.outputs['Z'])
        height=mathnode('MULTIPLY',height,1.1)
        coverage=mathnode('ADD',height,mathnode('MULTIPLY',noise(8),.45))
        coverage=ramp(coverage,.15,.85)
        dust=mix((.075,.045,.021,1),noise(100),(.25,.17,.083))
        source=mix(source,mathnode('MULTIPLY',coverage,.72 if rubber else .86),dust)
        l.new(source,b.inputs['Base Color'])
        if not glass:
            rough=n.new('ShaderNodeMapRange');rough.inputs['To Min'].default_value=.67;rough.inputs['To Max'].default_value=.98
            l.new(noise(45),rough.inputs[0]);l.new(rough.outputs[0],b.inputs['Roughness'])
            bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.43;bump.inputs['Distance'].default_value=.0018
            if b.inputs['Normal'].links:l.new(b.inputs['Normal'].links[0].from_socket,bump.inputs['Normal'])
            l.new(noise(95,4),bump.inputs['Height']);l.new(bump.outputs['Normal'],b.inputs['Normal'])
        else:
            # Glass remains reflective, with visible accumulated grime.
            for link in list(b.inputs['Roughness'].links):l.remove(link)
            b.inputs['Roughness'].default_value=.15

    def mesh(name,verts,faces,material):
        data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
        ob=bpy.data.objects.new(name,data);collection.objects.link(ob);data.materials.append(material);ob['asset']='Raider redesign';return ob
    def line(name,pts,width,material):
        c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=width;c.bevel_resolution=2
        sp=c.splines.new('POLY');sp.points.add(len(pts)-1)
        for p,co in zip(sp.points,pts):p.co=(*co,1)
        ob=bpy.data.objects.new(name,c);collection.objects.link(ob);c.materials.append(material);ob['asset']='Raider redesign';return ob
    def spot(name,center,u,v,rx,ry,material):
        center=Vector(center);u=Vector(u);v=Vector(v)
        points=[center]
        for j in range(13):
            t=j*math.tau/12;k=rng.uniform(.63,1.25)
            points.append(center+u*(math.cos(t)*rx*k)+v*(math.sin(t)*ry*k))
        return mesh(name,points,[(0,j,j+1) for j in range(1,13)],material)
    # Genuine panel deformation, preserving mating edges.
    for ob in list(scene.objects):
        if ob.type!='MESH':continue
        if ob.name.startswith(('Bonnet crown','Salvaged door reinforcement','Angled gun shield','Wheel arch top','Sloped fender wing','Tailgate')):
            if len(ob.data.polygons)==1:
                bm=bmesh.new();bm.from_mesh(ob.data);bmesh.ops.subdivide_edges(bm,edges=list(bm.edges),cuts=14,use_grid_fill=True);bm.to_mesh(ob.data);bm.free()
                for vert in ob.data.vertices:
                    x,y,z=vert.co
                    if ob.name.startswith('Bonnet crown'):
                        vert.co.z-=.045*math.exp(-((x-.40)**2/.032+(y+1.05)**2/.055))
                    elif ob.name.startswith('Salvaged door'):
                        vert.co.x-=math.copysign(.028*math.exp(-((y+.12)**2/.02+(z-1.10)**2/.008)),x)
                    elif ob.name.startswith(('Wheel arch','Sloped fender')):
                        vert.co.z+=.055*math.sin(y*13+x*2)*max(0,(abs(x)-.92)/.4)
                    elif ob.name.startswith('Angled gun'):
                        vert.co.y+=.026*math.sin(x*22)*max(0,(z-2.35)/.3)
            elif ob.name.startswith('Tailgate'):
                for vert in ob.data.vertices:
                    if vert.co.z>0:vert.co.y+=.016*math.sin(vert.co.x*5)

    # Low door splashes, vertical corrosion trails from exposed fasteners.
    for sign in (-1,1):
        x=sign*.879
        for j in range(70):
            y=rng.uniform(-.44,.40);z=rng.uniform(.88,1.05)
            spot('Dried door mud spatter',(x,y,z),(0,1,0),(0,0,1),rng.uniform(.004,.028),rng.uniform(.006,.025),mud)
        for y in (-.38,.35):
            line('Bolt rust runoff',[(x,y,1.245),(x,y+.006,1.18),(x,y-.008,1.10),(x,y-.012,1.06)],.0035,oxide)
        # Long torn-paint scrapes are directionally consistent with collisions.
        for j in range(9):
            y=rng.uniform(-.4,-.1);z=rng.uniform(1.08,1.22)
            line('Side impact gouge',[(x,y,z),(x,y+.08,z+.015),(x,y+.19,z+.009)],rng.uniform(.001,.0025),edge)
    # Projectile scars: dark irregular impact core, torn bright lip, rusty halo.
    def impact(center,u,v,r):
        c=Vector(center);u=Vector(u);v=Vector(v);normal=u.cross(v).normalized()
        spot('Old impact oxidation',c,u,v,r*2.0,r*1.6,oxide)
        spot('Blackened impact pit',c+normal*.0008,u,v,r*.75,r*.63,soot)
        pts=[]
        for j in range(11):
            t=j*math.tau/10;k=rng.uniform(.75,1.22)
            pts.append(c+normal*.002+u*math.cos(t)*r*k+v*math.sin(t)*r*k)
        line('Ragged impact lip',pts,.0014,edge)
    for y,z,r in [(-.27,1.20,.016),(-.09,1.16,.021),(.08,1.23,.013),(.28,1.17,.014)]:
        impact((.881,y,z),(0,1,0),(0,0,1),r)
    for x,z in [(.29,2.44),(.38,2.32),(-.34,2.48)]:
        impact((x,-.376+(abs(x)-.14)*.216,z),(1,.216 if x>0 else -.216,0),(0,0,1),.017)
    # A scabbed-on repair plate with uneven welded perimeter on the bonnet.
    verts=[(-.67,-1.23,1.252),(-.38,-1.21,1.256),(-.35,-.91,1.315),(-.62,-.90,1.317)]
    patch=mesh('Field-welded hood repair',verts,[(0,1,2,3)],oxide)
    thick=patch.modifiers.new('Salvaged sheet thickness','SOLIDIFY');thick.thickness=.006
    for i in range(4):
        start=Vector(verts[i]);end=Vector(verts[(i+1)%4])
        line('Rough field weld',[start.lerp(end,j/24)+Vector((0,0,.002+.0015*math.sin(j*2.4))) for j in range(25)],.003,edge)
    # Dry wheel spatter follows tire sidewall curvature, not floating spheres.
    for sign in (-1,1):
        for cy in (-1.24,1.24):
            for j in range(75):
                angle=rng.uniform(0,math.tau);r=rng.uniform(.29,.38)
                x=sign*(1.02+.20-(r-.30)*.33)
                spot('Tire dried clay splash',(x,cy+r*math.cos(angle),.44+r*math.sin(angle)),(0,math.cos(angle),math.sin(angle)),(0,-math.sin(angle),math.cos(angle)),rng.uniform(.004,.014),rng.uniform(.006,.026),mud)
    # Carbon around stack mouths and burn soot around the muzzle.
    for ob in list(scene.objects):
        if ob.name.startswith(('Open exhaust rim','Muzzle brake','Barrel cooling')) and ob.type=='MESH':
            ob.data.materials.clear();ob.data.materials.append(soot)
    # One damaged pane, radial hairline cracks situated on the sloped surface.
    cx,cz=.55,1.69
    def windshield(x,z):return (x,-.659+(z-1.45)*.502-.005,z)
    for j in range(6):
        angle=j*math.tau/6+.19;length=rng.uniform(.055,.14)
        endx=cx+math.cos(angle)*length;endz=cz+math.sin(angle)*length
        pts=[windshield(cx,cz),windshield(cx+(endx-cx)*.43+.007,cz+(endz-cz)*.43),windshield(endx,endz)]
        line('Windshield radial fracture',pts,.0008,pale)
    scene['Wear pass']='Layered chipped paint, rust runoff, baked mud, dented armor, projectile scars, field-welded patch, soot and fractured windshield.'
    print('BATTLE_WEAR_APPLIED',len(collection.objects),flush=True)


def apply_battle_refinements():
    """Remove door unit numbers and add a restrained second battle-wear pass."""
    scene=bpy.context.scene
    # Exact text matching preserves the separate RAIDER / 07 tailgate stencil.
    for ob in list(scene.objects):
        if ob.type=='FONT' and ob.data.body=='07':
            bpy.data.objects.remove(ob,do_unlink=True)
    if scene.get('Battle refinements v2'):return
    for ob in list(scene.objects):
        if ob.type!='MESH':continue
        if ob.name.startswith('Bonnet crown'):
            for v in ob.data.vertices:
                x,y,z=v.co
                v.co.z-=.027*math.exp(-((x+.19)**2/.025+(y+1.48)**2/.020))
                v.co.z-=.021*math.exp(-((x-.59)**2/.009+(y+1.62)**2/.014))
        elif ob.name.startswith('Salvaged door reinforcement'):
            for v in ob.data.vertices:
                x,y,z=v.co
                v.co.x-=math.copysign(.022*math.exp(-((y-.26)**2/.007+(z-1.10)**2/.004)),x)
        elif ob.name.startswith('Tailgate') and not ob.name.startswith('Tailgate hinge'):
            bm=bmesh.new();bm.from_mesh(ob.data)
            bmesh.ops.subdivide_edges(bm,edges=list(bm.edges),cuts=14,use_grid_fill=True)
            bm.to_mesh(ob.data);bm.free()
            for v in ob.data.vertices:
                x,y,z=v.co
                v.co.y-=.032*math.exp(-((x+.29)**2/.020+(z+.055)**2/.005))
        elif ob.name.startswith('Angled gun shield'):
            for v in ob.data.vertices:
                x,y,z=v.co
                v.co.y+=.020*math.exp(-((abs(x)-.39)**2/.005+(z-2.40)**2/.007))
    # A thin extra uneven dirt layer; retain the first pass's material contrast.
    for m in list(bpy.data.materials):
        if not m.use_nodes or not m.name.startswith(('01 |','02 |','03 |','04 |','05 |')):continue
        n=m.node_tree.nodes;l=m.node_tree.links;b=n.get('Principled BSDF')
        source=b.inputs['Base Color'].links[0].from_socket
        geo=n.new('ShaderNodeNewGeometry');noise=n.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value=6.5;noise.inputs['Detail'].default_value=4
        l.new(geo.outputs['Position'],noise.inputs['Vector'])
        amount=n.new('ShaderNodeMapRange');amount.inputs['From Min'].default_value=.30;amount.inputs['From Max'].default_value=.70
        amount.inputs['To Min'].default_value=.035;amount.inputs['To Max'].default_value=.23
        l.new(noise.outputs['Fac'],amount.inputs[0])
        mix=n.new('ShaderNodeMixRGB');mix.label='Extra accumulated road grime'
        mix.inputs[2].default_value=(.065,.039,.018,1)
        l.new(amount.outputs[0],mix.inputs[0]);l.new(source,mix.inputs[1]);l.new(mix.outputs[0],b.inputs['Base Color'])
    scene['Battle refinements v2']='Door 07 markings removed; extra mottled grime, two bonnet dents, door dents, tailgate impact and gun-shield deformation.'
    assert not any(o.type=='FONT' and o.data.body=='07' for o in scene.objects)
    print('BATTLE_REFINEMENTS_V2_APPLIED',flush=True)
