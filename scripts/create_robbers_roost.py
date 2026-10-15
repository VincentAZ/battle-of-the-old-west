"""Static stockade-method cabin; historical brief must precede authoring."""
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
BASE = ROOT / 'art/western/holdings/expansion-review-v001/robbers-roost'
OUT = BASE / 'local-source-v002'
BRIEF = BASE / 'local-brief-v002.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
assert sha(BASE/'historical-evidence.json') == brief['historical_evidence_sha256']
assert sha(BASE/'reference-review-v001.json') == brief['reference_review_sha256']
for path, digest in json.loads((BASE/'reference-review-v001.json').read_text())['references'].items():
    assert sha(ROOT/path) == digest, path
assert not OUT.exists()
OUT.mkdir()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
random.seed(1897)
rng = np.random.default_rng(1897)

# One atlas. Bark streaks run vertically in texture space and along each pole.
# Gray-brown exterior and warm exposed fibres are natural juniper, never paint.
atlas = Image.new('RGB', (2048, 2048), (125, 88, 56))
draw = ImageDraw.Draw(atlas)
regions = {'bark': (8,8,1016,2038), 'roof': (1040,8,2038,1510),
           'cut': (1040,1534,1530,2038), 'split': (1552,1534,2038,2038)}
for key in ('bark','roof','split'):
    x0,y0,x1,y1=regions[key]
    base=(143,123,100) if key=='bark' else (122,92,64) if key=='roof' else (157,112,68)
    draw.rectangle((x0,y0,x1,y1),fill=base)
    for x in range(x0+10,x1-20,37 if key!='split' else 70):
        width=random.randint(9,24);phase=random.random()*6
        points=[(x+math.sin(y*.009+phase)*9+math.sin(y*.003+phase)*13,y)for y in range(y0+4,y1-4,8)]
        draw.line(points,fill=(62,43,29),width=width)
        draw.line([(px-width*.55,py)for px,py in points],fill=(177,147,111),width=max(2,width//4))
    for x in range(x0+2,x1-2,3):
        warm=random.random()<.25
        tone=random.randint(-25,25)
        color=(147+tone,91+tone//2,48+tone//3) if warm else tuple(max(0,min(255,c+tone)) for c in base)
        points=[(x+math.sin(y*.017+x)*2+math.sin(y*.004+x)*2,y) for y in range(y0+2,y1-1,12)]
        draw.line(points,fill=color,width=1)
    for _ in range(115):
        x=random.randint(x0+8,x1-8);y=random.randint(y0+8,y1-30)
        draw.line([(x,y),(x+2,y+14),(x+1,min(y1-5,y+random.randint(25,150)))],fill=(59,40,25),width=1)
x0,y0,x1,y1=regions['cut']
cut=Image.new('RGB',(x1-x0,y1-y0),(176,131,80))
cut_draw=ImageDraw.Draw(cut)
for radius in range(12,350,9):
    cut_draw.ellipse((245-radius,252-radius,245+radius,252+radius),outline=(143,98,55),width=2)
atlas.paste(cut,(x0,y0))
pixels=np.asarray(atlas).astype(np.int16)+rng.integers(-3,4,(2048,2048,1),dtype=np.int16)
texture=OUT/'RobbersRoost_BaseColor.png'
Image.fromarray(np.clip(pixels,0,255).astype(np.uint8)).save(texture)
material=bpy.data.materials.new('M_RobbersRoost_Atlas');material.use_nodes=True
bsdf=material.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.92
node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack()
material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
objects=[]


def solid(name, vertices, faces, uvs, regions_per_face):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    ob=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(ob)
    mesh.materials.append(material)
    uv=mesh.uv_layers.new()
    for poly,coords,region in zip(mesh.polygons,uvs,regions_per_face):
        x0,y0,x1,y1=regions[region]
        for loop,(u,v) in zip(poly.loop_indices,coords):
            uv.data[loop].uv=((x0+5+u*(x1-x0-10))/2048,1-(y1-5-v*(y1-y0-10))/2048)
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    objects.append(ob)
    return ob


def pole(name, start, end, radius, region='bark', sides=12, wobble=.009):
    a,b=Vector(start),Vector(end);axis=(b-a).normalized()
    u=axis.cross(Vector((0,1,0)) if abs(axis.y)<.9 else Vector((1,0,0))).normalized()
    v=axis.cross(u).normalized();verts=[]
    phase=random.random()*math.tau
    radii=[radius*random.uniform(.84,1.18) for _ in range(sides)]
    uv_shift=random.uniform(0,.25)
    bend=Vector((random.uniform(-wobble,wobble),random.uniform(-wobble,wobble),0))
    for ring in range(4):
        t=ring/3;centre=a.lerp(b,t)+u*(math.sin(t*math.pi)*wobble)+v*(math.sin(t*math.tau)*wobble*.5)+bend*t
        for i in range(sides):
            angle=i*math.tau/sides+phase
            r=radii[i]*(1-.06*t)
            verts.append(tuple(centre+(u*math.cos(angle)+v*math.sin(angle))*r))
    faces=[];uvs=[];mats=[]
    for ring in range(3):
        for i in range(sides):
            j=(i+1)%sides
            faces.append((ring*sides+i,ring*sides+j,(ring+1)*sides+j,(ring+1)*sides+i))
            uvs.append(((i/sides,uv_shift+.7*ring/3),((i+1)/sides,uv_shift+.7*ring/3),((i+1)/sides,uv_shift+.7*(ring+1)/3),(i/sides,uv_shift+.7*(ring+1)/3)))
            mats.append(region)
    for ring in (0,3):
        faces.append(tuple(ring*sides+i for i in range(sides)))
        uvs.append(tuple((.5+.45*math.cos(i*math.tau/sides),.5+.45*math.sin(i*math.tau/sides))for i in range(sides)))
        mats.append('cut')
    return solid(name,verts,faces,uvs,mats)


def slab(name, polygon, thickness, region):
    # Polygon in world coordinates; closed underside offset vertically.
    n=len(polygon);verts=polygon+[(x,y,z-thickness)for x,y,z in polygon]
    faces=[tuple(range(n)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n)for i in range(n)]
    lo=[min(v[k]for v in polygon)for k in (0,1,2)]
    hi=[max(v[k]for v in polygon)for k in (0,1,2)]
    uv=[]
    for face in faces:
        uv.append(tuple(((verts[i][0]-lo[0])/max(.001,hi[0]-lo[0]),(verts[i][1]-lo[1])/max(.001,hi[1]-lo[1]))for i in face))
    return solid(name,verts,faces,uv,[region]*len(faces))


def box(name,centre,size,region='split'):
    x,y,z=centre;a,b,c=[s/2 for s in size]
    verts=[(x+u*a,y+v*b,z+w*c)for u,v,w in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    uv=[]
    along=0 if size[0]>size[2] else 2
    across=2 if along==0 else 0
    for face in faces:
        uv.append(tuple(((verts[i][across]-centre[across])/size[across]+.5,(verts[i][along]-centre[along])/size[along]+.5)for i in face))
    return solid(name,verts,faces,uv,[region]*6)


X,Y,EAVE,RIDGE=1.90,1.60,2.20,2.95
pitch=(RIDGE-EAVE)/X
door_low,door_high=-.64,.29
# Slight irregularity in tightly set posts; no horizontal notched-log courses.
for y in (-Y,Y):
    count=25;step=2*X/count
    for i in range(count+1):
        x=-X+i*step;top=RIDGE-abs(x)*pitch-.095
        if y<0 and door_low-.02<x<door_high+.02:
            pole('Stockade over entrance',(x,y,1.98),(x,y,top),.084,wobble=.003)
        else:
            pole('Upright gable wall post',(x,y,0),(x,y,top),.091*random.uniform(.97,1.08),wobble=.026)
for x in (-X,X):
    for i in range(1,21):
        y=-Y+i*(2*Y/21)
        pole('Upright side wall post',(x,y,0),(x,y,EAVE-.095),.091*random.uniform(.97,1.08),wobble=.026)
# Load-bearing wall plates, ridge and rafters remain visibly round poles.
for x in (-X,X):pole('Side wall plate',(x,-Y-.10,EAVE-.075),(x,Y+.10,EAVE-.075),.095,wobble=.003)
pole('Ridge support pole',(0,-Y-.18,RIDGE-.10),(0,Y+.18,RIDGE-.10),.10,wobble=.003)
for y in (-Y+.11,0,Y-.11):
    for sign in (-1,1):pole('Roof supporting rafter',(0,y,RIDGE-.10),(sign*(X+.18),y,EAVE-.17),.080,wobble=.002)
# Closely spaced smaller roof poles run down the pitch beneath the bark.
for j in range(32):
    y=-Y-.18+j*(2*(Y+.18)/31)
    for sign in (-1,1):
        pole('Small roof pole',(sign*.005,y,RIDGE-.005),(sign*(X+.20),y,EAVE-.08),.060,sides=8,wobble=.003)
# Fibrous sheets: staggered irregular broad strips, not a shingle grid.
# The sheet's longitudinal texture axis follows the roof slope (world X).
for sign in (-1,1):
    for j in range(25):
        y0=-Y-.23+j*(2*(Y+.23)/25);y1=y0+.19+random.uniform(-.014,.014)
        ridge=.008+random.uniform(-.003,.003);edge=X+.25+random.uniform(-.018,.018)
        # Three columns by eight rows create uneven fibrous relief; closed underside.
        verts=[];rows=8;cols=3
        for k in range(rows):
            x=ridge+(edge-ridge)*k/(rows-1)
            for c in range(cols):
                y=y0+(y1-y0)*c/(cols-1)+random.uniform(-.017,.017)
                z=RIDGE+.064-x*pitch+random.uniform(-.008,.009)+(.020 if c==1 else 0)
                verts.append((sign*x,y,z))
        count=len(verts);verts += [(x,y,z-.029)for x,y,z in verts]
        faces=[]
        for k in range(rows-1):
            for c in range(cols-1):
                a=k*cols+c;b=a+1;d=(k+1)*cols+c;e=d+1
                faces.extend([(a,b,e,d),(a+count,d+count,e+count,b+count)])
        perimeter=list(range(cols))+[k*cols+cols-1 for k in range(1,rows)]+list(range((rows-1)*cols+cols-2,(rows-1)*cols-1,-1))+[k*cols for k in range(rows-2,0,-1)]
        for i,a in enumerate(perimeter):
            b=perimeter[(i+1)%len(perimeter)];faces.append((a,b,b+count,a+count))
        uvs=[tuple(((verts[i][1]-y0)/(y1-y0+.04),abs(verts[i][0])/edge)for i in face)for face in faces]
        ob=solid('Uneven fibrous roof bark',verts,faces,uvs,['roof']*len(faces))
        # Longitudinal fibres follow the roof slope, with no normal-map dependency.
        x0,y0t,x1,y1t=regions['roof']
        for poly in ob.data.polygons:
            for loop in poly.loop_indices:
                co=ob.data.vertices[ob.data.loops[loop].vertex_index].co
                u=(co.y-y0)/(y1-y0+.01);v=abs(co.x)/edge
                ob.data.uv_layers.active.data[loop].uv=((x0+5+max(0,min(1,u))*(x1-x0-10))/2048,1-(y1t-5-v*(y1t-y0t-10))/2048)
# Bark folds over ridge, independently closed pieces, no metal ridge cap.
for j in range(15):
    y=-Y-.23+j*(2*(Y+.23)/15)
    for sign in (-1,1):
        slab('Bark ridge fold',[(0,y,RIDGE+.095),(sign*.20,y-.008,RIDGE+.021),(sign*.20,y+.28,RIDGE+.021),(0,y+.29,RIDGE+.095)],.032,'roof')
# Reconstructed plain entrance. Door is recessed behind irregular jamb posts.
for x in (door_low-.025,door_high+.025):pole('Doorway jamb',(x,-Y-.015,0),(x,-Y-.015,2.035),.079,region='split',wobble=0)
pole('Doorway lintel',(door_low-.10,-Y-.02,2.00),(door_high+.10,-Y-.02,2.00),.079,region='split',wobble=0)
for i in range(6):
    width=(door_high-door_low-.06)/6
    box('Reconstructed split-wood door',(door_low+.03+(i+.5)*width,-Y+.035,.976),(width-.003,.072,1.91))
for z in (.38,1.60):box('Door transverse wooden batten',((door_low+door_high)/2,-Y-.013,z),(.86,.045,.09))
box('Plain wooden latch',(door_high-.13,-Y-.052,1.02),(.14,.045,.055))

audit=[]
for ob in objects:
    bm=bmesh.new();bm.from_mesh(ob.data)
    nm=sum(not e.is_manifold for e in bm.edges);vol=bm.calc_volume(signed=True);area=min(f.calc_area()for f in bm.faces);bm.free()
    assert nm==0 and vol>1e-10 and area>1e-12,(ob.name,nm,vol,area)
    audit.append({'name':ob.name,'nonmanifold_edges':nm,'volume':vol,'minimum_face_area':area})
bpy.ops.object.select_all(action='DESELECT')
for ob in objects:ob.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'RobbersRoost.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'RobbersRoost.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
triangles=0
for ob in objects:ob.data.calc_loop_triangles();triangles+=len(ob.data.loop_triangles)
assert triangles<=30000
(OUT/'authoring.json').write_text(json.dumps({'status':'authored_unreviewed','brief_sha256':sha(BRIEF),'project_sha256':sha(project),'glb_sha256':sha(glb),'atlas_sha256':sha(texture),'objects':len(objects),'triangles':triangles,'materials':1,'rigged':False,'animations':0,'component_audit':audit,'limitations':brief['reconstruction']},indent=2)+'\n')
print('ROBBERS_ROOST_AUTHORED',triangles,flush=True)
