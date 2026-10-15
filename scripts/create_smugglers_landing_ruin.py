"""Separate fictional charred hull and landing remnants; preserves reviewed sources."""
import hashlib,json,math,random
from pathlib import Path
import bpy,bmesh
import numpy as np
from PIL import Image
from mathutils import Matrix,Vector
from bpy_extras.object_utils import world_to_camera_view
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/western/holdings/expansion-review-v001/smugglers-landing'
OUT=BASE/'ruin-source-v002'
BRIEF=BASE/'ruin-brief-v002.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text());source=BASE/brief['preservation']['source'];base_project=BASE/brief['preservation']['base']
assert sha(source)==brief['preservation']['sha256'] and sha(base_project)==brief['preservation']['base_sha256']
assert not OUT.exists();OUT.mkdir()
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
original=[o for o in bpy.context.scene.objects if o.type=='MESH']
points=[o.matrix_world@v.co for o in original for v in o.data.vertices]
rotation=Matrix.Rotation(math.pi,4,'Z')
points=[rotation@p for p in points]
lo=Vector([min(p[k]for p in points)for k in range(3)]);hi=Vector([max(p[k]for p in points)for k in range(3)])
scale=6.0/max(hi.x-lo.x,hi.y-lo.y);shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z))
normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)@rotation
material=original[0].data.materials[0].copy();material.name='M_SmugglersLanding_AuthoredRuin'
yy,xx=np.mgrid[0:2048,0:2048]
grain=np.sin(xx*.18+np.sin(yy*.006)*2)+.4*np.sin(xx*.43+yy*.003)
crack=(np.sin(xx*.045+np.sin(yy*.012)*.8)>.88)
image=np.empty((2048,2048,3),dtype=np.float32)
image[:]=np.array([37,27,19])+grain[...,None]*4-crack[...,None]*9
texture=OUT/'SmugglersLanding_Ruin_BaseColor.png';Image.fromarray(np.clip(image,0,255).astype(np.uint8)).save(texture)
for n in material.node_tree.nodes:
 if n.type=='TEX_IMAGE':n.image=bpy.data.images.load(str(texture));n.image.pack()
rng=random.Random(18791885);kept=[];removed=[];debris=[]
for o in original:
 name=o.name
 zmax=max(v.co.z for v in o.data.vertices)
 keep=False
 if name.startswith(('Punt bottom plank','Punt end bottom closure','Transverse bottom frame')):
  keep=True
 elif name.startswith(('Longitudinal hull side plank','Raked square transom plank')) and zmax<.38:
  keep=True
  if zmax>.25:
   for v in o.data.vertices:
    if v.co.z>.25:v.co.z-=.035*(.5+.5*math.sin(v.co.x*7.1+v.co.y*3.4))
 elif name.startswith('Interior removable floorboard'):
  # Some floorboards survive supported by the original transverse frames.
  keep=rng.random()<.55
 elif name.startswith('Plain timber mooring post'):
  for v in o.data.vertices:v.co.z*=.36
  keep=True
 elif name.startswith('Interior side frame'):
  keep=False
 if keep:
  o.data.materials.clear();o.data.materials.append(material);kept.append(o)
 else:
  removed.append(name);bpy.data.objects.remove(o,do_unlink=True)
# Broken approach planks rest on the dry bank. Their lengths/positions are
# fictional damage; do not retain a ramp pointing at a consumed gunwale.
for j in range(5):
 bpy.ops.mesh.primitive_cube_add(size=1,location=(.19+j*.18,2.03+rng.uniform(-.08,.08),.138))
 o=bpy.context.object;o.name='Charred ramp remnant %02d'%j
 o.scale=(.12,rng.uniform(.72,.90),.036)
 o.rotation_euler.z=rng.uniform(-.07,.07)
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 # Source-space bank is at .12 (review space .15), so each board bears on it.
 o.data.materials.append(material)
 kept.append(o);debris.append(o)
solid_checks=[]
for o in kept:
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
 row=dict(name=o.name,nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),signed_volume_m3=bm.calc_volume(signed=True),minimum_face_area=min(f.calc_area()for f in bm.faces))
 assert row['nonmanifold_edges']==0 and row['signed_volume_m3']>0 and row['minimum_face_area']>1e-12,row
 solid_checks.append(row);bm.to_mesh(o.data);bm.free()
 # Hull planks bear on the original bottom/frames; bank boards on the bank.
bpy.context.view_layer.update()
for o in kept:o.matrix_world=normalize@o.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for o in kept:o.select_set(True)
bpy.context.view_layer.objects.active=kept[0]
bpy.ops.object.join()
ruin=bpy.context.object;ruin.name='SM_HoldingRuin_SmugglersLanding'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
assert not bpy.data.actions and not any(o.type=='ARMATURE' for o in bpy.data.objects)
coords=[v.co.copy() for v in ruin.data.vertices]
bounds={'min':[min(p[k] for p in coords) for k in range(3)],'max':[max(p[k] for p in coords) for k in range(3)]}
assert abs(bounds['min'][2])<.0001 and bounds['max'][2]<.8
bsdf=material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value=.96
project=OUT/'SmugglersLanding-Ruin.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
ruin.matrix_world=Matrix.Rotation(math.pi,4,'Z')
fbx=OUT/'SM_HoldingRuin_SmugglersLanding.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
    bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_tspace=True,path_mode='STRIP',embed_textures=False)
ruin.matrix_world=Matrix.Identity(4)
with bpy.data.libraries.load(str(base_project),link=False) as (src,dst):
    dst.objects=json.loads((BASE/'base-v005/base.json').read_text())['objects']
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
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'SmugglersLanding-Ruin-Review.blend'))
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
print('SMUGGLERS_LANDING_RUIN_AUTHORED',flush=True)
