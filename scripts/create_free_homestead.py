"""Author a static Nebraska cabin reconstruction from the pinned NPS brief."""
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
BASE = ROOT/'art/western/holdings/expansion-review-v001/free-homestead'
OUT = BASE/'local-source-v003'
BRIEF = BASE/'local-authoring-brief-v003.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
assert sha(BASE/'historical-evidence.json') == brief['historical_evidence_sha256']
assert sha(BASE/'reference-review-v001.json') == brief['reference_review_sha256']
for photo in json.loads((BASE/'reference-review-v001.json').read_text())['photos']:
    assert sha(BASE/photo['file']) == photo['sha256']
assert not OUT.exists()
OUT.mkdir()
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
random.seed(1867)
rng = np.random.default_rng(1867)
atlas = Image.new('RGB', (2048, 2048), (115, 73, 40))
draw = ImageDraw.Draw(atlas)
regions = {'wood': (8, 8, 1016, 1016), 'brick': (1040, 8, 2038, 1016),
           'mortar': (8, 1040, 500, 1528), 'glass': (520, 1040, 1016, 1528),
           'roof': (1040, 1040, 2038, 2038), 'iron': (8, 1550, 500, 2038),
           'frame': (520, 1550, 1016, 2038)}
colours = {'wood': (117, 78, 43), 'brick': (221, 212, 187), 'mortar': (222, 214, 190),
           'glass': (28, 44, 49), 'roof': (73, 48, 30), 'iron': (39, 34, 27), 'frame': (151, 109, 67)}
for key, rect in regions.items(): draw.rectangle(rect, fill=colours[key])
# Hewn hardwood grain; the small value variations never desaturate the scene.
for y in range(13, 1010, 3):
    tone = random.randint(-24, 24)
    draw.line([(x, y+math.sin(x*.028+y)*2) for x in range(14, 1010, 18)],
              fill=(117+tone, 78+tone//2, 43+tone//3), width=1)
# Six metres of continuous brick bond across this atlas patch.
for row in range(94):
    for column in range(31):
        x=1044+column*33-(16 if row%2 else 0); y=12+row*10.7
        if x>=2034 or x+31<=1044 or y>=1013: continue
        tone=random.randint(-22,22)
        draw.rectangle((max(1043,x+1),y+1,min(2035,x+31),min(1014,y+9)),fill=(161+tone,67+tone//2,36+tone//3))
for row in range(14):
    for column in range(12):
        x = 1046+column*93-(46 if row%2 else 0); y = 1046+row*73
        if x >= 2034 or x+88 <= 1044: continue
        tone = random.randint(-12, 18)
        draw.rectangle((max(1043,x),y,min(2035,x+88),min(2035,y+68)), fill=(76+tone,49+tone//2,29+tone//3))
pixels = np.asarray(atlas).astype(np.int16)+rng.integers(-4,5,(2048,2048,1),dtype=np.int16)
texture = OUT/'FreeHomestead_BaseColor.png'
Image.fromarray(np.clip(pixels,0,255).astype(np.uint8)).save(texture)
material = bpy.data.materials.new('M_FreeHomestead_Atlas'); material.use_nodes = True
bsdf = material.node_tree.nodes.get('Principled BSDF'); bsdf.inputs['Roughness'].default_value = .86
node = material.node_tree.nodes.new('ShaderNodeTexImage'); node.image = bpy.data.images.load(str(texture)); node.image.pack()
material.node_tree.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
objects = []


def solid(name, vertices, faces, region):
    mesh = bpy.data.meshes.new(name); mesh.from_pydata(vertices, [], faces); mesh.update()
    o = bpy.data.objects.new(name, mesh); bpy.context.collection.objects.link(o)
    mesh.materials.append(material)
    bm = bmesh.new(); bm.from_mesh(mesh); bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
    uv = mesh.uv_layers.new(); x0,y0,x1,y1 = regions[region]
    for face in mesh.polygons:
        axis = max(range(3), key=lambda k: abs(face.normal[k]))
        a,b = [k for k in range(3) if k != axis]
        points = [mesh.vertices[i].co for i in face.vertices]
        low = [min(v[k] for v in points) for k in range(3)]
        high = [max(v[k] for v in points) for k in range(3)]
        for loop in face.loop_indices:
            v = mesh.vertices[mesh.loops[loop].vertex_index].co
            u = (v[a]-low[a])/max(1e-6,high[a]-low[a]); w = (v[b]-low[b])/max(1e-6,high[b]-low[b])
            if region == 'brick':
                u=(v.y+3)/6; w=v.z/6
            uv.data[loop].uv = ((x0+5+u*(x1-x0-10))/2048, 1-(y1-5-w*(y1-y0-10))/2048)
    objects.append(o)
    return o


def box(name, centre, size, region):
    x,y,z = centre; a,b,c = [v/2 for v in size]
    return solid(name,[(x+u*a,y+v*b,z+w*c)for u,v,w in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]],
                 [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],region)


def extrusion(name, polygon, axis, plane, depth, region):
    other = [k for k in range(3) if k != axis]; vertices=[]
    for side in (-1,1):
        for a,b in polygon:
            v=[0,0,0];v[axis]=plane+side*depth/2;v[other[0]]=a;v[other[1]]=b;vertices.append(v)
    n=len(polygon)
    return solid(name,vertices,[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n)for i in range(n)],region)


def facade_box(name, axis, plane, u, z, width, depth, height, region):
    return box(name,(plane,u,z)if axis==0 else(u,plane,z),(depth,width,height)if axis==0 else(width,depth,height),region)


def segments(low, high, bottom, top, openings):
    rects=[(low,high,bottom,top)]
    for left,right,lower,upper in openings:
        remaining=[]
        for a,b,c,d in rects:
            if right<=a or left>=b or upper<=c or lower>=d:remaining.append((a,b,c,d));continue
            if a<left:remaining.append((a,left,c,d))
            if b>right:remaining.append((right,b,c,d))
            aa,bb=max(a,left),min(b,right)
            if c<lower:remaining.append((aa,bb,c,lower))
            if d>upper:remaining.append((aa,bb,upper,d))
        rects=remaining
    return rects


X,Y=2.4384,2.1336
EAVE,RIDGE=2.66,4.15
door=(-1.34,-.48,.02,1.96)
front_window=(.42,1.17,.68,1.98)
end_window=(-.40,.40,.69,1.99)
loft_window=(-.30,.30,2.78,3.46)
for axis, plane, half, openings in [(1,-Y,X,[door,front_window]),(1,Y,X,[]),(0,-X,Y,[end_window]),(0,X,Y,[end_window])]:
    # Mortar cores are cut through at every opening. Logs project beyond them.
    core_half=half+(.095 if axis==1 else -.095)
    for a,b,c,d in segments(-core_half,core_half,0,EAVE,openings):
        facade_box('Lime-chink wall core',axis,plane,(a+b)/2,(c+d)/2,b-a,.19,d-c,'mortar')
    for row in range(10):
        bottom=.025+row*.262; top=min(EAVE,bottom+.20+.009*math.sin(row*1.7))
        middle=(bottom+top)/2
        cuts=list(openings)
        # Alternating half-lap ends interlock instead of passing through one another.
        for side in (-1,1):
            lo,hi=sorted((side*(half-.16),side*(half+.106)))
            cuts.append((lo,hi,middle if axis==1 else bottom,top if axis==1 else middle))
        for a,b,c,d in segments(-half-.105,half+.105,bottom,top,cuts):
            # Slightly hewn edges: a closed eight-sided longitudinal profile.
            mid=(a+b)/2; wave=min(.017,(d-c)*.12)
            poly=[(a,c+.008),(mid,c),(b,c+.014),(b,d-.008),(mid,d-wave),(a,d)]
            extrusion('Hewn hardwood log course',poly,axis,plane,.28,'wood')
    if axis==0:
        # Gable consists of a solid brick triangle with the loft opening cut out
        # using horizontal bands, clipped to the roof pitch.
        for low,high in [(EAVE,2.78),(2.78,3.46),(3.46,RIDGE)]:
            w0=Y*(RIDGE-low)/(RIDGE-EAVE); w1=Y*(RIDGE-high)/(RIDGE-EAVE)
            if low==2.78:
                for side in (-1,1):
                    polygon=[(side*.30,low),(side*w0,low),(side*w1,high),(side*.30,high)]
                    extrusion('Brick gable beside loft opening',polygon,0,plane,.20,'brick')
            else:
                polygon=[(-w0,low),(w0,low),(w1,high),(-w1,high)]
                if w1<1e-6:polygon=polygon[:3]
                extrusion('Brick gable infill',polygon,0,plane,.20,'brick')
        for u in [-1.6,-.8,0,.8,1.6]:
            top=RIDGE-abs(u)*(RIDGE-EAVE)/Y
            low=3.50 if u==0 else EAVE
            if top>low:facade_box('Gable timber stud',0,plane+math.copysign(.11,plane),u,(top+low)/2,.065,.05,top-low,'wood')


def window(axis, plane, u, bottom, width, height, rows):
    side=math.copysign(1,plane)
    facade_box('Recessed dark glazing',axis,plane+side*.06,u,bottom+height/2,width,.025,height,'glass')
    for edge in (-1,1):
        facade_box('Plain unpainted jamb',axis,plane+side*.16,u+edge*(width/2+.025),bottom+height/2,.065,.10,height+.12,'frame')
        facade_box('Window head or sill',axis,plane+side*.165,u,bottom+(height if edge==1 else 0),width+.13,.11,.065,'frame')
    facade_box('Sash central muntin',axis,plane+side*.13,u,bottom+height/2,.024,.035,height,'frame')
    for row in range(1,rows):facade_box('Sash horizontal rail',axis,plane+side*.123,u,bottom+height*row/rows,width,.035,.038 if row==rows/2 else .024,'frame')


window(1,-Y,.795,.68,.75,1.30,6)
for side in (-1,1):
    window(0,side*X,0,.69,.80,1.30,6)
    window(0,side*X,0,2.78,.60,.68,3)
for i in range(6):facade_box('Entrance vertical plank',1,-Y-.12,-1.34+.86*(i+.5)/6,.99,.86/6-.007,.07,1.94,'frame')
for x in (-1.38,-.44):facade_box('Door frame jamb',1,-Y-.18,x,1.0,.07,.11,2.0,'wood')
facade_box('Door lintel',1,-Y-.18,-.91,2.01,1.02,.12,.10,'wood')
for z in (.45,1.57):facade_box('Small iron door hinge',1,-Y-.168,-1.28,z,.17,.015,.035,'iron')
facade_box('Simple dark latch',1,-Y-.17,-.59,1.04,.045,.022,.11,'iron')
# Closed roof planes and layered eave boards, covering the wall without a plinth.
for side in (-1,1):
    edge=side*(Y+.19); zedge=EAVE; zridge=RIDGE+.075
    extrusion('Wood-shingle roof slope',[(0,zridge),(edge,zedge),(edge,zedge-.055),(0,zridge-.055)],0,0,2*(X+.21),'roof')
    box('Long roof eave fascia',(0,edge,zedge-.025),(2*(X+.25),.085,.15),'wood')
for side in (-1,1):
    for slope in (-1,1):
        y=slope*(Y+.19)
        extrusion('Gable verge board',[(0,RIDGE+.11),(y,EAVE+.04),(y,EAVE-.11),(0,RIDGE-.02)],0,side*(X+.235),.075,'wood')
box('Roof ridge cap',(0,0,RIDGE+.10),(2*(X+.25),.14,.07),'roof')

audit=[]
for o in objects:
    bm=bmesh.new();bm.from_mesh(o.data)
    nonmanifold=sum(not e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True)
    area=min(f.calc_area()for f in bm.faces);bm.free()
    assert nonmanifold==0 and volume>1e-10 and area>1e-12,(o.name,nonmanifold,volume,area)
    audit.append(dict(name=o.name,nonmanifold_edges=nonmanifold,volume=volume,minimum_face_area=area))
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'FreeHomestead.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'FreeHomestead.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
triangles=0
for o in objects:o.data.calc_loop_triangles();triangles+=len(o.data.loop_triangles)
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),atlas_sha256=sha(texture),objects=len(objects),triangles=triangles,materials=1,rigged=False,animations=0,component_audit=audit,limitations=brief['reconstruction']),indent=2)+'\n')
print('FREE_HOMESTEAD_AUTHORED',triangles,flush=True)
