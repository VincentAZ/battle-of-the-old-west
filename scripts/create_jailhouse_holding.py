"""Local static interpretation of Fort Smith's 1888 jail wing, circa 1891-1896.

Evidence and explicit reconstruction choices precede this modeling pass.
"""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/jailhouse'
OUT = BASE/'local-source-v002'
BRIEF = BASE/'local-authoring-brief-v002.json'
brief = json.loads(BRIEF.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert brief['pre_modeling_review']['completed']
assert sha(BASE/brief['sources'][0]['local_photo']) == brief['sources'][0]['sha256']
assert sha(BASE/brief['pre_modeling_review']['archived_pdf']) == brief['pre_modeling_review']['pdf_sha256']
assert not OUT.exists()
OUT.mkdir()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
random.seed(1888)
rng = np.random.default_rng(1888)

# One packed material atlas. Material colours are reconstructed natural values;
# the period postcard supplies architecture, not a recovered colour sample.
atlas = Image.new('RGB',(2048,2048),(112,100,84))
draw = ImageDraw.Draw(atlas)
draw.rectangle((0,0,1535,1535),fill=(139,122,100))
px = 1536/6
course = .075*px
row = 0
while row*course < 1536:
    y0,y1=round(row*course),round((row+1)*course)
    x=-.1075*px if row%2 else 0
    col=0
    while x < 1536:
        width=(.1075 if row%6==5 and col%2==0 else .215)*px
        tone=random.randint(-16,16)
        draw.rectangle((round(x+1),y0+1,round(x+width-1),y1-1),
            fill=(max(0,173+tone),max(0,67+tone//2),max(0,39+tone//3)))
        x+=width;col+=1
    row+=1
regions={'stone':(1544,8,2038,500),'slate':(1544,520,2038,1012),
         'iron':(1544,1032,1780,1268),'glass':(1800,1032,2038,1268),
         'wood':(1544,1290,2038,1528),'foundation':(8,1550,750,2028),
         'doorwood':(800,1570,2038,2028)}
colours={'stone':(191,189,174),'slate':(57,64,69),'iron':(37,36,32),
         'glass':(30,43,48),'wood':(202,195,167),'foundation':(224,216,193),
         'doorwood':(84,52,29)}
for key,region in regions.items():draw.rectangle(region,fill=colours[key])
for x in range(808,2030,3):
    tone=random.randint(-9,9)
    draw.line((x,1578,x+random.randint(-3,3),2020),fill=(84+tone,52+tone//2,29+tone//3))
pixels=np.asarray(atlas).astype(np.int16)
pixels+=rng.integers(-5,6,(2048,2048,1),dtype=np.int16)
atlas=Image.fromarray(np.clip(pixels,0,255).astype(np.uint8))
texture=OUT/'Jailhouse_BaseColor.png';atlas.save(texture)
material=bpy.data.materials.new('M_Jailhouse_Atlas');material.use_nodes=True
bsdf=material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value=.86
node=material.node_tree.nodes.new('ShaderNodeTexImage')
node.image=bpy.data.images.load(str(texture));node.image.pack()
material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
objects=[]

def box(name, location, dimensions, region='brick', rotation=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location)
    o=bpy.context.object;o.name=name;o.dimensions=dimensions
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if rotation:o.rotation_euler=rotation
    o.data.materials.append(material)
    uv=o.data.uv_layers.active
    for face in o.data.polygons:
        normal=max(range(3),key=lambda k:abs(face.normal[k]))
        axes=[k for k in range(3)if k!=normal]
        for loop in face.loop_indices:
            v=o.data.vertices[o.data.loops[loop].vertex_index].co
            if region=='brick':
                a=1 if normal==0 else 0
                u=(v[a]+location[a]+3)/6
                vv=(v.z+location[2])/6 if normal!=2 else (v.y+location[1]+3)/6
                uv.data[loop].uv=(u*.75,1-vv*.75)
            else:
                x0,y0,x1,y1=regions[region];a,b=axes
                u,vv=v[a]/dimensions[a]+.5,v[b]/dimensions[b]+.5
                uv.data[loop].uv=((x0+4+u*(x1-x0-8))/2048,1-(y1-4-vv*(y1-y0-8))/2048)
    objects.append(o)
    return o

def wall(name,axis,side,span,openings):
    # Construct actual openings rather than laying glass on an unbroken wall.
    rectangles=[(-span/2,span/2,.27,3.18)]
    for left,right,bottom,top in openings:
        next_rect=[]
        for a,b,c,d in rectangles:
            lo,hi=max(a,left),min(b,right);z0,z1=max(c,bottom),min(d,top)
            if lo>=hi or z0>=z1:next_rect.append((a,b,c,d));continue
            next_rect.extend([(a,b,c,z0),(a,b,z1,d),(a,lo,z0,z1),(hi,b,z0,z1)])
        rectangles=[r for r in next_rect if r[1]-r[0]>.001 and r[3]-r[2]>.001]
    for a,b,c,d in rectangles:
        if axis==0:box(name,(side,(a+b)/2,(c+d)/2),(.16,b-a,d-c))
        else:box(name,((a+b)/2,side,(c+d)/2),(b-a,.16,d-c))

box('White-painted raised brick foundation',(0,0,.135),(2.8,5.4,.27),'foundation')
box('Grey stone water table',(0,0,.29),(2.91,5.50,.085),'stone')
centres=[-2.175+.87*i for i in range(6)]
openings=[(y-.225,y+.225,.57,2.88)for y in centres]
for side in (-1,1):
    x=side*1.32
    wall('Brick long wall',0,x,5.4,openings)
    for y in centres:
        box('Dark glazed window',(side*1.345,y,1.725),(.018,.45,2.31),'glass')
        for edge in (-1,1):
            for k in range(9):
                width=.106 if k%2==0 else .082
                box('Rough limestone window quoin',(side*1.424,y+edge*(.225+width/2),.57+(k+.5)*2.31/9),
                    (.15,width,2.31/9-.009),'stone')
            box('Stone window lintel or sill',(side*1.42,y,1.725+edge*1.205),(.19,.69,.09),'stone')
        # Triple-hung nine-light sash: three panes wide and nine tall overall.
        for line in (-1,1):
            box('Sash vertical muntin',(side*1.365,y+line*.075,1.725),(.025,.016,2.31),'wood')
        for k in range(1,9):
            box('Sash horizontal rail',(side*1.365,y,.57+k*2.31/9),(.025,.45,.025 if k%3==0 else .014),'wood')
        for line in (-1.5,-.5,.5,1.5):
            box('Iron window bar',(side*1.462,y+line*.10,1.725),(.028,.018,2.31),'iron')
        for z in (.83,1.72,2.62):
            box('Iron bar cross tie',(side*1.466,y,z),(.026,.45,.023),'iron')
    for z,projection,height in [(.40,.05,.045),(.48,.06,.045),(2.98,.04,.05),(3.09,.065,.065),(3.19,.08,.08)]:
        box('Brick corbel band',(side*(1.4+projection/2),0,z),(projection,5.48,height))
    for k in range(32):
        box('Brick cornice modillion',(side*1.449,-2.62+k*.169,3.12),(.10,.07,.13))
    box('Stone eaves cornice',(side*1.44,0,3.27),(.16,5.55,.085),'stone')

# Plain detached end entrance is explicitly reconstructed; no modern vestibule.
# Butt the short walls against the inner faces of the long walls. Extending
# them through the corners produces overlapping coplanar exterior polygons.
wall('Front brick wall',1,-2.62,2.48,[(-.34,.34,.27,1.78)])
wall('Reconstructed closed rear wall',1,2.62,2.48,[])
for plank in range(6):
    box('Reconstructed timber door plank',(-.34+(plank+.5)*.68/6,-2.638,1.015),
        (.68/6-.003,.035,1.49),'doorwood')
for side in (-1,1):
    box('Door stone jamb',(side*.40,-2.718,1.015),(.115,.14,1.49),'stone')
box('Door stone lintel',(0,-2.715,1.84),(.91,.16,.12),'stone')
box('Stone doorstep',(0,-2.76,.125),(.98,.28,.25),'stone')
for z in (.59,1.41):box('Iron door strap',(0,-2.676,z),(.58,.025,.04),'iron')
box('Iron door handle',(.23,-2.69,1.04),(.025,.04,.15),'iron')

# Gable walls behind a slate roof, retaining the photographed parapet silhouette.
run,rise=1.4,.82
angle=math.atan2(rise,run);slope=math.hypot(run,rise)
for end in (-1,1):
    for row in range(12):
        z=3.26+(row+.5)*rise/12
        width=2*run*(1-(z-3.26)/rise)
        o=box('Brick parapet gable',(0,end*2.66,z),(max(width,.03),.14,rise/12))
        for v in o.data.vertices:
            v.co.x*=max(.01,1-v.co.z/(4.08-z))
        # Reproject after shaping the trapezoid so the masonry stays straight.
        o.data.update()
        for face in o.data.polygons:
            normal=max(range(3),key=lambda k:abs(face.normal[k]))
            for loop in face.loop_indices:
                v=o.data.vertices[o.data.loops[loop].vertex_index].co+o.location
                a=1 if normal==0 else 0
                vv=v.z if normal!=2 else v.y+3
                o.data.uv_layers.active.data[loop].uv=((v[a]+3)/8,1-vv/8)
    for side in (-1,1):
        box('Stone sloping gable cap',(side*.71,end*2.68,3.715),(slope+.08,.21,.07),'stone',(0,side*angle,0))
    box('Gable apex stone',(0,end*2.68,4.13),(.13,.23,.16),'stone')
for side in (-1,1):
    box('Roof slate underlay',(side*.70,0,3.67),(slope,5.28,.045),'slate',(0,side*angle,0))
    for row in range(8):
        d=(row+.5)*slope/8
        for col in range(24):
            box('Individual roof slate',(side*d*math.cos(angle),-2.53+col*.22,4.08-d*math.sin(angle)+.035),
                (.235,.218,.025),'slate',(0,side*(angle-.035),0))
box('Roof ridge cover',(0,0,4.105),(.13,5.30,.055),'slate')

def hip_cap(name,x,y,z,w,d,h,region):
    # Four roof slopes meeting a short ridge: no unsupported open roof planes.
    vertices=[(-w/2,-d/2,0),(w/2,-d/2,0),(w/2,d/2,0),(-w/2,d/2,0),(-w*.15,0,h),(w*.15,0,h)]
    faces=[(0,1,5,4),(1,2,5),(2,3,4,5),(3,0,4),(3,2,1,0)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o);o.location=(x,y,z)
    mesh.materials.append(material);uv=mesh.uv_layers.new();x0,y0,x1,y1=regions[region]
    for polygon in mesh.polygons:
        for i,loop in enumerate(polygon.loop_indices):uv.data[loop].uv=((x0+8+(i%2)*(x1-x0-16))/2048,1-(y0+8+(i//2)*(y1-y0-16))/2048)
    objects.append(o)

for side in (-1,1):
    for y in (-1.60,.70):
        x=side*1.17
        box('Square brick chimney',(x,y,3.85),(.22,.25,.73))
        for k in range(3):box('Flared chimney corbel',(x,y,4.20+k*.04),(.24+k*.035,.27+k*.035,.045))
        box('Dark chimney mouth',(x,y,4.305),(.19,.22,.015),'iron')
    x=side*1.20;y=2.39
    box('Junction masonry ventilation tower',(x,y,3.91),(.33,.35,1.13))
    for z in (3.47,4.39):box('Vent tower stone band',(x,y,z),(.38,.40,.065),'stone')
    box('Vent tower dark open throat',(x,y,4.49),(.25,.27,.13),'iron')
    hip_cap('Vent tower metal hood',x,y,4.56,.49,.51,.17,'iron')
for y in (-1.12,1.06):
    box('Ridge ventilator dark core',(0,y,4.24),(.37,.43,.26),'iron')
    for side in (-1,1):
        for z in (4.16,4.22,4.28,4.34):
            box('Louver slat',(side*.20,y,z),(.05,.46,.027),'wood',(0,side*.25,0))
            box('Louver slat',(0,y+side*.235,z),(.39,.05,.027),'wood',(-side*.25,0,0))
        box('Ventilator corner stile',(side*.20,y-.235,4.25),(.045,.045,.29),'wood')
        box('Ventilator corner stile',(side*.20,y+.235,4.25),(.045,.045,.29),'wood')
        box('Italianate support bracket',(side*.23,y,4.37),(.10,.08,.09),'wood',(0,side*.45,0))
    hip_cap('Ridge ventilator hip roof',0,y,4.39,.60,.65,.18,'slate')

bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'Jailhouse.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'Jailhouse.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,
    export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),
    project_sha256=sha(project),glb_sha256=sha(glb),atlas_sha256=sha(texture),objects=len(objects),
    materials=1,rigged=False,animations=0,paid_service_jobs=0,limitations=brief['reconstruction']),indent=2)+'\n')
print('JAILHOUSE_AUTHORED',str(glb),flush=True)
