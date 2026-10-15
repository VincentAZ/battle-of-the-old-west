"""Author three charred core remnants as a separate static damage state."""
from pathlib import Path
import hashlib,json,math
import bpy,bmesh,numpy as np
from PIL import Image
from mathutils import Matrix,Vector
from bpy_extras.object_utils import world_to_camera_view
R=Path(__file__).resolve().parents[1];B=R/'art/western/holdings/expansion-review-v001/timber-ram'
OUT=B/'ruin-source-v002';BRIEF=B/'ruin-brief-v002.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text());assert brief['pre_modeling_review']['completed']
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
for p,h in brief['source_records'].items():assert sha(R/p)==h
assert not OUT.exists();OUT.mkdir()
source=B/brief['preservation']['source'];base_project=B/brief['preservation']['base']
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
heading=Matrix.Rotation(math.radians(65),4,'Z')
pts=[heading@(o.matrix_world@v.co)for o in bpy.context.scene.objects if o.type=='MESH'for v in o.data.vertices]
lo=Vector([min(p[k]for p in pts)for k in range(3)]);hi=Vector([max(p[k]for p in pts)for k in range(3)])
scale=6/max(hi.x-lo.x,hi.y-lo.y);shift=Vector((-(hi.x+lo.x)/2,-(hi.y+lo.y)/2,-lo.z))
normalize=Matrix.Scale(scale,4)@Matrix.Translation(shift)@heading
bpy.ops.wm.read_factory_settings(use_empty=True)
rng=np.random.default_rng(1879);yy,xx=np.mgrid[0:2048,0:2048]
coarse=np.asarray(Image.fromarray(rng.integers(0,256,(90,210),dtype=np.uint8)).resize((2048,2048),Image.Resampling.BICUBIC),dtype=float)/255
grain=np.sin(yy*.20+np.sin(xx*.016)*1.5)
variation=15*(coarse-.5)+4*grain+rng.uniform(-2,2,(2048,2048))
pixels=np.clip(np.array([40,30,21])+variation[...,None],0,255).astype(np.uint8)
texture=OUT/'TimberRam_Ruin_BaseColor.png';Image.fromarray(pixels).save(texture)
mat=bpy.data.materials.new('M_TimberRam_CharredCore');mat.use_nodes=True
bsdf=mat.node_tree.nodes['Principled BSDF'];bsdf.inputs['Roughness'].default_value=.96
node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack();mat.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
pieces=[];solids=[];N=64;K=16
for part,(start,end,factor)in enumerate([(-2.02,-.67,.70),(-.49,.47,.57),(.68,2.02,.65)]):
    verts=[];faces=[];uvs=[]
    def end_relief(x,z):return .006*math.sin(x*43+z*19+part)+.005*math.cos(x*21-z*37)
    for j in range(K+1):
        t=j/K;y=start+(end-start)*t
        radius=(.235-.040*(y+2.1)/4.2)*factor
        for i in range(N):
            a=i*math.tau/N
            rr=radius*(1+.035*math.sin(5*a+y*6)+.025*math.sin(9*a-y*3)+.014*math.sin(a*17-y*11))
            z=radius+rr*math.sin(a)
            if math.sin(a)<-.95:z=0
            else:z=max(.0007,z)
            # Irregular ends represent consumed/broken wood, not planar saw cuts.
            dy=end_relief(rr*math.cos(a),z)if j in (0,K)else 0
            verts.append((rr*math.cos(a),y+dy,z))
    for j in range(K):
        for i in range(N):
            ni=(i+1)%N;faces.append((j*N+i,(j+1)*N+i,(j+1)*N+ni,j*N+ni))
            u0=(start+2.1+(end-start)*j/K)/4.2;u1=(start+2.1+(end-start)*(j+1)/K)/4.2
            uvs.append([(u0,i/N),(u1,i/N),(u1,(i+1)/N),(u0,(i+1)/N)])
    for j in (0,K):
        end_y=start if j==0 else end
        centre_z=(.235-.040*(end_y+2.1)/4.2)*factor
        c=len(verts);verts.append((0,end_y+end_relief(0,centre_z),centre_z))
        rings=[]
        for band in range(1,8):
            indices=[]
            for i in range(N):
                edge=verts[j*N+i];fraction=band/8
                x=edge[0]*fraction;z=centre_z+(edge[2]-centre_z)*fraction
                indices.append(len(verts));verts.append((x,end_y+end_relief(x,z),z))
            rings.append(indices)
        rings.append([j*N+i for i in range(N)])
        def cap_face(face):
            if j==K:face=face[::-1]
            faces.append(tuple(face));uvs.append([(.5+verts[idx][0],.5+verts[idx][2]-centre_z)for idx in face])
        for i in range(N):
            ni=(i+1)%N;cap_face([c,rings[0][i],rings[0][ni]])
            for band in range(7):cap_face([rings[band][i],rings[band+1][i],rings[band+1][ni],rings[band][ni]])
    mesh=bpy.data.meshes.new('Charred remnant');mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new(f'Charred core remnant {part+1}',mesh);bpy.context.collection.objects.link(o);mesh.materials.append(mat);uv=mesh.uv_layers.new()
    for f,coords in zip(mesh.polygons,uvs):
        for li,co in zip(f.loop_indices,coords):uv.data[li].uv=co
        f.use_smooth=f.index<K*N
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update();assert all(e.is_manifold for e in bm.edges)and bm.calc_volume(signed=True)>0
    solids.append(dict(name=o.name,volume_m3=bm.calc_volume(signed=True)));bm.to_mesh(mesh);bm.free();pieces.append(o)
components=OUT/'TimberRam-Ruin-Components.blend';bpy.ops.wm.save_as_mainfile(filepath=str(components))
for o in pieces:o.matrix_world=normalize;o.select_set(True)
bpy.context.view_layer.objects.active=pieces[0];bpy.ops.object.join();ruin=bpy.context.object;ruin.name='SM_HoldingRuin_TimberRam';bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
ruin.data.calc_loop_triangles();triangles=len(ruin.data.loop_triangles);assert triangles<30000
project=OUT/'TimberRam-Ruin.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
with bpy.data.libraries.load(str(base_project),link=False)as(src,dst):dst.objects=['Holding_Base_Ground','Holding_Base_Tuft','Holding_Base_Needle']
for o in dst.objects:bpy.context.collection.objects.link(o)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True;scene.render.threads_mode='FIXED';scene.render.threads=8
scene.render.resolution_x=1280;scene.render.resolution_y=960;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Ruin daylight');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.28,.31,.35,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.45;scene.view_settings.view_transform='AgX'
for name,pos,power,size in [('Clear warm key',(-5,-6,9),1900,6),('Sky fill',(5,3,8),1100,7)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;o=bpy.data.objects.new(name,data);scene.collection.objects.link(o);o.location=pos;o.rotation_euler=(-o.location).to_track_quat('-Z','Y').to_euler()
views={}
for name,pos in [('front',(7,-11,7)),('rear',(-7,11,7)),('right',(12,2,6)),('overhead',(0,-.01,15))]:
    data=bpy.data.cameras.new(name);data.type='ORTHO';camera=bpy.data.objects.new('Review_'+name,data);scene.collection.objects.link(camera);camera.location=pos;camera.rotation_euler=(Vector((0,0,.15))-camera.location).to_track_quat('-Z','Y').to_euler();bpy.context.view_layer.update()
    right=camera.rotation_euler.to_quaternion()@Vector((1,0,0));up=camera.rotation_euler.to_quaternion()@Vector((0,1,0));pts=[o.matrix_world@v.co for o in scene.objects if o.type=='MESH'for v in o.data.vertices]
    xs=[(p-camera.location).dot(right)for p in pts];ys=[(p-camera.location).dot(up)for p in pts];camera.location+=right*((max(xs)+min(xs))/2)+up*((max(ys)+min(ys))/2);camera.data.ortho_scale=1.15*max(max(xs)-min(xs),(max(ys)-min(ys))/.75)
    scene.camera=camera;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True);views[name]=sha(OUT/(name+'.png'))
review=OUT/'TimberRam-Ruin-Review.blend';bpy.ops.wm.save_as_mainfile(filepath=str(review))
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',brief_sha256=sha(BRIEF),source_sha256=sha(source),source_unchanged=True,normalization=dict(scale=scale,shift=list(shift),rotation_degrees=65),triangles=triangles,project_sha256=sha(project),review_project_sha256=sha(review),components_project_sha256=sha(components),base_project_sha256=sha(base_project),texture_sha256=sha(texture),views=views,imported=False,game_exported=False,component_count=3,component_solids=solids,limitations=brief['uncertainties']),indent=2)+'\n')
print('TIMBER_RAM_RUIN_AUTHORED',triangles,flush=True)
