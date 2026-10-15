"""Locally author a sourced, static expansion notice stand in Mixar.

No service calls, rigs, animation, Unreal import or gameplay changes. The GLB
feeds the existing eight-view holding review pipeline; originals are retained.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import random

import bpy
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/wanted-poster-board'
OUT = BASE/os.environ.get('OLDWEST_WANTED_SOURCE_REVISION','local-source-v004')
EVIDENCE = BASE/'historical-evidence.json'
assert not OUT.exists(), 'Preserve previous source revisions'
evidence = json.loads(EVIDENCE.read_text())
assert evidence['canonical_card_id'] == 'wanted_poster_board' and len(evidence['sources']) == 3
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
OUT.mkdir()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
rng = np.random.default_rng(1881)
random.seed(1881)

# One portable atlas. Use hardware-free wood samples at their original colour;
# the modern photograph is a material analogue, not historical evidence.
size = 2048
provenance=evidence['material_provenance']
wood_path=ROOT/provenance['path']
assert hashlib.sha256(wood_path.read_bytes()).hexdigest()==provenance['sha256']
wood=Image.open(wood_path).convert('RGBA')
atlas=Image.new('RGBA',(size,size),(237,233,217,255))
for strip,cx in enumerate((235,460,700,920,1140,1380,1600,1840)):
    sample=wood.crop((cx-65,700,cx+65,1320))
    atlas.paste(sample.resize((128,size),Image.Resampling.LANCZOS),(strip*128,0))
draw=ImageDraw.Draw(atlas)
font_path='/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf'
body_font=ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf',27)
for sheet in range(3):
    top=size-(sheet+1)*682+25
    for text,y,font_size in [('PROCLAMATION',top+22,78),('REWARDS',top+91,70),('STATE OF MISSOURI',top+188,45)]:
        font=ImageFont.truetype(font_path,font_size)
        box=draw.textbbox((0,0),text,font=font)
        draw.text((1536-(box[2]-box[0])/2,y),text,font=font,fill=(12,9,5,255))
    for y in (top+176,top+248):
        draw.line((1080,y,1990,y),fill=(12,9,5,255),width=3)
    y=top+274
    for paragraph in evidence['reconstructed_print']:
        line=''
        for word in paragraph.split():
            candidate=(line+' '+word).strip()
            if draw.textlength(candidate,font=body_font)>890:
                draw.text((1085,y),line,font=body_font,fill=(12,9,5,255))
                y+=37
                line=word
            else:
                line=candidate
        draw.text((1085,y),line,font=body_font,fill=(12,9,5,255))
        y+=54
    assert y < top+627, 'Printed copy must stay inside the sheet'
pixels=np.asarray(atlas,dtype=np.float32)[::-1]/255
image=bpy.data.images.new('WantedBoard_BaseColor',size,size,alpha=False)
image.pixels.foreach_set(pixels.ravel())
image.filepath_raw=str(OUT/'WantedBoard_BaseColor.png')
image.file_format='PNG'
image.save()
image.pack()
material=bpy.data.materials.new('M_WantedBoard')
material.use_nodes=True
bsdf=material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value=.85
texture=material.node_tree.nodes.new('ShaderNodeTexImage')
texture.image=image
material.node_tree.links.new(texture.outputs['Color'],bsdf.inputs['Base Color'])
objects=[]


def timber_part(name,position,dimensions,horizontal=False):
    bpy.ops.mesh.primitive_cube_add(size=1,location=position)
    obj=bpy.context.object
    obj.name=name
    obj.dimensions=dimensions
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bevel=obj.modifiers.new('Small dressed timber edge','BEVEL')
    bevel.width=.004
    bevel.segments=2
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    obj.data.materials.append(material)
    uv=obj.data.uv_layers.active or obj.data.uv_layers.new()
    strip=random.randrange(8)
    length=dimensions[0] if horizontal else dimensions[2]
    for poly in obj.data.polygons:
        for loop in poly.loop_indices:
            point=obj.data.vertices[obj.data.loops[loop].vertex_index].co
            along=point.x if horizontal else point.z
            across=point.z if horizontal else (point.x if abs(poly.normal.y)>.5 else point.y)
            width=dimensions[2] if horizontal else (dimensions[0] if abs(poly.normal.y)>.5 else dimensions[1])
            uv.data[loop].uv=((strip*128+8+(across/width+.5)*112)/2048, .02+(along/length+.5)*.96)
    objects.append(obj)


# Dimensions are authoring choices, never asserted as surveyed measurements.
for side in (-1,1):
    timber_part('Square_post', (side*1.2,.035,1.27),(.14,.14,2.54))
for z in (1.03,2.30):
    timber_part('Rear_rail',(0,.06,z),(2.52,.10,.12),True)
for i in range(12):
    timber_part('Posting_plank_%02d'%i,(-1.1+i*.2,0,1.69),(.197,.035,1.49))
for sheet,cx in enumerate((-.77,0,.77)):
    vertices=[]
    faces=[]
    nx,nz=16,20
    for j in range(nz+1):
        for i in range(nx+1):
            x=(i/nx-.5)*.65+cx
            z=(j/nz-.5)*.99+1.72+(0,.05,-.025)[sheet]
            edge=max(abs(i/nx-.5)*2,abs(j/nz-.5)*2)
            y=-.019-edge**10*.003
            vertices.append((x,y,z))
    for j in range(nz):
        for i in range(nx):
            a=j*(nx+1)+i
            faces.append((a,a+1,a+nx+2,a+nx+1))
    mesh=bpy.data.meshes.new('Pasted_bill')
    mesh.from_pydata(vertices,[],faces)
    mesh.materials.append(material)
    uv=mesh.uv_layers.new()
    for loop in mesh.loops:
        j,i=divmod(loop.vertex_index,nx+1)
        uv.data[loop.index].uv=(.506+i/nx*.488,(sheet*682+10+j/nz*662)/2048)
    obj=bpy.data.objects.new('Pasted_bill_%d'%sheet,mesh)
    bpy.context.collection.objects.link(obj)
    solid=obj.modifiers.new('Paper thickness','SOLIDIFY')
    solid.thickness=.0003
    objects.append(obj)
bpy.ops.object.select_all(action='DESELECT')
for obj in objects:
    obj.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'WantedPosterBoard.blend'))
glb=OUT/'WantedPosterBoard.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,
    export_apply=True,export_animations=False,export_materials='EXPORT')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',
    method='Local procedural mesh and material authoring in Mixar; no external service',
    research_sha256=sha(EVIDENCE),project_sha256=sha(OUT/'WantedPosterBoard.blend'),
    glb_sha256=sha(glb),atlas_sha256=sha(OUT/'WantedBoard_BaseColor.png'),
    unrigged=True,animations=0,unreal_imported=False,material_provenance=provenance,
    printed_copy=evidence['reconstructed_print'],
    reconstructed=['Exact stand dimensions and joinery','Unpainted timber and fresh paper colour','Historical headings with explicitly reconstructed serif paragraphs'],
    documented=['1881 Missouri reward-broadside typography','1871 carpenter-built lumber billboards and pasted bills']),indent=2)+'\n')
print('WANTED_POSTER_BOARD_AUTHORED',str(glb),flush=True)
