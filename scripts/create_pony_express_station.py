"""Static station reconstruction from the pinned Simpson Springs references."""
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
BASE = ROOT/'art/western/holdings/expansion-review-v001/pony-express-station'
OUT = BASE/'local-source-v003'
BRIEF = BASE/'local-authoring-brief-v003.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
for path, digest in brief['source_records'].items():
    assert sha(BASE/path) == digest, path
assert not OUT.exists(), 'Preserve previous source revisions'
OUT.mkdir()
bpy.ops.wm.read_factory_settings(use_empty=True)
random.seed(1890)
atlas = Image.new('RGB', (2048,2048))
draw = ImageDraw.Draw(atlas)
colours = {'stone0':(71,57,44), 'stone1':(85,77,67), 'stone2':(62,60,55),
           'stone3':(102,78,55), 'stone4':(111,104,89), 'mortar':(184,168,141),
           'wood':(137,87,44), 'darkwood':(74,47,28), 'shingle':(150,108,67),
           'recess':(25,25,21), 'iron':(37,34,29), 'endgrain':(130,87,48)}
regions = {}
for index,(key,colour) in enumerate(colours.items()):
    x0,y0 = (index%4)*512+8,(index//4)*682+8
    rect = (x0,y0,x0+496,y0+658); regions[key]=rect
    draw.rectangle(rect,fill=colour)
    if key in ('wood','darkwood','shingle','endgrain'):
        for x in range(x0+3,x0+491,4):
            t=random.randint(-18,18)
            draw.line([(x+math.sin(y*.035+x)*1.8,y) for y in range(y0+3,y0+652,9)],
                      fill=tuple(max(0,c+t) for c in colour),width=1)
    elif key.startswith('stone'):
        for i in range(1600):
            x,y=random.randrange(x0,x0+492),random.randrange(y0,y0+654)
            t=random.randint(-15,18)
            draw.ellipse((x,y,x+random.randint(1,5),y+random.randint(1,5)),
                         fill=tuple(max(0,c+t) for c in colour))
rng=np.random.default_rng(1890)
pixels=np.asarray(atlas).astype(np.int16)+rng.integers(-4,5,(2048,2048,1),dtype=np.int16)
texture=OUT/'PonyExpressStation_BaseColor.png'
Image.fromarray(np.clip(pixels,0,255).astype(np.uint8)).save(texture)
material=bpy.data.materials.new('M_PonyExpressStation_Atlas');material.use_nodes=True
bsdf=material.node_tree.nodes['Principled BSDF'];bsdf.inputs['Roughness'].default_value=.86
node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack()
material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
objects=[]


def solid(name,vertices,faces,region):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o)
    mesh.materials.append(material)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free()
    uv=mesh.uv_layers.new();x0,y0,x1,y1=regions[region]
    for face in mesh.polygons:
        axis=max(range(3),key=lambda k:abs(face.normal[k]));a,b=[k for k in range(3) if k!=axis]
        points=[mesh.vertices[i].co for i in face.vertices]
        low=[min(v[k] for v in points) for k in range(3)]
        high=[max(v[k] for v in points) for k in range(3)]
        for loop in face.loop_indices:
            v=mesh.vertices[mesh.loops[loop].vertex_index].co
            u=(v[a]-low[a])/max(1.e-6,high[a]-low[a]);w=(v[b]-low[b])/max(1.e-6,high[b]-low[b])
            uv.data[loop].uv=((x0+5+u*(x1-x0-10))/2048,1-(y1-5-w*(y1-y0-10))/2048)
    objects.append(o)
    return o


def box(name,centre,size,region):
    x,y,z=centre;a,b,c=[v/2 for v in size]
    return solid(name,[(x+u*a,y+v*b,z+w*c) for u,v,w in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]],
                 [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],region)


def extrusion(name,polygon,axis,plane,depth,region):
    other=[k for k in range(3) if k!=axis];vertices=[]
    for side in (-1,1):
        for a,b in polygon:
            v=[0,0,0];v[axis]=plane+side*depth/2;v[other[0]]=a;v[other[1]]=b;vertices.append(v)
    n=len(polygon)
    return solid(name,vertices,[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+
                 [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],region)


def facade_box(name,axis,plane,u,z,width,depth,height,region):
    return box(name,(plane,u,z) if axis==0 else (u,plane,z),
               (depth,width,height) if axis==0 else (width,depth,height),region)


def subtract(rectangles,openings):
    for left,right,bottom,top in openings:
        remaining=[]
        for a,b,c,d in rectangles:
            lo,hi=max(a,left),min(b,right);z0,z1=max(c,bottom),min(d,top)
            if lo>=hi or z0>=z1:
                remaining.append((a,b,c,d));continue
            remaining.extend([(a,b,c,z0),(a,b,z1,d),(a,lo,z0,z1),(hi,b,z0,z1)])
        rectangles=[r for r in remaining if r[1]-r[0]>.004 and r[3]-r[2]>.004]
    return rectangles


def stones(axis,plane,side,low,high,height,openings=(),gable=False):
    """Shallow irregular stones embedded into solid mortar wall sections."""
    z=0
    while z<height-.025:
        h=min(random.uniform(.11,.20),height-z)
        u=low
        while u<high-.025:
            w=min(random.uniform(.17,.36),high-u)
            for a,b,c,d in subtract([(u+.008,u+w-.008,z+.008,z+h-.008)],openings):
                if d-c<.025 or b-a<.025:continue
                dx=(b-a)*random.uniform(.12,.30);dz=(d-c)*random.uniform(.13,.30)
                poly=[(a+dx,c),(b-dx*.7,c+dz*.1),(b,c+dz),
                      (b-dx*random.uniform(.2,1),d),(a+dx*.3,d-dz*.1),(a,d-dz)]
                if random.random()<.5:poly=[(a+b-u,z) for u,z in reversed(poly)]
                if random.random()<.5:poly=[(u,c+d-z) for u,z in reversed(poly)]
                if gable:
                    # Clip the polygon, rather than discarding a triangular roof-edge wedge.
                    for slope in (-1/1.9,1/1.9):
                        clipped=[]
                        for i,p in enumerate(poly):
                            q=poly[(i+1)%len(poly)]
                            fp=p[1]-(3.044+slope*p[0]);fq=q[1]-(3.044+slope*q[0])
                            if fp<=0:clipped.append(p)
                            if (fp<=0)!=(fq<=0):
                                t=fp/(fp-fq);clipped.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
                        poly=clipped
                        if len(poly)<3:break
                if len(poly)<3:continue
                other=[k for k in range(3) if k!=axis];vertices=[]
                for depth in (-.018,.012):
                    for pu,pz in poly:
                        v=[0,0,0];v[axis]=plane+side*depth;v[other[0]]=pu;v[other[1]]=pz;vertices.append(v)
                n=len(poly);centre=[sum(v[k] for v in vertices[n:])/n for k in range(3)]
                centre[axis]+=side*random.uniform(.001,.005);vertices.append(centre)
                faces=[tuple(range(n-1,-1,-1))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
                faces += [(n+i,n+(i+1)%n,2*n) for i in range(n)]
                solid('Small faceted rubble face',vertices,faces,
                      'stone'+str(random.choices(range(5),weights=[3,3,3,2,1])[0]))
            u+=w
        z+=h


# Long axis Y; front entrance faces -Y. All dimensions are disclosed reconstruction.
width,length,eaves,ridge=3.8,5.5,2.05,3.05
door=(-.46,.46,0,1.82)
window=(.75,1.29,1.23,1.75)
for axis,plane,side,low,high,openings in [
    (1,-2.59,-1,-1.9,1.9,[door]),(1,2.59,1,-1.9,1.9,[]),
    (0,-1.74,-1,-2.43,2.43,[window]),(0,1.74,1,-2.43,2.43,[])]:
    for a,b,c,d in subtract([(low,high,0,eaves)],openings):
        facade_box('Solid mortar wall',axis,plane,(a+b)/2,(c+d)/2,b-a,.32,d-c,'mortar')
    surface=plane+side*.16
    stones(axis,surface,side,-2.75 if axis==0 else low,2.75 if axis==0 else high,eaves,openings)
for y,side in [(-2.59,-1),(2.59,1)]:
    extrusion('Closed stone gable',[(-1.9,eaves),(1.9,eaves),(0,ridge)],1,y,.32,'mortar')
    # Gable-only stone courses; openings below the eaves prevent duplicate faces.
    stones(1,y+side*.16,side,-1.9,1.9,ridge,[(-2,2,0,eaves)],True)

# Recessed plain door: no modern plaque, company mark or historical hardware claim.
for i in range(5):
    x=-.437+i*.175
    box('Plain vertical door plank',(x+.087,-2.685,.902),(.17,.07,1.804),'darkwood')
for x in (-.50,.50):box('Door timber jamb',(x,-2.76,.94),(.095,.10,1.88),'wood')
box('Door timber lintel',(0,-2.76,1.875),(1.095,.11,.11),'wood')
box('Door threshold',(0,-2.73,.024),(.92,.27,.048),'endgrain')
box('Plain iron latch',(.31,-2.731,.91),(.105,.025,.028),'iron')

# Small side opening, deeply recessed dark interior and plain timber frame.
box('Dark side-window recess',(-1.765,1.02,1.49),(.025,.54,.52),'recess')
for y in (.715,1.325):box('Window jamb',(-1.921,y,1.49),(.115,.07,.66),'wood')
for z in (1.195,1.785):box('Window sill or lintel',(-1.93,1.02,z),(.14,.68,.085),'wood')

# Two complete wood roof planes with short eaves and individually lapped shingles.
slope=1/1.9
for side in (-1,1):
    x0,x1=0,side*2.09
    z0,z1=ridge+.035,ridge+.035-2.09*slope
    poly=[(x0,z0),(x1,z1),(x1,z1-.065),(x0,z0-.065)]
    extrusion('Solid pitched roof deck',poly,1,0,5.84,'darkwood')
    # Place rows from eaves to ridge; the upper row laps the top of its neighbour.
    for row in range(10):
        outer=2.09-row*(2.09/10);inner=max(0,outer-.265)
        y=-2.92
        while y<2.91:
            span=min(random.uniform(.19,.29),2.92-y)
            if span<.01:break
            layer=.008+row*.001
            polygon=[(side*outer,ridge+.055-outer*slope+layer),
                     (side*inner,ridge+.055-inner*slope+layer),
                     (side*inner,ridge+.039-inner*slope+layer),
                     (side*outer,ridge+.039-outer*slope+layer)]
            extrusion('Lapped wood shingle',polygon,1,y+span/2,span-.006,'shingle')
            y+=span
    for y in (-2.92,2.92):
        a,b=Vector((0,y,ridge+.035)),Vector((side*2.10,y,ridge+.035-2.10*slope))
        o=box('Gable verge timber',(0,0,0),(.10,.10,(b-a).length),'wood')
        o.location=(a+b)/2;o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler()
    box('Short eave fascia',(side*2.08,0,z1-.02),(.07,5.92,.12),'wood')
box('Plain ridge cap',(0,0,ridge+.074),(.15,5.94,.055),'wood')
for y in (-2.95,2.95):
    box('Closed ridge timber end',(0,y,ridge+.052),(.17,.075,.105),'endgrain')

audit=[]
for o in objects:
    bm=bmesh.new();bm.from_mesh(o.data)
    edges=sum(not e.is_manifold for e in bm.edges);volume=bm.calc_volume(signed=True)
    area=min(f.calc_area() for f in bm.faces);bm.free()
    assert edges==0 and volume>1.e-10 and area>1.e-12,(o.name,edges,volume,area)
    audit.append(dict(name=o.name,nonmanifold_edges=edges,volume=volume,minimum_face_area=area))
bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'PonyExpressStation.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'PonyExpressStation.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,
                          export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
triangles=0
for o in objects:o.data.calc_loop_triangles();triangles+=len(o.data.loop_triangles)
assert triangles<=30000,triangles
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',
    brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),atlas_sha256=sha(texture),
    objects=len(objects),triangles=triangles,materials=1,rigged=False,animations=0,
    component_audit=audit,limitations=brief['reconstruction']),indent=2)+'\n')
print('PONY_EXPRESS_STATION_AUTHORED',triangles,flush=True)
