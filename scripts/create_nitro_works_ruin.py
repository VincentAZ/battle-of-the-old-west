"""Static burned-out derivative; preserve approved-source geometry and base."""
from pathlib import Path
import hashlib,json,math,random
import bpy,bmesh,numpy as np
from PIL import Image
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
R=Path(__file__).resolve().parents[1];B=R/'art/western/holdings/expansion-review-v001/nitro-works';OUT=B/'ruin-source-v001';BRIEF=B/'ruin-brief-v001.json';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();brief=json.loads(BRIEF.read_text());assert brief['pre_modeling_review']['completed']
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
for p,h in brief['source_records'].items():assert sha(R/p)==h
assert not OUT.exists();OUT.mkdir();source=B/brief['preservation']['source'];base_project=B/brief['preservation']['base'];bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
original=[o for o in bpy.context.scene.objects if o.type=='MESH'];pts=[o.matrix_world@v.co for o in original for v in o.data.vertices];lo=Vector([min(p[k]for p in pts)for k in range(3)]);hi=Vector([max(p[k]for p in pts)for k in range(3)]);scale=5.5/max(hi.x-lo.x,hi.y-lo.y);shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z));normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)
rng=random.Random(189507);nrng=np.random.default_rng(189507);old=np.asarray(Image.open(B/'local-source-v003/NitroWorks_BaseColor.png').convert('RGB'));atlas=old.copy();orm=np.asarray(Image.open(B/'local-source-v003/NitroWorks_ORM.png').convert('RGB')).copy();regions={}
for i,key in enumerate(('wood','metal','yellow','inside','glass','iron')):
 x,y=i%4*512,i//4*512;regions[key]=(x+8,y+8,x+504,y+504)
 yy,xx=np.mgrid[0:512,0:512];noise=np.asarray(Image.fromarray(nrng.integers(0,256,(18,18),dtype=np.uint8)).resize((512,512),Image.Resampling.BICUBIC)).astype(float);grain=4*np.sin(yy*.18+np.sin(xx*.04));var=(noise/255-.5)*19+nrng.uniform(-2,2,(512,512))+grain
 if key in('wood','inside'):atlas[y:y+512,x:x+512]=np.clip(np.array([36,26,17])+var[...,None],0,255).astype(np.uint8);orm[y:y+512,x:x+512,1]=235
 elif key in('metal','yellow'):
  soot=np.clip((noise-50)/160,0,.85);patch=old[y:y+512,x:x+512].astype(float)*(1-soot[...,None])+np.array([28,25,22])*soot[...,None]
  if key=='yellow':
   peel=noise>180;patch[peel]=np.array([139,144,144])*.75;orm[y:y+512,x:x+512,2][peel]=150
  atlas[y:y+512,x:x+512]=np.clip(patch,0,255).astype(np.uint8);orm[y:y+512,x:x+512,1]=205
  if key=='metal':orm[y:y+512,x:x+512,2]=170
texture=OUT/'NitroWorks_Ruin_BaseColor.png';Image.fromarray(atlas).save(texture);surface=OUT/'NitroWorks_Ruin_ORM.png';Image.fromarray(orm).save(surface)
mat=bpy.data.materials.new('M_NitroWorks_Ruin');mat.use_nodes=True;nt=mat.node_tree;bs=nt.nodes['Principled BSDF']
for p in (texture,surface):
 n=nt.nodes.new('ShaderNodeTexImage');n.image=bpy.data.images.load(str(p));n.image.pack()
 if p==texture:nt.links.new(n.outputs['Color'],bs.inputs['Base Color'])
 else:
  n.image.colorspace_settings.name='Non-Color';sep=nt.nodes.new('ShaderNodeSeparateColor');nt.links.new(n.outputs['Color'],sep.inputs['Color']);nt.links.new(sep.outputs['Green'],bs.inputs['Roughness']);nt.links.new(sep.outputs['Blue'],bs.inputs['Metallic'])
kept=[];roles={};removed=[];preserved=[]
def assign(o,role):
 o.data.materials.clear();o.data.materials.append(mat)
 for f in o.data.polygons:f.material_index=0
 kept.append(o);roles[o.name]=role

def uv(o,key):
 m=o.data;m.update();layer=m.uv_layers.active or m.uv_layers.new();x0,y0,x1,y1=regions[key]
 for f in m.polygons:
  axis=max(range(3),key=lambda k:abs(f.normal[k]));axes=[k for k in range(3)if k!=axis];pts=[m.vertices[i].co for i in f.vertices];low=[min(p[k]for p in pts)for k in range(3)];high=[max(p[k]for p in pts)for k in range(3)];a=max(axes,key=lambda k:high[k]-low[k]);b=next(k for k in axes if k!=a)
  for i in f.loop_indices:
   p=m.vertices[m.loops[i].vertex_index].co;u=(p[a]-low[a])/max(high[a]-low[a],1e-8);v=(p[b]-low[b])/max(high[b]-low[b],1e-8);layer.data[i].uv=((x0+5+u*(x1-x0-10))/2048,1-(y1-5-v*(y1-y0-10))/2048)
def deform_top(o,heights):
 pts=[o.matrix_world@v.co for v in o.data.vertices];bottom=min(p.z for p in pts);top=max(p.z for p in pts)
 for v,p in zip(o.data.vertices,pts):p.z=bottom+(p.z-bottom)*(heights(p)-bottom)/(top-bottom);v.co=p
 o.matrix_world=Matrix.Identity(4);o.data.update()
for o in original:
 n=o.name;pts=[o.matrix_world@v.co for v in o.data.vertices];bottom=min(p.z for p in pts)
 if n in brief['preserved_parts']:assign(o,'preserved_floor'if n in('Works floor','Office floor')else'preserved_base');preserved.append(n);continue
 if 'cladding'in n and bottom<.32:
  side='side'in n;isoffice=n.startswith('Office');axis=1 if side else 0;phase=rng.uniform(0,math.tau);floor=.22;target=(.66 if isoffice else .77)
  deform_top(o,lambda p,axis=axis,phase=phase,target=target:target+.12*math.sin(p[axis]*4.1+phase)+.055*math.sin(p[axis]*10.9+phase));assign(o,'standing_sheet');continue
 ispost=any(s in n for s in('corner post','porch post'))or(n.startswith(('Works entrance','Office door'))and'jamb'in n)
 if ispost:
  target=rng.uniform(.57,.92);deform_top(o,lambda p,target=target:target);assign(o,'charred_post');continue
 removed.append(n);bpy.data.objects.remove(o,do_unlink=True)
assert len(preserved)==8

def tree(o,eps=.003):return BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[list(f.vertices)for f in o.data.polygons],epsilon=eps)
def metal_piece(index,small):
 length=rng.uniform(.40,.59)if small else rng.uniform(.48,.83);width=rng.uniform(.20,.29)if small else rng.uniform(.25,.42);n=math.ceil(length/.11*6);N=n+1;vs=[]
 for v in(-width/2,width/2):
  for off in(-.005,.005):
   for j in range(N):
    u=-length/2+length*j/n;z=.013*math.cos(math.tau*u/.11)+.075*(u/length)**2+.025*math.sin(v/width*math.pi+u*6);vs.append((u,v,z+off))
 fs=[]
 for j in range(n):fs.extend([(j,j+1,2*N+j+1,2*N+j),(N+j,3*N+j,3*N+j+1,N+j+1),(j,N+j,N+j+1,j+1),(2*N+j,2*N+j+1,3*N+j+1,3*N+j)])
 fs.extend([(0,2*N,3*N,N),(n,N+n,3*N+n,2*N+n)]);m=bpy.data.meshes.new('Collapsed corrugated sheet');m.from_pydata(vs,[],fs);m.update();bm=bmesh.new();bm.from_mesh(m);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(m);bm.free();o=bpy.data.objects.new(f'Fallen metal sheet {index:02}',m);bpy.context.collection.objects.link(o);uv(o,'yellow'if small and index%2==0 else'metal');return o

debris=[];debris_supports={}
for i in range(32):
 ismetal=i<14;small=(i>=10 if ismetal else i>=28);bounds=(-2.27,-.93,-.52,1.25)if small else(-.46,1.94,-1.90,1.85);floorname='Office floor'if small else'Works floor';floorz=.25 if small else .27
 for attempt in range(3000):
  if ismetal:o=metal_piece(i,small)
  else:
   bpy.ops.mesh.primitive_cube_add(size=1);o=bpy.context.object;o.name=f'Fallen charred timber {i-14:02}';o.dimensions=(rng.uniform(.24,.48)if small else rng.uniform(.32,.72),rng.uniform(.045,.075),rng.uniform(.035,.055));bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
   for v in o.data.vertices:
    if v.co.x>0:v.co.x+=rng.uniform(-.02,.02)
   uv(o,'wood')
  o.location=(rng.uniform(bounds[0]+.12,bounds[1]-.12),rng.uniform(bounds[2]+.12,bounds[3]-.12),0);o.rotation_euler=(rng.uniform(-.11,.11),rng.uniform(-.11,.11),rng.uniform(-math.pi,math.pi));bpy.context.view_layer.update();o.location.z+=floorz-min((o.matrix_world@v.co).z for v in o.data.vertices);bpy.context.view_layer.update();pts=[o.matrix_world@v.co for v in o.data.vertices]
  if any(p.x<bounds[0]or p.x>bounds[1]or p.y<bounds[2]or p.y>bounds[3]for p in pts):bpy.data.objects.remove(o,do_unlink=True);continue
  t=tree(o)
  if any(t.overlap(tree(other))for other in kept if roles[other.name]not in('preserved_floor','preserved_base')):bpy.data.objects.remove(o,do_unlink=True);continue
  assign(o,'fallen_metal'if ismetal else'fallen_timber');debris.append(o);debris_supports[o.name]=floorname;break
 else:raise AssertionError(('could not place debris',i))
assert len(debris)==32
bpy.context.view_layer.update();solids=[]
for o in kept:
 bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world);bm.normal_update();assert all(e.is_manifold for e in bm.edges)and bm.calc_volume(signed=True)>0,o.name;assert all(f.calc_area()>1e-12 for f in bm.faces),o.name;solids.append(dict(name=o.name,role=roles[o.name],closed=True,volume_m3=bm.calc_volume(signed=True)));bm.free()
components=OUT/'NitroWorks-Ruin-Components.blend';bpy.ops.wm.save_as_mainfile(filepath=str(components))
for o in kept:o.matrix_world=normalize@o.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for o in kept:o.select_set(True)
bpy.context.view_layer.objects.active=kept[0];bpy.ops.object.join();ruin=bpy.context.object;ruin.name='SM_HoldingRuin_NitroWorks';bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles);assert 0<triangles<30000 and len(ruin.data.materials)==1
coords=[v.co for v in ruin.data.vertices];bounds=dict(min=[min(p[i]for p in coords)for i in range(3)],max=[max(p[i]for p in coords)for i in range(3)]);assert abs(bounds['min'][2])<1e-6 and bounds['max'][2]<1.65
project=OUT/'NitroWorks-Ruin.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
base_names=['Holding_Base_Ground','Holding_Base_Sorrel','Holding_Base_Litter']
with bpy.data.libraries.load(str(base_project),link=False)as(src,dst):dst.objects=base_names
for o in dst.objects:bpy.context.collection.objects.link(o)
bpy.context.view_layer.update();scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True;scene.render.threads_mode='FIXED';scene.render.threads=8;scene.render.resolution_x=1280;scene.render.resolution_y=960;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Ruin daylight');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.28,.31,.35,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.45;scene.view_settings.view_transform='AgX'
for name,pos,power,size in [('Clear warm key',(-5,-6,9),1900,6),('Sky fill',(5,3,8),1100,7)]:
 data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;o=bpy.data.objects.new(name,data);scene.collection.objects.link(o);o.location=pos;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
views={}
for name,pos in [('front',(7,-11,7)),('rear',(-7,11,7)),('right',(12,2,6)),('overhead',(0,-.01,15))]:
 data=bpy.data.cameras.new(name);data.type='ORTHO';camera=bpy.data.objects.new('Review_'+name,data);scene.collection.objects.link(camera);camera.location=pos;camera.rotation_euler=(Vector((0,0,.4))-camera.location).to_track_quat('-Z','Y').to_euler();bpy.context.view_layer.update();right=camera.rotation_euler.to_quaternion()@Vector((1,0,0));up=camera.rotation_euler.to_quaternion()@Vector((0,1,0));pts=[o.matrix_world@v.co for o in scene.objects if o.type=='MESH'for v in o.data.vertices];xs=[(p-camera.location).dot(right)for p in pts];ys=[(p-camera.location).dot(up)for p in pts];camera.location+=right*((max(xs)+min(xs))/2)+up*((max(ys)+min(ys))/2);camera.data.ortho_scale=1.15*max(max(xs)-min(xs),(max(ys)-min(ys))/.75);scene.camera=camera;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
 assert all(0<=p.x<=1 and 0<=p.y<=1 and p.z>0 for p in[world_to_camera_view(scene,camera,o.matrix_world@v.co)for o in scene.objects if o.type=='MESH'for v in o.data.vertices]),name
 views[name]=sha(OUT/(name+'.png'))
review=OUT/'NitroWorks-Ruin-Review.blend';bpy.ops.wm.save_as_mainfile(filepath=str(review))
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes());(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,normalization=dict(scale=scale,shift=list(shift),rotation_degrees=0),triangles=triangles,bounds_m=bounds,removed_parts=removed,project_sha256=sha(project),review_project_sha256=sha(review),components_project_sha256=sha(components),base_project_sha256=sha(base_project),texture_sha256=sha(texture),orm_sha256=sha(surface),views=views,imported=False,game_exported=False,component_count=len(solids),component_solids=solids,preserved_geometry=preserved,debris_supports=debris_supports,limitations=brief['uncertainties']),indent=2)+'\n');print('NITRO_RUIN_AUTHORED',triangles,len(solids),flush=True)
