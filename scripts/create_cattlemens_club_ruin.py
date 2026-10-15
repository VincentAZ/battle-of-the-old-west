"""Separate static CattlemensClub ruin: no game export or import."""
from pathlib import Path
import hashlib,json,math,random
import bpy,bmesh
import numpy as np
from PIL import Image,ImageDraw
from mathutils import Matrix,Vector
from bpy_extras.object_utils import world_to_camera_view
R=Path(__file__).resolve().parents[1];B=R/'art/western/holdings/expansion-review-v001/cattlemens-club'
OUT=B/'ruin-source-v001';BRIEF=B/'ruin-brief-v001.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text());assert brief['pre_modeling_review']['completed']
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
for p,h in brief['source_records'].items():assert sha(R/p)==h
assert not OUT.exists();OUT.mkdir()
source=B/brief['preservation']['source'];base_project=B/brief['preservation']['base']
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
original=[o for o in bpy.context.scene.objects if o.type=='MESH']
pts=[o.matrix_world@v.co for o in original for v in o.data.vertices]
lo=Vector([min(p[i] for p in pts) for i in range(3)]);hi=Vector([max(p[i] for p in pts) for i in range(3)])
scale=5.5/max(hi.x-lo.x,hi.y-lo.y);shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z));normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)
# Copy material data. Surface change is confined to the derivative, and glass
# transmission is deliberately absent because no glass components survive.
mat=bpy.data.materials.new('M_CattlemensClub_CharredTimber');mat.use_nodes=True
bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.94
bsdf.inputs['Metallic'].default_value=0
rng=random.Random(1886);nrng=np.random.default_rng(1886)
old=np.asarray(Image.open(B/'local-source-v010/CattlemensClub_BaseColor.png').convert('RGB')).astype(float)
coarse=np.asarray(Image.fromarray(nrng.integers(0,256,(56,56),dtype=np.uint8)).resize((2048,2048),Image.Resampling.BICUBIC)).astype(float)
variation=(coarse/255-.5)*14+nrng.uniform(-2,2,(2048,2048))
luma=old@np.array([.2126,.7152,.0722])
pixels=np.clip(luma[...,None]*.13+np.array([19,12,7])+variation[...,None],0,255).astype(np.uint8)
# Preserve mineral colour patches exactly; the source's paint becomes char.
for ys,xs in [(slice(520,1017),slice(8,505)),(slice(520,1017),slice(520,1017)),(slice(520,1017),slice(1544,2041)),(slice(1032,1529),slice(8,505)),(slice(1032,1529),slice(1544,2041))]:
 pixels[ys,xs]=old[ys,xs].astype(np.uint8)
# Unused former glass patch supplies individual slate-unit colours, rather than
# repeating the roof's multi-course pattern on each loose fragment.
pixels[1032:1529,1032:1273]=(62,80,95)
pixels[1032:1529,1280:1529]=(95,64,88)
texture=OUT/'CattlemensClub_Ruin_BaseColor.png';Image.fromarray(pixels).save(texture)
node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack();mat.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])

kept=[];removed=[];preserved=[];roles={}
for o in original:
 world=[o.matrix_world@v.co for v in o.data.vertices]
 for v,p in zip(o.data.vertices,world):v.co=p
 o.matrix_world=Matrix.Identity(4)
def assign(o,role):
 o.data.materials.clear();o.data.materials.append(mat);kept.append(o);roles[o.name]=role
def char_bevel(o,width=.004):
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
 m=o.modifiers.new('Rounded consumed timber edges','BEVEL');m.width=width;m.segments=1
 bpy.ops.object.modifier_apply(modifier=m.name)

regions={'wood':(1032,520,1528,1016),'slate':(1032,1032,1272,1528),'purple_slate':(1280,1032,1528,1528),'sign':(8,8,2040,480),'brick':(8,520,504,1016),'brick_plain':(1544,1032,2040,1528)}
def uvmap(o,key):
 mesh=o.data;mesh.update();uv=mesh.uv_layers.active or mesh.uv_layers.new()
 for f in mesh.polygons:
  axis=max(range(3),key=lambda k:abs(f.normal[k]));axes=[k for k in range(3) if k!=axis]
  points=[mesh.vertices[mesh.loops[i].vertex_index].co for i in f.loop_indices]
  low=[min(p[k] for p in points) for k in range(3)];high=[max(p[k] for p in points) for k in range(3)]
  tile='sign' if key=='sign' and f.normal.y<-.5 else 'wood' if key=='sign' else key
  a,b=axes
  if tile not in ('sign','brick'):b=max(axes,key=lambda k:high[k]-low[k]);a=next(k for k in axes if k!=b)
  x0,y0,x1,y1=regions[tile];margin=2 if tile=='brick' else 8
  for li in f.loop_indices:
   p=mesh.vertices[mesh.loops[li].vertex_index].co
   u=(p[a]-low[a])/max(high[a]-low[a],1e-9);v=(p[b]-low[b])/max(high[b]-low[b],1e-9)
   if tile=='sign':u*=.53
   if tile=='brick':u=(p[a]+2.40)/4.8;v=p.z/5.2
   uv.data[li].uv=((x0+margin+u*(x1-x0-2*margin))/2048,1-(y1-margin-v*(y1-y0-2*margin))/2048)

# Slice actual lower wall geometry, closing each independently capped remnant.
profiles={
 'front':(0,-2.4,2.4,[.96,1.28,1.05,1.32,1.14,1.50,1.06]),
 'rear':(0,-2.4,2.4,[1.34,.94,1.62,1.28,1.13,1.53,1.38]),
 'left':(1,-1.35,1.35,[1.20,1.45,1.02,1.68,1.33,1.15,1.29]),
 'right':(1,-1.35,1.35,[1.34,1.19,1.54,1.07,1.41,1.28,1.55])}

def clipped_wall(o,profile,key):
 axis,left,right,caps=profile
 low=[min(v.co[k] for v in o.data.vertices) for k in range(3)]
 high=[max(v.co[k] for v in o.data.vertices) for k in range(3)]
 for i,(hl,hr) in enumerate(zip(caps,caps[1:])):
  a=left+(right-left)*i/(len(caps)-1);b=left+(right-left)*(i+1)/(len(caps)-1)
  if min(b,high[axis])-max(a,low[axis])<1e-6 or low[2]>=max(hl,hr):continue
  bm=bmesh.new();bm.from_mesh(o.data)
  slope=(hr-hl)/(b-a)
  planes=[]
  for position,sign in [(a,-1),(b,1)]:
   co=Vector((0,0,0));co[axis]=position;n=Vector((0,0,0));n[axis]=sign
   planes.append((co,n))
  co=Vector((0,0,hl));co[axis]=a;n=Vector((0,0,1));n[axis]=-slope
  planes.append((co,n))
  for co,n in planes:
   if not bm.faces:break
   result=bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                               plane_co=co,plane_no=n,dist=1e-7,clear_outer=True,clear_inner=False)
   bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
   bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-7)
   boundary=[e for e in bm.edges if e.is_boundary]
   if boundary:bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
  if not bm.faces:bm.free();continue
  bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update()
  assert all(e.is_manifold for e in bm.edges),(o.name,i)
  if bm.calc_volume(signed=True)<1e-9:bm.free();continue
  mesh=bpy.data.meshes.new('Clipped original clubhouse masonry');bm.to_mesh(mesh);bm.free()
  part=bpy.data.objects.new('Remnant '+o.name+' section '+str(i),mesh)
  bpy.context.collection.objects.link(part);uvmap(part,key);assign(part,'masonry_wall' if key=='brick' else 'wall')

preserve_prefixes=('Masonry ground plinth','Painted main floor deck','Front veranda deck','Right veranda deck','Front veranda joist','Side veranda joist','Veranda foundation pier','Side veranda foundation pier','Front stair tread and riser','Side stair tread and riser','Front stair cheek','Side stair cheek','Veranda post foot')
for o in original:
 name=o.name;bottom=min(v.co.z for v in o.data.vertices);top=max(v.co.z for v in o.data.vertices)
 centre=sum((v.co for v in o.data.vertices),Vector())/len(o.data.vertices)
 if name.startswith(preserve_prefixes):
  assign(o,'foundation' if 'pier' in name or 'plinth' in name else 'retained_timber');preserved.append(name);continue
 if name.startswith(('Front masonry','Rear masonry','West masonry','East masonry')):
  side={'Front':'front','Rear':'rear','West':'left','East':'right'}[name.split()[0]]
  clipped_wall(o,profiles[side],'brick')
 elif name.startswith(('Veranda post','Stair newel','Side stair newel')):
  target=rng.uniform(1.00,1.37) if name.startswith('Veranda post') else rng.uniform(.76,.93)
  for v in o.data.vertices:
   fraction=(v.co.z-bottom)/(top-bottom)
   v.co.z=bottom+fraction*(target-bottom+.10*(v.co.x-centre.x)-.06*(v.co.y-centre.y))
  o.name='Charred stump '+name;char_bevel(o,.004);uvmap(o,'wood');assign(o,'stump');continue
 elif name.startswith('Front paneled entry'):
  for v in o.data.vertices:
   fraction=(v.co.z-bottom)/(top-bottom)
   v.co.z=bottom+fraction*(.91-bottom+.06*(v.co.x-centre.x))
  o.name='Charred lower entry';char_bevel(o,.003);uvmap(o,'wood');assign(o,'wall');continue
 removed.append(name);bpy.data.objects.remove(o,do_unlink=True)

def rectangle(x,y,w,h,angle):
 c,s=math.cos(angle),math.sin(angle)
 return [(x+c*a-s*b,y+s*a+c*b) for a,b in [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]]
def overlap(a,b):
 for poly in (a,b):
  for p,q in zip(poly,poly[1:]+poly[:1]):
   axis=(-(q[1]-p[1]),q[0]-p[0]);aa=[x*axis[0]+y*axis[1] for x,y in a];bb=[x*axis[0]+y*axis[1] for x,y in b]
   if max(aa)<min(bb) or max(bb)<min(aa):return False
 return True
def debris(name,loc,dim,rot,key):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dim
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 for v in o.data.vertices:
  if key=='wood':v.co.x+=(.006 if v.co.y>0 else -.004)*(1 if v.co.x>0 else -1)
  elif key in ('slate','purple_slate') and v.co.x>0 and v.co.y>0:v.co.x-=.05
  elif key=='sign' and v.co.x>0:v.co.x-=.028 if v.co.z>0 else .065
 uvmap(o,key);char_bevel(o,.001 if key in ('slate','purple_slate') else .003 if key=='brick_plain' else .004)
 o.rotation_euler=rot;bpy.context.view_layer.update()
 bottom=min((o.matrix_world@v.co).z for v in o.data.vertices);o.location.z+=.60-bottom
 assign(o,'masonry_debris' if key=='brick_plain' else 'fallen');return o

def plan_debris(rng):
 occupied=[rectangle(0,-.38,1.19,.28,.13)];planned=[];specs=[]
 for i in range(90):
  key='brick_plain' if i<48 else 'wood' if i<76 else 'slate' if i<85 else 'purple_slate'
  w=rng.uniform(.18,.28) if key=='brick_plain' else rng.uniform(.35,.70) if key=='wood' else rng.uniform(.23,.35)
  h=rng.uniform(.09,.13) if key=='brick_plain' else rng.uniform(.055,.085) if key=='wood' else rng.uniform(.14,.22)
  height=rng.uniform(.07,.11) if key=='brick_plain' else rng.uniform(.04,.065) if key=='wood' else .015
  specs.append((key,w,h,height))
 for key,w,h,height in sorted(specs,key=lambda spec:spec[1]*spec[2],reverse=True):
  for attempt in range(16000):
   x,y=rng.uniform(-2.02,2.02),rng.uniform(-1.15,1.15);angle=rng.uniform(-math.pi,math.pi)
   shape=rectangle(x,y,w+.024,h+.018,angle)
   if not all(-2.04<a<2.04 and -1.18<b<1.18 for a,b in shape):continue
   if any(overlap(shape,p) for p in occupied):continue
   occupied.append(shape);planned.append((key,w,h,height,x,y,angle));break
  else:raise AssertionError(('Could not place debris',key,w,h,len(planned)))
 return planned
layout=plan_debris(rng)
debris('Fallen partial clubhouse sign',(0,-.38,.65),(1.10,.035,.22),(-math.pi/2,0,.13),'sign')
for key,w,h,height,x,y,angle in layout:
 debris('Fallen brick fragment' if key=='brick_plain' else 'Fallen slate fragment' if key in ('slate','purple_slate') else 'Fallen charred timber',
        (x,y,.65),(w,h,height),(0,0,angle),key)
for x,y,angle in [(-1.35,-1.92,.10),(.78,-1.94,-.13),(2.70,-.58,1.50),(2.71,.67,1.42)]:
 debris('Fallen veranda timber',(x,y,.65),(.65,.085,.063),(0,0,angle),'wood')
# Verify actual solids before joining; normalized source coordinates stay available
# in a separate components file for independent support and preservation checks.
bpy.context.view_layer.update();solids=[]
for o in kept:
 o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update()
 assert all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True)>0,o.name
 assert all(f.calc_area()>1e-12 for f in bm.faces),o.name
 solids.append(dict(name=o.name,role=roles[o.name],closed=True,volume_m3=bm.calc_volume(signed=True)));bm.to_mesh(o.data);bm.free()
components=OUT/'CattlemensClub-Ruin-Components.blend';bpy.ops.wm.save_as_mainfile(filepath=str(components))
for o in kept:o.matrix_world=normalize@o.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for o in kept:o.select_set(True)
bpy.context.view_layer.objects.active=kept[0];bpy.ops.object.join();ruin=bpy.context.object;ruin.name='SM_HoldingRuin_CattlemensClub'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
coords=[v.co for v in ruin.data.vertices];bounds=dict(min=[min(p[i] for p in coords) for i in range(3)],max=[max(p[i] for p in coords) for i in range(3)])
assert abs(bounds['min'][2])<1e-6 and bounds['max'][2]<1.65
project=OUT/'CattlemensClub-Ruin.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
# Import only the unchanged static setting objects for honest contextual renders.
with bpy.data.libraries.load(str(base_project),link=False) as (src,dst):dst.objects=['Holding_Base_Ground']
for o in dst.objects:bpy.context.collection.objects.link(o)
bpy.context.view_layer.update()
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
scene.render.threads_mode='FIXED';scene.render.threads=8;scene.render.resolution_x=1280;scene.render.resolution_y=960;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Ruin daylight');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.28,.31,.35,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.45
scene.view_settings.view_transform='AgX'
for name,pos,power,size in [('Clear warm key',(-5,-6,9),1900,6),('Sky fill',(5,3,8),1100,7)]:
 data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
 o=bpy.data.objects.new(name,data);scene.collection.objects.link(o);o.location=pos;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
views={}
for name,pos in [('front',(7,-11,7)),('rear',(-7,11,7)),('right',(12,2,6)),('overhead',(0,-.01,15))]:
 data=bpy.data.cameras.new(name);data.type='ORTHO';camera=bpy.data.objects.new('Review_'+name,data);scene.collection.objects.link(camera)
 camera.location=pos;camera.rotation_euler=(Vector((0,0,.4))-camera.location).to_track_quat('-Z','Y').to_euler()
 bpy.context.view_layer.update()
 right=camera.rotation_euler.to_quaternion()@Vector((1,0,0));up=camera.rotation_euler.to_quaternion()@Vector((0,1,0));pts=[o.matrix_world@v.co for o in scene.objects if o.type=='MESH' for v in o.data.vertices]
 xs=[(p-camera.location).dot(right) for p in pts];ys=[(p-camera.location).dot(up) for p in pts];camera.location+=right*((max(xs)+min(xs))/2)+up*((max(ys)+min(ys))/2);camera.data.ortho_scale=1.15*max(max(xs)-min(xs),(max(ys)-min(ys))/.75)
 scene.camera=camera;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
 assert all(0<=p.x<=1 and 0<=p.y<=1 and p.z>0 for p in [world_to_camera_view(scene,camera,o.matrix_world@v.co) for o in scene.objects if o.type=='MESH' for v in o.data.vertices]),name
 views[name]=sha(OUT/(name+'.png'))
review=OUT/'CattlemensClub-Ruin-Review.blend';bpy.ops.wm.save_as_mainfile(filepath=str(review))
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,normalization=dict(scale=scale,shift=list(shift)),triangles=triangles,bounds_m=bounds,removed_parts=removed,project_sha256=sha(project),review_project_sha256=sha(review),components_project_sha256=sha(components),base_project_sha256=sha(base_project),texture_sha256=sha(texture),views=views,imported=False,game_exported=False,component_count=len(solids),component_solids=solids,preserved_geometry=preserved,fallen_timbers=32,fallen_slate_fragments=14,fallen_bricks=48,fallen_signs=1,limitations=brief['uncertainties']),indent=2)+'\n')
print('CATTLEMENS_CLUB_RUIN_AUTHORED',triangles,len(solids),flush=True)
