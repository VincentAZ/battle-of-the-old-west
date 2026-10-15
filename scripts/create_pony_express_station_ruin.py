"""Separate fictional ruin of the reviewed reconstructed stone stage station."""
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
BASE=ROOT/'art/western/holdings/expansion-review-v001/pony-express-station'
OUT=BASE/'ruin-source-v004'
BRIEF=BASE/'ruin-brief-v004.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text())
source=BASE/brief['preservation']['source']
base_project=BASE/brief['preservation']['base']
assert sha(source)==brief['preservation']['sha256']
assert sha(base_project)==brief['preservation']['base_sha256']
assert not OUT.exists();OUT.mkdir()
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
original=[o for o in bpy.context.scene.objects if o.type=='MESH']
points=[o.matrix_world@v.co for o in original for v in o.data.vertices]
lo=Vector([min(p[k] for p in points) for k in range(3)])
hi=Vector([max(p[k] for p in points) for k in range(3)])
scale=5.5/max(hi.x-lo.x,hi.y-lo.y)
shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z))
normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)
material=original[0].data.materials[0].copy();material.name='M_PonyExpressStation_AuthoredRuin'
image=np.asarray(Image.open(BASE/'local-source-v003/PonyExpressStation_BaseColor.png').convert('RGB')).astype(np.float32)
yy,xx=np.mgrid[0:2048,0:2048]
patch=(np.sin(xx*.017+np.sin(yy*.023)*1.8)*np.cos(yy*.013)+1)/2
soot=.18+.52*patch;carbon=np.array([27,23,19],dtype=np.float32)
image=image*(1-soot[...,None])+carbon*soot[...,None]
for index in (6,7,8,11):
 x,y=(index%4)*512+8,(index//4)*682+8
 image[y:y+659,x:x+497]=np.array([30,23,17])+np.sin(xx[y:y+659,x:x+497]*.17)[...,None]*4
image[690:1349,520:1017]=np.array([102,92,78])+np.random.default_rng(1890).integers(-6,7,(659,497,1))
texture=OUT/'PonyExpressStation_Ruin_BaseColor.png'
Image.fromarray(np.clip(image,0,255).astype(np.uint8)).save(texture)
for node in material.node_tree.nodes:
 if node.type=='TEX_IMAGE':node.image=bpy.data.images.load(str(texture));node.image.pack()
kept=[];removed=[]

def cap(x,y):
 return .76+.20*math.sin(x*2.7+y*.81)+.16*math.sin(y*2.3-x*.9)

def uv_region(obj,index):
 uv=obj.data.uv_layers.active or obj.data.uv_layers.new()
 x0,y0=(index%4)*512+8,(index//4)*682+8
 for face in obj.data.polygons:
  axis=max(range(3),key=lambda k:abs(face.normal[k]));a,b=[k for k in range(3) if k!=axis]
  points=[obj.data.vertices[i].co for i in face.vertices]
  low=[min(v[k] for v in points) for k in range(3)];high=[max(v[k] for v in points) for k in range(3)]
  for loop in face.loop_indices:
   v=obj.data.vertices[obj.data.loops[loop].vertex_index].co
   u=(v[a]-low[a])/max(1.e-6,high[a]-low[a]);w=(v[b]-low[b])/max(1.e-6,high[b]-low[b])
   uv.data[loop].uv=((x0+5+u*486)/2048,1-(y0+653-w*648)/2048)

def box(name,centre,size,index):
 bpy.ops.mesh.primitive_cube_add(size=1,location=centre)
 o=bpy.context.object;o.name=name;o.dimensions=size
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 o.data.materials.append(material);uv_region(o,index);kept.append(o);return o

stone_examples=[]
for o in original:
 o.data.materials.clear();o.data.materials.append(material)
 world=[o.matrix_world@v.co for v in o.data.vertices]
 lower=Vector([min(v[k] for v in world) for k in range(3)]);upper=Vector([max(v[k] for v in world) for k in range(3)])
 if o.name.startswith('Solid mortar wall'):
  axis=0 if upper.x-lower.x>upper.y-lower.y else 1
  width=upper[axis]-lower[axis];count=max(1,math.ceil(width/.17))
  for n in range(count):
   centre=(lower+upper)/2;centre[axis]=lower[axis]+(n+.5)*width/count
   top=min(upper.z,cap(centre.x,centre.y))
   if top<=lower.z+.03:continue
   centre.z=(lower.z+top)/2;size=upper-lower;size[axis]=width/count;size.z=top-lower.z
   box('Broken mortar wall core',centre,size,5)
 elif o.name.startswith('Small faceted rubble face'):
  centre=(lower+upper)/2;top=cap(centre.x,centre.y)
  if lower.z<top-.025:
   if upper.z>top:
    bm=bmesh.new();bm.from_mesh(o.data)
    inverse=o.matrix_world.inverted()
    bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=1.e-6,plane_co=inverse@Vector((0,0,top)),plane_no=(0,0,1),clear_outer=True,clear_inner=False)
    edges=[e for e in bm.edges if e.is_boundary]
    if edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()
   kept.append(o)
   inner=o.copy();inner.data=o.data.copy();bpy.context.collection.objects.link(inner)
   axis=1 if abs(centre.y)>2.50 else 0
   plane=math.copysign(2.59 if axis==1 else 1.74,centre[axis])
   for vertex in inner.data.vertices:vertex.co[axis]=2*plane-vertex.co[axis]
   inner.name='Reconstructed inner rubble';kept.append(inner);continue
 removed.append(o.name);bpy.data.objects.remove(o,do_unlink=True)

rng=random.Random(1890)
occupied=[]
def overlap(a,b):
 x,y,w,h,t=a;u,v,p,q,s=b
 for r in (t,t+math.pi/2,s,s+math.pi/2):
  radius=w/2*abs(math.cos(t-r))+h/2*abs(math.sin(t-r))+p/2*abs(math.cos(s-r))+q/2*abs(math.sin(s-r))+.008
  if abs((x-u)*math.cos(r)+(y-v)*math.sin(r))>radius:return False
 return True
for i in range(115):
 timber=i<18
 dims=(rng.uniform(.35,.68),.045,.035) if timber else (rng.uniform(.12,.29),rng.uniform(.09,.18),rng.uniform(.06,.13))
 for attempt in range(10000):
  x,y=rng.uniform(-1.35,1.35),rng.uniform(-2.2,2.2)
  angle=rng.uniform(-math.pi,math.pi);w,h=dims[:2]
  rectangle=(x,y,w,h,angle)
  if abs(x)+(abs(math.cos(angle))*w+abs(math.sin(angle))*h)/2>1.53 or abs(y)+(abs(math.sin(angle))*w+abs(math.cos(angle))*h)/2>2.35:continue
  if not any(overlap(rectangle,b) for b in occupied):break
 else:raise AssertionError(('Unable to place non-overlapping debris',i))
 occupied.append(rectangle)
 o=box('Consumed roof timber' if timber else 'Fallen rubble stone',(x,y,.061/scale+dims[2]/2),dims,7 if timber else rng.randrange(5))
 o.rotation_euler.z=angle
 if not timber:
  for v in o.data.vertices:
   v.co.x*=rng.uniform(.75,1);v.co.y*=rng.uniform(.75,1)

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
ruin=bpy.context.object;ruin.name='SM_HoldingRuin_PonyExpressStation'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
assert not bpy.data.actions and not any(o.type=='ARMATURE' for o in bpy.data.objects)
coords=[v.co.copy() for v in ruin.data.vertices]
bounds={'min':[min(p[k] for p in coords) for k in range(3)],'max':[max(p[k] for p in coords) for k in range(3)]}
assert abs(bounds['min'][2])<.0001 and bounds['max'][2]<1.4
bsdf=material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value=.96
project=OUT/'PonyExpressStation-Ruin.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
ruin.matrix_world=Matrix.Rotation(math.pi,4,'Z')
fbx=OUT/'SM_HoldingRuin_PonyExpressStation.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
    bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_tspace=True,path_mode='STRIP',embed_textures=False)
ruin.matrix_world=Matrix.Identity(4)
with bpy.data.libraries.load(str(base_project),link=False) as (src,dst):
    dst.objects=json.loads((base_project.parent/'base.json').read_text())['objects']
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
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'PonyExpressStation-Ruin-Review.blend'))
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
print('PONY_EXPRESS_STATION_RUIN_AUTHORED',flush=True)
