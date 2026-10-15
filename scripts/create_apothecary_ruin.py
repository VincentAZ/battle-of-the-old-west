"""Separate static Apothecary ruin: no game export or import."""
from pathlib import Path
import hashlib,json,math,random
import bpy,bmesh
import numpy as np
from PIL import Image,ImageDraw
from mathutils import Matrix,Vector
from bpy_extras.object_utils import world_to_camera_view
R=Path(__file__).resolve().parents[1];B=R/'art/western/holdings/expansion-review-v001/apothecary'
OUT=B/'ruin-source-v003';BRIEF=B/'ruin-brief-v003.json'
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
scale=4.5/max(hi.x-lo.x,hi.y-lo.y);shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z));normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)
# Copy material data. Surface change is confined to the derivative, and glass
# transmission is deliberately absent because no glass components survive.
mat=bpy.data.materials.new('M_Apothecary_CharredTimber');mat.use_nodes=True
bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.94
bsdf.inputs['Metallic'].default_value=0
rng=random.Random(1885);nrng=np.random.default_rng(1885)
old=np.asarray(Image.open(B/'local-source-v003/Apothecary_BaseColor.png').convert('RGB')).astype(float)
coarse=np.asarray(Image.fromarray(nrng.integers(0,256,(56,56),dtype=np.uint8)).resize((2048,2048),Image.Resampling.BICUBIC)).astype(float)
variation=(coarse/255-.5)*14+nrng.uniform(-2,2,(2048,2048))
pixels=np.clip(old*.17+np.array([14,9,5])+variation[...,None],0,255).astype(np.uint8)
texture=OUT/'Apothecary_Ruin_BaseColor.png';Image.fromarray(pixels).save(texture)
node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack();mat.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
kept=[];removed=[];preserved=[];roles={}
# Freeze source transforms into derivative mesh data, then retain exact support
# geometry. Each healthy object was already independent; nothing is welded away.
for o in original:o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
def assign(o,role):
 o.data.materials.clear();o.data.materials.append(mat);kept.append(o);roles[o.name]=role

def char_bevel(o,width=.004):
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
 m=o.modifiers.new('Rounded consumed timber edges','BEVEL');m.width=width;m.segments=1
 bpy.ops.object.modifier_apply(modifier=m.name)

def crop(o,axis,left,right,top=None):
 # Slice an axis-aligned box into a closed smaller box without degenerate caps.
 old_lo=min(v.co[axis] for v in o.data.vertices);old_hi=max(v.co[axis] for v in o.data.vertices)
 for v in o.data.vertices:
  v.co[axis]=left if abs(v.co[axis]-old_lo)<abs(v.co[axis]-old_hi) else right
  if top is not None:v.co.z=min(v.co.z,top)
 o.data.update()

for o in original:
 name=o.name
 if name.startswith(('Closed timber floor','Grounded longitudinal sill','Front plank step','Front step support','Rear timber step')):
  assign(o,'foundation' if name.startswith(('Grounded longitudinal sill','Front step support','Rear timber step')) else 'floor' if name.startswith('Closed timber floor') else 'step')
  preserved.append(name);continue
 if name.startswith(('Horizontal timber side siding','Timber side wall backing','Rear horizontal siding','Rear continuous timber backing')):
  axis=1 if name.startswith(('Horizontal timber side','Timber side')) else 0
  low=min(v.co[axis] for v in o.data.vertices);high=max(v.co[axis] for v in o.data.vertices)
  heights=([.43,.70,.36,.61,.47] if o.data.vertices[0].co.x<0 else [.61,.39,.56,.34,.68]) if axis==1 else [.55,.30,.47,.67,.43]
  bottom=min(v.co.z for v in o.data.vertices)
  for i,(hl,hr) in enumerate(zip(heights,heights[1:])):
   if bottom>=max(hl,hr)-.006:continue
   a=low+(high-low)*i/4;b=low+(high-low)*(i+1)/4
   part=o.copy();part.data=o.data.copy();bpy.context.collection.objects.link(part);part.name='Charred wall remnant '+name+' section '+str(i)
   # Clip a 2D wall cross-section then extrude it, avoiding microscopic
   # bevel triangles where a sloping break meets a thin siding course.
   z0=min(v.co.z for v in part.data.vertices);z1=max(v.co.z for v in part.data.vertices)
   other=1-axis;t0=min(v.co[other] for v in part.data.vertices);t1=max(v.co[other] for v in part.data.vertices)
   profile=[(a,z0),(b,z0),(b,z1),(a,z1)];clipped=[]
   distance=lambda p:p[1]-hl-(hr-hl)*(p[0]-a)/(b-a)
   previous=profile[-1];dp=distance(previous)
   for current in profile:
    dc=distance(current)
    if (dp<=0)!=(dc<=0):
     t=dp/(dp-dc);clipped.append(tuple(previous[k]+t*(current[k]-previous[k]) for k in range(2)))
    if dc<=0:clipped.append(current)
    previous,dp=current,dc
   clean=[]
   for point in clipped:
    if not clean or math.dist(point,clean[-1])>1e-7:clean.append(point)
   if len(clean)>1 and math.dist(clean[0],clean[-1])<1e-7:clean.pop()
   assert len(clean)>=3
   vertices=[]
   for t in (t0,t1):
    for u,z in clean:
     p=[0,0,z];p[axis]=u;p[other]=t;vertices.append(p)
   n=len(clean);faces=[tuple(range(n)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
   mesh=bpy.data.meshes.new('Closed irregular wall profile');mesh.from_pydata(vertices,[],faces);mesh.update()
   bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
   part.data=mesh;uv=mesh.uv_layers.new()
   for face in mesh.polygons:
    for li in face.loop_indices:
     p=mesh.vertices[mesh.loops[li].vertex_index].co
     uv.data[li].uv=((536+(p.z-z0)/max(z1-z0,1e-8)*464)/2048,1-(536+(p[axis]-a)/(b-a)*464)/2048)
   assign(part,'wall')
 elif name.startswith('Front painted horizontal board') and min(v.co.z for v in o.data.vertices)<.47:
  crop(o,0,min(v.co.x for v in o.data.vertices),max(v.co.x for v in o.data.vertices),top=.47)
  char_bevel(o,.003);o.name='Charred low front board';assign(o,'wall');continue
 elif name.startswith(('Front corner trim','Rear corner board','Doorway outer jamb')):
  bottom=min(v.co.z for v in o.data.vertices);top=max(v.co.z for v in o.data.vertices)
  height=rng.uniform(.24,.52)
  for v in o.data.vertices:v.co.z=bottom+(v.co.z-bottom)*height/(top-bottom)
  o.name='Charred stump '+name;char_bevel(o,.006);assign(o,'stump');continue
 removed.append(name);bpy.data.objects.remove(o,do_unlink=True)

# New debris uses the source material palette/UV regions. Rectangular pieces
# have rounded charred edges; exact burn extent is a fictional reconstruction.
regions={'wood':(520,520,1016,1016),'roof':(1032,520,1528,1016),'sign':(8,8,2040,480)}
def uvmap(o,key):
 mesh=o.data;mesh.update();uv=mesh.uv_layers.active or mesh.uv_layers.new()
 for f in mesh.polygons:
  n=max(range(3),key=lambda k:abs(f.normal[k]));axes=[k for k in range(3) if k!=n]
  points=[mesh.vertices[mesh.loops[i].vertex_index].co for i in f.loop_indices]
  lo=[min(p[k] for p in points) for k in range(3)];hi=[max(p[k] for p in points) for k in range(3)]
  tile='sign' if key=='sign' and f.normal.y<-.5 else 'wood' if key=='sign' else key
  a,b=axes
  if tile!='sign':b=max(axes,key=lambda k:hi[k]-lo[k]);a=next(k for k in axes if k!=b)
  x0,y0,x1,y1=regions[tile]
  for li in f.loop_indices:
   p=mesh.vertices[mesh.loops[li].vertex_index].co;u=(p[a]-lo[a])/max(hi[a]-lo[a],1e-9);v=(p[b]-lo[b])/max(hi[b]-lo[b],1e-9)
   if tile=='sign':u*=.47 # Left portion of the source trade sign only.
   uv.data[li].uv=((x0+8+u*(x1-x0-16))/2048,1-(y1-8-v*(y1-y0-16))/2048)

def debris(name,loc,dim,rot,key='wood'):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dim
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 # Unequal consumed end corners keep boards from looking freshly saw-cut.
 for vertex in o.data.vertices:
  if key!='sign':
   vertex.co.x += (.018 if vertex.co.y>0 else -.015)*(1 if vertex.co.x>0 else -1)
  elif vertex.co.x>0:
   vertex.co.x -= .035 if vertex.co.z>0 else .095
 uvmap(o,key)
 char_bevel(o,.004 if key!='roof' else .002)
 o.rotation_euler=rot;bpy.context.view_layer.update()
 bottom=min((o.matrix_world@v.co).z for v in o.data.vertices);o.location.z+=.218-bottom
 assign(o,'fallen');return o

# Oriented-rectangle SAT keeps the main fallen pieces from occupying the same
# horizontal space. All lie on the retained floor instead of hovering in a pile.
def rectangle(x,y,w,h,angle):
 c,s=math.cos(angle),math.sin(angle)
 return [(x+c*a-s*b,y+s*a+c*b) for a,b in [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]]
def overlap(a,b):
 for poly in (a,b):
  for p,q in zip(poly,poly[1:]+poly[:1]):
   axis=(-(q[1]-p[1]),q[0]-p[0]);aa=[x*axis[0]+y*axis[1] for x,y in a];bb=[x*axis[0]+y*axis[1] for x,y in b]
   if max(aa)<min(bb) or max(bb)<min(aa):return False
 return True
occupied=[rectangle(-.50,-.20,1.60,.84,.19)]
sign=debris('Fallen partial trade sign',(-.50,-.20,.30),(1.56,.045,.80),(-math.pi/2,0,.19),'sign')
for i in range(34):
 shingle=i>=24;w=rng.uniform(.18,.29) if shingle else rng.uniform(.47,1.03);h=rng.uniform(.14,.22) if shingle else rng.uniform(.07,.13)
 for attempt in range(1500):
  x,y=rng.uniform(-1.47,1.47),rng.uniform(-1.36,1.36);angle=rng.uniform(-math.pi,math.pi);shape=rectangle(x,y,w+.05,h+.022,angle)
  if not all(abs(a)<1.56 and abs(b)<1.44 for a,b in shape):continue
  if any(overlap(shape,p) for p in occupied):continue
  occupied.append(shape);break
 else:raise AssertionError('Could not place non-overlapping debris')
 debris('Fallen charred shingle' if shingle else 'Fallen charred board',(x,y,.30),(w,h,.020 if shingle else rng.uniform(.038,.074)),(0,0,angle),'roof' if shingle else 'wood')
# Verify actual solids before joining; normalized source coordinates stay available
# in a separate components file for independent support and preservation checks.
bpy.context.view_layer.update();solids=[]
for o in kept:
 o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update()
 assert all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True)>0,o.name
 assert all(f.calc_area()>1e-12 for f in bm.faces),o.name
 solids.append(dict(name=o.name,role=roles[o.name],closed=True,volume_m3=bm.calc_volume(signed=True)));bm.to_mesh(o.data);bm.free()
components=OUT/'Apothecary-Ruin-Components.blend';bpy.ops.wm.save_as_mainfile(filepath=str(components))
for o in kept:o.matrix_world=normalize@o.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for o in kept:o.select_set(True)
bpy.context.view_layer.objects.active=kept[0];bpy.ops.object.join();ruin=bpy.context.object;ruin.name='SM_HoldingRuin_Apothecary'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
coords=[v.co for v in ruin.data.vertices];bounds=dict(min=[min(p[i] for p in coords) for i in range(3)],max=[max(p[i] for p in coords) for i in range(3)])
assert abs(bounds['min'][2])<1e-6 and bounds['max'][2]<1.0
project=OUT/'Apothecary-Ruin.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
# Import only the unchanged static setting objects for honest contextual renders.
with bpy.data.libraries.load(str(base_project),link=False) as (src,dst):dst.objects=['Holding_Base_Ground','Holding_Base_Stone']
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
review=OUT/'Apothecary-Ruin-Review.blend';bpy.ops.wm.save_as_mainfile(filepath=str(review))
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,normalization=dict(scale=scale,shift=list(shift)),triangles=triangles,bounds_m=bounds,removed_parts=removed,project_sha256=sha(project),review_project_sha256=sha(review),components_project_sha256=sha(components),base_project_sha256=sha(base_project),texture_sha256=sha(texture),views=views,imported=False,game_exported=False,component_count=len(solids),component_solids=solids,preserved_geometry=preserved,fallen_boards=24,fallen_shingles=10,fallen_signs=1,limitations=brief['uncertainties']),indent=2)+'\n')
print('APOTHECARY_RUIN_AUTHORED',triangles,len(solids),flush=True)
