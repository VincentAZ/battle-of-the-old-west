"""Preserved healthy hall and setting, with a separate static fire-damage derivative."""
from pathlib import Path
import hashlib,json,math,random
import bpy,bmesh,numpy as np
from PIL import Image
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
R=Path(__file__).resolve().parents[1];B=R/'art/western/holdings/expansion-review-v001/vigilance-committee';OUT=B/'ruin-source-v002';BRIEF=B/'ruin-brief-v002.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text());assert brief['pre_modeling_review']['completed']
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
for p,h in brief['source_records'].items():assert sha(R/p)==h,p
assert not OUT.exists();OUT.mkdir();source=B/brief['preservation']['source'];base_project=B/brief['preservation']['base']
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
original=[o for o in bpy.context.scene.objects if o.type=='MESH'];pts=[o.matrix_world@v.co for o in original for v in o.data.vertices]
lo=Vector([min(p[k]for p in pts)for k in range(3)]);hi=Vector([max(p[k]for p in pts)for k in range(3)])
scale=5.5/max(hi.x-lo.x,hi.y-lo.y);shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z));normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)
rng=random.Random(186309);nrng=np.random.default_rng(186309)
old=np.asarray(Image.open(B/'local-source-v006/VigilanceCommittee_BaseColor.png').convert('RGB'))
atlas=old.copy();regions={}
for i,key in enumerate(('wood','roof','plaster','stone','mortar','inside','glass')):
 x,y=i%4*512,i//4*512;regions[key]=(x+8,y+8,x+504,y+504)
 if key not in ('wood','roof','inside'):continue
 yy,xx=np.mgrid[0:512,0:512];coarse=np.asarray(Image.fromarray(nrng.integers(0,256,(22,22),dtype=np.uint8)).resize((512,512),Image.Resampling.BICUBIC)).astype(float)
 var=(coarse/255-.5)*17+nrng.uniform(-2,2,(512,512))+4*np.sin(yy*.17+np.sin(xx*.04))
 atlas[y:y+512,x:x+512]=np.clip(np.array([36,25,16])+var[...,None],0,255).astype(np.uint8)
texture=OUT/'VigilanceCommittee_Ruin_BaseColor.png';Image.fromarray(atlas).save(texture)
mat=bpy.data.materials.new('M_VigilanceCommittee_Ruin');mat.use_nodes=True;bsdf=mat.node_tree.nodes['Principled BSDF'];bsdf.inputs['Roughness'].default_value=.94
n=mat.node_tree.nodes.new('ShaderNodeTexImage');n.image=bpy.data.images.load(str(texture));n.image.pack();mat.node_tree.links.new(n.outputs['Color'],bsdf.inputs['Base Color'])
kept=[];removed=[];preserved=[];roles={};templates=[]
def assign(o,role):
 o.data.materials.clear();o.data.materials.append(mat)
 for f in o.data.polygons:f.material_index=0
 kept.append(o);roles[o.name]=role
def uv(o,key):
 m=o.data;m.update();layer=m.uv_layers.active or m.uv_layers.new();x0,y0,x1,y1=regions[key]
 for f in m.polygons:
  axis=max(range(3),key=lambda k:abs(f.normal[k]));axes=[k for k in range(3)if k!=axis];pts=[m.vertices[i].co for i in f.vertices];lo=[min(p[k]for p in pts)for k in range(3)];hi=[max(p[k]for p in pts)for k in range(3)];a=max(axes,key=lambda k:hi[k]-lo[k]);b=next(k for k in axes if k!=a)
  for i in f.loop_indices:
   p=m.vertices[m.loops[i].vertex_index].co;u=(p[a]-lo[a])/max(hi[a]-lo[a],1e-8);v=(p[b]-lo[b])/max(hi[b]-lo[b],1e-8);layer.data[i].uv=((x0+5+u*(x1-x0-10))/2048,1-(y1-5-v*(y1-y0-10))/2048)
def shrink_top(o,target):
 pts=[o.matrix_world@v.co for v in o.data.vertices];bottom=min(p.z for p in pts);top=max(p.z for p in pts)
 for v,p in zip(o.data.vertices,pts):p.z=bottom+(p.z-bottom)*(target-bottom)/(top-bottom);v.co=p
 o.matrix_world=Matrix.Identity(4);o.data.update()
for o in original:
 n=o.name;pts=[o.matrix_world@v.co for v in o.data.vertices];center=sum(pts,Vector())/len(pts);top=max(p.z for p in pts);bottom=min(p.z for p in pts)
 if n.startswith(('Stone foundation','Ground timber floor','Door threshold')):
  assign(o,'preserved_floor'if n.startswith('Ground')else 'preserved_stone');preserved.append(n);continue
 if 'rubble block' in n:
  profile=([1.28,1.06,.84,1.28,1.50] if center.x<0 else [1.06,1.28,.84,1.06,1.28])if n.startswith('Side')else [1.50,1.28,1.06,1.28,1.50,1.06]
  coord,width=(center.y,3.12)if n.startswith('Side')else(center.x,4.44);index=min(len(profile)-1,max(0,int((coord/width+.5)*len(profile))));target=profile[index]
  if center.z<target-.06:assign(o,'retained_masonry');continue
  if len(templates)<16:templates.append((o.data.copy(),o.matrix_world.copy()))
 elif 'lime mortar core' in n:
  pass # Backing is reconstructed below, following the retained stone edges.
 elif n.startswith(('Front masonry pier','Scored lime plaster')):
  target=.91 if center.x<-1.6 else 1.12 if center.x<0 else .82 if center.x<1.6 else 1.02
  if bottom<target:
   if top>target:shrink_top(o,target)
   assign(o,'front_remnant');continue
 elif n.startswith('Door jamb'):
  shrink_top(o,.58+rng.uniform(0,.20));o.name='Charred doorway stump';uv(o,'wood');assign(o,'charred_post');continue
 removed.append(n);bpy.data.objects.remove(o,do_unlink=True)
# Piecewise mortar backing stays below the top of the actual retained stones.
for side in ('left','right','rear'):
 axis=0 if side=='rear'else 1
 stones=[o for o in kept if roles[o.name]=='retained_masonry'and (o.name.startswith('Rear')if side=='rear'else o.name.startswith('Side')and (o.location.x<0)==(side=='left'))]
 spans=[]
 for o in stones:
  pts=[o.matrix_world@v.co for v in o.data.vertices];spans.append((min(p[axis]for p in pts),max(p[axis]for p in pts),sum(p.z for p in pts)/len(pts)-.04))
 lo,hi=(-2.22,2.22)if side=='rear'else(-1.44,1.56)
 cuts=sorted(set([lo,hi]+[max(lo,min(hi,v))for a,b,z in spans for v in(a,b)]))
 for a,b in zip(cuts,cuts[1:]):
  if b-a<1e-6:continue
  top=max((z for x,y,z in spans if x<=(a+b)/2<=y),default=.72)
  center=((a+b)/2,1.52,(top+.18)/2)if side=='rear'else(-2.30 if side=='left'else 2.30,(a+b)/2,(top+.18)/2)
  dim=(b-a,.23,top-.18)if side=='rear'else(.23,b-a,top-.18)
  bpy.ops.mesh.primitive_cube_add(size=1,location=center);o=bpy.context.object;o.name='Ragged mortar backing '+side;o.dimensions=dim;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);uv(o,'mortar');assign(o,'shortened_core')
assert len(preserved)==5 and len(templates)==16
def tree(o):return BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[list(f.vertices)for f in o.data.polygons],epsilon=.010)
debris=[]
for attempt in range(4000):
 if len(debris)==40:break
 i=len(debris);stone=i<16
 if stone:
  mesh,matrix=templates[i];mesh=mesh.copy();points=[matrix@v.co for v in mesh.vertices];center=sum(points,Vector())/len(points)
  for v,p in zip(mesh.vertices,points):v.co=p-center
  o=bpy.data.objects.new(f'Fallen stone {i:02}',mesh);bpy.context.collection.objects.link(o)
  bm=bmesh.new();bm.from_mesh(mesh);bounds=[max(v.co[k]for v in bm.verts)-min(v.co[k]for v in bm.verts)for k in range(3)];axis=max(range(3),key=lambda k:bounds[k]);normal=Vector((.35,.24,.22));normal[axis]=1;point=Vector((0,0,0));point[axis]=bounds[axis]*.23
  bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=point,plane_no=normal,dist=1e-7,clear_outer=True,clear_inner=False)
  bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6);boundary=[e for e in bm.edges if e.is_boundary]
  if boundary:bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
  bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();uv(o,'stone')

 else:
  bpy.ops.mesh.primitive_cube_add(size=1);o=bpy.context.object;o.name=f'Charred roof fragment {i-16:02}';o.dimensions=(rng.uniform(.36,.86),rng.uniform(.055,.12),rng.uniform(.035,.065));bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
  for v in o.data.vertices:
   if v.co.x>0:v.co.x+=rng.uniform(-.015,.015)
  mod=o.modifiers.new('Consumed rounded corners','BEVEL');mod.width=.004;mod.segments=1;bpy.ops.object.modifier_apply(modifier=mod.name);uv(o,'wood')
 o.location=(rng.uniform(-1.88,1.88),rng.uniform(-1.16,1.16),0);o.rotation_euler=(rng.uniform(-.14,.14),rng.uniform(-.14,.14),rng.uniform(-math.pi,math.pi));bpy.context.view_layer.update();o.location.z+=.23-min((o.matrix_world@v.co).z for v in o.data.vertices);bpy.context.view_layer.update()
 candidate=tree(o)
 if any(candidate.overlap(tree(other))for other in kept if roles[other.name]not in ('preserved_floor','preserved_stone')):
  bpy.data.objects.remove(o,do_unlink=True);continue
 assign(o,'fallen_stone'if stone else 'fallen_timber');debris.append(o)
assert len(debris)==40
bpy.context.view_layer.update();solids=[]
for o in kept:
 bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world);bm.normal_update();assert all(e.is_manifold for e in bm.edges)and bm.calc_volume(signed=True)>0,o.name;assert all(f.calc_area()>1e-12 for f in bm.faces),o.name
 solids.append(dict(name=o.name,role=roles[o.name],closed=True,volume_m3=bm.calc_volume(signed=True)));bm.free()
components=OUT/'VigilanceCommittee-Ruin-Components.blend';bpy.ops.wm.save_as_mainfile(filepath=str(components))
for o in kept:o.matrix_world=normalize@o.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for o in kept:o.select_set(True)
bpy.context.view_layer.objects.active=kept[0];bpy.ops.object.join();ruin=bpy.context.object;ruin.name='SM_HoldingRuin_VigilanceCommittee';bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
coords=[v.co for v in ruin.data.vertices];bounds=dict(min=[min(p[i]for p in coords)for i in range(3)],max=[max(p[i]for p in coords)for i in range(3)])
assert abs(bounds['min'][2])<1e-6 and bounds['max'][2]<1.65
project=OUT/'VigilanceCommittee-Ruin.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
base_names=['Holding_Base_Ground','Holding_Base_Tuft','Holding_Base_Rock']
with bpy.data.libraries.load(str(base_project),link=False)as(src,dst):dst.objects=base_names
for o in dst.objects:bpy.context.collection.objects.link(o)
bpy.context.view_layer.update();scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True;scene.render.threads_mode='FIXED';scene.render.threads=8;scene.render.resolution_x=1280;scene.render.resolution_y=960;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Ruin daylight');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.28,.31,.35,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.45;scene.view_settings.view_transform='AgX'
for name,pos,power,size in [('Clear warm key',(-5,-6,9),1900,6),('Sky fill',(5,3,8),1100,7)]:
 data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;o=bpy.data.objects.new(name,data);scene.collection.objects.link(o);o.location=pos;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
views={}
for name,pos in [('front',(7,-11,7)),('rear',(-7,11,7)),('right',(12,2,6)),('overhead',(0,-.01,15))]:
 data=bpy.data.cameras.new(name);data.type='ORTHO';camera=bpy.data.objects.new('Review_'+name,data);scene.collection.objects.link(camera);camera.location=pos;camera.rotation_euler=(Vector((0,0,.4))-camera.location).to_track_quat('-Z','Y').to_euler();bpy.context.view_layer.update()
 right=camera.rotation_euler.to_quaternion()@Vector((1,0,0));up=camera.rotation_euler.to_quaternion()@Vector((0,1,0));pts=[o.matrix_world@v.co for o in scene.objects if o.type=='MESH'for v in o.data.vertices];xs=[(p-camera.location).dot(right)for p in pts];ys=[(p-camera.location).dot(up)for p in pts];camera.location+=right*((max(xs)+min(xs))/2)+up*((max(ys)+min(ys))/2);camera.data.ortho_scale=1.15*max(max(xs)-min(xs),(max(ys)-min(ys))/.75)
 scene.camera=camera;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
 assert all(0<=p.x<=1 and 0<=p.y<=1 and p.z>0 for p in[world_to_camera_view(scene,camera,o.matrix_world@v.co)for o in scene.objects if o.type=='MESH'for v in o.data.vertices]),name
 views[name]=sha(OUT/(name+'.png'))
review=OUT/'VigilanceCommittee-Ruin-Review.blend';bpy.ops.wm.save_as_mainfile(filepath=str(review))
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,normalization=dict(scale=scale,shift=list(shift),rotation_degrees=0),triangles=triangles,bounds_m=bounds,removed_parts=removed,project_sha256=sha(project),review_project_sha256=sha(review),components_project_sha256=sha(components),base_project_sha256=sha(base_project),texture_sha256=sha(texture),views=views,imported=False,game_exported=False,component_count=len(solids),component_solids=solids,preserved_geometry=preserved,limitations=brief['uncertainties']),indent=2)+'\n')
print('VIGILANCE_COMMITTEE_RUIN_AUTHORED',triangles,len(solids),flush=True)
