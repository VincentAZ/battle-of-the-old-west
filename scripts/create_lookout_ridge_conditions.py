"""Create separate geological conditions; never mutate the healthy source."""
import hashlib
import json
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector
from mathutils.noise import noise
from mathutils.geometry import delaunay_2d_cdt

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'art/western/holdings/expansion-review-v001/lookout-ridge'
kind = sys.argv[sys.argv.index('--')+1]
assert kind in ('damage', 'ruin')
condition = 'Damaged' if kind == 'damage' else 'Ruin'
version = 'v003' if kind == 'damage' else 'v002'
OUT = BASE/(kind+'-source-'+version)
BRIEF = BASE/(kind+'-brief-'+version+'.json')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
brief = json.loads(BRIEF.read_text())
assert brief['status'] == 'prepared_before_condition_modeling'
for key, digest in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:
    assert sha(BASE/brief['preservation'][key]) == brief['preservation'][digest]
assert not OUT.exists()
OUT.mkdir()
bpy.ops.wm.open_mainfile(filepath=str(BASE/brief['preservation']['reviewed_mesh']),use_scripts=False)
ridge = next(o for o in bpy.context.scene.objects if o.name.endswith('_Holding_Review'))
material = ridge.data.materials[0]
for obj in list(bpy.context.scene.objects):
    if obj != ridge: bpy.data.objects.remove(obj,do_unlink=True)
kept=[]
rng=random.Random(18661008 if kind=='damage' else 18661009)


def set_uv(obj, pale=False, limestone=False):
    mesh=obj.data; mesh.update(); uv=mesh.uv_layers.active or mesh.uv_layers.new()
    for face in mesh.polygons:
        axis=max(range(3),key=lambda k:abs(face.normal[k]))
        for loop in face.loop_indices:
            p=mesh.vertices[mesh.loops[loop].vertex_index].co
            u=(p.x+3.3)/6.6 if axis!=0 else (p.y+2.2)/4.4
            v=(p.z/2.8) if axis!=2 else (p.y+2.2)/4.4
            uv.data[loop].uv=(.05+.9*u,(.83+.15*v) if limestone else .79*(p.z+.10)/3.15)


if kind=='damage':
    bm=bmesh.new();bm.from_mesh(ridge.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
    cut=bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
        dist=1e-6,plane_co=(1.15,-.50,1.0),plane_no=(.8,-1,.35),clear_outer=True,clear_inner=False)
    edges=[e for e in bm.edges if e.is_boundary]
    assert edges
    # Constrained triangulation includes an interior grid; avoid long, thin
    # fans across the fracture and preserve the original rim exactly.
    normal=Vector((.8,-1,.35)).normalized(); origin=Vector((1.15,-.50,1.0))
    axis_u=normal.cross(Vector((0,0,1))).normalized();axis_v=normal.cross(axis_u)
    edge_set=set(edges);first=edges[0].verts[0];boundary=[first];current=first;previous=None
    while True:
        candidates=[e.other_vert(current) for e in current.link_edges if e in edge_set and e.other_vert(current)!=previous]
        nxt=candidates[0]
        if nxt==first:break
        boundary.append(nxt);previous,current=current,nxt
        assert len(boundary)<=len(edges)
    assert len(boundary)==len(edges)
    coords=[Vector(((v.co-origin).dot(axis_u),(v.co-origin).dot(axis_v))) for v in boundary]
    xmin,xmax=min(v.x for v in coords),max(v.x for v in coords)
    ymin,ymax=min(v.y for v in coords),max(v.y for v in coords)
    for ix in range(1,math.ceil((xmax-xmin)/.11)):
        for iy in range(1,math.ceil((ymax-ymin)/.11)):
            coords.append(Vector((xmin+ix*.11,ymin+iy*.11)))
    cv,ce,cf,orig,_,_=delaunay_2d_cdt(coords,[],[list(range(len(boundary)))],1,1e-7)
    mapping={}
    for i,p in enumerate(cv):
        old=next((k for k in orig[i] if k<len(boundary)),None)
        if old is not None:mapping[i]=boundary[old]
        else:
            point=origin+axis_u*p.x+axis_v*p.y
            point+=normal*(.075*noise(point*3.2)+.02*noise(point*11.7))
            mapping[i]=bm.verts.new(point)
    cap=[bm.faces.new([mapping[i] for i in face]) for face in cf]
    unused=[v for v in bm.verts if not v.link_faces]
    if unused:bmesh.ops.delete(bm,geom=unused,context='VERTS')
    uv=bm.loops.layers.uv.active
    for face in cap:
        face.smooth=False
        for loop in face.loops:
            p=loop.vert.co;loop[uv].uv=(.08+.84*(p.x+3.3)/6.6,.79*(p.z+.1)/3.15)
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    assert all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True)>0
    bm.to_mesh(ridge.data);bm.free();kept.append(ridge)
else:
    bpy.data.objects.remove(ridge,do_unlink=True)


def block(name,x,y,sx,sy,height,limestone=False,pale=True):
    bm=bmesh.new()
    # Unequal broad fracture planes give sediment fragments a flattened form.
    for k in range(19):
        p=Vector([rng.uniform(-1,1) for _ in range(3)]).normalized()
        bm.verts.new((p.x*sx*rng.uniform(.65,1),p.y*sy*rng.uniform(.65,1),p.z*height))
    bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    unused=[v for v in bm.verts if not v.link_faces]
    if unused:bmesh.ops.delete(bm,geom=unused,context='VERTS')
    bottom=min(v.co.z for v in bm.verts)
    top=max(v.co.z for v in bm.verts)
    for v in bm.verts:v.co=Vector((v.co.x+x,v.co.y+y,(v.co.z-bottom)*height/(top-bottom)))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    assert all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True)>0
    mesh=bpy.data.meshes.new(name);bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    mesh.materials.append(material);set_uv(obj,pale=pale,limestone=limestone);kept.append(obj)


if kind=='damage':
    for i,(x,y,sx,sy,h) in enumerate([(1.1,-1.23,.48,.35,.57),(1.9,-.73,.45,.35,.48),
        (1.8,-1.32,.32,.24,.22),(2.35,-.45,.22,.23,.31),(.62,-1.48,.21,.18,.21),
        (1.28,-1.63,.18,.14,.16),(2.03,-1.1,.15,.17,.19),(1.40,-.95,.29,.26,.34)]):
        block('Fallen shoulder fragment %02d'%i,x,y,sx,sy,h,limestone=i in (2,5))
else:
    for i,(x,y,sx,sy,h) in enumerate([(-1.7,.15,.8,.72,1.16),(-.45,.38,.9,.77,.91),
        (.9,.25,.85,.67,.74),(1.96,.18,.61,.54,.63),(-1.12,-.67,.72,.53,.62),
        (.28,-.63,.73,.54,.57),(-.52,1.02,.67,.54,.69)]):
        block('Low fractured sediment remnant %02d'%i,x,y,sx,sy,h,pale=False)
    for i in range(43):
        a=rng.uniform(0,math.tau);r=rng.uniform(.5,1)
        x=2.5*r*math.cos(a);y=1.35*r*math.sin(a)
        size=rng.uniform(.12,.32)
        block('Grounded sediment rubble %02d'%i,x,y,size,size*rng.uniform(.55,.9),
              size*rng.uniform(.45,.9),limestone=i%7==0)

bpy.ops.object.select_all(action='DESELECT')
for obj in kept:obj.select_set(True)
bpy.context.view_layer.objects.active=kept[0];bpy.ops.object.join()
mesh=bpy.context.object;mesh.name='SM_Holding'+condition+'_LookoutRidge'
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
bm=bmesh.new();bm.from_mesh(mesh.data)
bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(mesh.data);bm.free()
mesh.data.calc_loop_triangles();triangles=len(mesh.data.loop_triangles)
assert 0<triangles<30000 and len(mesh.data.materials)==1
coords=[v.co for v in mesh.data.vertices]
bounds={'min':[min(p[k] for p in coords) for k in range(3)],'max':[max(p[k] for p in coords) for k in range(3)]}
project=OUT/('LookoutRidge-'+condition+'.blend')
bpy.ops.wm.save_as_mainfile(filepath=str(project))
mesh.matrix_world=Matrix.Rotation(math.pi,4,'Z')
fbx=OUT/(mesh.name+'.fbx')
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},
    apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',
    bake_anim=False,add_leaf_bones=False,mesh_smooth_type='FACE',use_tspace=True,
    path_mode='STRIP',embed_textures=False)
mesh.matrix_world=Matrix.Identity(4)
base_project=BASE/brief['preservation']['base']
with bpy.data.libraries.load(str(base_project),link=False) as (src,dst):
    dst.objects=[n for n in src.objects if n.startswith('Holding_Base_')]
for obj in dst.objects:bpy.context.collection.objects.link(obj)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24
scene.cycles.use_denoising=True;scene.render.threads_mode='FIXED';scene.render.threads=8
scene.render.resolution_x,scene.render.resolution_y=1024,768;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
for name,pos,power,size in [('Warm daylight',(-11.7,-13.3,20),7200,13.3),('Sky fill',(13.3,-6.7,11.7),3300,11.7),('Rim',(0,13.3,18.3),8300,10)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
    obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj)
    obj.location=pos;obj.rotation_euler=(-obj.location).to_track_quat('-Z','Y').to_euler()
views={}
for name,pos in [('front',(7,-11,7)),('rear',(-7,11,7)),('right',(12,2,6)),('overhead',(0,-.01,15))]:
    data=bpy.data.cameras.new(name);data.type='ORTHO';data.ortho_scale=12
    camera=bpy.data.objects.new('Review_'+name,data);scene.collection.objects.link(camera)
    camera.location=pos;camera.rotation_euler=(Vector((0,0,.65))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera=camera;scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
    projected=[world_to_camera_view(scene,camera,o.matrix_world@v.co) for o in scene.objects if o.type=='MESH' for v in o.data.vertices]
    assert all(0<=p.x<=1 and 0<=p.y<=1 and p.z>0 for p in projected),name
    views[name]=sha(OUT/(name+'.png'))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/('LookoutRidge-'+condition+'-Review.blend')))
for key,digest in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:
    assert sha(BASE/brief['preservation'][key])==brief['preservation'][digest]
(OUT/'source-script.py').write_bytes(Path(__file__).read_bytes())
(OUT/'authoring.json').write_text(json.dumps(dict(status='static_candidate_pending_visual_review',
    brief_sha256=sha(BRIEF),source_sha256=brief['preservation']['sha256'],source_unchanged=True,
    triangles=triangles,bounds_m=bounds,project_sha256=sha(project),base_project_sha256=sha(base_project),
    fbx_sha256=sha(fbx),views=views,imported=False,limitations=brief['reconstruction']),indent=2)+'\n')
print('LOOKOUT_CONDITION_AUTHORED',condition,triangles,flush=True)
