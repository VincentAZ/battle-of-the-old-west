"""Separate fictional Bounty Office ruin; preserve all reviewed healthy sources."""
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
BASE=ROOT/'art/western/holdings/expansion-review-v001/bounty-office'
OUT=BASE/'ruin-source-v003'
BRIEF=BASE/'ruin-brief-v001.json'
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
scale=4.5/max(hi.x-lo.x,hi.y-lo.y)
shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z))
normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)
material=original[0].data.materials[0].copy()
material.name='M_BountyOffice_AuthoredRuin'
# A separate atlas retains exposed red brick and light stone under patchy soot.
healthy_atlas=BASE/'local-source-v003/BountyOffice_BaseColor.png'
image=np.asarray(Image.open(healthy_atlas).convert('RGB')).astype(np.float32)
yy,xx=np.mgrid[0:2048,0:2048]
patch=(np.sin(xx*.017+np.sin(yy*.023)*1.8)*np.cos(yy*.013)+1)/2
soot=.12+.48*patch
carbon=np.array([27,23,19],dtype=np.float32)
image=image*(1-soot[...,None])+carbon*soot[...,None]
# The wood swatch is consumed timber; other areas retain visible material colour.
image[1300:1529,1544:2039]=np.array([30,23,17])+np.sin(xx[1300:1529,1544:2039]*.17)[...,None]*4
texture=OUT/'BountyOffice_Ruin_BaseColor.png'
Image.fromarray(np.clip(image,0,255).astype(np.uint8)).save(texture)
for node in material.node_tree.nodes:
    if node.type=='TEX_IMAGE':
        node.image=bpy.data.images.load(str(texture));node.image.pack()
for obj in original:
    obj.data.materials.clear();obj.data.materials.append(material)
kept,removed=[],[]
wall_names=('Long brick office wall','Unpierced lower end wall','Square brick gallery pier')


def stone_uv(obj):
    obj.data.update()
    uv=obj.data.uv_layers.active
    for face in obj.data.polygons:
        normal=max(range(3),key=lambda k:abs(face.normal[k]))
        for loop in face.loop_indices:
            p=obj.matrix_world@obj.data.vertices[obj.data.loops[loop].vertex_index].co
            a=1 if normal==0 else 0
            vv=p.z if normal!=2 else p.y+4
            uv.data[loop].uv=((p[a]+4)/8*.75,1-vv/8*.75)


def cap(x,y):
    # Irregular surviving courses, not a uniform horizontal cutaway.
    h=1.01+.24*math.sin(x*2.2+y*.9)+.16*math.sin(y*3.2-x*.6)
    return max(.64,round((h-.08*abs(math.sin(x*23+y*31)))/.038)*.038)


for obj in original:
    if obj.name.startswith(wall_names):
        axis=0 if obj.dimensions.x>=obj.dimensions.y else 1
        width=obj.dimensions[axis]
        count=max(1,math.ceil(width/.14))
        for n in range(count):
            part=obj.copy();part.data=obj.data.copy()
            bpy.context.collection.objects.link(part)
            for v in part.data.vertices:
                v.co[axis]/=count
            part.location[axis]+=-width/2+(n+.5)*width/count
            bpy.context.view_layer.update()
            world=[part.matrix_world@v.co for v in part.data.vertices]
            height=cap(part.location.x,part.location.y)
            if min(p.z for p in world)>=height-.03:
                bpy.data.objects.remove(part,do_unlink=True)
                continue
            inverse=part.matrix_world.inverted()
            for v,p in zip(part.data.vertices,world):
                if p.z>height:
                    p.z=height;v.co=inverse@p
            stone_uv(part);kept.append(part)
        removed.append(obj.name)
        bpy.data.objects.remove(obj,do_unlink=True)
    elif obj.name.startswith(('Raised stone foundation','Cut-stone entrance step','Pier stone foot')):
        if obj.name.startswith('Raised stone foundation'):
            # Exposed foundation interior is soot-covered, not a pristine
            # patterned floor. UVs select the atlas's dark iron-colour region.
            for face in obj.data.polygons:
                if face.normal.z>.9:
                    for loop in face.loop_indices:
                        obj.data.uv_layers.active.data[loop].uv=(.81,.43)
        kept.append(obj)
    else:
        removed.append(obj.name)
        bpy.data.objects.remove(obj,do_unlink=True)

rng=random.Random(1886)
for i in range(220):
    timber=i>=195
    slate=175<=i<195
    stone=150<=i<175
    dims=(rng.uniform(.25,.64),.055,.045) if timber else ((.14,.11,.016) if slate else (rng.uniform(.08,.19),rng.uniform(.06,.12),rng.uniform(.045,.10)))
    x,y=rng.uniform(-1.77,1.77),rng.uniform(-.82,.82)
    bpy.ops.mesh.primitive_cube_add(size=1,location=(x,y,.6))
    o=bpy.context.object;o.name='Consumed roof timber' if timber else ('Fallen slate' if slate else ('Fallen pale stone trim' if stone else 'Fallen red brick masonry'))
    o.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    for v in o.data.vertices:
        v.co.x*=rng.uniform(.78,1);v.co.y*=rng.uniform(.78,1);v.co.z*=rng.uniform(.75,1)
    o.rotation_euler=(rng.uniform(-.25,.25),rng.uniform(-.25,.25),rng.uniform(-math.pi,math.pi))
    o.data.materials.append(material)
    bpy.context.view_layer.update()
    bottom=min((o.matrix_world@v.co).z for v in o.data.vertices)
    o.location.z+=.50-bottom
    bpy.context.view_layer.update()
    if timber or stone or slate:
        x0,y0,x1,y1=(1544,1300,2038,1528) if timber else ((1544,510,2038,1010) if slate else (1544,8,2038,490))
        for uv in o.data.uv_layers.active.data:
            uv.uv=((x0+6+uv.uv.x*(x1-x0-12))/2048,1-(y0+6+uv.uv.y*(y1-y0-12))/2048)
    else:
        stone_uv(o)
    kept.append(o)
# Remove detached upper-wall remnants exposed by independently cut courses.
# Support follows the ground, foundation and lower retained masonry; no loose
# wall fragment is retained simply because its local volume is closed.
bpy.context.view_layer.update()
def component_bounds(o):
    points=[o.matrix_world@v.co for v in o.data.vertices]
    return ([min(v[k] for v in points)for k in range(3)],
            [max(v[k] for v in points)for k in range(3)])
supported=[]
unsupported=[]
for o in sorted(kept,key=lambda o:component_bounds(o)[0][2]):
    low,high=component_bounds(o)
    cx,cy=(low[0]+high[0])/2,(low[1]+high[1])/2
    has_support=abs(low[2])<.0001
    for a,b in supported:
        if a[2]<low[2] and b[2]>=low[2]-.0001 and a[0]-.0001<=cx<=b[0]+.0001 and a[1]-.0001<=cy<=b[1]+.0001:
            has_support=True;break
    if has_support:supported.append((low,high))
    else:unsupported.append(o)
for o in unsupported:
    removed.append('Unsupported remnant: '+o.name)
    kept.remove(o);bpy.data.objects.remove(o,do_unlink=True)
# Check each separate component before joining; none may be an open or inverted sheet.
solid_checks=[]
for o in kept:
    bm=bmesh.new();bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    row=dict(name=o.name,nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
             signed_volume_m3=bm.calc_volume(signed=True),minimum_face_area=min(f.calc_area() for f in bm.faces),
             world_minimum_z_m=min((o.matrix_world@v.co).z for v in o.data.vertices))
    assert row['nonmanifold_edges']==0 and row['signed_volume_m3']>0 and row['minimum_face_area']>1e-12,row
    solid_checks.append(row);bm.to_mesh(o.data);bm.free()
bpy.context.view_layer.update()
for o in kept:o.matrix_world=normalize@o.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for o in kept:o.select_set(True)
bpy.context.view_layer.objects.active=kept[0]
bpy.ops.object.join()
ruin=bpy.context.object;ruin.name='SM_HoldingRuin_BountyOffice'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
assert not bpy.data.actions and not any(o.type=='ARMATURE' for o in bpy.data.objects)
coords=[v.co.copy() for v in ruin.data.vertices]
bounds={'min':[min(p[k] for p in coords) for k in range(3)],'max':[max(p[k] for p in coords) for k in range(3)]}
assert abs(bounds['min'][2])<.0001 and bounds['max'][2]<1.4
bsdf=material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value=.96
project=OUT/'BountyOffice-Ruin.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
ruin.matrix_world=Matrix.Rotation(math.pi,4,'Z')
fbx=OUT/'SM_HoldingRuin_BountyOffice.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
    bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_tspace=True,path_mode='STRIP',embed_textures=False)
ruin.matrix_world=Matrix.Identity(4)
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
views={}
for name,pos in [('front',(7,-11,7)),('rear',(-7,11,7)),('right',(12,2,6)),('overhead',(0,-.01,15))]:
    data=bpy.data.cameras.new(name);data.type='ORTHO';data.ortho_scale=11
    camera=bpy.data.objects.new('Review_'+name,data);scene.collection.objects.link(camera)
    camera.location=pos;camera.rotation_euler=(Vector((0,0,.5))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera=camera;scene.render.filepath=str(OUT/(name+'.png'))
    bpy.ops.render.render(write_still=True)
    projected=[world_to_camera_view(scene,camera,o.matrix_world@v.co)
               for o in scene.objects if o.type=='MESH' for v in o.data.vertices]
    assert all(0<=p.x<=1 and 0<=p.y<=1 and p.z>0 for p in projected),name
    views[name]=sha(OUT/(name+'.png'))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'BountyOffice-Ruin-Review.blend'))
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
print('BOUNTY_OFFICE_RUIN_AUTHORED',flush=True)
