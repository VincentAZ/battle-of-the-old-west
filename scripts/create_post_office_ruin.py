"""Separate fictional stone ruin; preserve all reviewed Post Office sources."""
import hashlib
import json
import math
from pathlib import Path
import random

import bpy
from mathutils import Matrix, Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/western/holdings/expansion-review-v001/post-office'
OUT=BASE/'ruin-source-v001'
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
material=original[0].data.materials[0]
kept,removed=[],[]
wall_names=('Front rubble masonry','Reconstructed rear masonry','Left end masonry','Right end masonry')


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
    # Broken courses vary by wall and along each wall; no uniform cutaway.
    if abs(y)>1.5:
        band=min(7,max(0,int((x+3.1)/.78)))
        profile=([1.43,.97,1.19,.76,1.38,1.72,1.23,.94] if y<0 else
                 [1.63,1.44,1.08,1.37,.81,1.21,1.54,1.79])
        h=profile[band]
    else:
        h=(1.21 if x<0 else 1.65)+.30*math.sin(y*2.3)
    return max(.48,round((h-.16*abs(math.sin(x*29+y*41)))/.13)*.13)


for obj in original:
    if obj.name.startswith(wall_names):
        axis=1 if obj.name.startswith(('Left end','Right end')) else 0
        width=obj.dimensions[axis]
        count=max(1,math.ceil(width/.22))
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
    elif obj.name.startswith(('Low masonry plinth','Worn stone doorstep')):
        if obj.name.startswith('Low masonry plinth'):
            # Exposed foundation interior is soot-covered, not a pristine
            # patterned floor. UVs select the atlas's dark iron-colour region.
            for face in obj.data.polygons:
                if face.normal.z>.9:
                    for loop in face.loop_indices:
                        obj.data.uv_layers.active.data[loop].uv=(.31,.12)
        kept.append(obj)
    else:
        removed.append(obj.name)
        bpy.data.objects.remove(obj,do_unlink=True)

rng=random.Random(1852)
for i in range(204):
    timber=i>=180
    dims=(rng.uniform(.35,.82),.07,.06) if timber else (rng.uniform(.12,.27),rng.uniform(.10,.20),rng.uniform(.07,.16))
    bpy.ops.mesh.primitive_cube_add(size=1,location=(rng.uniform(-2.45,2.45),rng.uniform(-1.18,1.18),.2))
    o=bpy.context.object;o.name='Consumed timber remnant' if timber else 'Fallen rough stone'
    o.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    # Only the derivative gets irregular broken corners.
    for v in o.data.vertices:
        v.co.x*=rng.uniform(.72,1);v.co.y*=rng.uniform(.70,1);v.co.z*=rng.uniform(.65,1)
    o.rotation_euler=(rng.uniform(-.3,.3),rng.uniform(-.3,.3),rng.uniform(-math.pi,math.pi))
    o.data.materials.append(material)
    bpy.context.view_layer.update()
    bottom=min((o.matrix_world@v.co).z for v in o.data.vertices)
    o.location.z+=.10-bottom
    bpy.context.view_layer.update()
    if timber:
        for uv in o.data.uv_layers.active.data:
            uv.uv=((1556+uv.uv.x*476)/2048,1-(14+uv.uv.y*740)/2048)
    else:
        stone_uv(o)
    kept.append(o)
bpy.context.view_layer.update()
for o in kept:o.matrix_world=normalize@o.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for o in kept:o.select_set(True)
bpy.context.view_layer.objects.active=kept[0]
bpy.ops.object.join()
ruin=bpy.context.object;ruin.name='SM_HoldingRuin_PostOffice'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
assert not bpy.data.actions and not any(o.type=='ARMATURE' for o in bpy.data.objects)
coords=[v.co.copy() for v in ruin.data.vertices]
bounds={'min':[min(p[k] for p in coords) for k in range(3)],'max':[max(p[k] for p in coords) for k in range(3)]}
assert abs(bounds['min'][2])<.0001 and bounds['max'][2]<1.4
bsdf=material.node_tree.nodes.get('Principled BSDF')
socket=bsdf.inputs['Base Color'];grain=socket.links[0].from_socket
multiply=material.node_tree.nodes.new('ShaderNodeMixRGB');multiply.blend_type='MULTIPLY'
multiply.inputs[0].default_value=1;multiply.inputs[2].default_value=(.17,.165,.16,1)
material.node_tree.links.new(grain,multiply.inputs[1]);material.node_tree.links.new(multiply.outputs[0],socket)
bsdf.inputs['Roughness'].default_value=.96
project=OUT/'PostOffice-Ruin.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
ruin.matrix_world=Matrix.Rotation(math.pi,4,'Z')
fbx=OUT/'SM_HoldingRuin_PostOffice.fbx'
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
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'PostOffice-Ruin-Review.blend'))
assert sha(source)==brief['preservation']['sha256']
assert sha(base_project)==brief['preservation']['base_sha256']
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',
    brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,
    normalization=dict(scale=scale,shift=list(shift)),triangles=triangles,bounds_m=bounds,
    removed_parts=removed,project_sha256=sha(project),base_project_sha256=sha(base_project),
    fbx_sha256=sha(fbx),views=views,imported=False,
    limitations=['Fictional game damage, not a historical event','Native conditions and repair restoration pending']),indent=2)+'\n')
print('POST_OFFICE_RUIN_AUTHORED',flush=True)
