"""Author a separate grounded Gallows ruin; historical scope is in the pinned brief."""
import hashlib,json,math,random
from pathlib import Path
import bpy,bmesh
import numpy as np
from PIL import Image
from mathutils import Matrix,Vector
from bpy_extras.object_utils import world_to_camera_view
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/western/holdings/expansion-review-v001/gallows'
OUT=BASE/'ruin-source-v003'
BRIEF=BASE/'ruin-brief-v003.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text());source=BASE/brief['preservation']['source'];base_project=BASE/brief['preservation']['base']
assert sha(source)==brief['preservation']['sha256'] and sha(base_project)==brief['preservation']['base_sha256']
assert not OUT.exists();OUT.mkdir()
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
original=[o for o in bpy.context.scene.objects if o.type=='MESH']
points=[o.matrix_world@v.co for o in original for v in o.data.vertices]
lo=Vector([min(p[k] for p in points) for k in range(3)]);hi=Vector([max(p[k] for p in points) for k in range(3)])
scale=5/max(hi.x-lo.x,hi.y-lo.y);shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z))
normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)
material=original[0].data.materials[0].copy();material.name='M_Gallows_AuthoredRuin'
yy,xx=np.mgrid[0:2048,0:2048]
grain=np.sin(xx*.18+np.sin(yy*.006)*2)+.4*np.sin(xx*.43+yy*.003)
image=np.empty((2048,2048,3),dtype=np.float32)
image[:]=np.array([36,28,21])+grain[...,None]*4
# Keep natural char colours; patchy whitewash survives only on retained heavy posts.
patch=np.sin(xx*.015+np.sin(yy*.012)*1.2)*np.cos(yy*.009)
weight=np.clip((patch-.68)*2,0,.15)
image[:,:512]=image[:,:512]*(1-weight[:,:512,None])+np.array([227,217,195])*weight[:,:512,None]
image[:,1024:1536]=np.array([39,35,30])+grain[:,1024:1536,None]*2
texture=OUT/'Gallows_Ruin_BaseColor.png';Image.fromarray(np.clip(image,0,255).astype(np.uint8)).save(texture)
for n in material.node_tree.nodes:
 if n.type=='TEX_IMAGE':n.image=bpy.data.images.load(str(texture));n.image.pack()
removed=[o.name for o in original]
for o in original:bpy.data.objects.remove(o,do_unlink=True)
kept=[];debris=[];rng=random.Random(1889);occupied=[]
def rect(x,y,length,width,angle):
 c,s=math.cos(angle),math.sin(angle)
 return [(x+a*c-b*s,y+a*s+b*c) for a,b in [(-length/2,-width/2),(length/2,-width/2),(length/2,width/2),(-length/2,width/2)]]
def intersects(a,b):
 for poly in (a,b):
  for i in range(2):
   dx=poly[i+1][0]-poly[i][0];dy=poly[i+1][1]-poly[i][1];norm=math.hypot(dx,dy);axis=(-dy/norm,dx/norm)
   av=[x*axis[0]+y*axis[1] for x,y in a];bv=[x*axis[0]+y*axis[1] for x,y in b]
   if max(av)+.025<min(bv) or max(bv)+.025<min(av):return False
 return True
def timber(name,x,y,length,width,height,angle=0,tile=1):
 bpy.ops.mesh.primitive_cube_add(size=1)
 o=bpy.context.object;o.name=name;o.dimensions=(length,width,height)
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 mod=o.modifiers.new('Charred rounded corners','BEVEL');mod.width=min(.018,height*.12,width*.12);mod.segments=1
 bpy.ops.object.modifier_apply(modifier=mod.name)
 # Grain follows the long direction, with every bevel remaining on its atlas strip.
 uv=o.data.uv_layers.active or o.data.uv_layers.new();axis=max(range(3),key=lambda i:o.dimensions[i])
 vs=[v.co for v in o.data.vertices];a=[min(v[i] for v in vs) for i in range(3)];d=[max(v[i] for v in vs)-a[i] for i in range(3)]
 for face in o.data.polygons:
  across=max((i for i in range(3) if i!=axis),key=lambda i:d[i]*(1-abs(face.normal[i])))
  for li in face.loop_indices:
   v=o.data.vertices[o.data.loops[li].vertex_index].co;uv.data[li].uv=((tile+.02+.96*(v[across]-a[across])/d[across])/4,.02+.96*(v[axis]-a[axis])/d[axis])
 o.data.materials.append(material);o.rotation_euler.z=angle;o.location=(x,y,lo.z+height/2)
 kept.append(o);debris.append(o);occupied.append(rect(x,y,length,width,angle));return o
for i,(x,y) in enumerate(( (x,y) for x in (-2.88,0,2.88) for y in (-2.25,2.25))):
 timber('Charred original platform support %02d'%i,x,y,.285,.285,[.96,.57,.75,.44,.84,.61][i],tile=0)
for i,x in enumerate((-2.5908,2.5908)):
 timber('Charred original tall upright %02d'%i,x,-1.72,.285,.285,[.78,1.12][i],tile=0)
timber('Fallen heavy crossbeam',0,-.65,4.76,.25,.24,angle=.045)
for i in range(16):
 for attempt in range(3000):
  x,y=rng.uniform(-2.45,2.45),rng.uniform(-1.4,1.9)
  length,width=rng.uniform(.70,1.75),.13 if i<12 else .15
  angle=rng.uniform(0,math.tau);candidate=rect(x,y,length,width,angle)
  if any(abs(px)>2.7 or py>2.07 or py< -1.57 for px,py in candidate):continue
  if any(intersects(candidate,existing) for existing in occupied):continue
  timber(('Fallen roof rafter ' if i<12 else 'Fallen floor joist ')+str(i),x,y,length,width,.19,angle=angle)
  break
 else:raise AssertionError('Unable to place separated ruin timber')
for i in range(3):
 timber('Fallen stair stringer %02d'%i,2.15,-2.9-i*.63,.92,.17,.22,angle=.30 if i%2 else -.20)
bpy.context.view_layer.update()
assert all(abs(min((o.matrix_world@v.co).z for v in o.data.vertices)-lo.z)<1e-6 for o in kept)
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
ruin=bpy.context.object;ruin.name='SM_HoldingRuin_Gallows'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
assert not bpy.data.actions and not any(o.type=='ARMATURE' for o in bpy.data.objects)
coords=[v.co.copy() for v in ruin.data.vertices]
bounds={'min':[min(p[k] for p in coords) for k in range(3)],'max':[max(p[k] for p in coords) for k in range(3)]}
assert abs(bounds['min'][2])<.0001 and bounds['max'][2]<1.4
bsdf=material.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Roughness'].default_value=.96
project=OUT/'Gallows-Ruin.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(project))
ruin.matrix_world=Matrix.Rotation(math.pi,4,'Z')
fbx=OUT/'SM_HoldingRuin_Gallows.fbx'
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
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Gallows-Ruin-Review.blend'))
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
print('GALLOWS_RUIN_AUTHORED',flush=True)
