"""Author the sourced, static Army Surgeon's Tent reconstruction in local Mixar."""
import hashlib
import json
import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/western/holdings/expansion-review-v001/army-surgeons-tent'
OUT=BASE/'local-source-v001'
BRIEF=BASE/'local-authoring-brief-v001.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text())
assert brief['pre_modeling_review']['completed']
assert all(sha(BASE/s['local_photo'])==s['sha256'] for s in brief['sources'])
assert sha(BASE/'historical-evidence.json')==brief['historical_brief_sha256']
assert not OUT.exists()
OUT.mkdir()
bpy.ops.wm.read_factory_settings(use_empty=True)
rng=np.random.default_rng(1864)
pixels=np.empty((2048,2048,3),dtype=np.int16)
pixels[:]=[235,231,215]
yy,xx=np.indices((2048,2048))
grain=((xx%4==0).astype(float)-(yy%4==0).astype(float))*2
grain+=rng.integers(-3,4,(2048,2048))
pixels+=grain[:,:,None].astype(np.int16)
pixels[:1000,1536:]=np.array([111,72,36])+rng.integers(-10,11,(1000,512,1))
pixels[1024:,1536:]=np.array([162,127,77])+rng.integers(-6,7,(1024,512,1))
for x in range(1540,2044,5):pixels[:1000,x:x+1]-=13
texture=OUT/'ArmySurgeonsTent_BaseColor.png'
Image.fromarray(np.clip(pixels,0,255).astype(np.uint8)).save(texture)
material=bpy.data.materials.new('M_ArmySurgeonsTent_Atlas');material.use_nodes=True
bsdf=material.node_tree.nodes['Principled BSDF'];bsdf.inputs['Roughness'].default_value=.86
tex=material.node_tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(texture));tex.image.pack()
material.node_tree.links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
regions={'canvas':(.006,.008,.742,.992),'wood':(.758,.518,.992,.992),'rope':(.758,.008,.992,.49)}
objects=[]


def finish(obj,region='canvas',uvs=None):
    obj.data.materials.append(material)
    layer=obj.data.uv_layers.active or obj.data.uv_layers.new()
    a,b,c,d=regions[region]
    for face in obj.data.polygons:
        face.use_smooth=True
        for loop in face.loop_indices:
            if uvs is not None:u,v=uvs[obj.data.loops[loop].vertex_index]
            else:u,v=layer.data[loop].uv
            layer.data[loop].uv=(a+u*(c-a),b+v*(d-b))
    objects.append(obj)
    return obj


def fabric(name,point,nu,nv):
    vertices=[];uvs=[]
    for j in range(nv+1):
        for i in range(nu+1):
            u,v=i/nu,j/nv;vertices.append(point(u,v));uvs.append((u,v))
    faces=[]
    for j in range(nv):
        for i in range(nu):
            k=j*(nu+1)+i;faces.append((k,k+1,k+nu+2,k+nu+1))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);finish(obj,uvs=uvs)
    bpy.context.view_layer.objects.active=obj
    mod=obj.modifiers.new('Actual canvas thickness','SOLIDIFY');mod.thickness=.006;mod.offset=0
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def rod(name,a,b,radius,region='wood',sides=10):
    a,b=Vector(a),Vector(b);axis=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=sides,radius=radius,depth=axis.length,location=(a+b)/2)
    obj=bpy.context.object;obj.name=name;obj.rotation_euler=axis.to_track_quat('Z','Y').to_euler()
    return finish(obj,region)


def line(name,points,radius=.009,region='canvas'):
    curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D';curve.resolution_u=1
    curve.bevel_depth=radius;curve.bevel_resolution=1;curve.resolution_u=1
    spline=curve.splines.new('POLY');spline.points.add(len(points)-1)
    for p,co in zip(spline.points,points):p.co=(*co,1)
    obj=bpy.data.objects.new(name,curve);bpy.context.collection.objects.link(obj)
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.ops.object.convert(target='MESH');obj=bpy.context.object
    # Rope/hem colour needs no directional UV claims; assign a small atlas patch.
    return finish(obj,region,[(.4,.5) for _ in obj.data.vertices])


for side in (-1,1):
    def wall(u,v,side=side):
        y=-2.1+4.2*u;z=.025+1.675*v
        bow=.026*math.sin(math.pi*v)*math.sin(math.pi*u)
        fold=.013*math.sin(u*math.pi*16)*math.sin(math.pi*v)
        return (side*(1.65-bow+fold),y,z)
    fabric('Closed canvas side',wall,36,12)
    for v in (0,1):line('Side hem',[wall(i/36,v) for i in range(37)],.012)
    for u in (.25,.5,.75):line('Side sewn overlap',[wall(u,i/12) for i in range(13)],.006)
    for fly in (False,True):
        run,half_y,ridge,eave=(1.88,2.30,3.57,1.65) if fly else (1.65,2.10,3.42,1.70)
        def roof(u,v,side=side,run=run,half_y=half_y,ridge=ridge,eave=eave):
            x=side*run*u;y=(2*v-1)*half_y
            sag=.021*math.sin(math.pi*u)*math.sin(math.pi*v)
            fold=.009*math.sin(v*math.pi*16)*math.sin(math.pi*u)
            return x,y,ridge-(ridge-eave)*u-sag+fold
        fabric('Separate canvas fly' if fly else 'Inner tent roof',roof,18,32)
        if fly:
            for v in (0,1):line('Fly end hem',[roof(i/18,v) for i in range(19)],.014)
            line('Fly eave hem',[roof(1,i/32) for i in range(33)],.014)
            for v in (.25,.5,.75):line('Fly sewn overlap',[roof(i/18,v) for i in range(19)],.006)
    def flap(u,v,side=side):
        z=.025+3.375*v
        outer=min(1.65,(3.42-z)*1.65/1.72)
        inner=min(outer*.72,.95*(1-(z/3.42)**2))
        x=side*(inner+(outer-inner)*u)
        y=-2.10-.06*math.sin(math.pi*u)*math.sin(math.pi*v)
        y+=.014*math.sin(u*math.pi*8)*math.sin(math.pi*v)
        return x,y,z
    fabric('Swept open front flap',flap,12,28)
    for u in (0,1):line('Front flap hem',[flap(u,i/28) for i in range(29)],.012)
    # Small cloth tie-back, with no modern buckle or invented metal hardware.
    p=flap(.8,.30);line('Plain flap tie',[p,(side*1.65,-2.13,1.08),(side*1.57,-2.17,1.04)],.011,'rope')
    for y in (-2.10,-1.05,0,1.05,2.10):
        anchor=(side*2.64,y,.19)
        rod('Wood guy peg',(side*2.59,y,0),(side*2.67,y,.30),.024)
        line('Taut fly guy',[(side*1.88,y,1.65),anchor],.011,'rope')

fabric('Closed rear wall',lambda u,v:((2*u-1)*1.65,2.1,.025+1.675*v),28,12)
# Rear triangle uses a single apex, avoiding degenerate collapsed grid faces.
verts=[];uvs=[];faces=[];cols=24;rows=14
for j in range(rows):
    v=j/rows
    for i in range(cols+1):
        u=i/cols;verts.append(((2*u-1)*1.65*(1-v),2.1,1.7+1.72*v));uvs.append((u,v))
for j in range(rows-1):
    for i in range(cols):
        k=j*(cols+1)+i;faces.append((k,k+1,k+cols+2,k+cols+1))
tip=len(verts);verts.append((0,2.1,3.42));uvs.append((.5,1))
for i in range(cols):k=(rows-1)*(cols+1)+i;faces.append((k,k+1,tip))
mesh=bpy.data.meshes.new('Rear canvas gable');mesh.from_pydata(verts,[],faces);mesh.update()
obj=bpy.data.objects.new('Rear canvas gable',mesh);bpy.context.collection.objects.link(obj);finish(obj,uvs=uvs)
bpy.context.view_layer.objects.active=obj;mod=obj.modifiers.new('Canvas thickness','SOLIDIFY');mod.thickness=.006
bpy.ops.object.modifier_apply(modifier=mod.name)
for end in (-1,1):
    rod('Round ridge upright',(0,end*2.18,0),(0,end*2.18,3.61),.048, sides=12)
    rod('Ridge guy peg',(0,end*2.94,0),(0,end*3.03,.30),.027)
    line('Ridge guy',[(0,end*2.18,3.60),(0,end*3.0,.19)],.012,'rope')
rod('Internal timber ridge',(0,-2.18,3.365),(0,2.18,3.365),.055,sides=12)
bpy.ops.object.select_all(action='DESELECT')
for obj in objects:obj.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
assert not bpy.data.actions and not any(o.type=='ARMATURE' for o in objects)
project=OUT/'ArmySurgeonsTent.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'ArmySurgeonsTent.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),
    project_sha256=sha(project),glb_sha256=sha(glb),atlas_sha256=sha(texture),objects=len(objects),materials=1,
    rigged=False,animations=0,paid_service_jobs=0,limitations=brief['reconstruction']),indent=2)+'\n')
print('ARMY_SURGEONS_TENT_AUTHORED',str(glb),flush=True)
