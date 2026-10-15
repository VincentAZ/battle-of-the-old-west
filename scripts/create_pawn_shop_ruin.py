"""Separate static PawnShop ruin: no game export or import."""
from pathlib import Path
import hashlib,json,math,random
import bpy,bmesh
import numpy as np
from PIL import Image,ImageDraw
from mathutils import Matrix,Vector
from bpy_extras.object_utils import world_to_camera_view
R=Path(__file__).resolve().parents[1];B=R/'art/western/holdings/expansion-review-v001/pawn-shop'
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
scale=5.0/max(hi.x-lo.x,hi.y-lo.y);shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z));normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)
# Copy material data. Surface change is confined to the derivative, and glass
# transmission is deliberately absent because no glass components survive.
mat=bpy.data.materials.new('M_PawnShop_CharredTimber');mat.use_nodes=True
bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.94
bsdf.inputs['Metallic'].default_value=0
rng=random.Random(1885);nrng=np.random.default_rng(1885)
old=np.asarray(Image.open(B/'local-source-v004/PawnShop_BaseColor.png').convert('RGB')).astype(float)
coarse=np.asarray(Image.fromarray(nrng.integers(0,256,(56,56),dtype=np.uint8)).resize((2048,2048),Image.Resampling.BICUBIC)).astype(float)
variation=(coarse/255-.5)*14+nrng.uniform(-2,2,(2048,2048))
luma=old@np.array([.2126,.7152,.0722])
pixels=np.clip(luma[...,None]*.13+np.array([19,12,7])+variation[...,None],0,255).astype(np.uint8)
# Exact healthy brick, mortar, plain brick and red roof palette patches.
for ys,xs in [(slice(520,1017),slice(8,505)),(slice(520,1017),slice(520,1017)),(slice(520,1017),slice(1544,2041)),(slice(1544,2041),slice(520,1017))]:
 pixels[ys,xs]=old[ys,xs].astype(np.uint8)
texture=OUT/'PawnShop_Ruin_BaseColor.png';Image.fromarray(pixels).save(texture)
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

regions={'wood':(8,1032,504,1528),'roof':(1544,520,2040,1016),'sign':(8,8,2040,480),'brick':(8,520,504,1016),'brick_plain':(520,1544,1016,2040)}
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
   if tile=='brick':u=(p[a]+2.35)/4.7;v=p.z/5.2
   uv.data[li].uv=((x0+margin+u*(x1-x0-2*margin))/2048,1-(y1-margin-v*(y1-y0-2*margin))/2048)

# Slice actual lower wall geometry, closing each independently capped remnant.
profiles={
 'rear':(0,-2.1,2.1,[.91,.69,1.10,.82,.66,1.08,.93]),
 'left':(1,-1.5,1.5,[.61,.89,.75,1.14,.84,.73,.91]),
 'right':(1,-1.5,1.5,[.71,.57,.90,.70,1.08,.82,.93])}
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
  mesh=bpy.data.meshes.new('Clipped original log or lime');bm.to_mesh(mesh);bm.free()
  part=bpy.data.objects.new('Remnant '+o.name+' section '+str(i),mesh)
  bpy.context.collection.objects.link(part);uvmap(part,key);assign(part,'masonry_wall' if key=='brick' else 'wall')

for o in original:
 name=o.name;bottom=min(v.co.z for v in o.data.vertices);top=max(v.co.z for v in o.data.vertices)
 centre=sum((v.co for v in o.data.vertices),Vector())/len(o.data.vertices)
 if name.startswith(('Masonry ground plinth','Entry threshold','Rear threshold')) or (name.startswith('Timber floor deck') and top<.30):
  assign(o,'floor' if name.startswith('Timber floor') else 'foundation');preserved.append(name);continue
 if name.startswith(('Side lower masonry','Rear lower masonry')):
  profile=profiles['rear'] if name.startswith('Rear') else profiles['left' if centre.x<0 else 'right']
  clipped_wall(o,profile,'brick')
 elif name.startswith(('Storefront timber upright','Entry door stile','Front corner pilaster')):
  height=rng.uniform(.39,.67)
  for v in o.data.vertices:
   fraction=(v.co.z-bottom)/(top-bottom)
   v.co.z=bottom+fraction*(height+.10*(v.co.x-centre.x)-.06*(v.co.y-centre.y))
  o.name='Charred stump '+name;char_bevel(o,.004);uvmap(o,'wood');assign(o,'stump');continue
 elif name.startswith(('Display bulkhead','Entry return bulkhead','Entry recessed door')):
  target=.45 if name.startswith('Display') else .41
  for v in o.data.vertices:
   fraction=(v.co.z-bottom)/(top-bottom)
   v.co.z=bottom+fraction*(target-bottom+.06*(v.co.x-centre.x))
  o.name='Charred lower panel '+name;char_bevel(o,.003);uvmap(o,'wood');assign(o,'wall');continue
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
  elif key=='sign' and v.co.x>0:v.co.x-=.028 if v.co.z>0 else .065
 uvmap(o,key);char_bevel(o,.002 if key in ('roof','brick') else .004)
 o.rotation_euler=rot;bpy.context.view_layer.update()
 bottom=min((o.matrix_world@v.co).z for v in o.data.vertices);o.location.z+=.28-bottom
 assign(o,'masonry_debris' if key=='brick_plain' else 'fallen');return o

def plan_debris(rng):
 occupied=[rectangle(0,-.38,1.19,.28,.13)];planned=[];specs=[]
 for i in range(70):
  key='brick_plain' if i<42 else 'wood' if i<66 else 'roof'
  w=rng.uniform(.19,.29) if key=='brick_plain' else rng.uniform(.34,.69) if key=='wood' else rng.uniform(.31,.45)
  h=rng.uniform(.09,.13) if key=='brick_plain' else rng.uniform(.055,.085) if key=='wood' else rng.uniform(.18,.26)
  height=rng.uniform(.07,.11) if key=='brick_plain' else rng.uniform(.04,.065) if key=='wood' else .016
  specs.append((key,w,h,height))
 for key,w,h,height in sorted(specs,key=lambda spec:spec[1]*spec[2],reverse=True):
  for attempt in range(12000):
   x,y=rng.uniform(-1.85,1.85),rng.uniform(-.96,1.22);angle=rng.uniform(-math.pi,math.pi)
   shape=rectangle(x,y,w+.022,h+.014,angle)
   if not all(-1.88<a<1.88 and -.98<b<1.24 for a,b in shape):continue
   if any(overlap(shape,p) for p in occupied):continue
   occupied.append(shape);planned.append((key,w,h,height,x,y,angle));break
  else:raise AssertionError(('Could not place debris',key,w,h,len(planned)))
 return planned
layout=plan_debris(rng)
debris('Fallen partial pawn-shop sign',(0,-.38,.35),(1.10,.035,.22),(-math.pi/2,0,.13),'sign')
for key,w,h,height,x,y,angle in layout:
 debris('Fallen brick fragment' if key=='brick_plain' else 'Fallen red tin fragment' if key=='roof' else 'Fallen charred timber',
        (x,y,.35),(w,h,height),(0,0,angle),key)
# Verify actual solids before joining; normalized source coordinates stay available
# in a separate components file for independent support and preservation checks.
bpy.context.view_layer.update();solids=[]
for o in kept:
 o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update()
 assert all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True)>0,o.name
 assert all(f.calc_area()>1e-12 for f in bm.faces),o.name
 solids.append(dict(name=o.name,role=roles[o.name],closed=True,volume_m3=bm.calc_volume(signed=True)));bm.to_mesh(o.data);bm.free()
components=OUT/'PawnShop-Ruin-Components.blend';bpy.ops.wm.save_as_mainfile(filepath=str(components))
for o in kept:o.matrix_world=normalize@o.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for o in kept:o.select_set(True)
bpy.context.view_layer.objects.active=kept[0];bpy.ops.object.join();ruin=bpy.context.object;ruin.name='SM_HoldingRuin_PawnShop'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
coords=[v.co for v in ruin.data.vertices];bounds=dict(min=[min(p[i] for p in coords) for i in range(3)],max=[max(p[i] for p in coords) for i in range(3)])
assert abs(bounds['min'][2])<1e-6 and bounds['max'][2]<1.4
project=OUT/'PawnShop-Ruin.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
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
review=OUT/'PawnShop-Ruin-Review.blend';bpy.ops.wm.save_as_mainfile(filepath=str(review))
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,normalization=dict(scale=scale,shift=list(shift)),triangles=triangles,bounds_m=bounds,removed_parts=removed,project_sha256=sha(project),review_project_sha256=sha(review),components_project_sha256=sha(components),base_project_sha256=sha(base_project),texture_sha256=sha(texture),views=views,imported=False,game_exported=False,component_count=len(solids),component_solids=solids,preserved_geometry=preserved,fallen_timbers=24,fallen_tin_fragments=4,fallen_bricks=42,fallen_signs=1,limitations=brief['uncertainties']),indent=2)+'\n')
print('PAWN_SHOP_RUIN_AUTHORED',triangles,len(solids),flush=True)
