"""Audit saved ram ruin solids, actual ground contact and preserved setting."""
from pathlib import Path
import hashlib,json,math,sys
import bpy,bmesh
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from bpy_extras.object_utils import world_to_camera_view
R=Path(__file__).resolve().parents[1];out=Path(sys.argv[sys.argv.index('--')+1]).resolve();B=out.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((out/'authoring.json').read_text());brief=B/('ruin-brief-'+out.name.rsplit('-',1)[-1]+'.json');b=json.loads(brief.read_text());assert sha(brief)==a['brief_sha256']
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/b['preservation'][k])==b['preservation'][h]
for n,h in b['source_records'].items():assert sha(R/n)==h
def signature(o):return ([tuple(o.matrix_world@v.co)for v in o.data.vertices],[tuple(f.vertices)for f in o.data.polygons])
def tree(o):return BVHTree.FromPolygons([o.matrix_world@v.co for v in o.data.vertices],[tuple(f.vertices)for f in o.data.polygons])
transform=Matrix.Scale(a['normalization']['scale'],4)@Matrix.Translation(Vector(a['normalization']['shift']))@Matrix.Rotation(math.radians(65),4,'Z')
cp=out/'TimberRam-Ruin-Components.blend';assert sha(cp)==a['components_project_sha256'];bpy.ops.wm.open_mainfile(filepath=str(cp),use_scripts=False)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(objects)==3
expected=[];roots={};trees={};rows=[]
for o in objects:
    bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world);bm.normal_update()
    assert all(e.is_manifold for e in bm.edges)and bm.calc_volume(signed=True)>0,o.name
    assert all(f.calc_area()>1e-12 for f in bm.faces)
    unseen=set(bm.verts);q=[unseen.pop()]
    while q:
        v=q.pop()
        for edge in v.link_edges:
            n=edge.other_vert(v)
            if n in unseen:unseen.remove(n);q.append(n)
    assert not unseen,o.name
    points=[v.co.copy()for v in bm.verts];assert all(math.isfinite(c)for p in points for c in p);assert min(p.z for p in points)>=-1e-7
    bm.verts.index_update();faces=[[v.index for v in f.verts]for f in bm.faces];t=BVHTree.FromPolygons(points,faces);trees[o.name]=t
    crossings=[(i,j)for i,j in t.overlap(t)if i<j and not(set(faces[i])&set(faces[j]))];assert not crossings,(o.name,crossings[:10])
    grounded=[transform@p for p in points if abs(p.z)<1e-7];assert len(grounded)>50;roots[o.name]=grounded
    expected.extend(tuple(transform@p)for p in points);rows.append(dict(name=o.name,volume_m3=bm.calc_volume(signed=True),closed=True,ground_contact_vertices=len(grounded),self_intersections=0));bm.free()
for i,o in enumerate(objects):
    for other in objects[i+1:]:assert not trees[o.name].overlap(trees[other.name]),(o.name,other.name)
project=out/'TimberRam-Ruin.blend';assert sha(project)==a['project_sha256'];bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(meshes)==1;o=meshes[0];actual=[tuple(o.matrix_world@v.co)for v in o.data.vertices];assert len(actual)==len(expected)
errors=[]
for aa,bb in [(actual,expected),(expected,actual)]:
    kd=KDTree(len(aa))
    for i,p in enumerate(aa):kd.insert(Vector(p),i)
    kd.balance();errors.append(max(kd.find(Vector(p))[2]for p in bb))
assert max(errors)<1e-5
o.data.calc_loop_triangles();assert len(o.data.loop_triangles)==a['triangles']<30000
assert len(o.data.materials)==1 and o.data.uv_layers
assert all(math.isfinite(c)and 0<=c<=1 for p in o.data.uv_layers.active.data for c in p.uv)
images=[n.image for n in o.data.materials[0].node_tree.nodes if n.type=='TEX_IMAGE'];assert len(images)==1 and images[0].packed_file and tuple(images[0].size)==(2048,2048)
assert not bpy.data.actions and not any(o.type=='ARMATURE'for o in bpy.data.objects)
lo=[min(p[k]for p in actual)for k in range(3)];hi=[max(p[k]for p in actual)for k in range(3)]
manifest=json.loads((B/'review-v002/manifest.json').read_text());assert abs(lo[2])<1e-6 and hi[2]<manifest['size_m'][2]
assert all(lo[k]>=manifest['bounds_m']['min'][k]and hi[k]<=manifest['bounds_m']['max'][k]for k in range(2))
sig=signature(o);uvs=[tuple(x.uv)for x in o.data.uv_layers.active.data];name=o.name
bpy.ops.wm.open_mainfile(filepath=str(B/b['preservation']['base']),use_scripts=False)
names=['Holding_Base_Ground','Holding_Base_Tuft','Holding_Base_Needle']
base={n:signature(bpy.data.objects[n])for n in names}
colours=lambda o:{a.name:[tuple(v.color)for v in a.data]for a in o.data.color_attributes}
colors={n:colours(bpy.data.objects[n])for n in names}
review=out/'TimberRam-Ruin-Review.blend';assert sha(review)==a['review_project_sha256'];bpy.ops.wm.open_mainfile(filepath=str(review),use_scripts=False)
o=bpy.data.objects[name];assert signature(o)==sig and [tuple(x.uv)for x in o.data.uv_layers.active.data]==uvs
for n in names:assert signature(bpy.data.objects[n])==base[n]and colours(bpy.data.objects[n])==colors[n],n
ground=tree(bpy.data.objects['Holding_Base_Ground']);ruin=tree(o)
for n in names[1:]:assert not ruin.overlap(tree(bpy.data.objects[n])),n
gaps={}
for n,points in roots.items():
    gaps[n]=[]
    for p in points:
        hit=ground.ray_cast(p+Vector((0,0,.05)),Vector((0,0,-1)),.06)[0];assert hit is not None and abs(hit.z-p.z)<1e-6
        gaps[n].append(abs(hit.z-p.z))
assert set(a['views'])=={'front','rear','right','overhead'}
for view,h in a['views'].items():
    assert sha(out/(view+'.png'))==h;cam=bpy.data.objects['Review_'+view]
    projected=[world_to_camera_view(bpy.context.scene,cam,m.matrix_world@v.co)for m in bpy.context.scene.objects if m.type=='MESH'for v in m.data.vertices]
    assert all(0<=p.x<=1 and 0<=p.y<=1 and p.z>0 for p in projected),view
    assert max(max(p.x for p in projected)-min(p.x for p in projected),max(p.y for p in projected)-min(p.y for p in projected))>.7
baseline=json.loads((B.parent/'baseline.json').read_text());assert all(sha(R/p)==h for p,h in baseline['protected_sha256'].items());assert str((R/'dist/current').resolve())==baseline['selected_package']
mechanics=json.loads((B.parent/'mechanics-baseline.json').read_text())['sha256'];assert all(sha(R/p)==h for p,h in mechanics.items())
report=dict(status='passed',scope='Saved static solids, terrain support, nonintersection, footprint, framing and source/base preservation; not native or historical approval',project_sha256=sha(project),review_project_sha256=sha(review),components_project_sha256=sha(cp),triangles=a['triangles'],components=3,component_checks=rows,actual_ground_contact_vertices=sum(map(len,roots.values())),maximum_ground_gap_m=max(max(v)for v in gaps.values()),maximum_join_coordinate_error_m=max(errors),debris_intersections=0,scatter_ruin_intersections=0,inside_healthy_footprint=True,bounds_m=dict(min=lo,max=hi),healthy_source_and_base_unchanged=True,base_geometry_unchanged=True,base_vertex_colours_unchanged=True,no_rigs_or_animation=True,game_exported=False,game_imported=False,protected_files_unchanged=len(baseline['protected_sha256']),mechanics_files_unchanged=len(mechanics),selected_package_unchanged=baseline['selected_package'],views=a['views'],limitations=b['uncertainties'])
(out/'validator-source.py').write_bytes(Path(__file__).read_bytes());(out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print('TIMBER_RAM_RUIN_VALIDATED',a['triangles'],report['actual_ground_contact_vertices'],flush=True)
