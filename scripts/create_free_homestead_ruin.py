"""Author a separate, documented fictional homestead fire condition in Mixar."""
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
from bpy_extras.object_utils import world_to_camera_view

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/western/holdings/expansion-review-v001/free-homestead'
OUT=BASE/'ruin-source-v003'
BRIEF=BASE/'ruin-brief-v003.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text())
source=BASE/brief['preservation']['source']
base_project=BASE/brief['preservation']['base']
assert sha(source)==brief['preservation']['sha256']
assert sha(base_project)==brief['preservation']['base_sha256']
assert not OUT.exists()
OUT.mkdir()
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
original=[o for o in bpy.context.scene.objects if o.type=='MESH']
points=[o.matrix_world@v.co for o in original for v in o.data.vertices]
lo=Vector([min(p[k] for p in points) for k in range(3)])
hi=Vector([max(p[k] for p in points) for k in range(3)])
scale=5/max(hi.x-lo.x,hi.y-lo.y)
shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z))
normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)
material=original[0].data.materials[0].copy();material.name='M_FreeHomestead_AuthoredRuin'
image=np.asarray(Image.open(BASE/'local-source-v003/FreeHomestead_BaseColor.png').convert('RGB')).astype(np.float32)
yy,xx=np.mgrid[0:2048,0:2048]
soot=.28+.35*(np.sin(xx*.018+np.sin(yy*.027))*np.cos(yy*.019)+1)/2
image=image*(1-soot[...,None])+np.array([26,22,18])*soot[...,None]
# Wood and framing really are charred material; keep red brick and lime readable.
for x0,y0,x1,y1 in [(8,8,1016,1016),(520,1550,1016,2038)]:
    grain=np.sin(xx[y0:y1,x0:x1]*.04+np.sin(yy[y0:y1,x0:x1]*.1))
    image[y0:y1,x0:x1]=np.array([35,27,20])+grain[...,None]*7
texture=OUT/'FreeHomestead_Ruin_BaseColor.png'
Image.fromarray(np.clip(image,0,255).astype(np.uint8)).save(texture)
for n in material.node_tree.nodes:
    if n.type=='TEX_IMAGE':n.image=bpy.data.images.load(str(texture));n.image.pack()
kept=[];removed=[]
for o in original:
    coords=[v.co for v in o.data.vertices]
    low=min(v.z for v in coords);high=max(v.z for v in coords)
    centre=sum(coords,Vector())/len(coords)
    cap=.51 if centre.y < -2 else (1.015 if centre.y>2 else .75)
    keep=False
    if o.name.startswith('Hewn hardwood log course') and high<=cap:
        keep=True
    elif o.name.startswith('Lime-chink wall core') and low<cap:
        keep=True
        for v in o.data.vertices:v.co.z=min(v.co.z,cap-.065)
    if keep:
        o.data.materials.clear();o.data.materials.append(material);kept.append(o)
    else:
        removed.append(o.name);bpy.data.objects.remove(o,do_unlink=True)

rng=random.Random(1868)
debris=[]
# Fallen members and gable brick sit inside the same floor area. Their absence
# from the rest of the roof is an explicit game abstraction, not a mass balance.
for i in range(72):
    timber=i<14
    size=(rng.uniform(.55,1.5),rng.uniform(.12,.23),rng.uniform(.10,.20)) if timber else (rng.uniform(.14,.26),rng.uniform(.09,.14),rng.uniform(.055,.12))
    bpy.ops.mesh.primitive_cube_add(size=1)
    o=bpy.context.object;o.name=('Fallen charred timber' if timber else 'Fallen gable brick')+f' {i:02}'
    o.scale=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bevel=o.modifiers.new('Worn fragment edges','BEVEL');bevel.width=.015 if timber else .008;bevel.segments=1
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    # Slight fragment irregularity, preserving convex closed solids.
    for v in o.data.vertices:
        v.co.x*=rng.uniform(.96,1.04);v.co.y*=rng.uniform(.96,1.04)
    o.location=(rng.uniform(-1.5,1.5),rng.uniform(-1.4,1.4),0)
    o.rotation_euler=(rng.uniform(-.20,.20),rng.uniform(-.15,.15),rng.uniform(0,math.tau))
    bpy.context.view_layer.update()
    o.location.z-=min((o.matrix_world@v.co).z for v in o.data.vertices)
    o.data.materials.append(material)
    if not o.data.uv_layers:o.data.uv_layers.new()
    # Each brick fragment samples one brick rather than a wall-sized bond.
    x0,y0,x1,y1=(30,30,970,970) if timber else (1050,15,1067,20)
    for uv in o.data.uv_layers.active.data:
        uv.uv=((x0+uv.uv.x*(x1-x0))/2048,1-(y0+uv.uv.y*(y1-y0))/2048)
    kept.append(o);debris.append(o)
bpy.context.view_layer.update()
assert all(abs(min((o.matrix_world@v.co).z for v in o.data.vertices))<1e-6 for o in debris)
# Check each separate component before joining; none may be an open or inverted sheet.
solid_checks=[]
for o in kept:
    bm=bmesh.new();bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    row=dict(name=o.name,nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
             signed_volume_m3=bm.calc_volume(signed=True),minimum_face_area=min(f.calc_area() for f in bm.faces))
    assert row['nonmanifold_edges']==0 and row['signed_volume_m3']>0 and row['minimum_face_area']>1e-12,row
    solid_checks.append(row);bm.to_mesh(o.data);bm.free()
bpy.context.view_layer.update()
for o in kept:o.matrix_world=normalize@o.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for o in kept:o.select_set(True)
bpy.context.view_layer.objects.active=kept[0]
bpy.ops.object.join()
ruin=bpy.context.object;ruin.name='SM_HoldingRuin_FreeHomestead'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
assert not bpy.data.actions and not any(o.type=='ARMATURE' for o in bpy.data.objects)
coords=[v.co.copy() for v in ruin.data.vertices]
bounds={'min':[min(p[k] for p in coords) for k in range(3)],'max':[max(p[k] for p in coords) for k in range(3)]}
assert abs(bounds['min'][2])<.0001 and bounds['max'][2]<1.4
bsdf=material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value=.96
project=OUT/'FreeHomestead-Ruin.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
ruin.matrix_world=Matrix.Rotation(math.pi,4,'Z')
fbx=OUT/'SM_HoldingRuin_FreeHomestead.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
    bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_tspace=True,path_mode='STRIP',embed_textures=False)
ruin.matrix_world=Matrix.Identity(4)
with bpy.data.libraries.load(str(base_project),link=False) as (src,dst):
    dst.objects=['Holding_Base_Ground','Holding_Base_Tuft']
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
views={}
for name,pos in [('front',(7,-11,7)),('rear',(-7,11,7)),('right',(12,2,6)),('overhead',(0,-.01,15))]:
    data=bpy.data.cameras.new(name);data.type='ORTHO';data.ortho_scale=13
    camera=bpy.data.objects.new('Review_'+name,data);scene.collection.objects.link(camera)
    camera.location=pos;camera.rotation_euler=(Vector((0,0,.5))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera=camera;scene.render.filepath=str(OUT/(name+'.png'))
    bpy.ops.render.render(write_still=True)
    projected=[world_to_camera_view(scene,camera,o.matrix_world@v.co)
               for o in scene.objects if o.type=='MESH' for v in o.data.vertices]
    assert all(0<=p.x<=1 and 0<=p.y<=1 and p.z>0 for p in projected),name
    views[name]=sha(OUT/(name+'.png'))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'FreeHomestead-Ruin-Review.blend'))
assert sha(source)==brief['preservation']['sha256']
assert sha(base_project)==brief['preservation']['base_sha256']
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',
    brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,
    normalization=dict(scale=scale,shift=list(shift)),triangles=triangles,bounds_m=bounds,
    removed_parts=removed,project_sha256=sha(project),base_project_sha256=sha(base_project),
    fbx_sha256=sha(fbx),texture_sha256=sha(texture),views=views,imported=False,
    component_solids=solid_checks,component_count=len(solid_checks),
    limitations=['Fictional game damage, not a historical event','Native conditions and repair restoration pending']),indent=2)+'\n')
print('FREE_HOMESTEAD_RUIN_AUTHORED',flush=True)
