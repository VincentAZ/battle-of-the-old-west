"""Separate static BoardingHouse ruin: no game export or import."""
from pathlib import Path
import hashlib,json,math,random
import bpy,bmesh
import numpy as np
from PIL import Image,ImageDraw
from mathutils import Matrix,Vector
from bpy_extras.object_utils import world_to_camera_view
R=Path(__file__).resolve().parents[1];B=R/'art/western/holdings/expansion-review-v001/boarding-house'
OUT=B/'ruin-source-v002';BRIEF=B/'ruin-brief-v002.json'
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
scale=6.0/max(hi.x-lo.x,hi.y-lo.y);shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z));normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)
# Copy material data. Surface change is confined to the derivative, and glass
# transmission is deliberately absent because no glass components survive.
mat=bpy.data.materials.new('M_BoardingHouse_CharredTimber');mat.use_nodes=True
bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.94
bsdf.inputs['Metallic'].default_value=0
rng=random.Random(1885);nrng=np.random.default_rng(1885)
old=np.asarray(Image.open(B/'local-source-v004/BoardingHouse_BaseColor.png').convert('RGB')).astype(float)
coarse=np.asarray(Image.fromarray(nrng.integers(0,256,(56,56),dtype=np.uint8)).resize((2048,2048),Image.Resampling.BICUBIC)).astype(float)
variation=(coarse/255-.5)*14+nrng.uniform(-2,2,(2048,2048))
luma=old@np.array([.2126,.7152,.0722])
pixels=np.clip(luma[...,None]*.13+np.array([19,12,7])+variation[...,None],0,255).astype(np.uint8)
# Preserve natural red-brown masonry separately from charred wood.
pixels[1032:1529,8:505]=old[1032:1529,8:505].astype(np.uint8)
texture=OUT/'BoardingHouse_Ruin_BaseColor.png';Image.fromarray(pixels).save(texture)
node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack();mat.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])

kept=[];removed=[];preserved=[];roles={}
for o in original:o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
def assign(o,role):
 o.data.materials.clear();o.data.materials.append(mat);kept.append(o);roles[o.name]=role
def char_bevel(o,width=.004):
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
 m=o.modifiers.new('Rounded consumed timber edges','BEVEL');m.width=width;m.segments=1
 bpy.ops.object.modifier_apply(modifier=m.name)

regions={'wood':(1032,520,1528,1016),'roof':(1544,520,2040,1016),
         'sign':(8,8,2040,480),'brick':(24,1044,112,1080)}
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
   uv.data[li].uv=((x0+margin+u*(x1-x0-2*margin))/2048,1-(y1-margin-v*(y1-y0-2*margin))/2048)

# Continuous cap profiles keep individual siding courses connected to their
# backing. Every remnant is a new closed extrusion of the clipped section.
profiles={
 'Main front':(0,-2.25,.70,[.55,.85,.40,.64,.48]),
 'Main west':(1,-1.30,1.55,[.55,.40,.71,.63,.62]),
 'Rear':(0,-2.25,2.20,[.62,.32,.76,.51,.67]),
 'Wing east':(1,-.30,1.55,[.65,.50,.33,.52,.67]),
 'Wing recessed front':(0,.70,2.20,[.50,.37,.72,.47,.65]),
 'Exposed return':(1,-1.30,-.30,[.48,.31,.40,.39,.50])}
def wall_remnants(o,profile):
 axis,left,right,caps=profile;other=1-axis
 bounds=([min(v.co[k] for v in o.data.vertices) for k in range(3)],
         [max(v.co[k] for v in o.data.vertices) for k in range(3)])
 low,high=bounds;z0,z1=low[2],high[2]
 for i,(hl,hr) in enumerate(zip(caps,caps[1:])):
  a0=left+(right-left)*i/4;b0=left+(right-left)*(i+1)/4
  a=max(a0,low[axis]);b=min(b0,high[axis])
  if b-a<1e-6 or z0>=max(hl,hr)-1e-6:continue
  section=[(a,z0),(b,z0),(b,z1),(a,z1)];clipped=[]
  distance=lambda p:p[1]-hl-(hr-hl)*(p[0]-a0)/(b0-a0)
  previous=section[-1];dp=distance(previous)
  for current in section:
   dc=distance(current)
   if (dp<=0)!=(dc<=0):
    t=dp/(dp-dc);clipped.append(tuple(previous[k]+t*(current[k]-previous[k]) for k in range(2)))
   if dc<=0:clipped.append(current)
   previous,dp=current,dc
  clean=[]
  for point in clipped:
   if not clean or math.dist(point,clean[-1])>1e-7:clean.append(point)
  if len(clean)>1 and math.dist(clean[0],clean[-1])<1e-7:clean.pop()
  if len(clean)<3:continue
  area=abs(sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(clean,clean[1:]+clean[:1])))/2
  if area<1e-8:continue
  vertices=[]
  for t in (low[other],high[other]):
   for u,z in clean:
    p=[0,0,z];p[axis]=u;p[other]=t;vertices.append(p)
  n=len(clean);faces=[tuple(range(n)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
  mesh=bpy.data.meshes.new('Closed charred wall profile');mesh.from_pydata(vertices,[],faces);mesh.update()
  bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
  part=bpy.data.objects.new('Charred '+o.name+' section '+str(i),mesh);bpy.context.collection.objects.link(part)
  uvmap(part,'wood');assign(part,'wall')

for o in original:
 name=o.name;bottom=min(v.co.z for v in o.data.vertices);top=max(v.co.z for v in o.data.vertices)
 if name.startswith(('Grounded timber foundation','Grounded porch foot','Entrance step')) or (top<.30 and name.startswith(('Timber floor or ceiling','Porch floor plank','Porch supporting joist'))):
  role='step' if name.startswith('Entrance step') else 'floor' if name.startswith(('Timber floor','Porch floor')) else 'foundation'
  assign(o,role);preserved.append(name);continue
 if 'wall backing' in name or 'green clapboard' in name:
  prefix=next(k for k in profiles if name.startswith(k+' '));wall_remnants(o,profiles[prefix])
 elif name.startswith(('Closed painted corner block','Painted porch post','Grounded fence post')):
  height=rng.uniform(.32,.48) if name.startswith('Grounded fence') else rng.uniform(.36,.65)
  cx=sum(v.co.x for v in o.data.vertices)/len(o.data.vertices);cy=sum(v.co.y for v in o.data.vertices)/len(o.data.vertices)
  for v in o.data.vertices:
   fraction=(v.co.z-bottom)/(top-bottom)
   v.co.z=bottom+fraction*(height+.08*(v.co.x-cx)-.04*(v.co.y-cy))
  o.name='Charred stump '+name;char_bevel(o,.004);uvmap(o,'wood');assign(o,'stump');continue
 elif name.startswith('Fence horizontal rail') and top<.30:
  low=min(v.co.x for v in o.data.vertices);high=max(v.co.x for v in o.data.vertices)
  for v in o.data.vertices:v.co.x=low if abs(v.co.x-low)<abs(v.co.x-high) else low+.58
  o.name='Short charred fence rail';char_bevel(o,.003);uvmap(o,'wood');assign(o,'wall');continue
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
  if key in ('wood','roof'):v.co.x+=(.006 if v.co.y>0 else -.004)*(1 if v.co.x>0 else -1)
  elif key=='sign' and v.co.x>0:v.co.x-=.028 if v.co.z>0 else .065
 uvmap(o,key);char_bevel(o,.002 if key in ('roof','brick') else .004)
 o.rotation_euler=rot;bpy.context.view_layer.update()
 bottom=min((o.matrix_world@v.co).z for v in o.data.vertices);o.location.z+=.22-bottom
 assign(o,'masonry_debris' if key=='brick' else 'fallen');return o

def plan_debris(rng):
 occupied=[rectangle(-.55,-.32,1.27,.32,.18)]
 areas=[(-2.06,.50,-1.10,1.36),(.89,2.03,-.10,1.35)]
 specs=[]
 for i in range(69):
  key='brick' if i<12 else 'wood' if i<57 else 'roof'
  w=.19 if key=='brick' else rng.uniform(.30,.65) if key=='wood' else rng.uniform(.17,.27)
  h=.095 if key=='brick' else rng.uniform(.055,.095) if key=='wood' else rng.uniform(.13,.20)
  height=.065 if key=='brick' else .020 if key=='roof' else rng.uniform(.035,.067)
  specs.append((key,w,h,height))
 planned=[]
 for key,w,h,height in sorted(specs,key=lambda spec:spec[1]*spec[2],reverse=True):
  for attempt in range(12000):
   xl,xr,yl,yr=areas[0 if rng.random()<.79 else 1]
   x,y=rng.uniform(xl,xr),rng.uniform(yl,yr);angle=rng.uniform(-math.pi,math.pi)
   shape=rectangle(x,y,w+.022,h+.012,angle)
   if not all(xl<a<xr and yl<b<yr for a,b in shape):continue
   if any(overlap(shape,p) for p in occupied):continue
   occupied.append(shape);planned.append((key,w,h,height,x,y,angle));break
  else:raise AssertionError(('Could not place non-overlapping debris',key,w,h,len(planned)))
 return planned
layout=plan_debris(rng)
debris('Fallen partial boarding-house sign',(-.55,-.32,.30),(1.19,.035,.27),(-math.pi/2,0,.18),'sign')
# Displaced chimney brick is kept as brick, with no fabricated freestanding core.
for key,w,h,height,x,y,angle in layout:
 debris('Fallen chimney brick' if key=='brick' else 'Fallen charred shingle' if key=='roof' else 'Fallen charred board',
        (x,y,.30),(w,h,height),(0,0,angle),key)
# Verify actual solids before joining; normalized source coordinates stay available
# in a separate components file for independent support and preservation checks.
bpy.context.view_layer.update();solids=[]
for o in kept:
 o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update()
 assert all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True)>0,o.name
 assert all(f.calc_area()>1e-12 for f in bm.faces),o.name
 solids.append(dict(name=o.name,role=roles[o.name],closed=True,volume_m3=bm.calc_volume(signed=True)));bm.to_mesh(o.data);bm.free()
components=OUT/'BoardingHouse-Ruin-Components.blend';bpy.ops.wm.save_as_mainfile(filepath=str(components))
for o in kept:o.matrix_world=normalize@o.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for o in kept:o.select_set(True)
bpy.context.view_layer.objects.active=kept[0];bpy.ops.object.join();ruin=bpy.context.object;ruin.name='SM_HoldingRuin_BoardingHouse'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
coords=[v.co for v in ruin.data.vertices];bounds=dict(min=[min(p[i] for p in coords) for i in range(3)],max=[max(p[i] for p in coords) for i in range(3)])
assert abs(bounds['min'][2])<1e-6 and bounds['max'][2]<1.4
project=OUT/'BoardingHouse-Ruin.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
# Import only the unchanged static setting objects for honest contextual renders.
with bpy.data.libraries.load(str(base_project),link=False) as (src,dst):dst.objects=['Holding_Base_Ground']
for o in dst.objects:bpy.context.collection.objects.link(o)
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
 right=camera.rotation_euler.to_quaternion()@Vector((1,0,0));up=camera.rotation_euler.to_quaternion()@Vector((0,1,0));pts=[o.matrix_world@v.co for o in scene.objects if o.type=='MESH' for v in o.data.vertices]
 xs=[(p-camera.location).dot(right) for p in pts];ys=[(p-camera.location).dot(up) for p in pts];camera.location+=right*((max(xs)+min(xs))/2)+up*((max(ys)+min(ys))/2);camera.data.ortho_scale=1.15*max(max(xs)-min(xs),(max(ys)-min(ys))/.75)
 scene.camera=camera;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
 assert all(0<=p.x<=1 and 0<=p.y<=1 and p.z>0 for p in [world_to_camera_view(scene,camera,o.matrix_world@v.co) for o in scene.objects if o.type=='MESH' for v in o.data.vertices]),name
 views[name]=sha(OUT/(name+'.png'))
review=OUT/'BoardingHouse-Ruin-Review.blend';bpy.ops.wm.save_as_mainfile(filepath=str(review))
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,normalization=dict(scale=scale,shift=list(shift)),triangles=triangles,bounds_m=bounds,removed_parts=removed,project_sha256=sha(project),review_project_sha256=sha(review),components_project_sha256=sha(components),base_project_sha256=sha(base_project),texture_sha256=sha(texture),views=views,imported=False,game_exported=False,component_count=len(solids),component_solids=solids,preserved_geometry=preserved,fallen_boards=45,fallen_shingles=12,fallen_bricks=12,fallen_signs=1,limitations=brief['uncertainties']),indent=2)+'\n')
print('BOARDING_HOUSE_RUIN_AUTHORED',triangles,len(solids),flush=True)
