"""Sourced fictional prairie cemetery; static source only, no game integration."""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
import bmesh
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/western/holdings/expansion-review-v001/boot-hill'
OUT=BASE/'local-source-v001'
BRIEF=BASE/'local-authoring-brief-v001.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text())
assert brief['pre_modeling_review']['completed']
assert sha(BASE/'historical-evidence.json')==brief['historical_evidence_sha256']
for name,digest in brief['source_records'].items():assert sha(ROOT/name)==digest,name
assert not OUT.exists();OUT.mkdir()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
rng=random.Random(1880)
regions={'wood':(8,8,1008,1016),'earth':(1040,8,2040,1016),
         'grass':(8,1040,1008,2040),'label':(1040,1040,1536,2040),
         'leaf':(1560,1040,2040,2040)}
colours={'wood':(142,91,47),'earth':(108,81,48),'grass':(57,105,53),
         'label':(142,91,47),'leaf':(53,110,56)}
atlas=Image.new('RGB',(2048,2048),(100,76,44));draw=ImageDraw.Draw(atlas)
for name,rect in regions.items():
    draw.rectangle(rect,fill=colours[name]);x0,y0,x1,y1=rect
    if name in ('wood','label'):
        for x in range(x0+2,x1-2,3):
            delta=rng.randint(-15,15);color=tuple(max(0,c+delta)for c in colours[name])
            draw.line((x,y0,x+rng.randint(-2,2),y1),fill=color)
    else:
        for _ in range(22000):
            x,y=rng.randint(x0,x1-3),rng.randint(y0,y1-3)
            delta=rng.randint(-13,13);color=tuple(max(0,c+delta)for c in colours[name])
            draw.ellipse((x,y,x+rng.randint(1,5),y+rng.randint(1,5)),fill=color)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',64)
draw.text((1288,1290),'UNKNOWN',font=font,anchor='mm',fill=(57,34,18),stroke_width=0)
texture=OUT/'BootHill_BaseColor.png';atlas.save(texture)
material=bpy.data.materials.new('M_BootHill_Atlas');material.use_nodes=True
shader=material.node_tree.nodes.get('Principled BSDF');shader.inputs['Roughness'].default_value=.86
node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack()
material.node_tree.links.new(node.outputs['Color'],shader.inputs['Base Color'])
objects=[];contact_rows=[]


def finish(obj,region,label_front=False):
    obj.data.materials.append(material)
    bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update()
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(obj.data);bm.free();obj.data.update()
    uv=obj.data.uv_layers.active or obj.data.uv_layers.new()
    for face in obj.data.polygons:
        use_label=label_front and face.normal.y<-.9
        x0,y0,x1,y1=regions['label' if use_label else region]
        axis=max(range(3),key=lambda k:abs(face.normal[k]))
        a,b=[k for k in range(3)if k!=axis]
        if use_label:a,b=0,2
        coords=[obj.data.vertices[obj.data.loops[i].vertex_index].co for i in face.loop_indices]
        low=[min(p[k]for p in coords)for k in range(3)]
        high=[max(p[k]for p in coords)for k in range(3)]
        if region=='wood' and not use_label and high[a]-low[a]>high[b]-low[b]:a,b=b,a
        for loop in face.loop_indices:
            p=obj.data.vertices[obj.data.loops[loop].vertex_index].co
            u=(p[a]-low[a])/max(high[a]-low[a],1e-6)
            v=(p[b]-low[b])/max(high[b]-low[b],1e-6)
            uv.data[loop].uv=((x0+5+u*(x1-x0-10))/2048,1-(y1-5-v*(y1-y0-10))/2048)
    objects.append(obj);return obj


def solid(name,verts,faces,region,label=False):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    return finish(obj,region,label)


# The holding itself includes the low rise; its setting base remains a separate apron.
sides,rings=80,16
outline=[1+.014*math.sin(i*.37)+.008*math.sin(i*.91)for i in range(sides)]
verts=[(0,0,.24)]
for ring in range(1,rings+1):
    r=ring/rings
    for j in range(sides):
        a=j*math.tau/sides
        verts.append((2.73*r*outline[j]*math.cos(a),2.42*r*outline[j]*math.sin(a),.24*(1-r*r)**.8))
faces=[(0,1+j,1+(j+1)%sides)for j in range(sides)]
for ring in range(rings-1):
    for j in range(sides):
        a=1+ring*sides+j;b=1+ring*sides+(j+1)%sides
        faces.extend([(a,a+sides,b+sides),(a,b+sides,b)])
faces.append(tuple(reversed([1+(rings-1)*sides+j for j in range(sides)])))
hill=solid('Low prairie cemetery rise',verts,faces,'grass')
surface=BVHTree.FromPolygons([v.co for v in hill.data.vertices],[p.vertices for p in hill.data.polygons])


def ground(x,y):
    hit,*_=surface.ray_cast(Vector((x,y,3)),Vector((0,0,-1)))
    assert hit is not None,(x,y)
    return hit.z


graves=[(-1.42,-1.10),(.0,-1.08),(1.42,-1.03),(-1.42,1.02),(.0,1.04),(1.42,1.07)]
for index,(cx,cy)in enumerate(graves):
    width=.38+rng.uniform(-.02,.02);length=.77+rng.uniform(-.02,.02)
    height=.105+rng.uniform(-.015,.015)
    n=40;nr=6
    vv=[(cx,cy,ground(cx,cy)+height)]
    for ring in range(1,nr+1):
        r=ring/nr
        for j in range(n):
            a=j*math.tau/n;x=cx+width*r*math.cos(a);y=cy+length*r*math.sin(a)
            vv.append((x,y,ground(x,y)+.005+height*(1-r*r)**.6))
    ff=[(0,1+j,1+(j+1)%n)for j in range(n)]
    for ring in range(nr-1):
        for j in range(n):
            a=1+ring*n+j;b=1+ring*n+(j+1)%n
            ff.extend([(a,a+n,b+n),(a,b+n,b)])
    edge=[1+(nr-1)*n+j for j in range(n)];bottom=len(vv)
    vv.extend((vv[k][0],vv[k][1],ground(vv[k][0],vv[k][1])-.01)for k in edge)
    ff.append(tuple(reversed(range(bottom,bottom+n))))
    for j,k in enumerate(edge):
        jj=(j+1)%n;ff.append((k,bottom+j,bottom+jj,edge[jj]))
    solid('Low earth grave mound %d'%index,vv,ff,'earth')
    mx,my=cx,cy+length+.05
    gz=ground(mx,my)-.025
    if index in (2,4):
        # Two closed timbers with physical overlap at the ordinary cross joint.
        for name,loc,dims in [('upright',(mx,my,gz+.39),(.095,.07,.78)),
                              ('crossbar',(mx,my-.014,gz+.59),(.46,.074,.083))]:
            bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
            obj=bpy.context.object;obj.name=f'Rough cross {index} {name}';obj.dimensions=dims
            bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
            finish(obj,'wood')
    else:
        w=.32+rng.uniform(-.02,.02);h=.66+rng.uniform(-.07,.08);t=.047
        profile=[(-w/2,0),(w/2,0),(w/2,h-.04),(w/2-.045,h),(-w/2+.045,h),(-w/2,h-.04)]
        vv=[(mx+x,my+y,gz+z)for y in (-t/2,t/2)for x,z in profile];n=len(profile)
        ff=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
        ff.extend((j,(j+1)%n,(j+1)%n+n,j+n)for j in range(n))
        solid('Plain plank headboard %d'%index,vv,ff,'wood',index==0)
    contact_rows.append(dict(grave=index,marker_root=[mx,my,gz],terrain_z=ground(mx,my),root_embedded_m=.025))

# Short, solid grass blades root into the exact sampled hill surface.
for tuft in range(170):
    for attempt in range(500):
        x,y=rng.uniform(-2.50,2.50),rng.uniform(-2.20,2.20)
        if (x/2.52)**2+(y/2.22)**2>.96:continue
        if any(((x-cx)/.53)**2+((y-cy)/.99)**2<1.05 for cx,cy in graves):continue
        break
    else:raise AssertionError('Grass exclusion space exhausted')
    for leaf in range(5):
        a=rng.uniform(0,math.tau);height=rng.uniform(.10,.19);width=rng.uniform(.013,.023)
        lx,ly=x+rng.uniform(-.035,.035),y+rng.uniform(-.035,.035)
        z=ground(lx,ly)-.007;dx,dy=math.cos(a),math.sin(a)
        # Closed bent triangular prism, rather than a two-sided transparent card.
        vv=[]
        for off in (-.0015,.0015):
            vv.extend([(lx-dy*width/2+dx*off,ly+dx*width/2+dy*off,z),
                       (lx+dy*width/2+dx*off,ly-dx*width/2+dy*off,z),
                       (lx+dx*.065+dx*off,ly+dy*.065+dy*off,z+height)])
        solid('Rooted short prairie grass',vv,[(2,1,0),(3,4,5),(0,1,4,3),(1,2,5,4),(2,0,3,5)],'leaf')

checks=[]
bpy.context.view_layer.update()
for obj in objects:
    bm=bmesh.new();bm.from_mesh(obj.data);bm.normal_update()
    volume=bm.calc_volume(signed=True)
    assert all(e.is_manifold for e in bm.edges)and volume>0,obj.name
    assert min(f.calc_area()for f in bm.faces)>1e-12,obj.name
    checks.append(dict(name=obj.name,positive_volume_m3=volume,closed=True));bm.free()
assert not bpy.data.actions and not any(o.type=='ARMATURE'for o in bpy.data.objects)
bpy.ops.object.select_all(action='DESELECT')
for obj in objects:obj.select_set(True)
bpy.context.view_layer.objects.active=objects[0]
project=OUT/'BootHill.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'BootHill.glb'
bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False)
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'solid-validation.json').write_text(json.dumps(dict(status='passed',components=checks,scope='Closed positive-volume component solids; terrain/marker support separately recorded.'),indent=2)+'\n')
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),atlas_sha256=sha(texture),objects=len(objects),marker_contacts=contact_rows,materials=1,rigged=False,animations=0,paid_service_jobs=0,limitations=brief['reconstruction']),indent=2)+'\n')
print('BOOT_HILL_AUTHORED',flush=True)
