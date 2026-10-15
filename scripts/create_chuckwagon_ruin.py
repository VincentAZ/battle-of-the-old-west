"""Author a separate, documented fictional chuckwagon fire condition in Mixar."""
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
BASE=ROOT/'art/western/holdings/expansion-review-v001/chuckwagon'
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
normalize=Matrix.Rotation(math.pi,4,'Z')@Matrix.Scale(scale,4)@Matrix.Translation(shift)
material=original[0].data.materials[0].copy();material.name='M_Chuckwagon_AuthoredRuin'
image=np.asarray(Image.open(BASE/'local-source-v001/Chuckwagon_BaseColor.png').convert('RGB')).astype(np.float32)
yy,xx=np.mgrid[0:2048,0:2048]
soot=.28+.35*(np.sin(xx*.018+np.sin(yy*.027))*np.cos(yy*.019)+1)/2
image=image*(1-soot[...,None])+np.array([26,22,18])*soot[...,None]
# Char all wooden regions while retaining the original iron and tin atlas regions.
for x0,y0,x1,y1 in [(8,8,1016,1016),(1040,8,2038,1016),(1540,1540,2038,2038)]:
    grain=np.sin(xx[y0:y1,x0:x1]*.04+np.sin(yy[y0:y1,x0:x1]*.1))
    image[y0:y1,x0:x1]=np.array([35,27,20])+grain[...,None]*7
texture=OUT/'Chuckwagon_Ruin_BaseColor.png'
Image.fromarray(np.clip(image,0,255).astype(np.uint8)).save(texture)
for n in material.node_tree.nodes:
    if n.type=='TEX_IMAGE':n.image=bpy.data.images.load(str(texture));n.image.pack()
kept=[];removed=[];debris=[]
# Bake the separate source parts to world coordinates before arranging the wreck.
for o in original:
    o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
wheel_prefixes=('Timber wheel felloe','Narrow iron tire','Projecting wooden hub',
                'Hub iron band','Dished wooden spoke','Axle outer cap')
body_prefixes=('Bed floor plank','Bed runner','Equipment boot')
tilt=(Matrix.Translation((0,1.13,.98))@Matrix.Rotation(.26,4,'X')@
      Matrix.Translation((0,-1.13,-.98)))
for o in original:
    points=[v.co for v in o.data.vertices]
    centre=sum(points,Vector())/len(points)
    keep=False
    if o.name.startswith(wheel_prefixes):
        keep=True
        front=centre.y<0
        if front:
            # Rotate each entire wheel consistently about its axle, then set it
            # horizontally on its projecting hub rather than leave it floating.
            side=-1 if centre.x<0 else 1
            original_centre=Vector((side*.88,-1.08,.55))
            new_centre=Vector((-.25 if side<0 else .20,-1.95 if side<0 else -.72,.151))
            o.data.transform(Matrix.Translation(new_centre)@Matrix.Rotation(math.pi/2,4,'Y')@Matrix.Translation(-original_centre))
        elif o.name.startswith('Dished wooden spoke'):
            # Retain alternating spokes: heavy rear hubs and rims survive as
            # a readable partial wheel, without claiming engineering stability.
            index=int(o.name.rsplit('.',1)[1]) if '.' in o.name else 0
            keep=index%2==0
    elif o.name.startswith(body_prefixes):
        keep=True
        if o.name.startswith('Bed floor plank'):
            index=int(o.name.rsplit('.',1)[1]) if '.' in o.name else 0
            front=-1.5+[.1,.7,1.1,.15,.3,.85,.5,.25][index]
            for v in o.data.vertices:v.co.y=max(v.co.y,front)
        o.data.transform(tilt)
    elif o.name.startswith(('Wood axle','Continuous iron axle','Axle bolster','Iron axle strap')) and centre.y>0:
        keep=True
    elif o.name.startswith('Hinged worktable plank') or o.name.startswith('Table underside batten'):
        keep=True;o.data.transform(Matrix.Translation((0,0,-1.054)))
        debris.append(o)
    elif o.name.startswith('Lidded cast iron pot'):
        keep=True;o.data.transform(Matrix.Translation((.62,.68,-1.588)))
    if keep:
        o.data.materials.clear();o.data.materials.append(material);kept.append(o)
    else:
        removed.append(o.name);bpy.data.objects.remove(o,do_unlink=True)
# Fallen short boards are rounded charcoal fragments, retained inside the
# original wheel-to-wheel width. Their sparse count is explicitly abstracted.
rng=random.Random(1866)
for i in range(16):
    bpy.ops.mesh.primitive_cube_add(size=1)
    o=bpy.context.object;o.name=f'Fallen charred board {i:02}'
    o.scale=(rng.uniform(.25,.58),rng.uniform(.055,.105),rng.uniform(.045,.085))
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bevel=o.modifiers.new('Charred rounded corners','BEVEL');bevel.width=.008;bevel.segments=1
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    o.rotation_euler=(rng.uniform(-.15,.15),rng.uniform(-.12,.12),rng.uniform(-.7,.7))
    o.location=(rng.uniform(-.58,.58),rng.uniform(-2.45,1.85),0)
    bpy.context.view_layer.update()
    o.location.z-=min((o.matrix_world@v.co).z for v in o.data.vertices)
    o.data.materials.append(material)
    if not o.data.uv_layers:o.data.uv_layers.new()
    for uv in o.data.uv_layers.active.data:
        uv.uv=((30+uv.uv.x*940)/2048,1-(30+uv.uv.y*940)/2048)
    kept.append(o);debris.append(o)
# Grounding audit covers whole fallen assemblies separately from the planks
# above their common underside battens; the table intentionally rests on those.
bpy.context.view_layer.update()
assert all(abs(min((o.matrix_world@v.co).z for v in o.data.vertices))<1e-6
           for o in debris if o.name.startswith('Fallen charred'))
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
ruin=bpy.context.object;ruin.name='SM_HoldingRuin_Chuckwagon'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
assert not bpy.data.actions and not any(o.type=='ARMATURE' for o in bpy.data.objects)
coords=[v.co.copy() for v in ruin.data.vertices]
bounds={'min':[min(p[k] for p in coords) for k in range(3)],'max':[max(p[k] for p in coords) for k in range(3)]}
assert abs(bounds['min'][2])<.0001 and bounds['max'][2]<1.4
bsdf=material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value=.96
project=OUT/'Chuckwagon-Ruin.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
ruin.matrix_world=Matrix.Rotation(math.pi,4,'Z')
fbx=OUT/'SM_HoldingRuin_Chuckwagon.fbx'
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
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Chuckwagon-Ruin-Review.blend'))
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
print('CHUCKWAGON_RUIN_AUTHORED',flush=True)
