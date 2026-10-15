"""Build an original, editable environment and export it for Unreal.

Run with Blender --background --python scripts/create_water_outpost.py.
This is an art/pipeline study, not an implementation of a game card.
"""
import bpy
import json
import math
import random
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art' / 'water_outpost'
OUT.mkdir(parents=True, exist_ok=True)
random.seed(38)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1
palette = {}

def material(name, color, metal=0, rough=0.6, emission=0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Roughness'].default_value = rough
    if emission:
        bsdf.inputs['Emission Color'].default_value = (*color, 1)
        bsdf.inputs['Emission Strength'].default_value = emission
    palette[name] = dict(color=list(color), metallic=metal, roughness=rough, emission=emission)
    return mat

rust = material('Oxide', (0.29, 0.075, 0.035), .65, .7)
steel = material('DarkSteel', (.037, .056, .067), .8, .38)
edge = material('WornSteel', (.31, .35, .34), .85, .32)
ivory = material('DustWhite', (.68, .55, .36), .45, .6)
pink = material('ReclaimedMagenta', (.52, .014, .10), .45, .52)
teal = material('OxidizedTeal', (.018, .24, .24), .6, .54)
cyan = material('WaterLight', (.025, .65, .80), .1, .26, 4)
amber = material('WarningLight', (1, .22, .025), .1, .3, 5)
rubber = material('Rubber', (.018, .016, .022), .05, .9)
sand = material('RedSand', (.24, .12, .095), 0, .96)
stone = material('Basalt', (.08, .055, .084), 0, .93)
cloth = material('FlagCloth', (.6, .023, .125), 0, .87)
black = material('SignDark', (.01, .022, .024), .2, .65)

def finish(obj, name, mat, bevel=0):
    obj.name = name
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Worn edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
    return obj

def box(name, loc, size, mat=steel, bevel=.025, rotation=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if rotation:
        obj.rotation_euler = rotation
    return finish(obj, name, mat, bevel)

def cylinder(name, loc, radius, depth, mat=steel, vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    obj = bpy.context.object
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return finish(obj, name, mat, .018)

def beam(name, start, end, radius=.045, mat=steel):
    mid = (Vector(start) + Vector(end)) / 2
    obj = cylinder(name, mid, radius, (Vector(end)-Vector(start)).length, mat, 16)
    obj.rotation_euler = (Vector(end)-Vector(start)).to_track_quat('Z', 'Y').to_euler()
    return obj

def ring(name, loc, radius, tube=.035, mat=edge, rotation=None):
    bpy.ops.mesh.primitive_torus_add(major_segments=40, minor_segments=8, location=loc, major_radius=radius, minor_radius=tube)
    obj = finish(bpy.context.object, name, mat)
    if rotation:
        obj.rotation_euler = rotation
    return obj

def text_obj(name, body, loc, size, mat, rotation=(math.pi/2, 0, 0)):
    data = bpy.data.curves.new(name, 'FONT')
    data.body = body
    data.align_x = 'CENTER'
    data.align_y = 'CENTER'
    data.size = size
    data.extrude = .006
    data.space_character = 1.15
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = rotation
    obj.data.materials.append(mat)
    return obj

# Wind-scoured terrain, deliberately without a tabletop or board boundary.
verts, faces = [], []
N, span = 70, 110
for y in range(N):
    for x in range(N):
        px, py = (x/(N-1)-.5)*span, (y/(N-1)-.5)*span
        z = .13*math.sin(px*.47 + py*.3) + .09*math.sin(py*1.3) + .11*random.random()
        z *= min(1, max(0, (math.hypot(px, py)-5)/9))
        verts.append((px, py, z-.18))
for y in range(N-1):
    for x in range(N-1):
        i=y*N+x
        faces.append((i, i+1, i+1+N, i+N))
mesh=bpy.data.meshes.new('Scoured terrain')
mesh.from_pydata(verts, [], faces)
terrain=bpy.data.objects.new('Desert floor', mesh)
scene.collection.objects.link(terrain)
terrain.data.materials.append(sand)
for poly in terrain.data.polygons:
    poly.use_smooth=True

box('Concrete plinth', (0, .35, .12), (7.6, 6.2, .35), stone, .12)
box('Container body', (0, .2, 1.55), (5.5, 3.2, 2.55), teal, .1)
box('Roof rim', (0, .2, 2.88), (5.85, 3.55, .16), rust)
for x in [-2.65, 2.65]:
    for y in [-1.35, 1.75]:
        box('Corner casting', (x, y, 1.55), (.16,.16,2.65), edge)
for x in [i*.25-2.5 for i in range(21)]:
    box('Corrugated front', (x,-1.427,1.53), (.055,.075,2.3), teal, .009)
for y in [i*.23-1.25 for i in range(14)]:
    box('Corrugated side', (2.777,y,1.53), (.055,.06,2.3), rust, .008)
box('Door recess', (-1.5,-1.51,1.34), (1.15,.08,2.05), steel)
box('Door panel', (-1.5,-1.59,1.34), (.95,.07,1.86), pink)
box('Door handle', (-1.18,-1.68,1.4), (.06,.1,.29), edge)
box('Service hatch', (.92,-1.51,1.75), (2.0,.11,.86), black)
for x in [.25,.95,1.65]:
    box('Service hatch bars', (x,-1.60,1.75), (.035,.08,.86), steel)
box('Counter ledge', (.92,-1.78,1.23), (2.24,.59,.12), edge)
box('Canopy sheet', (.45,-2.00,2.70), (5.2,1.4,.10), pink, .02, (.11,0,0))
for x in [-2.02, 2.95]:
    beam('Canopy upright', (x,-2.54,.22), (x,-2.54,2.55), .045, rust)
    beam('Canopy diagonal', (x,-2.54,2.0), (x,-1.5,2.68), .035, edge)
for x in [-1.8,-.8,.2,1.2,2.2]:
    box('Canopy seam', (x,-2.0,2.775), (.025,1.4,.028), rust, .004, (.11,0,0))

# Elevated pressure vessel with braces and pipework.
tx, ty = .85, .7
for dx in [-.92,.92]:
    for dy in [-.92,.92]:
        beam('Tank support', (tx+dx,ty+dy,2.97), (tx+dx,ty+dy,4.07), .072, rust)
for dy in [-.92,.92]:
    beam('Tank cross brace', (tx-.92,ty+dy,2.97), (tx+.92,ty+dy,4.02), .032, edge)
    beam('Tank cross brace', (tx+.92,ty+dy,2.97), (tx-.92,ty+dy,4.02), .032, edge)
cylinder('Pressure vessel', (tx,ty,4.82), 1.22, 1.7, ivory, 64)
for z in [4.0,4.26,5.39,5.66]:
    ring('Tank reinforcing hoop', (tx,ty,z), 1.225, .045, rust)
for z in [4.0,5.66]:
    cylinder('Tank cap', (tx,ty,z), 1.20, .09, edge, 64)
cylinder('Tank manhole', (tx+.28,ty,5.81), .29, .23, steel)
ring('Manhole wheel', (tx+.28,ty,6.0), .25, .03, pink)
beam('Pressure pipe vertical', (2.23,.6,.43), (2.23,.6,5.12), .105, teal)
beam('Pressure pipe inlet', (1.98,.6,5.12), (2.23,.6,5.12), .105, teal)
beam('Distribution main', (2.23,.6,.43), (2.23,-2.9,.43), .105, teal)
for z in [1.0,2.45,3.75]:
    ring('Pipe collar', (2.23,.6,z), .117, .035, edge)
ring('Red valve', (2.23,-2.78,.8), .27, .042, pink, (math.pi/2,0,0))
beam('Valve stem', (2.23,-2.55,.45), (2.23,-2.78,.8), .04, edge)
for a in [0,math.pi/2]:
    beam('Valve spokes', (2.23-.24*math.cos(a),-2.78,.8-.24*math.sin(a)), (2.23+.24*math.cos(a),-2.78,.8+.24*math.sin(a)), .021, pink)
box('Water gauge frame', (tx,ty-1.232,4.81), (.3,.1,1.21), steel)
box('Water gauge glow', (tx,ty-1.29,4.65), (.15,.03,.79), cyan, .005)
for z in [4.32,4.5,4.68,4.86,5.04,5.22]:
    box('Gauge ticks', (tx+.25,ty-1.30,z), (.15,.018,.018), black, .002)
text_obj('Tank number', '03', (tx-.7,ty-1.19,4.79), .58, pink)

# A welded lookout, ladder, transmitter and torn signal banner.
box('Lookout deck', (-2.1,.5,3.08), (1.9,2.7,.13), steel)
for y in [-.82,1.80]:
    for x in [-2.94,-1.25]:
        beam('Rail stanchion', (x,y,3.1), (x,y,4.05), .032, edge)
    beam('Lookout rail', (-2.94,y,4.05), (-1.25,y,4.05), .034, edge)
for x in [-3.1,-2.58]:
    beam('Ladder side', (x,-.28,.25), (x,-.28,3.38), .035, rust)
for z in [.42+i*.27 for i in range(12)]:
    beam('Ladder rung', (-3.1,-.28,z), (-2.58,-.28,z), .026, edge)
beam('Transmitter mast', (-2.6,1.5,3.1), (-2.6,1.5,7.2), .045, steel)
for z in [5.9,6.3,6.7]:
    beam('Antenna dipole', (-3.25,1.5,z), (-1.95,1.5,z), .016, edge)
for x,y in [(-4,3),(-.8,2.5)]:
    beam('Guy wire', (-2.6,1.5,6.1), (x,y,.18), .008, edge)
fv, ff = [], []
for row in range(10):
    for col in range(17):
        u,v=col/16,row/9
        fv.append((-2.58+u*2.5, 1.50+.19*math.sin(u*8+v*2)*u, 6.65-v*1.14-.17*u+.06*math.sin(u*13)))
for row in range(9):
    for col in range(16):
        i=row*17+col
        if not (col>13 and row==8 and col%2):
            ff.append((i,i+1,i+18,i+17))
flagmesh=bpy.data.meshes.new('Banner fabric')
flagmesh.from_pydata(fv,[],ff)
flag=bpy.data.objects.new('Signal banner',flagmesh)
scene.collection.objects.link(flag)
flag.data.materials.append(cloth)
solid=flag.modifiers.new('Fabric thickness','SOLIDIFY'); solid.thickness=.012

# Typography, warning lamps and small props give the outpost a human scale.
box('Sign backing', (.45,-2.74,2.57), (3.15,.15,.40), black)
text_obj('Water sign', 'W A T E R', (.45,-2.827,2.57), .28, cyan)
for x in [-2.5,2.5]:
    cylinder('Lamp body', (x,-1.22,3.02), .14, .17, steel)
    cylinder('Amber beacon', (x,-1.22,3.16), .10, .14, amber)
for i in range(10):
    x,y=-1.25+(i%5)*.44, -3.8+(i//5)*.4
    box('Water canister', (x,y,.4), (.29,.21,.52), teal, .05)
    box('Canister handle', (x,y,.70), (.17,.065,.11), edge, .018)
    cylinder('Canister cap', (x+.08,y,.69), .035,.045, black,16)
for i in range(3):
    x,y=-3.1+i*.65,-2.05
    cylinder('Salvage barrel',(x,y,.73),.27,.95,rust)
    for z in [.34,.74,1.08]:
        ring('Barrel hoop',(x,y,z),.28,.026,steel)
for x,y in [(3.4,1.7),(3.4,2.4),(-3.6,2.7)]:
    box('Supply crate',(x,y,.58),(.85,.65,.77),ivory,.04)
    for dx in [-.28,.28]:
        box('Crate strap',(x+dx,y,.98),(.065,.67,.025),steel,.002)
for i in range(20):
    a=i*math.tau/20
    x,y=4.4*math.cos(a),3.5*math.sin(a)
    if y < -2.5 and abs(x)<2.5:
        continue
    box('Scrap barricade',(x,y,.58),(.7,.17,.96), [rust,steel,ivory][i%3],.015,(.10*random.random(),0,a+math.pi/2))
    beam('Barricade stake',(x,y,0),(x,y,1.23),.028,edge)
for i in range(70):
    a=random.random()*math.tau
    r=random.uniform(5,24)
    x,y=math.cos(a)*r,math.sin(a)*r
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1,location=(x,y,0))
    ob=bpy.context.object
    scale=random.uniform(.13,.63)
    ob.scale=(scale*random.uniform(1,1.8),scale,scale*.6)
    ob.rotation_euler=(random.random(),random.random(),random.random())
    finish(ob,'Wind worn rock',stone)
for i in range(12):
    x,y=random.uniform(-40,40),random.uniform(17,40)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1,location=(x,y,1.8))
    ob=bpy.context.object; ob.scale=(random.uniform(2,5),random.uniform(2,4),random.uniform(3,7))
    finish(ob,'Distant basalt spire',stone)

def aim(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

world=bpy.data.worlds.new('Violet dusk')
scene.world=world; world.use_nodes=True
world.node_tree.nodes['Background'].inputs['Color'].default_value=(.12,.075,.20,1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value=.38
bpy.ops.object.light_add(type='SUN',location=(-10,-8,18))
sun=bpy.context.object; sun.name='Low desert sun'; sun.data.energy=3.2; sun.data.color=(1,.53,.30); sun.data.angle=.12
aim(sun,(0,0,0))
for name,loc,color,power,size in [
    ('Cool sky fill',(2,-8,10),(.23,.54,1),2300,10),
    ('Pink rim',(-1,6,8),(1,.09,.25),1900,7),
    ('Canopy glow',(.4,-2.7,2.0),(.08,.8,1),95,2)]:
    bpy.ops.object.light_add(type='AREA',location=loc)
    light=bpy.context.object; light.name=name; light.data.color=color; light.data.energy=power; light.data.shape='DISK'; light.data.size=size
    aim(light,(0,0,2))

bpy.ops.object.camera_add(location=(-11,-14,7.6))
camera=bpy.context.object; camera.name='Stagecoach Station reveal'; camera.data.lens=43; scene.camera=camera
camera.data.dof.use_dof=True; camera.data.dof.focus_distance=18; camera.data.dof.aperture_fstop=8
for frame,loc,target in [(1,(-11,-16,3.9),(0,0,3.1)),(96,(-9,-15,3.3),(.1,0,3.1)),(192,(-7,-14,2.8),(.5,.3,3.2))]:
    camera.location=loc; aim(camera,target)
    camera.keyframe_insert(data_path='location',frame=frame)
    camera.keyframe_insert(data_path='rotation_euler',frame=frame)
scene.frame_start=1; scene.frame_end=192; scene.render.fps=24; scene.frame_set(80)
scene.render.engine='CYCLES'; scene.cycles.samples=32
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX'
devices=prefs.get_devices_for_type('OPTIX')
for device in devices:
    device.use=(device.type=='OPTIX')
scene.cycles.device='GPU'; scene.cycles.use_denoising=True
scene.render.resolution_x=1600; scene.render.resolution_y=900; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.filepath=str(OUT/'WaterOutpost.png')
scene.view_settings.view_transform='AgX'
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.shading.type='MATERIAL'

bpy.ops.object.select_all(action='DESELECT')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'WaterOutpost.blend'))
bpy.ops.render.render(write_still=True)
(OUT/'materials.json').write_text(json.dumps(palette,indent=2))

# The .blend above keeps all components editable. Only the export copy is joined.
for obj in list(scene.objects):
    obj.select_set(obj.type in {'MESH','FONT','CURVE'})
selected=list(bpy.context.selected_objects)
bpy.context.view_layer.objects.active=selected[0]
bpy.ops.object.convert(target='MESH')
for obj in list(bpy.context.selected_objects):
    bpy.context.view_layer.objects.active=obj
    for modifier in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=modifier.name)
bpy.context.view_layer.objects.active=bpy.context.selected_objects[0]
bpy.ops.object.join()
asset=bpy.context.object; asset.name='WaterOutpost'
scene.cursor.location=(0,0,0)
bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'WaterOutpost.fbx'),use_selection=True,object_types={'MESH'},apply_unit_scale=True,add_leaf_bones=False,bake_anim=False,axis_forward='-Y',axis_up='Z')
print('WATER_OUTPOST_ASSETS_READY', OUT)
