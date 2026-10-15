"""Author a separate, sourced static Revival Tent ruin; no game export/import."""
from pathlib import Path
import hashlib,json,math,random
import bpy,bmesh
import numpy as np
from PIL import Image
from mathutils import Matrix,Vector
from bpy_extras.object_utils import world_to_camera_view

R=Path(__file__).resolve().parents[1]
B=R/'art/western/holdings/expansion-review-v001/revival-tent'
OUT=B/'ruin-source-v002';BRIEF=B/'ruin-brief-v002.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text());assert brief['pre_modeling_review']['completed']
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
for p,h in brief['source_records'].items():assert sha(R/p)==h
assert not OUT.exists();OUT.mkdir()
source=B/brief['preservation']['source'];base_project=B/brief['preservation']['base']
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
original=[o for o in bpy.context.scene.objects if o.type=='MESH']
heading=Matrix.Rotation(0,4,'Z')
pts=[heading@(o.matrix_world@v.co) for o in original for v in o.data.vertices]
lo=Vector([min(p[k] for p in pts) for k in range(3)])
hi=Vector([max(p[k] for p in pts) for k in range(3)])
scale=5.5/max(hi.x-lo.x,hi.y-lo.y)
shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z))
normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)@heading
mat=bpy.data.materials.new('M_RevivalTent_CharredTimber');mat.use_nodes=True
bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.94
rng=random.Random(1874);nrng=np.random.default_rng(1874)

coarse=np.asarray(Image.fromarray(nrng.integers(0,256,(80,80),dtype=np.uint8)).resize((2048,2048),Image.Resampling.BICUBIC)).astype(float)
yy,xx=np.mgrid[0:2048,0:2048]
variation=(coarse/255-.5)*18+5*np.sin(yy*.10+np.sin(xx*.035))+nrng.uniform(-2,2,(2048,2048))
pixels=np.clip(np.array([39,28,18])+variation[...,None],0,255).astype(np.uint8)
texture=OUT/'RevivalTent_Ruin_BaseColor.png';Image.fromarray(pixels).save(texture)
node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack()
mat.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
kept=[];removed=[];preserved=[];roles={}
for o in original:
    world=[o.matrix_world@v.co for v in o.data.vertices]
    for v,p in zip(o.data.vertices,world):v.co=p
    o.matrix_world=Matrix.Identity(4)

def assign(o,role):
    o.data.materials.clear();o.data.materials.append(mat);kept.append(o);roles[o.name]=role

def bevel(o):
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
    m=o.modifiers.new('Rounded charred corners','BEVEL');m.width=.003;m.segments=1
    bpy.ops.object.modifier_apply(modifier=m.name)

for o in original:
    n=o.name
    if n.startswith(('Wooden stake ','Platform ')):
        assign(o,'preserved_stake' if n.startswith('Wooden stake ')else 'preserved_platform');preserved.append(n);continue
    if n.startswith(('Central timber mast','Perimeter pole ')):
        h=.42 if n.startswith('Central')else rng.uniform(.16,.54)
        for v in o.data.vertices:
            if v.co.z>.001:v.co.z=h+.025*math.sin(v.co.x*17+v.co.y*11)
        bevel(o);assign(o,'mast_stump' if n.startswith('Central')else 'perimeter_stump');continue
    if n.startswith('Bench ')and ' seat' in n:
        centre=sum((v.co for v in o.data.vertices),Vector())/len(o.data.vertices)
        zmin=min(v.co.z for v in o.data.vertices)
        length_factor=rng.uniform(.63,.87)
        dx,dy=rng.uniform(-.08,.08),rng.uniform(-.07,.07)
        angle=rng.uniform(-.13,.13)
        for v in o.data.vertices:
            v.co.x=centre.x+(v.co.x-centre.x)*length_factor
            v.co.y=centre.y+(v.co.y-centre.y)*.92
            v.co.z=(v.co.z-zmin)*.78
        for v in o.data.vertices:
            if v.co.z>.001:v.co.x+=rng.uniform(-.035,.035)
        rotation=Matrix.Translation((centre.x+dx,centre.y+dy,0))@Matrix.Rotation(angle,4,'Z')@Matrix.Translation((-centre.x,-centre.y,0))
        o.data.transform(rotation)
        bevel(o);assign(o,'fallen_bench_seat');continue
    removed.append(n);bpy.data.objects.remove(o,do_unlink=True)

def fallen_pole(name,centre,length,radius,angle,sides,role):
    bpy.ops.mesh.primitive_cylinder_add(vertices=sides,radius=radius,depth=length,location=centre)
    o=bpy.context.object;o.name=name
    o.rotation_euler=(Matrix.Rotation(angle,4,'Z')@Matrix.Rotation(math.pi/2,4,'Y')).to_euler()
    bpy.context.view_layer.update()
    world=[o.matrix_world@v.co for v in o.data.vertices];bottom=min(p.z for p in world)
    for v,p in zip(o.data.vertices,world):v.co=p-Vector((0,0,bottom))
    o.matrix_world=Matrix.Identity(4);bevel(o)
    lowest=min(v.co.z for v in o.data.vertices)
    for v in o.data.vertices:v.co.z-=lowest
    assign(o,role)

fallen_pole('Fallen central mast core',(.11,-2.0,.08),3.0,.073,math.pi/2,12,'fallen_mast')
for i in range(16):
    a=i*math.tau/16+math.pi/16;r=rng.uniform(3.70,3.83)
    fallen_pole(f'Fallen perimeter timber {i:02}',(r*math.cos(a),r*math.sin(a),.05),rng.uniform(.67,.88),.043,a+math.pi/2+rng.uniform(-.95,.95),8,'fallen_perimeter')
for i,(x,y)in enumerate([(-.5,2.48),(.5,2.48),(-.5,2.93),(.5,2.93)]):
    bpy.ops.mesh.primitive_cube_add(size=1,location=(x,y,.261))
    o=bpy.context.object;o.name=f'Fallen lectern fragment {i}'
    o.dimensions=(.36,.09,.042);o.rotation_euler.z=rng.uniform(-.18,.18)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bpy.context.view_layer.update();points=[o.matrix_world@v.co for v in o.data.vertices]
    for v,p in zip(o.data.vertices,points):v.co=p
    o.matrix_world=Matrix.Identity(4);bevel(o);assign(o,'fallen_lectern')

# Verify actual solids before joining; normalized source coordinates stay available
# in a separate components file for independent support and preservation checks.
bpy.context.view_layer.update();solids=[]
for o in kept:
 o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update()
 assert all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True)>0,o.name
 assert all(f.calc_area()>1e-12 for f in bm.faces),o.name
 solids.append(dict(name=o.name,role=roles[o.name],closed=True,volume_m3=bm.calc_volume(signed=True)));bm.to_mesh(o.data);bm.free()
components=OUT/'RevivalTent-Ruin-Components.blend';bpy.ops.wm.save_as_mainfile(filepath=str(components))
for o in kept:o.matrix_world=normalize@o.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for o in kept:o.select_set(True)
bpy.context.view_layer.objects.active=kept[0];bpy.ops.object.join();ruin=bpy.context.object;ruin.name='SM_HoldingRuin_RevivalTent'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
coords=[v.co for v in ruin.data.vertices];bounds=dict(min=[min(p[i] for p in coords) for i in range(3)],max=[max(p[i] for p in coords) for i in range(3)])
assert abs(bounds['min'][2])<1e-6 and bounds['max'][2]<1.0
project=OUT/'RevivalTent-Ruin.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
# Import only the unchanged static setting objects for honest contextual renders.
with bpy.data.libraries.load(str(base_project),link=False) as (src,dst):dst.objects=['Holding_Base_Ground','Holding_Base_Tuft']
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
review=OUT/'RevivalTent-Ruin-Review.blend';bpy.ops.wm.save_as_mainfile(filepath=str(review))
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,normalization=dict(scale=scale,shift=list(shift),rotation_degrees=0),triangles=triangles,bounds_m=bounds,removed_parts=removed,project_sha256=sha(project),review_project_sha256=sha(review),components_project_sha256=sha(components),base_project_sha256=sha(base_project),texture_sha256=sha(texture),views=views,imported=False,game_exported=False,component_count=len(solids),component_solids=solids,preserved_geometry=preserved,limitations=brief['uncertainties']),indent=2)+'\n')
print('REVIVAL_TENT_RUIN_AUTHORED',triangles,len(solids),flush=True)
