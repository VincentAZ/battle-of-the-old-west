"""Static detached interpretation of Fort Laramie's stone postal portion."""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/western/holdings/expansion-review-v001/post-office'
OUT = BASE / 'local-source-v002'
BRIEF = BASE / 'local-authoring-brief-v002.json'
brief = json.loads(BRIEF.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert brief['pre_modeling_review']['completed']
assert sha(BASE / brief['sources'][0]['local_photo']) == brief['sources'][0]['sha256']
assert not OUT.exists()
OUT.mkdir()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
random.seed(1852)
rng = np.random.default_rng(1852)

# Rough stone in irregular courses, not a regular brick bond. UVs follow world
# coordinates so the material keeps the same scale across wall opening pieces.
atlas = Image.new('RGB', (2048, 2048), (184, 167, 135))
draw = ImageDraw.Draw(atlas)
scale = 1536 / 8
y = 0
while y < 1536:
    height = random.randint(14, 29)
    x = -random.randint(1, 90)
    while x < 1536:
        width = random.randint(22, 66)
        tone = random.randint(-28, 25)
        polygon = [(x+3,y+random.randint(2,5)), (x+width//2,y+1),
                   (x+width-4,y+random.randint(2,5)), (x+width-1,y+height//2),
                   (x+width-5,y+height-2), (x+width//2,y+height-random.randint(1,4)),
                   (x+2,y+height-3), (x+1,y+height//2)]
        draw.polygon(polygon, fill=(207+tone,188+tone,153+tone))
        draw.line(polygon[:3], fill=(224+tone//2,205+tone//2,174+tone//2), width=1)
        # Irregular mineral flecks give each stone a rough face without
        # inventing cut ornament or deeply incised mortar grooves.
        for _ in range(width*height//18):
            sx=random.randint(x+5,x+width-5)
            sy=random.randint(y+5,y+height-5)
            fleck=random.randint(-13,10)
            draw.point((sx,sy),fill=(207+tone+fleck,188+tone+fleck,153+tone+fleck))
        x += width
    y += height
regions = {'wood': (1550, 8, 2038, 760), 'roof': (1550, 780, 2038, 1530),
           'glass': (8, 1550, 490, 2038), 'iron': (510, 1550, 770, 2038),
           'threshold': (790, 1550, 1260, 2038), 'chimney': (1280, 1550, 2038, 2038)}
colours = {'wood': (112, 70, 34), 'roof': (109, 88, 59),
           'glass': (30, 44, 48), 'iron': (36, 34, 28),
           'threshold': (183, 164, 129), 'chimney': (194, 175, 140)}
for key, region in regions.items():
    draw.rectangle(region, fill=colours[key])
for key in ('wood', 'roof'):
    x0, y0, x1, y1 = regions[key]
    for x in range(x0+5, x1-4, 3):
        tone = random.randint(-17, 16)
        colour = tuple(c+tone for c in colours[key])
        draw.line((x,y0+4,x+random.randint(-2,2),y1-4), fill=colour)
pixels = np.asarray(atlas).astype(np.int16)
pixels += rng.integers(-5,6,(2048,2048,1),dtype=np.int16)
texture = OUT / 'PostOffice_BaseColor.png'
Image.fromarray(np.clip(pixels,0,255).astype(np.uint8)).save(texture)
material = bpy.data.materials.new('M_PostOffice_Atlas')
material.use_nodes = True
bsdf = material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value = .86
node = material.node_tree.nodes.new('ShaderNodeTexImage')
node.image = bpy.data.images.load(str(texture))
node.image.pack()
material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
objects = []


def map_uv(o, region):
    mesh = o.data
    mesh.update()
    uv = mesh.uv_layers.active or mesh.uv_layers.new()
    for face in mesh.polygons:
        normal = max(range(3), key=lambda k: abs(face.normal[k]))
        axes = [k for k in range(3) if k != normal]
        points = [mesh.vertices[mesh.loops[i].vertex_index].co for i in face.loop_indices]
        lows = [min(p[k] for p in points) for k in range(3)]
        highs = [max(p[k] for p in points) for k in range(3)]
        for loop in face.loop_indices:
            v = mesh.vertices[mesh.loops[loop].vertex_index].co
            if region == 'stone':
                horizontal = 1 if normal == 0 else 0
                u = (v[horizontal]+o.location[horizontal]+4)/8
                vv = (v.z+o.location.z)/8 if normal != 2 else (v.y+o.location.y+4)/8
                uv.data[loop].uv = (u*.75,1-vv*.75)
            else:
                a,b = axes
                u = (v[a]-lows[a])/max(highs[a]-lows[a],.00001)
                vv = (v[b]-lows[b])/max(highs[b]-lows[b],.00001)
                x0,y0,x1,y1 = regions[region]
                uv.data[loop].uv = ((x0+5+u*(x1-x0-10))/2048,
                                    1-(y1-5-vv*(y1-y0-10))/2048)


def box(name, location, dimensions, region='stone', rotation=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location)
    o = bpy.context.object
    o.name = name
    o.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(material)
    map_uv(o,region)
    if rotation:
        o.rotation_euler = rotation
    objects.append(o)
    return o


def wall(name, axis, side, span, openings):
    rectangles = [(-span/2,span/2,.10,2.5)]
    for left,right,bottom,top in openings:
        next_rect = []
        for a,b,c,d in rectangles:
            lo,hi = max(a,left),min(b,right)
            z0,z1 = max(c,bottom),min(d,top)
            if lo >= hi or z0 >= z1:
                next_rect.append((a,b,c,d))
                continue
            next_rect.extend([(a,b,c,z0),(a,b,z1,d),(a,lo,z0,z1),(hi,b,z0,z1)])
        rectangles = [r for r in next_rect if r[1]-r[0]>.001 and r[3]-r[2]>.001]
    for a,b,c,d in rectangles:
        if axis == 1:
            box(name,((a+b)/2,side,(c+d)/2),(b-a,.20,d-c))
        else:
            box(name,(side,(a+b)/2,(c+d)/2),(.20,b-a,d-c))


box('Low masonry plinth',(0,0,.05),(6.2,3.5,.10))
# The photographed facade has two doors. Retain that distinction from a
# generic one-door store, while compressing the photographed complex.
windows = [-2.03,.41]
doors = [-.79,1.68]
openings = [(x-.38,x+.38,.73,1.98) for x in windows]
openings += [(x-.40,x+.40,.10,2.03) for x in doors]
wall('Front rubble masonry',1,-1.65,6.2,openings)
wall('Reconstructed rear masonry',1,1.65,6.2,[])
wall('Left end masonry',0,-3,3.1,[])
wall('Right end masonry',0,3,3.1,[(-.35,.35,.91,1.79)])


def window(name, centre, width, height, columns, rows, side=False):
    # A complete recessed glazed sash. Side face is a rotated front assembly.
    x,y,z = centre
    def part(label, dx,dy,dz,w,d,h,region='wood'):
        if side:
            return box(name+' '+label,(x-dy,y+dx,z+dz),(d,w,h),region)
        return box(name+' '+label,(x+dx,y+dy,z+dz),(w,d,h),region)
    part('dark glazing',0,.025,0,width,.018,height,'glass')
    for sign in (-1,1):
        part('jamb',sign*(width/2+.036),0,0,.072,.11,height+.144)
        part('head or sill',0,0,sign*(height/2+.036),width,.13,.072)
    for col in range(1,columns):
        part('muntin',-width/2+col*width/columns,-.012,0,.022,.043,height)
    for row in range(1,rows):
        part('sash rail',0,-.012,-height/2+row*height/rows,width,.045,.038 if row==rows//2 else .022)


for x in windows:
    window('Front divided sash',(x,-1.755,1.355),.76,1.25,3,4)
window('Gable divided sash',(3.105,0,1.35),.70,.88,2,2,side=True)
for x in doors:
    for n in range(6):
        box('Plain timber door plank',(x-.40+(n+.5)*.80/6,-1.72,1.065),
            (.80/6-.003,.048,1.93),'wood')
    for sign in (-1,1):
        box('Door timber jamb',(x+sign*.435,-1.765,1.065),(.07,.12,1.93),'wood')
    box('Door timber lintel',(x,-1.765,2.065),(.94,.12,.07),'wood')
    box('Worn stone doorstep',(x,-1.81,.07),(.98,.30,.14),'threshold')
    box('Simple iron latch',(x+.28,-1.761,1.10),(.035,.035,.115),'iron')

# Low-pitched gables and physical shingle layers, without repeated modern
# corrugated sheet or unsupported planar roof edges.
run,rise = 1.92,.77
angle = math.atan2(rise,run)
slope = math.hypot(run,rise)
for side in (-1,1):
    o=box('Rubble masonry gable',(side*3,0,2.88),(.20,3.5,.76))
    for v in o.data.vertices:
        if v.co.z > 0:
            v.co.y = 0
    map_uv(o,'stone')
    box('Timber roof boarding',(0,side*run/2,2.51+rise/2),
        (6.60,slope,.085),'wood',(-side*angle,0,0))
    for row in range(9):
        distance = (row+.5)*slope/9
        offset = .125 if row%2 else 0
        for col in range(27):
            left=max(-3.29,-3.29+col*.25-offset)
            right=min(3.29,-3.29+(col+1)*.25-offset)
            if right-left<.01:
                continue
            box('Individual wood shingle',((left+right)/2,side*distance*math.cos(angle),
                2.51+rise-distance*math.sin(angle)+.064),
                (right-left-.002,slope/9+.037,.023),'roof',(-side*(angle-.025),0,0))
    box('Long eave fascia',(0,side*1.895,2.525),(6.62,.072,.15),'wood')
    for x in [-2.85,-1.90,-.95,0,.95,1.90,2.85]:
        box('Projecting square eave support',(x,side*1.775,2.415),(.12,.36,.14),'wood')
    for end in (-1,1):
        box('Gable rake trim',(end*3.285,side*run/2,2.51+rise/2),
            (.09,slope+.035,.12),'wood',(-side*angle,0,0))
box('Timber ridge cap',(0,0,3.345),(6.60,.14,.075),'roof')
for end in (-1,1):
    box('Closed timber ridge joint',(end*3.285,0,3.285),(.095,.13,.16),'wood')
box('Squat masonry chimney',(-2.05,.04,3.37),(.42,.45,1.00),'chimney')
box('Chimney projecting cap',(-2.05,.04,3.855),(.54,.57,.10),'threshold')
box('Dark recessed flue',(-2.05,.04,3.909),(.28,.30,.009),'iron')

bpy.ops.object.select_all(action='DESELECT')
for o in objects:
    o.select_set(True)
bpy.context.view_layer.objects.active = objects[0]
project = OUT / 'PostOffice.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb = OUT / 'PostOffice.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,
    export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',
    brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),
    atlas_sha256=sha(texture),objects=len(objects),materials=1,rigged=False,
    animations=0,paid_service_jobs=0,limitations=brief['reconstruction']),indent=2)+'\n')
print('POST_OFFICE_AUTHORED',str(glb),flush=True)
