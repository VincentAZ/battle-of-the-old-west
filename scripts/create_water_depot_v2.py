"""Editable, textured industrial water depot. Real geometry, rendered in Cycles.

Run Blender --background --python this_file.py -- --preview for a look check;
omit --preview for the 3840x2160 master. CC0 sources are in the library manifest.
"""
import bpy
import json
import math
import random
import sys
from pathlib import Path
from mathutils import Vector, noise

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/water_depot_v2'
LIB = ROOT / 'art/library/polyhaven'
OUT.mkdir(parents=True, exist_ok=True)
PREVIEW = '--preview' in sys.argv
random.seed(107)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1
catalog = {}
groups = {}
current_group = 'Depot'

def texpath(aid, suffix):
    matches = list((LIB / aid).rglob(aid + '_' + suffix + '_4k.*'))
    return matches[0] if matches else None

def image_node(mat, path, color=False):
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    node.image = bpy.data.images.load(str(path), check_existing=True)
    if not color: node.image.colorspace_settings.name = 'Non-Color'
    return node

def material(name, color=(.2,.2,.2), rough=.7, metal=0, asset=None, tile=2,
             tint=(1,1,1), emission=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    mat['tile_m'] = tile
    tree = mat.node_tree; bs = tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color,1)
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metal
    record = dict(color=list(color), roughness=rough, metallic=metal,
                  tint=list(tint), emission=emission, textures={})
    if asset:
        diff = texpath(asset,'diff')
        tn = image_node(mat,diff,True)
        mix = tree.nodes.new('ShaderNodeMixRGB'); mix.blend_type='MULTIPLY'
        mix.inputs[0].default_value=1; mix.inputs[2].default_value=(*tint,1)
        tree.links.new(tn.outputs['Color'],mix.inputs[1]);tree.links.new(mix.outputs[0],bs.inputs['Base Color'])
        record['textures']['diff']=str(diff.relative_to(ROOT))
        normal = texpath(asset,'nor_gl')
        if normal:
            im=image_node(mat,normal)
            nm=tree.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value=.8
            tree.links.new(im.outputs['Color'],nm.inputs['Color']);tree.links.new(nm.outputs['Normal'],bs.inputs['Normal'])
            record['textures']['normal']=str(texpath(asset,'nor_dx').relative_to(ROOT))
        arm=texpath(asset,'arm'); rmap=texpath(asset,'rough')
        if arm:
            im=image_node(mat,arm); sep=tree.nodes.new('ShaderNodeSeparateColor')
            tree.links.new(im.outputs['Color'],sep.inputs[0])
            tree.links.new(sep.outputs['Green'],bs.inputs['Roughness'])
            # These scans are oxide/dirt/dielectrics, not bare conducting metal.
            record['textures']['arm']=str(arm.relative_to(ROOT))
        elif rmap:
            im=image_node(mat,rmap);tree.links.new(im.outputs['Color'],bs.inputs['Roughness'])
            record['textures']['rough']=str(rmap.relative_to(ROOT))
    elif not emission:
        # Fine surface breakup on small hardware; exported colour remains explicit.
        n=tree.nodes.new('ShaderNodeTexNoise');n.inputs['Scale'].default_value=85
        b=tree.nodes.new('ShaderNodeBump');b.inputs['Strength'].default_value=.17;b.inputs['Distance'].default_value=.008
        tree.links.new(n.outputs['Fac'],b.inputs['Height']);tree.links.new(b.outputs['Normal'],bs.inputs['Normal'])
    if emission:
        bs.inputs['Emission Color'].default_value=(*color,1)
        bs.inputs['Emission Strength'].default_value=emission
    catalog[name]=record
    return mat

paint=material('AgedGalvanized',asset='rusty_metal_sheet',tile=2.4,tint=(.8,.89,.86),metal=.25)
darkpaint=material('PatchedGraphite',asset='rusty_metal_sheet',tile=1.9,tint=(.16,.20,.21),metal=.35)
rust=material('FlakingOxide',asset='rust_coarse_01',tile=2,tint=(.78,.75,.70),metal=.08)
concrete=material('WeatheredConcrete',asset='concrete_wall_007',tile=3.0,tint=(.79,.77,.70))
groundmat=material('DustAndGravel',asset='dirt',tile=3.5,tint=(1.10,1.03,.90))
farsoil=material('DistantSoil',asset='dirt_aerial_03',tile=25,tint=(.83,.79,.68))
steel=material('OiledSteel',(.055,.064,.063),.48,.7)
edge=material('ExposedZinc',(.30,.32,.30),.5,.72)
rubber=material('DryRubber',(.019,.019,.017),.86)
ivory=material('ChalkMarkings',asset='concrete_wall_007',tile=.5,tint=(1.0,.95,.80))
yellow=material('WornOchrePaint',asset='rusty_metal_sheet',tile=.8,tint=(1.0,.53,.15),metal=.1)
cloth=material('DustyCanvas',(.15,.175,.13),.96)
glass=material('DarkGaugeGlass',(.02,.035,.029),.22,.1)
lamp=material('WarmLamp',(.95,.61,.28),.3,emission=5)
green=material('StatusLED',(.22,.65,.43),.35,emission=2)

def tag(obj, name, mat=None):
    obj.name=name
    if mat: obj.data.materials.append(mat)
    groups.setdefault(current_group,[]).append(obj)
    return obj

def uv_project(obj, tile, offset=None):
    uv=obj.data.uv_layers.active or obj.data.uv_layers.new(name='UVMap')
    offset=offset or (random.random()*3,random.random()*3)
    for p in obj.data.polygons:
        axis=max(range(3),key=lambda a:abs(p.normal[a]))
        axes=(1,2) if axis==0 else (0,2) if axis==1 else (0,1)
        for li in p.loop_indices:
            v=obj.data.vertices[obj.data.loops[li].vertex_index].co
            uv.data[li].uv=(v[axes[0]]/tile+offset[0],v[axes[1]]/tile+offset[1])

def bevel(obj, size=.008, segments=2):
    m=obj.modifiers.new('Manufactured edge radius','BEVEL');m.width=size;m.segments=segments

def box(name,loc,size,mat=steel,edge_radius=.008,rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    ob=bpy.context.object;ob.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    uv_project(ob,mat.get('tile_m',2))
    if rot:ob.rotation_euler=rot
    if edge_radius:bevel(ob,edge_radius)
    return tag(ob,name,mat)

def cyl(name,loc,radius,depth,mat=steel,vertices=48,rot=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=loc)
    ob=bpy.context.object;tile=mat.get('tile_m',2)
    uv=ob.data.uv_layers.active
    for p in ob.data.polygons:
        if len(p.vertices)==4:
            p.use_smooth=True
            angles=[math.atan2(ob.data.vertices[ob.data.loops[li].vertex_index].co.y,
                               ob.data.vertices[ob.data.loops[li].vertex_index].co.x) for li in p.loop_indices]
            if max(angles)-min(angles)>math.pi:angles=[a+2*math.pi if a<0 else a for a in angles]
            for li,a in zip(p.loop_indices,angles):
                v=ob.data.vertices[ob.data.loops[li].vertex_index].co
                uv.data[li].uv=(a*radius/tile,(v.z+depth/2)/tile)
        else:
            for li in p.loop_indices:
                v=ob.data.vertices[ob.data.loops[li].vertex_index].co
                uv.data[li].uv=(v.x/tile,v.y/tile)
    if rot:ob.rotation_euler=rot
    bevel(ob,min(.008,radius*.07))
    return tag(ob,name,mat)

def beam(name,a,b,r=.035,mat=steel,vertices=24):
    a,b=Vector(a),Vector(b)
    ob=cyl(name,(a+b)/2,r,(b-a).length,mat,vertices)
    ob.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    return ob

def tube(name,points,r,mat=steel):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.resolution_u=12
    data.bevel_depth=r;data.bevel_resolution=3
    sp=data.splines.new('BEZIER');sp.bezier_points.add(len(points)-1)
    for p,co in zip(sp.bezier_points,points):
        p.co=co;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
    ob=bpy.data.objects.new(name,data);scene.collection.objects.link(ob)
    return tag(ob,name,mat)

def ring(name,loc,r,t=.012,mat=steel,rot=None):
    bpy.ops.mesh.primitive_torus_add(major_segments=64,minor_segments=10,major_radius=r,minor_radius=t,location=loc)
    ob=bpy.context.object
    for p in ob.data.polygons:p.use_smooth=True
    if rot:ob.rotation_euler=rot
    return tag(ob,name,mat)

def text(name,body,loc,size,mat=ivory,rotation=(math.pi/2,0,0)):
    data=bpy.data.curves.new(name,'FONT');data.body=body;data.align_x='CENTER';data.align_y='CENTER'
    data.size=size;data.space_character=1.1;data.extrude=.0008
    data.font=bpy.data.fonts.load('/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf')
    ob=bpy.data.objects.new(name,data);scene.collection.objects.link(ob)
    ob.location=loc;ob.rotation_euler=rotation
    return tag(ob,name,mat)

def mesh_obj(name,verts,faces,mat,uvs=None):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
    ob=bpy.data.objects.new(name,me);scene.collection.objects.link(ob);tag(ob,name,mat)
    if uvs:
        layer=me.uv_layers.new(name='UVMap')
        for p in me.polygons:
            for li in p.loop_indices:layer.data[li].uv=uvs[me.loops[li].vertex_index]
    else:uv_project(ob,mat.get('tile_m',2))
    return ob

def terrain_z(x,y):
    f=noise.fractal(Vector((x*.09,y*.09,.74)),1.0,2.0,4)
    flatten=min(1,max(0,(math.hypot(x,y-1)-6)/10))
    rut=-.05*(math.exp(-((x+.7)/.22)**2)+math.exp(-((x-1.0)/.22)**2)) if y<-3 else 0
    return -.06+f*.8*flatten+noise.noise_vector(Vector((x*1.6,y*1.6,2.3))).z*.028+rut

current_group='Terrain'
N=245;span=110
vs=[];fs=[];uvs=[]
for j in range(N):
    for i in range(N):
        x=(i/(N-1)-.5)*span;y=(j/(N-1)-.43)*span
        vs.append((x,y,terrain_z(x,y)));uvs.append((x/3.5,y/3.5))
for j in range(N-1):
    for i in range(N-1):
        k=j*N+i;fs.append((k,k+1,k+N+1,k+N))
terrain=mesh_obj('Uneven dust road and alluvial gravel',vs,fs,groundmat,uvs)
for p in terrain.data.polygons:p.use_smooth=True
box('Distant ground',(0,150,-.4),(1400,1400,.15),farsoil,0)
# Continuous eroded ridges, beyond the scanned foreground outcrops.
vs=[];fs=[];uvs=[];Nfar=350
for j in range(Nfar):
    for i in range(Nfar):
        x=(i/(Nfar-1)-.5)*1000;y=(j/(Nfar-1)-.32)*1000
        peaks=sum(h*math.exp(-((x-cx)/wx)**2-((y-cy)/wy)**2) for cx,cy,h,wx,wy in
                  [(-150,140,58,115,90),(60,190,67,130,140),(235,155,68,120,110),(-310,230,75,150,170)])
        f=noise.fractal(Vector((x*.025,y*.025,6.41)),1.1,2.1,5)
        erosion=(.20+.12*abs(f))*peaks
        fall=min(1,max(0,(math.hypot(x,y-5)-50)/35))
        z=erosion*fall-.6
        vs.append((x,y,z));uvs.append((x/25,y/25))
for j in range(Nfar-1):
    for i in range(Nfar-1):
        k=j*Nfar+i;fs.append((k,k+1,k+Nfar+1,k+Nfar))
ridge=mesh_obj('Eroded distant ridgelines',vs,fs,farsoil,uvs)
for p in ridge.data.polygons:p.use_smooth=True

current_group='Depot'
# The tank has a skirt, rolled seams, inspection hatch and a supported ladder.
tx,ty=-2.6,1.8
cyl('Cast foundation',(tx,ty,.08),1.98,.28,concrete,96)
cyl('Tank skirt',(tx,ty,.46),1.64,.66,rust,96)
cyl('Pressure vessel',(tx,ty,3.0),1.77,4.45,paint,128)
for z in [.82,2.24,3.65,5.22]:
    cyl('Welded reinforcing strap',(tx,ty,z),1.79,.07,darkpaint,128)
    ring('Weld bead',(tx,ty,z+.045),1.776,.009,edge)
# Shallow domed lid, formed from a surface of revolution.
vs=[];fs=[];uvs=[]
for j in range(17):
    rr=1.78*(1-j/16);z=5.23+.40*math.sin(j/16*math.pi/2)
    for i in range(97):
        a=2*math.pi*i/96;vs.append((tx+rr*math.cos(a),ty+rr*math.sin(a),z));uvs.append((i/96*4,j/16))
for j in range(16):
    for i in range(96):
        k=j*97+i;fs.append((k,k+1,k+98,k+97))
cap=mesh_obj('Dished steel tank roof',vs,fs,darkpaint,uvs)
for p in cap.data.polygons:p.use_smooth=True
cyl('Roof inspection manway',(tx+.3,ty,5.68),.37,.16,rust)
for i in range(12):
    a=i*math.tau/12;cyl('Manway bolt',(tx+.3+.30*math.cos(a),ty+.30*math.sin(a),5.78),.022,.045,edge,6)
tube('Roof breather',[(tx-.5,ty,5.55),(tx-.5,ty,6.08),(tx-.7,ty,6.23),(tx-.93,ty,6.05)],.065,rust)
for z in [1.05+i*.27 for i in range(19)]:
    beam('Ladder rung',(tx-1.97,ty-.33,z),(tx-1.97,ty+.22,z),.018,edge)
for y in [ty-.36,ty+.25]:
    beam('Ladder stile',(tx-1.97,y,.65),(tx-1.97,y,6.1),.027,darkpaint)
    for z in [1.0,2.5,4,5.2]:beam('Ladder bracket',(tx-1.97,y,z),(tx-1.68,y,z),.02,rust)
for z in [2.9,3.75,4.6,5.5]:
    # Open-ended safety cage arcs.
    pts=[(tx-1.84-.54*math.cos(a),ty-.05+.54*math.sin(a),z) for a in [(-1.9+i*3.8/18) for i in range(19)]]
    tube('Ladder safety hoop',pts,.014,rust)

# Reinforced service house, with actual openings and thin corrugated cladding.
box('Service house slab',(2.8,1.7,.08),(5.6,4.5,.24),concrete,.035)
box('Back wall',(2.8,3.82,1.65),(5.45,.22,3.18),concrete,.016)
for x in [.14,5.47]:box('Side wall',(x,1.8,1.54),(.22,4.2,2.9),concrete,.02)
for x,w in [(1.22,2.1),(4.73,1.45)]:box('Front wall below cladding',(x,-.27,1.51),(w,.25,2.86),concrete,.018)
box('Door lintel',(3.25,-.27,2.83),(1.75,.26,.28),concrete,.018)
box('Door shadow',(3.25,1.1,1.3),(1.45,.035,2.5),rubber,0)
box('Door frame left',(2.43,-.45,1.37),(.10,.17,2.60),darkpaint)
box('Door frame right',(4.08,-.45,1.37),(.10,.17,2.60),darkpaint)
door=box('Steel door ajar',(3.88,-.65,1.37),(.10,1.24,2.45),darkpaint,.009,rot=(0,0,.27))
box('Threshold',(3.25,-.49,.20),(1.72,.65,.18),concrete,.015)
box('Step',(3.25,-1.02,.10),(1.88,.43,.16),concrete,.018)

def corrugation(name,center,width,height,mat,roof=False):
    nx=int(width/.027);ny=8;vs=[];uv=[];fs=[]
    for j in range(ny+1):
        for i in range(nx+1):
            x=(i/nx-.5)*width;z=(j/ny-.5)*height
            w=.025*math.sin(x*math.tau/.15)+.004*math.sin(z*4+x*2)
            if roof:vs.append((center[0]+x,center[1]+z,center[2]+w+z*.055))
            else:vs.append((center[0]+x,center[1]+w,center[2]+z))
            uv.append((x/2.4+random.random()*.0001,z/2.4))
    for j in range(ny):
        for i in range(nx):
            k=j*(nx+1)+i;fs.append((k,k+1,k+nx+2,k+nx+1))
    ob=mesh_obj(name,vs,fs,mat,uv)
    so=ob.modifiers.new('Sheet thickness','SOLIDIFY');so.thickness=.002
    return ob
for i in range(6):
    x=.58+i*.87
    corrugation('Salvaged roof sheet',(x,1.65,3.17+random.uniform(-.012,.012)),.95,4.9,paint if i%3 else rust,True)
for x in [.45,1.30,2.15,4.45,5.25]:
    corrugation('Upper wall patch',(x,-.418,2.4),.83,1.35,darkpaint if x<3 else paint)
    for z in [1.81,2.94]:
        for off in [-.32,.32]:cyl('Roofing screw',(x+off,-.46,z),.012,.028,edge,6,rot=(math.pi/2,0,0))
for z in [1.66,3.02]:box('Cladding channel',(2.8,-.47,z),(5.57,.07,.08),rust)
box('Drain gutter',(2.8,-.89,3.04),(5.85,.14,.11),darkpaint)
tube('Downpipe',[(5.6,-.75,3.08),(5.72,-.75,2.9),(5.72,-.67,.25),(5.98,-.75,.14)],.055,rust)
for x in [.15,5.49]:box('Roof fascia',(x,1.7,3.2),(.09,4.9,.14),darkpaint)

# A vent array, breaker box, meters, conduit and plausible service hardware.
box('Vent opening',(1.20,-.58,1.48),(1.2,.15,.70),steel)
for j in range(11):box('Vent louvre',(1.2,-.68,1.18+j*.057),(1.16,.08,.039),darkpaint,.004,rot=(.30,0,0))
box('Breaker enclosure',(4.78,-.55,1.35),(.64,.22,.85),paint,.008)
box('Breaker lid',(4.78,-.685,1.35),(.58,.022,.78),darkpaint,.005)
for x in [4.53,5.02]:
    for z in [1.03,1.67]:cyl('Enclosure screw',(x,-.71,z),.012,.018,edge,8,rot=(math.pi/2,0,0))
for i in range(3):
    tube('Wall conduit',[(4.63+i*.09,-.56,.10),(4.63+i*.09,-.56,.67),(4.69+i*.09,-.56,.84)],.012,steel)
    cyl('Indicator light',(4.59+i*.17,-.72,1.53),.025,.025,green if i==0 else glass,24,rot=(math.pi/2,0,0))
text('Electrical warning','DANGER',(4.78,-.713,1.25),.10,ivory)
text('Voltage','440 V',(4.78,-.715,1.10),.10,ivory)

# Pump manifold: chunky cast body, finned motor and bolted pipe flanges.
box('Pump pad',(-2.6,-1.47,.1),(2.55,1.1,.28),concrete,.035)
for x in [-3.22,-2.38]:box('Pump mounting rail',(x,-1.46,.29),(.13,.85,.12),rust)
cyl('Pump volute',(-2.8,-1.45,.79),.43,.32,paint,64,rot=(math.pi/2,0,0))
cyl('Electric motor',(-1.94,-1.45,.67),.25,.9,darkpaint,64,rot=(0,math.pi/2,0))
for x in [-2.30+i*.053 for i in range(14)]:
    cyl('Motor cooling fin',(x,-1.45,.67),.27,.018,steel,48,rot=(0,math.pi/2,0))
box('Motor junction box',(-1.95,-1.45,.98),(.26,.24,.20),paint)
for x in [-3.30,-2.27,-1.60]:
    for y in [-1.82,-1.12]:cyl('Anchor stud',(x,y,.39),.025,.075,edge,6)
tube('Tank outlet pipe',[(tx,.1,.97),(tx,-.30,.97),(tx,-.67,.94),(-2.8,-.98,.8)],.13,rust)
tube('Delivery pipe',[(-2.8,-1.47,1.11),(-2.8,-1.47,1.56),(-2.45,-1.47,1.84),(.10,-1.47,1.84),(.60,-1.40,1.66),(.60,-.38,1.65)],.10,paint)
for x in [-1.96,-.40]:
    cyl('Pipe flange',(x,-1.47,1.84),.18,.09,rust,48,rot=(0,math.pi/2,0))
    for i in range(8):
        a=i*math.tau/8
        cyl('Flange bolt',(x-.059,-1.47+.142*math.cos(a),1.84+.142*math.sin(a)),.018,.13,edge,6,rot=(0,math.pi/2,0))
beam('Valve stem',(-.92,-1.47,1.84),(-.92,-1.47,2.17),.035,steel)
ring('Valve wheel',(-.92,-1.47,2.20),.20,.020,rust)
for i in range(5):
    a=i*math.tau/5;beam('Valve spoke',(-.92,-1.47,2.2),(-.92+.19*math.cos(a),-1.47+.19*math.sin(a),2.2),.012,rust)
beam('Pressure gauge stem',(-2.1,-1.47,1.85),(-2.1,-1.47,2.09),.02,steel)
cyl('Pressure gauge rim',(-2.1,-1.52,2.19),.13,.08,edge,48,rot=(math.pi/2,0,0))
cyl('Pressure gauge face',(-2.1,-1.565,2.19),.113,.006,ivory,48,rot=(math.pi/2,0,0))
beam('Gauge needle',(-2.1,-1.573,2.19),(-2.15,-1.575,2.24),.005,rubber,12)

# Worn placards, tank lettering, a small inspection lamp.
box('Station sign',(.82,-.54,3.58),(3.05,.07,.59),darkpaint,.006)
for x in [-.53,2.17]:beam('Sign support',(x,-.43,2.86),(x,-.43,3.88),.02,rust)
text('Station name','WATER  /  07',(.82,-.588,3.58),.35,ivory)
text('Service line','FILTER • RESERVE • DISTRIBUTE',(1.23,-.735,.96),.071,ivory)
for name,body,z,size in [('Tank ID','07',4.25,1.0),('Tank capacity','RESERVE / 18 000 L',3.11,.115)]:
    lettering=text(name,body,(tx,ty-1.777,z),size,ivory)
    bpy.ops.object.select_all(action='DESELECT');lettering.select_set(True);bpy.context.view_layer.objects.active=lettering
    bpy.ops.object.convert(target='MESH');lettering=bpy.context.object
    # Bend the marking onto the tank surface instead of floating flat type.
    for v in lettering.data.vertices:
        v.co.z=math.sqrt(max(.01,1.773**2-v.co.x**2))-1.777+.015
for x in [2.42,4.12]:
    tube('Gooseneck lamp',[(x,-.42,2.82),(x,-.80,2.98),(x,-1.0,2.79)],.014,steel)
    cyl('Lamp shade',(x,-1.0,2.75),.14,.05,darkpaint)
    cyl('Lamp lens',(x,-1.0,2.72),.09,.012,lamp)
    bpy.ops.object.light_add(type='AREA',location=(x,-1.0,2.69))
    ob=bpy.context.object;ob.name='Practical service light';ob.data.energy=24;ob.data.color=(1,.69,.37);ob.data.size=.20

# Patchwork sunshade over the tap station, tensioned and visibly sagging.
for a,b in [((-.1,-2.9,0),(-.05,-2.9,2.63)),((2.0,-2.9,0),(2.03,-2.9,2.62))]:beam('Sunshade pole',a,b,.035,rust)
vs=[];fs=[];uv=[]
for j in range(25):
    for i in range(29):
        u=i/28;v=j/24;x=-.12+2.18*u;y=-.7-2.25*v
        z=2.84-.22*v-.18*math.sin(math.pi*u)*math.sin(math.pi*v)+.015*math.sin(u*35+v*12)
        vs.append((x,y,z));uv.append((u*2,v*2))
for j in range(24):
    for i in range(28):
        if j==23 and i in [2,3,16,17,18]:continue
        k=j*29+i;fs.append((k,k+1,k+30,k+29))
shade=mesh_obj('Repaired olive canvas shade',vs,fs,cloth,uv)
for p in shade.data.polygons:p.use_smooth=True
for x in [-.1,2.03]:
    tube('Canopy tension cord',[(x,-2.91,2.61),(x+.2,-3.5,1.2),(x+.4,-4.0,.03)],.006,rubber)
    beam('Ground stake',(x+.4,-4.0,-.03),(x+.42,-4.0,.22),.012,rust)

current_group='Props'
def drum(x,y,z=0,lean=0):
    cyl('Reclaimed steel drum',(x,y,z+.46),.295,.90,paint if random.random()>.5 else rust,48)
    for h in [.05,.28,.65,.88]:ring('Drum rolled rim',(x,y,z+h),.297,.016,darkpaint)
    cyl('Drum bung',(x+.12,y,z+.921),.045,.016,steel,24)
for x,y in [(5.95,-.15),(6.53,.05),(6.12,.63),(-4.87,1.24)]:drum(x,y)
for x,y in [(1.2,-1.4),(1.57,-1.0)]:
    box('Water can',(x,y,.24),(.30,.19,.43),darkpaint,.018)
    beam('Water can handle',(x-.075,y,.50),(x+.075,y,.50),.018,steel)
    for z in [.16,.32]:box('Pressed can rib',(x,y-.10,z),(.23,.013,.024),paint,.003)
# Concrete road barriers with sloping sides, cast seams and lifting loops.
def barrier(x,y,length,angle):
    cross=[(-.32,0),(-.32,.18),(-.16,.52),(-.12,.87),(.12,.87),(.16,.52),(.32,.18),(.32,0)]
    vs=[(xx,yy,zz) for xx in [-length/2,length/2] for yy,zz in cross]
    fs=[tuple(range(7,-1,-1)),tuple(range(8,16))]+[(i,(i+1)%8,(i+1)%8+8,i+8) for i in range(8)]
    ob=mesh_obj('Chipped Jersey barrier',vs,fs,concrete);ob.location=(x,y,terrain_z(x,y));ob.rotation_euler.z=angle;bevel(ob,.022,3)
    for xx in [-length*.32,length*.32]:
        wx=x+xx*math.cos(angle);wy=y+xx*math.sin(angle)
        ring('Barrier lifting loop',(wx,wy,.87+terrain_z(x,y)),.050,.009,rust,rot=(math.pi/2,0,angle))
barrier(-5.3,-3.4,2.7,-.16);barrier(5.9,-3.5,2.4,.23)
for x,y in [(-4.9,-4.1),(6.4,-2.9)]:
    beam('Scrap steel length',(x,y,.08),(x+1.4,y+.22,.07),.042,rust)
# Long loose hose with believable bend radius, in the foreground.
tube('Discarded delivery hose',[(-2.5,-1.9,.18),(-3.5,-2.6,.055),(-3.7,-4.1,.06),(-2.8,-4.9,.045),(-1.8,-4.5,.03),(-2.0,-3.8,.055),(-2.7,-3.8,.055),(-2.9,-4.3,.06)],.028,rubber)
for i in range(24):
    x=random.uniform(-7,7);y=random.uniform(-6,5)
    if -4<x<5.6 and -.4<y<4:continue
    size=random.uniform(.08,.25)
    ob=box('Broken concrete fragment',(x,y,terrain_z(x,y)+size*.18),(size*1.5,size,size*.45),concrete,.005,rot=(random.random()*.3,random.random()*.3,random.random()*6.28))

# Utility poles and a thin, sagging supply line tie the site into the landscape.
for x,y,h in [(-7.1,5.3,7.9),(8.8,9.5,7.4),(19,20,6.9)]:
    cyl('Weathered utility pole',(x,y,h/2),.085,h,rust,20)
    box('Utility crossarm',(x,y,h-.32),(1.75,.085,.09),darkpaint)
    for d in [-.7,0,.7]:
        beam('Insulator pin',(x+d,y,h-.3),(x+d,y,h-.02),.013,steel)
        for z in [h-.18,h-.11,h-.04]:cyl('Ceramic insulator',(x+d,y,z),.045,.035,ivory,24)
for d in [-.7,0,.7]:
    tube('Sagging aerial cable',[(-7.1+d,5.3,7.85),(1+d,7.4,6.35),(8.8+d,9.5,7.36),(14+d,15,5.9),(19+d,20,6.85)],.008,rubber)
tube('Service drop',[(-7.1,5.3,7.8),(-3,3.2,5.7),(1,3.4,3.3)],.014,rubber)

print('DEPOT_GEOMETRY',len(scene.objects),flush=True)

# Scanned rock meshes are shared instances. No primitive boulders in the render.
rock_prototypes={};rock_instances=[]
for aid in ['rock_07','coast_rocks_05']:
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(texpath(aid,'4k') or LIB/aid/(aid+'_4k.gltf')))
    imported=[o for o in bpy.data.objects if o not in before]
    candidates=[o for o in imported if o.type=='MESH']
    assert candidates, aid
    ob=max(candidates,key=lambda o:len(o.data.polygons))
    ob.parent=None;ob.location=(0,0,0)
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    # Keep the scans' UVs and normal maps. Reduce only the largest distant scan.
    if len(ob.data.polygons)>150000:
        dec=ob.modifiers.new('Environment LOD','DECIMATE');dec.ratio=110000/len(ob.data.polygons)
        bpy.ops.object.modifier_apply(modifier=dec.name)
    mat=material('Scan_'+aid,asset=aid,tint=(.87,.82,.73),tile=1)
    ob.data.materials.clear();ob.data.materials.append(mat)
    ob.name='SOURCE_'+aid
    for o in imported:
        if o!=ob:bpy.data.objects.remove(o,do_unlink=True)
    rock_prototypes[aid]=ob
    print('SCAN',aid,len(ob.data.polygons),tuple(ob.dimensions),flush=True)

def place_rock(aid,loc,scale,angle):
    src=rock_prototypes[aid];ob=bpy.data.objects.new(aid,src.data);scene.collection.objects.link(ob)
    ob.location=loc;ob.scale=scale if isinstance(scale,tuple) else (scale,scale,scale)
    ob.rotation_euler=(random.uniform(-.15,.15),random.uniform(-.15,.15),angle)
    rock_instances.append(ob);ob['rock_asset']=aid
    return ob
for i in range(240):
    x=random.uniform(-23,23);y=random.uniform(-16,28)
    if -4.7<x<6 and -2.4<y<4.5:continue
    s=random.uniform(.12,.9)
    if y<-7:s=random.uniform(.2,1.3)
    place_rock('rock_07',(x,y,terrain_z(x,y)-.015),s,random.random()*math.tau)
# Small shared scan LOD for the gravel field. Exported as one geometry group.
small=rock_prototypes['rock_07'].copy();small.data=small.data.copy();scene.collection.objects.link(small)
small.hide_set(False);bpy.ops.object.select_all(action='DESELECT');small.select_set(True);bpy.context.view_layer.objects.active=small
dec=small.modifiers.new('Pebble LOD','DECIMATE');dec.ratio=.035;bpy.ops.object.modifier_apply(modifier=dec.name)
current_group='Gravel'
for i in range(2600):
    x=random.uniform(-18,18);y=random.uniform(-17,17)
    if -4.8<x<5.7 and -2.4<y<4.5:continue
    # Leave a travelled corridor, with rubble accumulating along the shoulders.
    if -.7<x<1.9 and y<-3 and random.random()<.82:continue
    ob=bpy.data.objects.new('Scattered gravel',small.data);scene.collection.objects.link(ob)
    s=random.uniform(.12,.60);ob.scale=(s,s*random.uniform(.65,1.15),s)
    ob.location=(x,y,terrain_z(x,y)-.01);ob.rotation_euler=(random.random()*.5,random.random()*.5,random.random()*math.tau)
    tag(ob,'Scattered gravel')
bpy.data.objects.remove(small,do_unlink=True)
for x,y,s in [(-8,2,1.4),(-9,6,2.1),(-12,10,2.6),(-17,16,3.2),(-23,20,3),
              (8,6,1.8),(12,11,2.8),(17,17,3.8),(24,25,3.5),(-6,20,3.3),(2,27,4.1),
              (-19,33,4),(13,35,4.5),(32,42,6),(-35,45,6),(-9,-6,.60),(9,-4,.7)]:
    place_rock('coast_rocks_05',(x,y,terrain_z(x,y)-.25*s),(s,s*.82,s*.72),random.random()*math.tau)
for ob in rock_prototypes.values():ob.hide_render=True;ob.hide_set(True)

# Sparse, dry stems provide fine silhouettes and human-scale surface detail.
current_group='Scrub'
for i in range(100):
    x=random.uniform(-18,18);y=random.uniform(-10,20)
    if -5<x<6 and -4<y<5:continue
    h=random.uniform(.12,.45);z=terrain_z(x,y)
    for j in range(random.randint(3,6)):
        a=random.random()*math.tau;d=random.uniform(.06,.24)
        tube('Dry grass stem',[(x,y,z),(x+d*.4*math.cos(a),y+d*.4*math.sin(a),z+h*.6),
                               (x+d*math.cos(a),y+d*math.sin(a),z+h*random.uniform(.6,1))],.0015,cloth)

def aim(ob,target):ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()
world=bpy.data.worlds.new('Overcast late afternoon');world.use_nodes=True;scene.world=world
tree=world.node_tree;env=tree.nodes.new('ShaderNodeTexEnvironment')
env.image=bpy.data.images.load(str(LIB/'qwantani_sunset_puresky/qwantani_sunset_puresky_4k.hdr'))
mapping=tree.nodes.new('ShaderNodeMapping');mapping.inputs['Rotation'].default_value[2]=math.radians(115)
coord=tree.nodes.new('ShaderNodeTexCoord');tree.links.new(coord.outputs['Generated'],mapping.inputs['Vector'])
tree.links.new(mapping.outputs['Vector'],env.inputs['Vector']);tree.links.new(env.outputs['Color'],tree.nodes['Background'].inputs['Color'])
tree.nodes['Background'].inputs['Strength'].default_value=.7
bpy.ops.object.light_add(type='SUN',location=(-18,-2,8))
sun=bpy.context.object;sun.name='Grazing late afternoon sunlight';sun.data.energy=2.2;sun.data.angle=.025;sun.data.color=(1,.73,.47);aim(sun,(0,1,0))
bpy.ops.object.light_add(type='AREA',location=(-3,-9,7))
fill=bpy.context.object;fill.name='Soft open sky bounce';fill.data.energy=900;fill.data.shape='DISK';fill.data.size=12;fill.data.color=(.68,.81,1);aim(fill,(0,1,2))
# A little aerial perspective, never a coloured fog filter over the subjects.
fogmat=bpy.data.materials.new('Airborne mineral dust');fogmat.use_nodes=True
ft=fogmat.node_tree;ft.nodes.clear();out=ft.nodes.new('ShaderNodeOutputMaterial');vol=ft.nodes.new('ShaderNodeVolumePrincipled')
vol.inputs['Density'].default_value=.0011;vol.inputs['Color'].default_value=(.72,.69,.61,1);vol.inputs['Anisotropy'].default_value=.2;ft.links.new(vol.outputs['Volume'],out.inputs['Volume'])
current_group='Atmosphere'
fog=box('Atmosphere volume',(0,30,22),(260,260,70),fogmat,0)

bpy.ops.object.camera_add(location=(-12.8,-20.2,3.15))
camera=bpy.context.object;camera.name='Water depot cinematic camera';camera.data.lens=43;camera.data.sensor_width=36;scene.camera=camera
camera.data.dof.use_dof=True;camera.data.dof.focus_distance=24.3;camera.data.dof.aperture_fstop=9
shots=[(1,(-13.8,-21.2,3.35),(.15,1.3,2.75)),(96,(-12.8,-20.2,3.15),(.3,1.3,2.72)),(192,(-11.8,-19.5,3.02),(.45,1.4,2.70))]
for frame,loc,target in shots:
    camera.location=loc;aim(camera,target);camera.keyframe_insert(data_path='location',frame=frame);camera.keyframe_insert(data_path='rotation_euler',frame=frame)
scene.frame_start=1;scene.frame_end=192;scene.render.fps=24;scene.frame_set(96)
scene.render.engine='CYCLES';scene.cycles.samples=48 if PREVIEW else 192
scene.cycles.adaptive_threshold=.018 if PREVIEW else .008
scene.cycles.use_denoising=True;scene.cycles.max_bounces=8
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX'
for dev in prefs.get_devices_for_type('OPTIX'):dev.use=dev.type=='OPTIX'
scene.cycles.device='GPU'
scene.render.resolution_x=3840;scene.render.resolution_y=2160;scene.render.resolution_percentage=40 if PREVIEW else 100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.image_settings.color_depth='16'
scene.render.filepath=str(OUT/('look_check.png' if PREVIEW else 'WaterDepot_4K.png'))
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=.05
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='RENDERED'
            area.spaces.active.overlay.show_overlays=False
bpy.ops.object.select_all(action='DESELECT')
# Source uses portable relative texture paths; downloaded originals are preserved.
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'WaterDepot.blend'))
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'WaterDepot.blend'))
(OUT/'materials.json').write_text(json.dumps(catalog,indent=2))
(OUT/'camera.json').write_text(json.dumps(dict(lens=43,shots=shots),indent=2))
print('RENDER_BEGIN',scene.render.filepath,flush=True)
bpy.ops.render.render(write_still=True)
print('DEPOT_RENDER_COMPLETE',flush=True)

if '--export' in sys.argv:
    # Export unique meshes plus instance transforms, keeping source fully editable.
    exports=[]
    def export_objects(name,objects):
        bpy.ops.object.select_all(action='DESELECT')
        for ob in objects:ob.hide_set(False);ob.select_set(True)
        bpy.context.view_layer.objects.active=objects[0]
        bpy.ops.object.convert(target='MESH')
        for ob in list(bpy.context.selected_objects):
            bpy.context.view_layer.objects.active=ob
            for mod in list(ob.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.context.view_layer.objects.active=bpy.context.selected_objects[0]
        bpy.ops.object.join();ob=bpy.context.object;ob.name=name
        scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
        bpy.ops.export_scene.fbx(filepath=str(OUT/(name+'.fbx')),use_selection=True,object_types={'MESH'},apply_unit_scale=True,add_leaf_bones=False,bake_anim=False,axis_forward='-Y',axis_up='Z')
        exports.append(name)
    instances=[dict(asset=ob['rock_asset'],location=list(ob.location),rotation=list(ob.rotation_euler),scale=list(ob.scale)) for ob in rock_instances]
    for group in ['Depot','Props','Terrain','Scrub','Gravel']:
        export_objects(group,[o for o in groups[group] if o.type in {'MESH','CURVE','FONT'}])
    for aid,ob in rock_prototypes.items():
        # Detach from rendered instances before export mutations.
        ob.data=ob.data.copy();export_objects(aid,[ob])
    (OUT/'geometry.json').write_text(json.dumps(dict(meshes=exports,instances=instances),indent=2))
    print('DEPOT_EXPORT_COMPLETE',flush=True)
