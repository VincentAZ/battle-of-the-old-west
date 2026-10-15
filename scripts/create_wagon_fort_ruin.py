"""Author a separate, sourced static Wagon Fort ruin; no game export/import."""
from pathlib import Path
import hashlib,json,math,random
import bpy,bmesh
import numpy as np
from PIL import Image
from mathutils import Matrix,Vector
from bpy_extras.object_utils import world_to_camera_view

R=Path(__file__).resolve().parents[1]
B=R/'art/western/holdings/expansion-review-v001/wagon-fort'
OUT=B/'ruin-source-v002';BRIEF=B/'ruin-brief-v002.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text());assert brief['pre_modeling_review']['completed']
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
for p,h in brief['source_records'].items():assert sha(R/p)==h
assert not OUT.exists();OUT.mkdir()
source=B/brief['preservation']['source'];base_project=B/brief['preservation']['base']
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
original=[o for o in bpy.context.scene.objects if o.type=='MESH']
heading=Matrix.Rotation(math.radians(-50),4,'Z')
pts=[heading@(o.matrix_world@v.co) for o in original for v in o.data.vertices]
lo=Vector([min(p[k] for p in pts) for k in range(3)])
hi=Vector([max(p[k] for p in pts) for k in range(3)])
scale=6.5/max(hi.x-lo.x,hi.y-lo.y)
shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z))
normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)@heading
mat=bpy.data.materials.new('M_WagonFort_CharredTimber');mat.use_nodes=True
bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Roughness'].default_value=.94
rng=random.Random(1867);nrng=np.random.default_rng(1867)
old=np.asarray(Image.open(B/'local-source-v004/WagonFort_BaseColor.png').convert('RGB'))
coarse=np.asarray(Image.fromarray(nrng.integers(0,256,(80,80),dtype=np.uint8)).resize((2048,2048),Image.Resampling.BICUBIC)).astype(float)
yy,xx=np.mgrid[0:2048,0:2048]
grain=5*np.sin(yy*.10+np.sin(xx*.035))
variation=(coarse/255-.5)*18+grain+nrng.uniform(-2,2,(2048,2048))
pixels=np.clip(np.array([37,27,19])+variation[...,None],0,255).astype(np.uint8)
# Iron keeps its material colour. Only the derivative wooden atlas patches
# receive char; the original paint and the separate earth source are untouched.
pixels[1032:2041,8:675]=old[1032:2041,8:675]
texture=OUT/'WagonFort_Ruin_BaseColor.png';Image.fromarray(pixels).save(texture)
node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack()
mat.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])

kept=[];removed=[];preserved=[];roles={};moved={};transforms={}
for o in original:
    world=[o.matrix_world@v.co for v in o.data.vertices]
    for v,p in zip(o.data.vertices,world):v.co=p
    o.matrix_world=Matrix.Identity(4)


def assign(o,role):
    o.data.materials.clear();o.data.materials.append(mat);kept.append(o);roles[o.name]=role


def bevel(o):
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
    m=o.modifiers.new('Small rounded charred corners','BEVEL');m.width=.003;m.segments=1
    bpy.ops.object.modifier_apply(modifier=m.name)


own_groups={i:[o for o in original if o.get('wagon_index')==i] for i in range(8)}
for index in range(8):
    theta=index*math.tau/9
    frame=Matrix.Translation((6.7*math.cos(theta),6.7*math.sin(theta),0))@Matrix.Rotation(theta,4,'Z')
    inverse=frame.inverted()
    own=own_groups[index]
    # Solve the bed's tilt from the actual runner geometry. The lowest runner
    # end meets earth; the rear bolster continues to support the other end.
    runners=[o for o in own if o.name[4:].startswith('Red bed runner')]
    runner_points=[inverse@v.co for o in runners for v in o.data.vertices]
    pivot=Vector((0,1.08,1.0))
    def tilt(angle):return Matrix.Translation(pivot)@Matrix.Rotation(angle,4,'X')@Matrix.Translation(-pivot)
    low,high=0,.6
    for _ in range(32):
        mid=(low+high)/2
        if min((tilt(mid)@p).z for p in runner_points)>0:low=mid
        else:high=mid
    angle=(low+high)/2;body=tilt(angle)
    transforms[str(index)]=dict(body_tilt_radians=angle,frame=[list(row) for row in frame])
    for o in own:
        name=o.name[4:];local=[inverse@v.co for v in o.data.vertices]
        centre=sum(local,Vector())/len(local)
        wheel=name.startswith(('Red wheel felloe','Iron wheel tire','Red wheel hub','Red dished spoke','Retaining linchpin'))
        if wheel and centre.y>0:
            assign(o,'rear_wheel');preserved.append(o.name);continue
        if name.startswith(('Red wood axle','Iron axle','Red bolster')) and centre.y>0:
            assign(o,'rear_running_gear');preserved.append(o.name);continue
        if wheel and not name.startswith('Retaining linchpin'):
            side=-1 if centre.x<0 else 1
            centre_old=Vector((side*.88,-1.08,.54))
            # Both wheels fall inward; their hubs rest on earth. Staggering
            # the pair keeps the inner corral open and avoids the tilted bed.
            centre_new=Vector((0,-2.0,.13)) if side<0 else Vector((-1.30,-1.40,.13))
            transform=frame@Matrix.Translation(centre_new)@Matrix.Rotation(math.pi/2,4,'Y')@Matrix.Translation(-centre_old)@inverse
            o.data.transform(transform);o['fallen_wheel']=f'{index}-{side}'
            moved[o.name]=[list(row) for row in transform]
            assign(o,'fallen_wheel');continue
        if name.startswith(('Floor plank','Red bed runner')):
            transform=frame@body@inverse;o.data.transform(transform)
            moved[o.name]=[list(row) for row in transform]
            assign(o,'tilted_bed');continue
        if name.startswith(('Blue side plank','Blue end plank')) and centre.z<1.2 and not (name.startswith('Blue end plank') and centre.y<0):
            bottom=min(p.z for p in local);top=max(p.z for p in local)
            for v,p in zip(o.data.vertices,local):
                if p.z>bottom+.001:
                    # Low uneven charred edge, still one closed solid.
                    p.z=bottom+.08+.027*math.sin(p.y*3.1+p.x*2.2+index)
                v.co=p
            bevel(o);o.data.transform(frame@body)
            assign(o,'lower_box_remnant');continue
        removed.append(o.name);bpy.data.objects.remove(o,do_unlink=True)
    # Six separate charred plank fragments sit directly on the actual bed.
    for j,(x,y) in enumerate([(x,y) for y in (-.90,-.10,.70) for x in (-.25,.25)]):
        bpy.ops.mesh.primitive_cube_add(size=1,location=(x,y,1.061))
        o=bpy.context.object;o.name=f'W{index+1:02d} Fallen charred bed fragment {j}'
        o.dimensions=(rng.uniform(.30,.38),rng.uniform(.07,.10),.042)
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        o.rotation_euler.z=rng.uniform(-.25,.25);bpy.context.view_layer.update()
        o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
        uv=o.data.uv_layers.active or o.data.uv_layers.new()
        for item in uv.data:item.uv=(.4+item.uv.x*.18,.02+item.uv.y*.46)
        bevel(o);o.data.transform(frame@body)
        o['wagon_index']=index;assign(o,'fallen')

# A collapsed chain can retain interlinked upright/flat rings in contact with
# earth. Each original link is translated vertically; its iron geometry stays
# intact. Links are connected objects, not loose-timber collision candidates.
for o in list(bpy.context.scene.objects):
    if o.name.startswith('Connecting chain'):
        dz=-min(v.co.z for v in o.data.vertices)
        transform=Matrix.Translation((0,0,dz));o.data.transform(transform)
        moved[o.name]=[list(row) for row in transform];assign(o,'fallen_chain')
    elif o.name.startswith('Entrance slack chain'):
        assign(o,'entrance_chain');preserved.append(o.name)

# Verify actual solids before joining; normalized source coordinates stay available
# in a separate components file for independent support and preservation checks.
bpy.context.view_layer.update();solids=[]
for o in kept:
 o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update()
 assert all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True)>0,o.name
 assert all(f.calc_area()>1e-12 for f in bm.faces),o.name
 solids.append(dict(name=o.name,role=roles[o.name],closed=True,volume_m3=bm.calc_volume(signed=True)));bm.to_mesh(o.data);bm.free()
components=OUT/'WagonFort-Ruin-Components.blend';bpy.ops.wm.save_as_mainfile(filepath=str(components))
for o in kept:o.matrix_world=normalize@o.matrix_world
bpy.ops.object.select_all(action='DESELECT')
for o in kept:o.select_set(True)
bpy.context.view_layer.objects.active=kept[0];bpy.ops.object.join();ruin=bpy.context.object;ruin.name='SM_HoldingRuin_WagonFort'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles)
assert 0<triangles<30000 and len(ruin.data.materials)==1
coords=[v.co for v in ruin.data.vertices];bounds=dict(min=[min(p[i] for p in coords) for i in range(3)],max=[max(p[i] for p in coords) for i in range(3)])
assert abs(bounds['min'][2])<1e-6 and bounds['max'][2]<1.0
project=OUT/'WagonFort-Ruin.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
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
review=OUT/'WagonFort-Ruin-Review.blend';bpy.ops.wm.save_as_mainfile(filepath=str(review))
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,normalization=dict(scale=scale,shift=list(shift),rotation_degrees=-50),triangles=triangles,bounds_m=bounds,removed_parts=removed,project_sha256=sha(project),review_project_sha256=sha(review),components_project_sha256=sha(components),base_project_sha256=sha(base_project),texture_sha256=sha(texture),views=views,imported=False,game_exported=False,component_count=len(solids),component_solids=solids,preserved_geometry=preserved,fallen_timbers=48,wagon_transforms=transforms,moved_parts=moved,limitations=brief['uncertainties']),indent=2)+'\n')
print('WAGON_FORT_RUIN_AUTHORED',triangles,len(solids),flush=True)
