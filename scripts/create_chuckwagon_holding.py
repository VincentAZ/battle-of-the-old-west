"""Author a static chuckwagon reconstruction in Mixar from pinned references."""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/chuckwagon'
OUT = BASE/'local-source-v001'
BRIEF = BASE/'local-authoring-brief-v001.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
assert sha(BASE/'historical-evidence.json') == brief['historical_evidence_sha256']
assert sha(BASE/'reference-review-v001.json') == brief['reference_review_sha256']
for photo in json.loads((BASE/'reference-review-v001.json').read_text())['photos']:
    assert sha(BASE/photo['file']) == photo['sha256']
assert not OUT.exists(), 'Preserve previous source revisions'
OUT.mkdir()
bpy.ops.wm.read_factory_settings(use_empty=True)
random.seed(1866)
atlas = Image.new('RGB', (2048, 2048))
draw = ImageDraw.Draw(atlas)
regions = {'wood': (8,8,1016,1016), 'lightwood': (1040,8,2038,1016),
           'canvas': (8,1040,1016,2038), 'iron': (1040,1040,1518,1518),
           'tin': (1540,1040,2038,1518), 'rope': (1040,1540,1518,2038),
           'darkwood': (1540,1540,2038,2038)}
colours = {'wood': (149,88,37), 'lightwood': (181,119,57), 'canvas': (232,218,183),
           'iron': (32,34,35), 'tin': (157,164,164), 'rope': (136,102,59),
           'darkwood': (105,60,25)}
for key, rect in regions.items():
    draw.rectangle(rect,fill=colours[key])
    x0,y0,x1,y1=rect
    if 'wood' in key:
        for y in range(y0+5,y1-5,5):
            t=random.randint(-18,18); c=colours[key]
            draw.line([(x,y+math.sin(x*.021+y)*1.8) for x in range(x0+5,x1-5,12)],
                      fill=(c[0]+t,c[1]+t//2,c[2]+t//3),width=1)
    elif key=='canvas':
        for y in range(y0+3,y1-3,4):draw.line((x0+3,y,x1-3,y),fill=(222,208,173))
        for x in range(x0+3,x1-3,4):draw.line((x,y0+3,x,y1-3),fill=(228,214,179))
rng=np.random.default_rng(1866)
pixels=np.asarray(atlas).astype(np.int16)+rng.integers(-3,4,(2048,2048,1),dtype=np.int16)
texture=OUT/'Chuckwagon_BaseColor.png'
Image.fromarray(np.clip(pixels,0,255).astype(np.uint8)).save(texture)
material=bpy.data.materials.new('M_Chuckwagon_Atlas');material.use_nodes=True
bsdf=material.node_tree.nodes['Principled BSDF'];bsdf.inputs['Roughness'].default_value=.78
node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack()
material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
objects=[]


def solid(name,verts,faces,region,smooth=False):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o)
    mesh.materials.append(material)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    uv=mesh.uv_layers.new();x0,y0,x1,y1=regions[region]
    for face in mesh.polygons:
        axis=max(range(3),key=lambda k:abs(face.normal[k]));a,b=[k for k in range(3)if k!=axis]
        points=[mesh.vertices[i].co for i in face.vertices]
        low=[min(v[k]for v in points)for k in range(3)];high=[max(v[k]for v in points)for k in range(3)]
        for loop in face.loop_indices:
            v=mesh.vertices[mesh.loops[loop].vertex_index].co
            u=(v[a]-low[a])/max(1e-6,high[a]-low[a]);w=(v[b]-low[b])/max(1e-6,high[b]-low[b])
            uv.data[loop].uv=((x0+5+u*(x1-x0-10))/2048,1-(y1-5-w*(y1-y0-10))/2048)
        face.use_smooth=smooth
    objects.append(o)
    return o


def box(name,centre,size,region='wood'):
    x,y,z=centre;a,b,c=[v/2 for v in size]
    return solid(name,[(x+u*a,y+v*b,z+w*c)for u,v,w in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]],
                 [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],region)


def beam(name,a,b,width,depth,region='wood'):
    a,b=Vector(a),Vector(b);o=box(name,(0,0,0),(width,depth,(b-a).length),region)
    o.location=(a+b)/2;o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    return o


def tube(name,points,radius,region='iron',sides=8):
    points=[Vector(p)for p in points];verts=[]
    for i,p in enumerate(points):
        tangent=points[min(i+1,len(points)-1)]-points[max(0,i-1)]
        q=tangent.to_track_quat('Z','Y')
        verts += [p+q@Vector((radius*math.cos(j*math.tau/sides),radius*math.sin(j*math.tau/sides),0))for j in range(sides)]
    faces=[tuple(range(sides-1,-1,-1)),tuple((len(points)-1)*sides+j for j in range(sides))]
    for i in range(len(points)-1):
        for j in range(sides):
            a=i*sides+j;b=i*sides+(j+1)%sides;faces.append((a,b,b+sides,a+sides))
    return solid(name,verts,faces,region)


def annulus(name,radius,width,thickness,centre,region,segments=40):
    # Four circular loops around X; no doubled seam vertices or open end rings.
    x,y,z=centre;verts=[]
    for xx,rr in [(-width/2,radius-thickness),(-width/2,radius),(width/2,radius),(width/2,radius-thickness)]:
        verts += [(x+xx,y+rr*math.cos(i*math.tau/segments),z+rr*math.sin(i*math.tau/segments))for i in range(segments)]
    faces=[]
    for j in range(4):
        for i in range(segments):faces.append((j*segments+i,j*segments+(i+1)%segments,((j+1)%4)*segments+(i+1)%segments,((j+1)%4)*segments+i))
    return solid(name,verts,faces,region)


def vessel(name,centre,radius,height,region):
    x,y,z=centre;n=24;verts=[]
    # Closed exterior with a distinct lipped lid; no simulated contents.
    profile=[(.82*radius,0),(radius,.035),(radius,height*.83),(.87*radius,height*.9),
             (radius*1.04,height*.9),(radius*1.04,height*.94),(.65*radius,height)]
    for r,h in profile:verts += [(x+r*math.cos(i*math.tau/n),y+r*math.sin(i*math.tau/n),z+h)for i in range(n)]
    faces=[tuple(range(n-1,-1,-1)),tuple((len(profile)-1)*n+i for i in range(n))]
    for j in range(len(profile)-1):
        for i in range(n):faces.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
    solid(name,verts,faces,region)
    tube(name+' lid loop',[(x-.025,y,z+height),(x-.025,y,z+height+.035),(x+.025,y,z+height+.035),(x+.025,y,z+height)],.009,region)


# Front is -Y, kitchen is +Y. Review heading 180 makes the kitchen the facade.
for i in range(8):box('Bed floor plank',(-.525+i*.15,0,.98),(.147,3.0,.065),'lightwood')
for x in (-.63,.63):
    for i in range(4):box('Straight bed side board',(x,0,1.09+i*.13),(.055,3.04,.124))
    for y in (-1.43,-.52,.52,1.43):
        box('Side stake',(x*1.07,y,1.24),(.055,.075,.65),'darkwood')
        for z in (1.04,1.47):tube('Iron stake bolt',[(x*1.075,y,z),(x*1.12,y,z)],.012)
    box('Side top rail',(x,0,1.56),(.08,3.08,.055),'lightwood')
    box('Bed runner',(x*.7,0,.88),(.13,2.99,.15),'darkwood')
for i in range(4):box('Front bed board',(0,-1.5,1.09+i*.13),(1.2,.055,.124))
for y,z in [(-1.08,.55),(1.13,.67)]:
    box('Wood axle',(0,y,z),(1.75,.14,.14),'darkwood')
    tube('Continuous iron axle',[(-1.02,y,z),(1.02,y,z)],.032)
    box('Axle bolster',(0,y,(z+.95)/2),(1.1,.18,.95-z),'wood')
    for x in (-.48,.48):box('Iron axle strap',(x,y,z),(.046,.151,.15),'iron')
box('Reach between axles',(0,.03,.68),(.13,2.40,.14),'darkwood')
for x in (-.40,.40):
    beam('Front hound',(x,-1.06,.72),(x*.28,-1.89,.69),.07,.09)
    beam('Rear brace',(x,1.13,.74),(0,.1,.68),.065,.075)
tube('Front kingpin',[(0,-1.08,.45),(0,-1.08,.97)],.03)
beam('Wood tongue',(0,-1.1,.70),(0,-3.40,.40),.10,.11,'lightwood')
for y in (-1.7,-3.25):
    z=.70+(y+1.1)*.30/2.3;box('Tongue iron band',(0,y,z),(.112,.065,.122),'iron')
for x in (-.21,.21):beam('Tongue resting prop',(x,-3.20,.018),(0,-3.20,.434),.055,.065,'darkwood')

for x in (-.88,.88):
    for y,r,count in [(-1.08,.55,12),(1.13,.67,14)]:
        annulus('Timber wheel felloe',r-.008,.10,.07,(x,y,r),'wood')
        annulus('Narrow iron tire',r,.106,.014,(x,y,r),'iron')
        tube('Projecting wooden hub',[(x-.14,y,r),(x+.14,y,r)],.093,'darkwood',12)
        for hx in (x-.10,x+.10):annulus('Hub iron band',.098,.028,.012,(hx,y,r),'iron',24)
        for i in range(count):
            a=i*math.tau/count
            beam('Dished wooden spoke',(x-math.copysign(.026,x),y+.071*math.cos(a),r+.071*math.sin(a)),
                 (x,y+(r-.049)*math.cos(a),r+(r-.049)*math.sin(a)),.039,.047,'lightwood')
        tube('Axle outer cap',[(x-.151,y,r),(x+.151,y,r)],.034)

def bow(y,a,offset=0):
    normal=Vector((math.cos(a)/.635,0,math.sin(a)/1.06)).normalized()
    return Vector((.635*math.cos(a),y,1.55+1.06*math.sin(a)))+normal*offset

for y in (-1.43,-.36,.83):
    tube('Bentwood canvas bow',[bow(y,i*math.pi/32)for i in range(33)],.021,'lightwood')
    for x in (-.64,.64):box('Bow iron socket',(x,y,1.48),(.056,.07,.18),'iron')
# Cloth partly gathered towards the front, leaving the pantry and rear hoop visible.
na,ny=32,28;verts=[]
def cloth(y,a):return bow(y,a,.026+.012*(1-math.cos((y+1.5)*35+a*.5)))
for j in range(ny+1):
    y=-1.5+j*1.30/ny
    for i in range(na+1):verts.append(cloth(y,i*math.pi/na))
faces=[(j*(na+1)+i,j*(na+1)+i+1,(j+1)*(na+1)+i+1,(j+1)*(na+1)+i)for j in range(ny)for i in range(na)]
canvas=solid('Partly gathered cream canvas',verts,faces,'canvas',True)
bpy.context.view_layer.objects.active=canvas
mod=canvas.modifiers.new('Cloth thickness','SOLIDIFY');mod.thickness=.004
bpy.ops.object.modifier_apply(modifier=mod.name)
for y in (-1.5,-.20):tube('Canvas stitched hem',[cloth(y,i*math.pi/32)for i in range(33)],.008,'canvas')
for x in (-.655,.655):
    for y in (-1.40,-.85,-.31):tube('Plain cord tie',[(x,y,1.56),(x*1.025,y+.02,1.41),(x,y+.045,1.40)],.006,'rope')

# Rear pantry has an actual open front, shelves, drawers and a supported worktable.
box('Pantry back',(0,1.31,1.66),(1.23,.05,1.15),'darkwood')
for x in (-.61,.61):box('Pantry side',(x,1.59,1.66),(.055,.61,1.15),'lightwood')
for z in (1.105,1.64,1.925,2.23):box('Pantry shelf',(0,1.59,z),(1.24,.62,.045),'lightwood')
box('Pantry lower divider',(0,1.61,1.37),(.04,.57,.49))
for x in (-.405,0,.405):
    box('Small pantry drawer',(x,1.605,2.073),(.378,.54,.238))
    box('Drawer front',(x,1.89,2.073),(.386,.045,.243),'lightwood')
    tube('Wood drawer pull',[(x,1.909,2.073),(x,1.944,2.073)],.025,'darkwood',12)
for i in range(7):box('Hinged worktable plank',(-.534+i*.178,2.33,1.107),(.174,.91,.045),'lightwood')
for x in (-.52,.52):
    box('Table underside batten',(x,2.32,1.069),(.058,.89,.03),'darkwood')
    tube('Table iron hinge',[(x-.058,1.892,1.119),(x+.058,1.892,1.119)],.015)
    beam('Worktable support',(x,1.72,.76),(x,2.68,1.066),.042,.047,'darkwood')
box('Equipment boot floor',(0,1.62,.723),(1.11,.53,.045),'darkwood')
for x in (-.54,.54):box('Equipment boot side',(x,1.62,.86),(.045,.53,.25))
for y in (1.375,1.865):box('Equipment boot end',(0,y,.86),(1.06,.04,.25))
vessel('Lidded cast iron pot',(-.32,1.65,1.663),.137,.205,'iron')
vessel('Second cast iron pot',(.27,1.65,1.663),.117,.19,'iron')
for x,r in [(-.32,.137),(.27,.117)]:
    for side in (-1,1):tube('Small pot side handle',[(x+side*r,1.65,1.77),(x+side*(r+.028),1.65,1.79),(x+side*r,1.65,1.81)],.008)
vessel('Plain tin coffee pot',(-.30,1.65,1.129),.112,.32,'tin')
tube('Coffee pot handle',[(-.397,1.65,1.18),(-.47,1.65,1.19),(-.47,1.65,1.38),(-.397,1.65,1.4)],.012,'tin')
tube('Coffee pot spout',[(-.20,1.65,1.25),(-.12,1.65,1.36),(-.1,1.65,1.40)],.027,'tin',12)

audit=[]
for o in objects:
    bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(o.data)
    nonmanifold=sum(not e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True)
    area=min(f.calc_area()for f in bm.faces);bm.free()
    assert nonmanifold==0 and volume>1e-10 and area>1e-12,(o.name,nonmanifold,volume,area)
    audit.append(dict(name=o.name,nonmanifold_edges=nonmanifold,volume=volume,minimum_face_area=area))
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'Chuckwagon.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'Chuckwagon.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
triangles=0
for o in objects:o.data.calc_loop_triangles();triangles+=len(o.data.loop_triangles)
assert triangles<=30000,triangles
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),atlas_sha256=sha(texture),objects=len(objects),triangles=triangles,materials=1,rigged=False,animations=0,component_audit=audit,limitations=brief['reconstruction']),indent=2)+'\n')
print('CHUCKWAGON_AUTHORED',triangles,flush=True)
