"""Author a separate, sourced fictional Coal Yard fire condition in Mixar."""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
import bmesh
import numpy as np
from PIL import Image
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/coal-yard'
OUT = BASE/'ruin-source-v005'
BRIEF = BASE/'ruin-brief-v005.json'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
source = BASE/brief['preservation']['source']
base_project = BASE/brief['preservation']['base']
for key, digest in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:
    assert sha(BASE/brief['preservation'][key]) == brief['preservation'][digest]
assert not OUT.exists()
OUT.mkdir()
bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
original = [o for o in bpy.context.scene.objects if o.type == 'MESH']
points = [o.matrix_world@v.co for o in original for v in o.data.vertices]
lo = Vector([min(p[k] for p in points) for k in range(3)])
hi = Vector([max(p[k] for p in points) for k in range(3)])
scale = 5.5/max(hi.x-lo.x, hi.y-lo.y)
shift = Vector((-(hi.x+lo.x)/2, -(hi.y+lo.y)/2, -lo.z))
normalize = Matrix.Scale(scale,4)@Matrix.Translation(shift)
material = original[0].data.materials[0].copy()
material.name = 'M_CoalYard_AuthoredRuin'
pixels = np.asarray(Image.open(BASE/'local-source-v003/CoalYard_BaseColor.png').convert('RGB')).copy()
yy, xx = np.mgrid[0:2048, 0:2048]
grain = np.sin(xx*.17+np.sin(yy*.014)*1.5)
cracks = np.sin(xx*.041+np.sin(yy*.015)) > .85
char = np.array([38,28,20])+grain[...,None]*5-cracks[...,None]*10
pixels[8:1017,8:1009] = np.clip(char[8:1017,8:1009],0,255)
texture = OUT/'CoalYard_Ruin_BaseColor.png'
Image.fromarray(pixels).save(texture)
for node in material.node_tree.nodes:
    if node.type == 'TEX_IMAGE':
        node.image = bpy.data.images.load(str(texture)); node.image.pack()
material.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = .94
rng = random.Random(1889)
kept, removed, supported = [], [], []


def finish(obj, region='wood', support='ground'):
    obj.data.materials.clear(); obj.data.materials.append(material)
    if region:
        # Original atlas UVs retained for copied railway components.
        rect = {'wood':(8,8,1008,1016), 'coal':(8,1040,1008,2040)}[region]
        uv = obj.data.uv_layers.active or obj.data.uv_layers.new()
        for face in obj.data.polygons:
            axis = max(range(3),key=lambda k:abs(face.normal[k]))
            a,b = [k for k in range(3) if k != axis]
            coords = [obj.data.vertices[obj.data.loops[i].vertex_index].co for i in face.loop_indices]
            low = [min(p[k] for p in coords) for k in range(3)]
            high = [max(p[k] for p in coords) for k in range(3)]
            if high[a]-low[a] > high[b]-low[b]: a,b = b,a
            x0,y0,x1,y1 = rect
            for loop in face.loop_indices:
                v = obj.data.vertices[obj.data.loops[loop].vertex_index].co
                u = (v[a]-low[a])/max(high[a]-low[a],1e-6)
                w = (v[b]-low[b])/max(high[b]-low[b],1e-6)
                uv.data[loop].uv = ((x0+5+u*(x1-x0-10))/2048,1-(y1-5-w*(y1-y0-10))/2048)
    kept.append(obj); supported.append((obj,support))
    return obj


def grounded_box(name, position, dims, angle=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(*position, dims[2]/2))
    obj = bpy.context.object; obj.name = name; obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bevel = obj.modifiers.new('Rounded charred edges','BEVEL'); bevel.width = .009; bevel.segments = 1
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    obj.rotation_euler.z = angle
    return finish(obj)


for obj in original:
    obj.data.transform(obj.matrix_world); obj.matrix_world = Matrix.Identity(4)
    if obj.name.startswith(('Sawn timber rail tie','Closed flat-bottom iron rail','Plain rail spike head')):
        support = 'ground' if obj.name.startswith('Sawn') else 'railway assembly'
        if obj.name.startswith('Plain rail spike head'):
            # Spike heads straddle the edge of the rail flange and embed in ties.
            for v in obj.data.vertices: v.co.z -= .018
        finish(obj,None,support)
    else:
        removed.append(obj.name); bpy.data.objects.remove(obj,do_unlink=True)

for y in (-.30,1.60):
    for x in (-2.25,-.75,.75,2.25):
        obj = grounded_box('Charred frame stump',(x,y),(.15,.15,rng.uniform(.24,.65)))
        # Tilt the top cut without altering the supported underside.
        top = max(v.co.z for v in obj.data.vertices)
        for v in obj.data.vertices:
            if v.co.z > top-.025: v.co.z += .22*v.co.x+.12*v.co.y
for i in range(23):
    x = -2.20+i*.195
    grounded_box('Rear charred board remnant',(x,1.65),(.15,.045,rng.uniform(.12,.35)))
for x in (-2.30,2.30):
    for i in range(8):
        grounded_box('End charred board remnant',(x,-.12+i*.22),(.045,.15,rng.uniform(.12,.40)))

# Low tapered coal remnants, grounded directly after their timber bins collapse.
for bay in (-1,0,1):
    cx, cy = bay*1.48,.66
    rings, sides = 7,32
    peak = .31+.045*bay
    outline = [rng.uniform(.86,1.05) for _ in range(sides)]
    vertices = [(cx,cy,peak)]
    for ring in range(1,rings+1):
        radius = ring/rings
        for j in range(sides):
            a = j*math.tau/sides
            z = peak*(1-radius*radius)+rng.uniform(-.018,.018)*(1-radius)
            vertices.append((cx+.69*radius*outline[j]*math.cos(a),cy+.85*radius*outline[j]*math.sin(a),max(0,z)))
    faces = [(0,1+j,1+(j+1)%sides) for j in range(sides)]
    for ring in range(rings-1):
        for j in range(sides):
            a=1+ring*sides+j; b=1+ring*sides+(j+1)%sides
            faces.extend([(a,a+sides,b+sides),(a,b+sides,b)])
    edge = [1+(rings-1)*sides+j for j in range(sides)]
    faces.append(tuple(reversed(edge)))
    mesh = bpy.data.meshes.new('Spilled coal');mesh.from_pydata(vertices,[],faces);mesh.update()
    obj = bpy.data.objects.new('Low spilled coal heap',mesh);bpy.context.collection.objects.link(obj)
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    finish(obj,'coal')
    tree = BVHTree.FromPolygons([v.co for v in mesh.vertices],[p.vertices for p in mesh.polygons])
    for i in range(170):
        a=rng.uniform(0,math.tau);r=math.sqrt(rng.random())*.77
        x,y=cx+.69*r*math.cos(a),cy+.85*r*math.sin(a)
        hit,*_=tree.ray_cast(Vector((x,y,2)),Vector((0,0,-1)))
        assert hit is not None
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1,location=(x,y,hit.z-.018))
        chunk=bpy.context.object;chunk.name='Coal fragment bedded in spill'
        chunk.scale=(rng.uniform(.04,.07),rng.uniform(.04,.07),rng.uniform(.025,.045))
        chunk.rotation_euler=(rng.random(),rng.random(),rng.random()*math.tau)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        finish(chunk,'coal','coal heap')
        bpy.context.view_layer.update()
        lowest=min((chunk.matrix_world@v.co).z for v in chunk.data.vertices)
        chunk.location.z-=min(0,lowest)
        bpy.context.view_layer.update()
        gaps=[]
        for v in chunk.data.vertices:
            p=chunk.matrix_world@v.co
            surface,*_=tree.ray_cast(Vector((p.x,p.y,2)),Vector((0,0,-1)))
            if surface is not None:gaps.append(p.z-surface.z)
        assert gaps and min(gaps)<0<max(gaps),chunk.name

# Sparse fallen boards in the space between shed and siding, no repeated piles.
for i in range(12):
    x=-2.02+(i%6)*.80
    y=-.52-(i//6)*.22
    grounded_box('Fallen charred roof board',(x,y),(rng.uniform(.38,.63),.12,rng.uniform(.12,.17)),rng.uniform(-.60,.60))

solid_checks=[]
bpy.context.view_layer.update()
for obj,support in supported:
    bm=bmesh.new();bm.from_mesh(obj.data);bm.transform(obj.matrix_world)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update()
    if bm.calc_volume(signed=True)<0:
        bmesh.ops.reverse_faces(bm,faces=list(bm.faces));bm.normal_update()
    row=dict(name=obj.name,nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),signed_volume_m3=bm.calc_volume(signed=True),minimum_face_area=min(f.calc_area() for f in bm.faces),minimum_z_m=min(v.co.z for v in bm.verts),support=support)
    assert row['nonmanifold_edges']==0 and row['signed_volume_m3']>0 and row['minimum_face_area']>1e-12,row
    if support=='ground':assert abs(row['minimum_z_m'])<1e-6,row
    solid_checks.append(row)
    bm.to_mesh(obj.data);bm.free();obj.matrix_world=Matrix.Identity(4)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'CoalYard-Ruin-Components.blend'))
for obj in kept:obj.matrix_world=normalize@obj.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for obj in kept:obj.select_set(True)
bpy.context.view_layer.objects.active=kept[0];bpy.ops.object.join()
ruin=bpy.context.object;ruin.name='SM_HoldingRuin_CoalYard'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
coords=[v.co.copy() for v in ruin.data.vertices]
bounds={'min':[min(p[k] for p in coords) for k in range(3)],'max':[max(p[k] for p in coords) for k in range(3)]}
assert abs(bounds['min'][2])<.0001 and bounds['max'][2]<1.4
project=OUT/'CoalYard-Ruin.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
ruin.matrix_world=Matrix.Rotation(math.pi,4,'Z')
fbx=OUT/'SM_HoldingRuin_CoalYard.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_tspace=True,path_mode='STRIP',embed_textures=False)
ruin.matrix_world=Matrix.Identity(4)

from bpy_extras.object_utils import world_to_camera_view
with bpy.data.libraries.load(str(base_project),link=False) as (src,dst):
    dst.objects=['Holding_Base_Ground']
for o in dst.objects:bpy.context.collection.objects.link(o)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24
scene.cycles.use_denoising=True
scene.render.threads_mode='FIXED';scene.render.threads=8
scene.render.resolution_x,scene.render.resolution_y=1024,768
scene.render.resolution_percentage=100
if scene.world is None:scene.world=bpy.data.worlds.new('Ruin review world')
scene.world.color=(.25,.30,.36)
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
scene.view_settings.exposure=.7
sun_data=bpy.data.lights.new('Clear warm sunlight','SUN');sun_data.energy=2.2
sun_data.angle=math.radians(12);sun_data.color=(1,.93,.83)
sun=bpy.data.objects.new('Clear warm sunlight',sun_data);scene.collection.objects.link(sun)
sun.rotation_euler=(math.radians(25),math.radians(-20),math.radians(-30))
for name,pos,power,size in [('Warm daylight',(-5,-6,9),1700,6),('Sky fill',(5,3,8),1200,7)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
    o=bpy.data.objects.new(name,data);scene.collection.objects.link(o)
    o.location=pos;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
bpy.context.view_layer.update()
views={}
for name,pos in [('front',(7,-11,7)),('rear',(-7,11,7)),('right',(12,2,6)),('overhead',(0,-.01,15))]:
    data=bpy.data.cameras.new(name);data.type='ORTHO';data.ortho_scale=13
    camera=bpy.data.objects.new('Review_'+name,data);scene.collection.objects.link(camera)
    camera.location=pos;camera.rotation_euler=(Vector((0,0,.5))-camera.location).to_track_quat('-Z','Y').to_euler()
    right=camera.rotation_euler.to_quaternion()@Vector((1,0,0))
    up=camera.rotation_euler.to_quaternion()@Vector((0,1,0))
    points=[o.matrix_world@v.co for o in scene.objects if o.type=='MESH' for v in o.data.vertices]
    xs=[(p-camera.location).dot(right)for p in points];ys=[(p-camera.location).dot(up)for p in points]
    camera.location+=right*((max(xs)+min(xs))/2)+up*((max(ys)+min(ys))/2)
    camera.data.ortho_scale=1.15*max(max(xs)-min(xs),(max(ys)-min(ys))/.75)
    scene.camera=camera;scene.render.filepath=str(OUT/(name+'.png'))
    bpy.ops.render.render(write_still=True)
    projected=[world_to_camera_view(scene,camera,o.matrix_world@v.co)
               for o in scene.objects if o.type=='MESH' for v in o.data.vertices]
    assert all(0<=p.x<=1 and 0<=p.y<=1 and p.z>0 for p in projected),name
    views[name]=sha(OUT/(name+'.png'))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'CoalYard-Ruin-Review.blend'))

for key,digest in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:
    assert sha(BASE/brief['preservation'][key])==brief['preservation'][digest]
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,normalization=dict(scale=scale,shift=list(shift)),triangles=triangles,bounds_m=bounds,removed_parts=removed,project_sha256=sha(project),base_project_sha256=sha(base_project),fbx_sha256=sha(fbx),texture_sha256=sha(texture),views=views,imported=False,component_solids=solid_checks,component_count=len(solid_checks),limitations=['Fictional damage, not a historical event or engineering simulation.','Ground contact and coal bedding checked; siding is a retained supported assembly.','Native condition/repair review pending.']),indent=2)+'\n')
print('COAL_YARD_RUIN_AUTHORED',flush=True)
