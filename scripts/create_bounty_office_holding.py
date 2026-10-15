"""Static game-scale interpretation of the 1875–1888 Fort Smith office type.

Run in Mixar; the pinned brief and inspected NPS nomination photographs precede authoring.
"""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
import bmesh
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/bounty-office'
OUT = BASE/'local-source-v003'
BRIEF = BASE/'local-authoring-brief-v003.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
assert brief['pre_modeling_review']['completed']
for path, digest in brief['source_records'].items():
    assert sha(ROOT/path) == digest, path
assert not OUT.exists(), 'Preserve earlier authoring sources'
OUT.mkdir()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
random.seed(1886)
rng = np.random.default_rng(1886)

# One atlas: five stretcher courses followed by an all-header course.
# World-space projection keeps the bond continuous across opening pieces.
atlas = Image.new('RGB', (2048, 2048), (149, 132, 113))
draw = ImageDraw.Draw(atlas)
px = 1536/8
course = .038*px
row = 0
while row*course < 1536:
    y0,y1 = round(row*course),round((row+1)*course)
    width = (.057 if row%6 == 5 else .116)*px
    x = -width/2 if row%2 else 0
    while x < 1536:
        tone = random.randint(-19,18)
        draw.rectangle((round(x+.7),y0+1,round(x+width-.7),y1-1),
                       fill=(180+tone,65+tone//2,40+tone//3))
        x += width
    row += 1
regions = {'stone':(1544,8,2038,490), 'roof':(1544,510,2038,1010),
           'iron':(1544,1030,1775,1280), 'glass':(1795,1030,2038,1280),
           'wood':(1544,1300,2038,1528), 'door':(8,1550,1020,2038),
           'foundation':(1040,1550,2038,2038)}
colours = {'stone':(236,231,215), 'roof':(59,64,68), 'iron':(35,34,30),
           'glass':(33,48,57), 'wood':(142,94,47), 'door':(108,65,32),
           'foundation':(181,170,147)}
for key, rect in regions.items():
    draw.rectangle(rect,fill=colours[key])
for x in range(15,1014,3):
    tone = random.randint(-14,14)
    draw.line((x,1558,x+random.randint(-2,2),2030),fill=(108+tone,65+tone//2,32+tone//3))
pixels = np.asarray(atlas).astype(np.int16)
pixels += rng.integers(-4,5,(2048,2048,1),dtype=np.int16)
texture = OUT/'BountyOffice_BaseColor.png'
Image.fromarray(np.clip(pixels,0,255).astype(np.uint8)).save(texture)
material = bpy.data.materials.new('M_BountyOffice_Atlas')
material.use_nodes = True
bsdf = material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value = .82
node = material.node_tree.nodes.new('ShaderNodeTexImage')
node.image = bpy.data.images.load(str(texture)); node.image.pack()
material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
objects = []


def finish(o, region):
    o.data.materials.append(material)
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(o.data); bm.free(); o.data.update()
    uv = o.data.uv_layers.active or o.data.uv_layers.new()
    for face in o.data.polygons:
        axis = max(range(3),key=lambda k:abs(face.normal[k]))
        a,b = [k for k in range(3) if k != axis]
        coords = [o.data.vertices[o.data.loops[i].vertex_index].co for i in face.loop_indices]
        lows = [min(p[k] for p in coords) for k in range(3)]
        highs = [max(p[k] for p in coords) for k in range(3)]
        for loop in face.loop_indices:
            v = o.data.vertices[o.data.loops[loop].vertex_index].co
            if region == 'brick':
                world = o.matrix_world @ v
                h = 1 if axis == 0 else 0
                u = (world[h]+4)/8
                vv = world.z/8 if axis != 2 else (world.y+4)/8
                uv.data[loop].uv = (u*.75,1-vv*.75)
            else:
                x0,y0,x1,y1 = regions[region]
                u = (v[a]-lows[a])/max(highs[a]-lows[a],.00001)
                vv = (v[b]-lows[b])/max(highs[b]-lows[b],.00001)
                uv.data[loop].uv = ((x0+6+u*(x1-x0-12))/2048,
                                    1-(y1-6-vv*(y1-y0-12))/2048)
    objects.append(o)
    return o


def box(name, location, dimensions, region='brick', rotation=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location)
    o = bpy.context.object; o.name = name; o.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if rotation:
        o.rotation_euler = rotation
    bpy.context.view_layer.update()
    return finish(o,region)


def solid(name, vertices, faces, region):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices,[],faces); mesh.update()
    o = bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o)
    return finish(o,region)


def prism(name, polygon, axis, position, thickness, region):
    # Closed extrusion of a 2D polygon in the two other coordinate axes.
    axes = [k for k in range(3) if k != axis]
    vertices = []
    for side in (-1,1):
        for a,b in polygon:
            p = [0,0,0]; p[axis] = position+side*thickness/2
            p[axes[0]],p[axes[1]] = a,b; vertices.append(p)
    n = len(polygon)
    faces = [tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return solid(name,vertices,faces,region)


def wall(name, axis, position, low, high, openings, zlow=.12, zhigh=2.38):
    rectangles = [(low,high,zlow,zhigh)]
    for left,right,bottom,top in openings:
        next_rect = []
        for a,b,c,d in rectangles:
            lo,hi = max(a,left),min(b,right); z0,z1 = max(c,bottom),min(d,top)
            if lo >= hi or z0 >= z1:
                next_rect.append((a,b,c,d)); continue
            next_rect.extend([(a,b,c,z0),(a,b,z1,d),(a,lo,z0,z1),(hi,b,z0,z1)])
        rectangles = [r for r in next_rect if r[1]-r[0]>.001 and r[3]-r[2]>.001]
    for a,b,c,d in rectangles:
        if axis == 0: box(name,(position,(a+b)/2,(c+d)/2),(.10,b-a,d-c))
        else: box(name,((a+b)/2,position,(c+d)/2),(b-a,.10,d-c))



# Static detached five-bay reconstruction. The historical office occupied
# part of a ten-bay building; neither dimensions nor independence are claims.
box('Raised stone foundation',(0,0,.25),(4.30,3.54,.50),'foundation')
box('Stone belt course',(0,0,.48),(4.40,2.40,.10),'stone')
windows=[-1.64,-.82,.82,1.64]

def sash(axis,plane,along,z,width,height,rows=6,columns=3):
    def part(name,offset,dz,w,h,depth,region,shift=0):
        if axis==1: return box(name,(along+offset,plane+shift,z+dz),(w,depth,h),region)
        return box(name,(plane+shift,along+offset,z+dz),(depth,w,h),region)
    part('Recessed dark glazing',0,0,width,height,.025,'glass')
    for sign in (-1,1):
        part('Timber sash stile',sign*(width/2+.025),0,.05,height+.10,.055,'wood')
        part('Timber sash rail',0,sign*(height/2+.025),width,.05,.06,'wood')
    for i in range(1,columns):part('Vertical glazing bar',-width/2+i*width/columns,0,.016,height,.04,'wood')
    for i in range(1,rows):part('Horizontal glazing bar',0,-height/2+i*height/rows,width,.034 if i==rows//2 else .016,.04,'wood')
    part('Pale stone lintel',0,height/2+.10,width+.20,.10,.15,'stone')
    part('Pale stone sill',0,-height/2-.08,width+.20,.08,.17,'stone')

for side in (-1,1):
    openings=[(x-.26,x+.26,.89,1.97) for x in windows]+[(-.30,.30,.53,2.10)]
    wall('Long brick office wall',1,side*1.10,-2.05,2.05,openings,zlow=.50,zhigh=2.405)
    for x in windows:sash(1,side*1.145,x,1.43,.52,1.08)
    for x in [-.25,-.15,-.05,.05,.15,.25]:
        box('Plain timber door plank',(x,side*1.145,1.315),(.096,.052,1.57),'door')
    for x in (-.335,.335):box('Door timber jamb',(x,side*1.16,1.325),(.065,.10,1.59),'wood')
    box('Door header',(0,side*1.16,2.135),(.74,.10,.07),'wood')
    box('Door stone lintel',(0,side*1.13,2.23),(.86,.17,.12),'stone')
    box('Plain iron latch',(.205,side*1.18,1.28),(.025,.025,.09),'iron')
    # Deck boards and piers physically meet the common roof, without rigs.
    for i in range(29):box('Gallery deck board',(-2.175+(i+.5)*4.35/29,side*1.43,.53),(4.35/29-.004,.66,.06),'door')
    box('Gallery timber edge beam',(0,side*1.73,.46),(4.38,.10,.14),'wood')
    for x in [-2.07,-1.24,-.41,.41,1.24,2.07]:
        box('Square brick gallery pier',(x,side*1.66,1.245),(.15,.15,1.47),'brick')
        box('Pier stone foot',(x,side*1.66,.49),(.21,.21,.10),'stone')
        box('Pier capital',(x,side*1.66,1.995),(.20,.20,.07),'brick')
    box('Gallery wall plate',(0,side*1.66,2.01),(4.37,.17,.095),'wood')
    for i in range(5):
        height=(5-i)*.105
        box('Cut-stone entrance step',(0,side*(1.80+i*.115),height/2),(.85,.125,height),'stone')

# The two upper windows and parapet/chimneys come from the inspected historic
# end views. No later first-floor end windows or ridge ventilators are added.
for side in (-1,1):
    x=side*2.10
    wall('Unpierced lower end wall',0,x,-1.10,1.10,[],zlow=.50,zhigh=2.405)
    wall('Upper parapet wall',0,x,-.60,.60,[(-.34,-.12,2.49,2.89),(.12,.34,2.49,2.89)],zlow=2.40,zhigh=3.10)
    for y in (-.23,.23):sash(0,side*2.155,y,2.69,.22,.40,rows=2,columns=1)
    for sign in (-1,1):
        prism('Sloping brick gable shoulder',[(sign*.60,2.40),(sign*1.10,2.40),(sign*.60,2.69)],0,x,.10,'brick')
        # Coping follows the inclined edge of each shoulder.
        box('Inclined stone gable coping',(x,sign*.85,2.585),(.17,.59,.07),'stone',(-sign*math.atan2(.29,.50),0,0))
        box('Paired brick end chimney',(x,sign*.53,3.25),(.24,.24,.80),'brick')
        box('Chimney corbel cap',(x,sign*.53,3.645),(.29,.29,.07),'brick')
        box('Recessed flue',(x,sign*.53,3.683),(.16,.16,.007),'iron')
    box('Flat stone parapet coping',(x,0,3.12),(.17,1.03,.075),'stone')

run,rise=1.88,1.02
angle=math.atan2(rise,run);slope=math.hypot(run,rise)
for side in (-1,1):
    box('Continuous roof boarding',(0,side*run/2,3.0-rise/2),(4.23,slope,.065),'wood',(-side*angle,0,0))
    for row in range(12):
        distance=(row+.5)*slope/12
        shift=.10 if row%2 else 0
        for col in range(23):
            left=max(-2.125,-2.125+col*.20-shift);right=min(2.125,-2.125+(col+1)*.20-shift)
            if right-left<.01:continue
            box('Overlapping slate',(left/2+right/2,side*distance*math.cos(angle),3.0-distance*math.sin(angle)+.048),
                (right-left-.002,slope/12+.025,.019),'roof',(-side*(angle-.025),0,0))
    box('Roof eave fascia',(0,side*1.865,1.995),(4.26,.06,.11),'wood')
box('Closed ridge cap',(0,0,3.055),(4.23,.11,.06),'roof')

bpy.ops.object.select_all(action='DESELECT')
for obj in objects:obj.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'BountyOffice.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'BountyOffice.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),atlas_sha256=sha(texture),objects=len(objects),materials=1,rigged=False,animations=0,paid_service_jobs=0,limitations=brief['reconstruction']),indent=2)+'\n')
print('BOUNTY_OFFICE_AUTHORED',str(glb),flush=True)
