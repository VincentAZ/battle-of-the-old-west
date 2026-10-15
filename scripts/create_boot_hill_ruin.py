"""Author Boot Hill's sourced fictional fire condition as a separate static asset."""
import hashlib,json,math,random
from pathlib import Path
import bpy,bmesh
import numpy as np
from PIL import Image
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/western/holdings/expansion-review-v001/boot-hill'
OUT=BASE/'ruin-source-v002';BRIEF=BASE/'ruin-brief-v002.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text());source=BASE/brief['preservation']['source'];base_project=BASE/brief['preservation']['base']
for key,digest in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(BASE/brief['preservation'][key])==brief['preservation'][digest]
for path,digest in brief['source_records'].items():assert sha(ROOT/path)==digest
assert not OUT.exists();OUT.mkdir()
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
original=[o for o in bpy.context.scene.objects if o.type=='MESH']
points=[o.matrix_world@v.co for o in original for v in o.data.vertices]
lo=Vector([min(p[k]for p in points)for k in range(3)]);hi=Vector([max(p[k]for p in points)for k in range(3)])
scale=5.5/max(hi.x-lo.x,hi.y-lo.y);shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z));normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)
for obj in original:obj.data.transform(obj.matrix_world);obj.matrix_world=Matrix.Identity(4)
hill=bpy.data.objects['Low prairie cemetery rise']
surface=BVHTree.FromPolygons([v.co for v in hill.data.vertices],[p.vertices for p in hill.data.polygons])
preserved={o.name:[tuple(v.co)for v in o.data.vertices]for o in original if o==hill or o.name.startswith('Low earth grave mound')}
material=original[0].data.materials[0].copy();material.name='M_BootHill_AuthoredRuin'
pixels=np.asarray(Image.open(BASE/'local-source-v001/BootHill_BaseColor.png').convert('RGB')).copy()
yy,xx=np.mgrid[0:2048,0:2048]
grain=np.sin(xx*.17+np.sin(yy*.015));cracks=np.sin(xx*.038+np.sin(yy*.023))>.87
char=np.clip(np.array([38,27,18])+grain[...,None]*6-cracks[...,None]*11,0,255).astype(np.uint8)
pixels[8:1017,8:1009]=char[8:1017,8:1009]
pixels[1040:2041,1040:1537]=char[1040:2041,1040:1537]
# The hill receives one planar UV patch, with unburned green around the fire edge.
py,px=np.mgrid[0:1001,0:1001];u=(px-500)/500;v=(py-500)/500
radius=np.sqrt(u*u+v*v);edge=.79+.024*np.sin(px*.027)*np.sin(py*.021)
weight=np.clip((edge-radius)/.14,0,1)
old=pixels[1040:2041,8:1009].astype(float)
noise_rng=np.random.default_rng(1884)
coarse=Image.fromarray(noise_rng.integers(0,256,(45,45),dtype=np.uint8)).resize((1001,1001),Image.Resampling.BICUBIC)
variation=(np.asarray(coarse).astype(float)/255-.5)*14+noise_rng.uniform(-3,3,(1001,1001))
ash=np.array([31,28,23])+variation[...,None]
pixels[1040:2041,8:1009]=np.clip(old*(1-weight[...,None])+ash*weight[...,None],0,255)
# Left half of the leaf region is stubble, right half stays native green.
pixels[1040:2041,1560:1800]=char[1040:2041,1560:1800]
texture=OUT/'BootHill_Ruin_BaseColor.png';Image.fromarray(pixels).save(texture)
for node in material.node_tree.nodes:
 if node.type=='TEX_IMAGE':node.image=bpy.data.images.load(str(texture));node.image.pack()
material.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.94
# Re-map only the hill surface; its geometry and the grave-mound UVs are retained.
for face in hill.data.polygons:
 for li in face.loop_indices:
  p=hill.data.vertices[hill.data.loops[li].vertex_index].co
  u=.5+p.x/5.6;v=.5+p.y/5.0
  hill.data.uv_layers.active.data[li].uv=((13+u*990)/2048,1-(2035-v*990)/2048)
rng=random.Random(1884);kept=[];removed=[];burned_blades=0;surviving_blades=0
for obj in original:
 name=obj.name
 if 'crossbar' in name:
  removed.append(name);bpy.data.objects.remove(obj,do_unlink=True);continue
 if name.startswith('Plain plank headboard') or 'upright' in name:
  bottom=min(v.co.z for v in obj.data.vertices);top=max(v.co.z for v in obj.data.vertices);height=rng.uniform(.17,.25)
  for v in obj.data.vertices:v.co.z=bottom+(v.co.z-bottom)*height/(top-bottom)
  obj.name='Charred '+name
 elif name.startswith('Rooted short prairie grass'):
  centre=sum((v.co for v in obj.data.vertices),Vector())/len(obj.data.vertices)
  radius=math.hypot(centre.x/2.8,centre.y/2.5)
  burned=radius<.78
  if burned:
   low=min(v.co.z for v in obj.data.vertices)
   for v in obj.data.vertices:v.co.z=low+(v.co.z-low)*.28
   obj.name='Burned rooted grass stubble';burned_blades+=1
  else:surviving_blades+=1
  for loop in obj.data.uv_layers.active.data:
   u=(loop.uv.x*2048-1565)/470
   loop.uv.x=(1565+u*225+(0 if burned else 240))/2048
 obj.data.materials.clear();obj.data.materials.append(material);kept.append(obj)

def ground(x,y):
 hit,normal,*_=surface.ray_cast(Vector((x,y,3)),Vector((0,0,-1)))
 assert hit is not None,(x,y)
 return hit,normal

# Closed timber remnants are bedded onto the actual sloping hill, beside graves.
fallen=[]
for i,(x,y,angle)in enumerate([(-.72,-1.10,.30),(.70,-.96,-.48),(-.70,1.06,-.20),(.72,1.17,.65),(-.50,.22,.85),(.43,.26,-.35)]):
 hit,normal=ground(x,y)
 bpy.ops.mesh.primitive_cube_add(size=1,location=hit)
 obj=bpy.context.object;obj.name='Fallen charred marker fragment %d'%i
 obj.dimensions=(.48 if i<4 else .39,.23 if i<4 else .075,.054)
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 bevel=obj.modifiers.new('Rounded charred timber corners','BEVEL');bevel.width=.007;bevel.segments=1;bpy.ops.object.modifier_apply(modifier=bevel.name)
 obj.rotation_euler=(normal.to_track_quat('Z','Y').to_matrix().to_4x4()@Matrix.Rotation(angle,4,'Z')).to_euler()
 bpy.context.view_layer.update()
 gaps=[]
 for v in obj.data.vertices:
  p=obj.matrix_world@v.co;hit,_=ground(p.x,p.y);gaps.append(p.z-hit.z)
 obj.location.z-=min(gaps)+.004
 obj.data.materials.append(material)
 for loop in obj.data.uv_layers.active.data:loop.uv=((15+loop.uv.x*980)/2048,1-(15+loop.uv.y*990)/2048)
 kept.append(obj);fallen.append(obj)
# Bake and audit before the lossless join; retain this source for independent contacts.
bpy.context.view_layer.update();solid_checks=[]
for obj in kept:
 obj.data.transform(obj.matrix_world);obj.matrix_world=Matrix.Identity(4)
 bm=bmesh.new();bm.from_mesh(obj.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update()
 if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces));bm.normal_update()
 row=dict(name=obj.name,nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),signed_volume_m3=bm.calc_volume(signed=True),minimum_face_area=min(f.calc_area()for f in bm.faces))
 assert row['nonmanifold_edges']==0 and row['signed_volume_m3']>0 and row['minimum_face_area']>1e-12,row
 bm.to_mesh(obj.data);bm.free();solid_checks.append(row)
for name,coords in preserved.items():assert coords==[tuple(v.co)for v in bpy.data.objects[name].data.vertices],name
components=OUT/'BootHill-Ruin-Components.blend';bpy.ops.wm.save_as_mainfile(filepath=str(components))
for obj in kept:obj.matrix_world=normalize@obj.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for obj in kept:obj.select_set(True)
bpy.context.view_layer.objects.active=kept[0];bpy.ops.object.join()
ruin=bpy.context.object;ruin.name='SM_HoldingRuin_BootHill';bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
coords=[v.co.copy()for v in ruin.data.vertices];bounds={'min':[min(p[k]for p in coords)for k in range(3)],'max':[max(p[k]for p in coords)for k in range(3)]}
assert abs(bounds['min'][2])<.0001 and bounds['max'][2]<.7
project=OUT/'BootHill-Ruin.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
# Review-folder FBX is a static interchange source, not a game import/export package.
ruin.matrix_world=Matrix.Rotation(math.pi,4,'Z');fbx=OUT/'SM_HoldingRuin_BootHill.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_tspace=True,path_mode='STRIP',embed_textures=False)
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
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'BootHill-Ruin-Review.blend'))


for key,digest in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(BASE/brief['preservation'][key])==brief['preservation'][digest]
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,normalization=dict(scale=scale,shift=list(shift)),triangles=triangles,bounds_m=bounds,removed_parts=removed,project_sha256=sha(project),components_project_sha256=sha(components),base_project_sha256=sha(base_project),fbx_sha256=sha(fbx),texture_sha256=sha(texture),views=views,imported=False,component_solids=solid_checks,component_count=len(solid_checks),burned_grass_blades=burned_blades,surviving_grass_blades=surviving_blades,preserved_geometry=list(preserved),limitations=['Fictional damage, not a historical event or fire simulation.','All six graves and hill geometry unchanged; material and aboveground wood/vegetation changes only.','Native condition, repair, regional terrain and gameplay review pending.']),indent=2)+'\n')
print('BOOT_HILL_RUIN_AUTHORED',flush=True)
