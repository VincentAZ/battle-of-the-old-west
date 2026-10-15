"""Create a sourced plain tree-trunk ram, with no invented siege machinery."""
import hashlib,json,math
from pathlib import Path
import bpy,bmesh,numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'art/western/holdings/expansion-review-v001/timber-ram'
OUT=BASE/'local-source-v002';BRIEF=BASE/'local-authoring-brief-v002.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
brief=json.loads(BRIEF.read_text());assert brief['pre_modeling_review']['completed']
assert sha(BASE/'historical-evidence.json')==brief['historical_evidence_sha256']
for p,h in brief['source_records'].items():assert sha(ROOT/p)==h,p
assert 'mixar' in Path(bpy.app.binary_path).name.lower()
assert not OUT.exists();OUT.mkdir()
bpy.ops.wm.read_factory_settings(use_empty=True)
rng=np.random.default_rng(1879)
# An original procedural atlas, based on the documented material hues and
# irregular plated bark. It does not copy or project the reference photographs.
w,h=1024,700;yy,xx=np.mgrid[0:h,0:w]
def noise(nx,ny):
    small=Image.fromarray(rng.uniform(0,255,(ny,nx)).astype(np.uint8))
    return np.asarray(small.resize((w,h),Image.Resampling.BICUBIC),dtype=float)/255
# Warped, unequal plates with small layered flakes, rather than a tile grid.
wx=xx+18*(noise(25,21)-.5)+5*(noise(100,80)-.5)
wy=yy+15*(noise(29,19)-.5)+4*(noise(100,80)-.5)
best=np.full((h,w),np.inf);second=best.copy();labels=np.zeros((h,w),int)
centres=list(zip(rng.uniform(-30,w+30,760),rng.uniform(-30,h+30,760)))
for i,(cx,cy)in enumerate(centres):
    dist=((wx-cx)/1.6)**2+(wy-cy)**2
    mask=dist<best;second=np.where(mask,best,np.minimum(second,dist));best=np.where(mask,dist,best);labels=np.where(mask,i,labels)
tints=rng.uniform(-23,25,len(centres));edge=np.clip((np.sqrt(second)-np.sqrt(best))/(2.2+noise(120,100)*2.8),0,1)
flakes=noise(240,180);grain=21*(noise(140,100)-.5)+12*(flakes-.5)+6*(noise(600,400)-.5)
bright=np.array([162,83,37])+tints[labels,...,None]+grain[...,None]
bright+=np.maximum(flakes-.63,0)[...,None]*np.array([80,71,52])
dark=np.array([57,30,18]);bark=dark+(bright-dark)*edge[...,None]
image=Image.new('RGB',(2048,2048),(109,62,29))
image.paste(Image.fromarray(np.clip(bark,0,255).astype(np.uint8)).resize((2048,1400),Image.Resampling.BICUBIC),(0,0))
pix=np.array(image);Y,X=np.mgrid[0:2048,0:2048]
for cx in (512,1536):
    dx=(X-cx)/295;dy=(Y-1724)/295;rad=np.sqrt(dx*dx+dy*dy);ang=np.arctan2(dy,dx)
    rr=rad+.010*np.sin(ang*4)+.005*np.cos(ang*7)
    rings=np.sin(rr*math.tau*26);fine=1.5*np.sin(X*.81+Y*.11)
    mix=np.clip((rad-.66)/.19,0,1)
    rgb=np.array([188,130,69])+(np.array([237,211,151])-np.array([188,130,69]))*mix[...,None]
    rgb-=np.maximum(rings,0)[...,None]*np.array([15,16,12]);rgb+=fine[...,None]
    for a in (.24,2.1,4.6):
        delta=np.arctan2(np.sin(ang-a),np.cos(ang-a));check=(abs(delta)<.010)&(rad>.64)&(rad<.98)
        rgb[check]=[101,65,32]
    inside=rad<=1.01;pix[inside]=np.clip(rgb,0,255).astype(np.uint8)[inside]
texture=OUT/'TimberRam_BaseColor.png';Image.fromarray(pix).save(texture)
material=bpy.data.materials.new('M_TimberRam_Atlas');material.use_nodes=True
bsdf=material.node_tree.nodes['Principled BSDF'];bsdf.inputs['Roughness'].default_value=.87
node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(texture));node.image.pack()
material.node_tree.links.new(node.outputs['Color'],bsdf.inputs['Base Color'])

N=80;K=40;L=4.2;verts=[]
for j in range(K+1):
    t=j/K;nominal=.235-.040*t
    for i in range(N):
        a=i*math.tau/N
        relief=.007*math.sin(a*7+t*9)+.004*math.sin(a*19-t*16)+.003*math.sin(t*52+a*3)
        rr=nominal+relief
        x=rr*math.cos(a)+.009*math.sin(t*math.pi)
        y=-L/2+L*t
        # Planar cuts prevent artificial radial fan shading on the end grain.
        z=nominal+rr*math.sin(a)
        # A narrow contact strip keeps the rested log grounded along its length.
        if math.sin(a)<-.97:z=0
        else:z=max(z,.001)
        verts.append((x,y,z))
verts.extend([(0,-L/2,.235),(0,L/2,.195)])
faces=[];uvs=[]
for j in range(K):
    for i in range(N):
        ni=(i+1)%N;faces.append((j*N+i,(j+1)*N+i,(j+1)*N+ni,j*N+ni))
        # Longitudinal U and continuous angular V, with seam at the far side.
        u0=.003+j/K*.994;u1=.003+(j+1)/K*.994
        v0=1-(8+i/N*1384)/2048;v1=1-(8+(i+1)/N*1384)/2048
        uvs.append([(u0,v0),(u1,v0),(u1,v1),(u0,v1)])
for j,cx in [(0,512),(K,1536)]:
    centre=(K+1)*N+(j==K)
    for i in range(N):
        ring=[j*N+i,j*N+(i+1)%N]
        face=(centre,*ring)if j==0 else (centre,*ring[::-1]);faces.append(face)
        capuv=[]
        for idx in face:
            if idx==centre:capuv.append((cx/2048,1-1724/2048))
            else:
                a=(idx%N)*math.tau/N
                capuv.append(((cx+289*math.cos(a))/2048,1-(1724+289*math.sin(a))/2048))
        uvs.append(capuv)
mesh=bpy.data.meshes.new('Plain trunk');mesh.from_pydata(verts,[],faces);mesh.update()
o=bpy.data.objects.new('Timber ram — plain pine trunk',mesh);bpy.context.collection.objects.link(o);mesh.materials.append(material)
uv=mesh.uv_layers.new()
for f,coords in zip(mesh.polygons,uvs):
    for loop,co in zip(f.loop_indices,coords):uv.data[loop].uv=co
    f.use_smooth=f.index<K*N
bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.normal_update()
assert all(e.is_manifold for e in bm.edges)and bm.calc_volume(signed=True)>0
assert all(f.calc_area()>1e-12 for f in bm.faces)
volume=bm.calc_volume(signed=True);bm.to_mesh(mesh);bm.free()
mesh.calc_loop_triangles();triangles=len(mesh.loop_triangles);assert triangles<=30000
o.select_set(True);bpy.context.view_layer.objects.active=o
project=OUT/'TimberRam.blend';bpy.ops.wm.save_as_mainfile(filepath=str(project))
glb=OUT/'TimberRam.glb';bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_apply=True,export_animations=False,export_materials='EXPORT')
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='authored_unreviewed',brief_sha256=sha(BRIEF),project_sha256=sha(project),glb_sha256=sha(glb),atlas_sha256=sha(texture),objects=1,triangles=triangles,volume_m3=volume,materials=1,rigged=False,animations=0,limitations=brief['reconstruction']),indent=2)+'\n')
print('TIMBER_RAM_AUTHORED',triangles,volume,flush=True)
