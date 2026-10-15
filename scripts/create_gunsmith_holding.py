"""Local static interpretation of Hull's 1868 Freund shop photograph."""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/gunsmith'
OUT = BASE/'local-source-v004'
BRIEF = BASE/'local-authoring-brief-v001.json'
brief = json.loads(BRIEF.read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(ROOT/brief['photo']) == brief['photo_sha256']
wood_record = brief['material_provenance']
assert sha(ROOT/wood_record['path']) == wood_record['sha256']
assert not OUT.exists()
OUT.mkdir()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
random.seed(1868)

size = 2048
atlas = Image.new('RGBA', (size,size), (237,232,215,255))
wood = Image.open(ROOT/wood_record['path']).convert('RGBA')
for strip in range(12):
    cx = (235,460,700,920,1140,1380,1600,1840)[strip % 8]
    sample = wood.crop((cx-65,700,cx+65,1320))
    atlas.paste(sample.resize((128,size),Image.Resampling.LANCZOS),(strip*128,0))
draw = ImageDraw.Draw(atlas)
regions = {}
signs=[('FREUND & BRO.',4.96,3.92,.64),('GUNS',4.15,1.32,.35),
       ('PISTOLS',3.76,1.32,.35),('AMMUNITION',3.27,1.36,.27)]
for index,(label,_,width,height) in enumerate(signs):
    y = index*256
    texture_height = 496*height/width
    regions[label] = (1544,y+128-texture_height*.5,2040,y+128+texture_height*.5)
    draw.rectangle((1536,y,2047,y+255),fill=(238,232,212,255))
    font_size = 70
    while True:
        font = ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf',font_size)
        bounds = draw.textbbox((0,0),label,font=font)
        if bounds[2]-bounds[0] < 470 and bounds[3]-bounds[1] < texture_height*.75:break
        font_size -= 1
    draw.text((1792-(bounds[2]+bounds[0])*.5,y+128-(bounds[3]+bounds[1])*.5),label,font=font,fill=(20,17,13,255))
for name,y,color in [('glass',1024,(30,48,57,255)),('chinking',1280,(197,183,150,255)),('iron',1536,(42,39,34,255))]:
    draw.rectangle((1536,y,2047,y+255),fill=color)
    regions[name] = (1544,y+8,2040,y+248)
texture = bpy.data.images.new('Gunsmith_BaseColor',size,size,alpha=False)
texture.pixels.foreach_set((np.asarray(atlas,dtype=np.float32)[::-1]/255).ravel())
texture.filepath_raw = str(OUT/'Gunsmith_BaseColor.png')
texture.file_format = 'PNG'
texture.save(); texture.pack()
material = bpy.data.materials.new('M_Gunsmith')
material.use_nodes = True
bsdf = material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value = .78
node = material.node_tree.nodes.new('ShaderNodeTexImage'); node.image = texture
material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
objects = []


def box(name, pos, dims, region=None, bevel=0, rotation=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bpy.context.object; obj.name = name; obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel:
        modifier = obj.modifiers.new('Timber arris','BEVEL')
        modifier.width, modifier.segments = bevel, 1
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.data.materials.append(material)
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new()
    along = max(range(3),key=lambda k:dims[k])
    strip = random.randrange(12)
    for face in obj.data.polygons:
        normal_axis = max(range(3),key=lambda k:abs(face.normal[k]))
        axes = [k for k in range(3) if k != normal_axis]
        for loop in face.loop_indices:
            point = obj.data.vertices[obj.data.loops[loop].vertex_index].co
            if region:
                x0,y0,x1,y1 = regions[region]
                # Sign lettering on front/back uses X/Z, with top image row at +Z.
                a,b = (0,2) if normal_axis == 1 else axes
                u,v = point[a]/dims[a]+.5, point[b]/dims[b]+.5
                uv.data[loop].uv=((x0+u*(x1-x0))/size,1-(y1-v*(y1-y0))/size)
            else:
                across = next(k for k in axes if k != along) if along in axes else axes[0]
                length_axis = along if along in axes else axes[1]
                u = point[across]/dims[across]+.5
                v = point[length_axis]/dims[length_axis]+.5
                uv.data[loop].uv=((strip*128+8+u*112)/size,.02+v*.96)
    if rotation:obj.rotation_euler = rotation
    objects.append(obj)
    return obj


# Front is -Y. Dimensions are compact game reconstruction, not a survey.
box('Closed timber floor',(0,0,.075),(4.1,4.5,.15))
box('Chinking core',(0,0,2.22),(3.98,4.38,4.32),'chinking')
for row in range(22):
    z=.20+row*.194
    for sign in (-1,1):
        box('Hewn side log',(sign*2.015,0,z),(.20,4.50,.177),bevel=.012)
        if row < 21:
            box('Side pale chinking',(sign*2.06,0,z+.097),(.10,4.45,.026),'chinking')
    # Rear wall deliberately has no repeated storefront.
    box('Rear hewn log',(0,2.22,z),(4.13,.18,.177),bevel=.012)
    if row < 21:
        box('Rear pale chinking',(0,2.27,z+.097),(4.10,.08,.026),'chinking')
for sign in (-1,1):
    for y in (-1.15,1.25):
        box('Side vertical brace',(sign*2.14,y,2.2),(.11,.15,4.3),bevel=.006)

openings=[(-1.22,.84,.32,1.96),(0,.86,.13,2.12),(1.22,.84,.32,1.96),
          (-1.22,.82,2.94,4.36),(1.22,.82,2.94,4.36)]
for index in range(25):
    x=-2.04+index*.17
    # Subtract the actual openings, preserving narrow plank strips beside
    # each frame instead of deleting the entire intersecting board width.
    segments=[(x-.0825,x+.0825,.15,5.45)]
    for cx,width,z0,z1 in openings:
        remaining=[]
        for left,right,lo,hi in segments:
            a,b=max(left,cx-width*.5),min(right,cx+width*.5)
            bottom,top=max(lo,z0),min(hi,z1)
            if a>=b or bottom>=top:
                remaining.append((left,right,lo,hi))
            else:
                remaining.extend([(left,right,lo,bottom),(left,right,top,hi),
                                  (left,a,bottom,top),(b,right,bottom,top)])
        segments=[s for s in remaining if s[1]-s[0]>.0001 and s[3]-s[2]>.0001]
    for left,right,lo,hi in segments:
        box('False front vertical board',((left+right)*.5,-2.33,(lo+hi)*.5),(right-left,.10,hi-lo))
for z,height,depth in [(2.47,.17,.15),(5.46,.18,.19),(5.60,.10,.28),(5.67,.06,.33)]:
    box('Facade rail and cornice',(0,-2.37,z),(4.40,depth,height),bevel=.005)

def window(cx,cz,width,height):
    box('Dark window glass',(cx,-2.365,cz),(width,.025,height),'glass')
    for side in (-1,1):
        box('Window jamb',(cx+side*(width+.065)*.5,-2.42,cz),(.09,.10,height+.18))
        box('Window head sill',(cx,-2.43,cz+side*(height+.075)*.5),(width+.19,.12,.09))
    box('Window centre muntin',(cx,-2.405,cz),(.035,.045,height))
    for z in (-height/6,height/6):
        box('Window horizontal muntin',(cx,-2.405,cz+z),(width,.045,.032))
for cx in (-1.22,1.22):
    window(cx,1.14,.78,1.56)
    window(cx,3.65,.76,1.34)
box('Closed wooden door',(0,-2.345,1.13),(.86,.07,2.0))
for side in (-1,1):
    box('Door frame',(side*.475,-2.425,1.13),(.10,.12,2.10))
box('Door lintel',(0,-2.43,2.19),(1.06,.12,.13))
for z in (.66,1.62):
    box('Door inset panel',(0,-2.39,z),(.58,.04,.65),bevel=.004)
box('Door latch',(.31,-2.44,1.08),(.045,.055,.16),'iron',.008)
box('Timber threshold',(0,-2.60,.105),(1.20,.43,.16),bevel=.009)

for label,z,width,height in signs:
    box('Trade sign '+label,(0,-2.46,z),(width,.04,height),label)

# Shingled side-gabled roof, hidden at the front by the tall squared facade.
rise,run=1.0,2.16
angle=math.atan2(rise,run)
slope=math.hypot(rise,run)
for side in (-1,1):
    box('Roof timber substrate',(side*1.08,.05,4.84),(slope+.035,4.80,.05),
        rotation=(0,side*angle,0))
    for row in range(10):
        distance=(row+.5)*slope/10
        x=side*distance*math.cos(angle); z=5.37-distance*math.sin(angle)
        for col in range(18):
            y=-2.225+col*.265
            # Slightly raised butt and pitched overlap avoid coplanar sheets.
            box('Wood roof shingle',(x,y,z+.03),(.285,.263,.027),
                rotation=(0,side*(angle-.065),0))
    box('Eaves fascia',(side*2.17,0,4.34),(.10,4.82,.17))
    box('Reconstructed rear rake trim',(side*1.08,2.40,4.92),(slope+.05,.16,.12),
        rotation=(0,side*angle,0))
box('Roof ridge cap',(0,.05,5.41),(.18,4.84,.06),bevel=.01)
# Trim the rear boards to the roof pitch, rather than letting the rectangular
# upper corners protrude through the shingles as a row of triangular spikes.
for row in range(5):
    height=1.01/5
    z=4.36+(row+.5)*height
    board=box('Rear gable board',(0,2.24,z),(4.32,.10,height))
    for vertex in board.data.vertices:
        fraction=max(.00001,(5.37-(z+vertex.co.z))/1.01)
        vertex.co.x *= fraction

bpy.ops.object.select_all(action='DESELECT')
for obj in objects:obj.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'Gunsmith.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'Gunsmith.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,
                        export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',method='Local static modeling in Mixar, no service call',
    brief_sha256=sha(BRIEF),historical_evidence_sha256=sha(BASE/'historical-evidence.json'),
    photo_sha256=brief['photo_sha256'],project_sha256=sha(project),glb_sha256=sha(glb),
    atlas_sha256=sha(OUT/'Gunsmith_BaseColor.png'),objects=len(objects),materials=1,
    rigged=False,animations=0,unreal_imported=False,material_provenance=wood_record,
    limitations=['Dimensions and rear are reconstruction','Black/white signs and natural timber are not recovered paint hues','Letterforms approximate the period photograph','Setting base and source/native reviews remain']),indent=2)+'\n')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
print('GUNSMITH_AUTHORED',str(glb),flush=True)
