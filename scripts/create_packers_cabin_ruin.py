"""Separate documented static cabin ruin; preserve healthy sources and setting."""
from pathlib import Path
import hashlib,json,math,random,re
import bpy,bmesh,numpy as np
from PIL import Image,ImageDraw
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
R=Path(__file__).resolve().parents[1];B=R/'art/western/holdings/expansion-review-v001/packers-cabin';OUT=B/'ruin-source-v002';BRIEF=B/'ruin-brief-v002.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text());assert brief['pre_modeling_review']['completed']
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
for p,h in brief['source_records'].items():assert sha(R/p)==h
assert not OUT.exists();OUT.mkdir();source=B/brief['preservation']['source'];base_project=B/brief['preservation']['base']
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
original=[o for o in bpy.context.scene.objects if o.type=='MESH'];pts=[o.matrix_world@v.co for o in original for v in o.data.vertices]
lo=Vector([min(p[k]for p in pts)for k in range(3)]);hi=Vector([max(p[k]for p in pts)for k in range(3)])
scale=4.5/max(hi.x-lo.x,hi.y-lo.y);shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z));normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)
rng=random.Random(187409);nrng=np.random.default_rng(187409)
# New procedural atlas uses the healthy tile arrangement, with material-specific
# char colours; stone and earth remain natural mineral colours.
palette={'wood':(40,28,18),'roof':(37,26,17),'stone':(188,157,113),'chink':(149,125,94),'endgrain':(45,31,20),'door':(39,27,18),'inside':(95,68,42)}
atlas=Image.new('RGB',(2048,2048));regions={}
for i,(key,color)in enumerate(palette.items()):
 x,y=(i%4)*512,(i//4)*512;regions[key]=(x+8,y+8,x+504,y+504)
 yy,xx=np.mgrid[0:512,0:512];coarse=np.asarray(Image.fromarray(nrng.integers(0,256,(23,23),dtype=np.uint8)).resize((512,512),Image.Resampling.BICUBIC)).astype(float)
 variation=(coarse/255-.5)*(18 if key in ('wood','roof','endgrain','door')else 8)+nrng.uniform(-2,2,(512,512))
 if key in ('wood','roof','endgrain','door'):variation+=4*np.sin(yy*.16+np.sin(xx*.045))
 tile=Image.fromarray(np.clip(np.array(color)+variation[...,None],0,255).astype(np.uint8));atlas.paste(tile,(x,y))
texture=OUT/'PackersCabin_Ruin_BaseColor.png';atlas.save(texture)
mat=bpy.data.materials.new('M_PackersCabin_Ruin');mat.use_nodes=True;bsdf=mat.node_tree.nodes['Principled BSDF'];bsdf.inputs['Roughness'].default_value=.94
node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack();mat.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
kept=[];removed=[];preserved=[];roles={}
def assign(o,role):
 o.data.materials.clear();o.data.materials.append(mat)
 for f in o.data.polygons:f.material_index=0
 kept.append(o);roles[o.name]=role
for o in original:
 n=o.name;world=[o.matrix_world@v.co for v in o.data.vertices]
 if n.startswith(('Stone wall footing','Interior earth floor')) or(n.startswith('Chimney rubble')and max(p.z for p in world)<1.53):
  if n.startswith('Chimney rubble')and max(p.z for p in world)>1.15:
   bpy.ops.mesh.primitive_cube_add(size=1,location=(-2.20,0,1.6));cut=bpy.context.object;cut.dimensions=(.36,.38,1.0);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
   bpy.context.view_layer.objects.active=o;mod=o.modifiers.new('Open reconstructed upper flue','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cut,do_unlink=True)
   bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6);bm.to_mesh(o.data);bm.free();assign(o,'cut_chimney');continue
  assign(o,'preserved_floor'if n=='Interior earth floor'else'preserved_stone');preserved.append(n);continue
 if n.startswith('Wall X log '):
  row=int(re.match(r'Wall X log (\d+)',n)[1]);rear=o.location.y>0
  if row<(3 if rear else 2):assign(o,'charred_wall');continue
 if n.startswith('Wall Y log '):
  row=int(re.match(r'Wall Y log (\d+)',n)[1]);right=o.location.x>0
  if row<(4 if right else 2):assign(o,'charred_wall');continue
 if n=='Door threshold':assign(o,'charred_threshold');continue
 removed.append(n);bpy.data.objects.remove(o,do_unlink=True)
def map_char(o):
 uv=o.data.uv_layers.active or o.data.uv_layers.new();x0,y0,x1,y1=regions['wood']
 for f in o.data.polygons:
  axes=sorted(range(3),key=lambda k:abs(f.normal[k]))[:2];points=[o.data.vertices[i].co for i in f.vertices];lo=[min(p[k]for p in points)for k in axes];hi=[max(p[k]for p in points)for k in axes]
  for i in f.loop_indices:
   p=o.data.vertices[o.data.loops[i].vertex_index].co;u=(p[axes[0]]-lo[0])/max(hi[0]-lo[0],1e-8);v=(p[axes[1]]-lo[1])/max(hi[1]-lo[1],1e-8)
   uv.data[i].uv=((x0+8+u*(x1-x0-16))/2048,1-(y1-8-v*(y1-y0-16))/2048)
def fragment(name,x,y,length,radius,angle,support,role):
 bpy.ops.mesh.primitive_cone_add(vertices=10,radius1=radius,radius2=radius*.75,depth=length,location=(x,y,0));o=bpy.context.object;o.name=name
 o.rotation_euler=(Matrix.Rotation(angle,4,'Z')@Matrix.Rotation(math.pi/2,4,'Y')).to_euler();bpy.context.view_layer.update()
 lowest=min((o.matrix_world@v.co).z for v in o.data.vertices);o.location.z+=support-lowest;map_char(o);assign(o,role)
def tree(o):return BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[list(f.vertices)for f in o.data.polygons],epsilon=.015)
debris=[]
for attempt in range(1000):
 if len(debris)==16:break
 fragment(f'Fallen roof core {len(debris):02}',rng.uniform(-1.30,1.30),rng.uniform(-.95,.95),rng.uniform(.28,.71),rng.uniform(.035,.075),rng.uniform(-math.pi,math.pi),.07,'fallen_roof')
 o=kept[-1];bpy.context.view_layer.update();candidate=tree(o)
 if any(candidate.overlap(tree(other))for other in kept[:-1]if roles[other.name]!='preserved_floor'):
  kept.remove(o);roles.pop(o.name);bpy.data.objects.remove(o,do_unlink=True);continue
 debris.append(o)
assert len(debris)==16
fragment('Rear crown remnant 0',-1.02,1.45,.72,.06,.025,.82,'wall_crown')
fragment('Rear crown remnant 1',.78,1.45,.61,.055,-.02,.82,'wall_crown')
bpy.context.view_layer.update();solids=[]
for o in kept:
 bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world);bm.normal_update()
 assert all(e.is_manifold for e in bm.edges)and bm.calc_volume(signed=True)>0,o.name
 assert all(f.calc_area()>1e-12 for f in bm.faces),o.name
 solids.append(dict(name=o.name,role=roles[o.name],closed=True,volume_m3=bm.calc_volume(signed=True)));bm.free()
components=OUT/'PackersCabin-Ruin-Components.blend';bpy.ops.wm.save_as_mainfile(filepath=str(components))
for o in kept:o.matrix_world=normalize@o.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for o in kept:o.select_set(True)
bpy.context.view_layer.objects.active=kept[0];bpy.ops.object.join();ruin=bpy.context.object;ruin.name='SM_HoldingRuin_PackersCabin';bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
coords=[v.co for v in ruin.data.vertices];bounds=dict(min=[min(p[i]for p in coords)for i in range(3)],max=[max(p[i]for p in coords)for i in range(3)])
assert abs(bounds['min'][2])<1e-6 and bounds['max'][2]<1.5
project=OUT/'PackersCabin-Ruin.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
base_names=['Holding_Base_Ground','Holding_Base_Tuft','Holding_Base_Rock','Holding_Base_Needle']
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
review=OUT/'PackersCabin-Ruin-Review.blend';bpy.ops.wm.save_as_mainfile(filepath=str(review))
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,normalization=dict(scale=scale,shift=list(shift),rotation_degrees=0),triangles=triangles,bounds_m=bounds,removed_parts=removed,project_sha256=sha(project),review_project_sha256=sha(review),components_project_sha256=sha(components),base_project_sha256=sha(base_project),texture_sha256=sha(texture),views=views,imported=False,game_exported=False,component_count=len(solids),component_solids=solids,preserved_geometry=preserved,limitations=brief['uncertainties']),indent=2)+'\n')
print('PACKERS_CABIN_RUIN_AUTHORED',triangles,len(solids),flush=True)
