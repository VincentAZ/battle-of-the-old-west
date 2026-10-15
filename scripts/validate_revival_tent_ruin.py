"""Independently reopen the static ruin, measure support and verify preservation."""
from pathlib import Path
import hashlib,json,math,sys
import bpy,bmesh
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
R=Path(__file__).resolve().parents[1];out=Path(sys.argv[sys.argv.index('--')+1]).resolve();B=out.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record=json.loads((out/'authoring.json').read_text());brief_path=B/('ruin-brief-'+out.name.rsplit('-',1)[-1]+'.json');brief=json.loads(brief_path.read_text());assert sha(brief_path)==record['brief_sha256']
for k,h in [('source','sha256'),('reviewed_mesh','review_sha256'),('base','base_sha256')]:assert sha(B/brief['preservation'][k])==brief['preservation'][h]
def signature(o):return ([tuple(o.matrix_world@v.co) for v in o.data.vertices],sorted(tuple(sorted(f.vertices)) for f in o.data.polygons))
bpy.ops.wm.open_mainfile(filepath=str(B/brief['preservation']['source']),use_scripts=False)
expected_preserved=[];source_geometry={}
for o in bpy.context.scene.objects:
 if o.type!='MESH':continue
 source_geometry[o.name]=signature(o)
 if o.name.startswith(('Wooden stake ','Platform ')):expected_preserved.append(o.name)
assert len(expected_preserved)==33 and set(expected_preserved)==set(record['preserved_geometry'])
original={n:signature(bpy.data.objects[n]) for n in expected_preserved}
components=out/'RevivalTent-Ruin-Components.blend';assert sha(components)==record['components_project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(components),use_scripts=False)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(objects)==record['component_count']
preservation_diffs={}
for n,s in original.items():
 actual=signature(bpy.data.objects[n])
 if actual!=s:
  assert actual[1]==s[1],n
  err=max(abs(a-b) for p,q in zip(actual[0],s[0]) for a,b in zip(p,q))
  assert err<5e-6,(n,err)
  preservation_diffs[n]=err
roles={x['name']:x['role'] for x in record['component_solids']}
transform=Matrix.Scale(record['normalization']['scale'],4)@Matrix.Translation(Vector(record['normalization']['shift']))@Matrix.Rotation(math.radians(record['normalization']['rotation_degrees']),4,'Z')
expected=[];rows=[];geometry={}
for o in objects:
 bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world);bm.normal_update()
 volume=bm.calc_volume(signed=True);assert volume>0 and all(e.is_manifold for e in bm.edges),o.name
 assert all(f.calc_area()>1e-12 for f in bm.faces),o.name
 assert all(math.isfinite(c) for v in bm.verts for c in v.co),o.name
 points=[v.co.copy() for v in bm.verts];samples=points+[f.calc_center_median() for f in bm.faces]
 bm.verts.index_update();faces=[[v.index for v in f.verts] for f in bm.faces]
 bounds=([min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)])
 geometry[o.name]=dict(points=points,samples=samples,bounds=bounds,tree=BVHTree.FromPolygons(points,faces,epsilon=1e-6))
 bm.free();expected.extend(tuple(transform@p) for p in points)
 rows.append(dict(name=o.name,role=roles[o.name],volume_m3=volume,closed=True))
# Actual closed-surface intersections/contact, followed by a graph traversal
# from grounded components. This permits siding attached to a stump/backing,
# while rejecting a whole floating assembly even if its pieces touch each other.
graph={o.name:set() for o in objects};contacts=[];names=list(graph)
for i,a in enumerate(names):
 ga=geometry[a];alo,ahi=ga['bounds']
 for b in names[i+1:]:
  gb=geometry[b];blo,bhi=gb['bounds']
  if any(ahi[k]<blo[k]-1e-5 or bhi[k]<alo[k]-1e-5 for k in range(3)):continue
  intersections=ga['tree'].overlap(gb['tree']);method='surface_intersection' if intersections else None
  if not method:
   for samples,tree in [(ga['samples'],gb['tree']),(gb['samples'],ga['tree'])]:
    if any((hit:=tree.find_nearest(point,1e-5))[0] is not None for point in samples):method='surface_contact';break
  if method:graph[a].add(b);graph[b].add(a);contacts.append(dict(a=a,b=b,method=method))
roots={n for n,g in geometry.items() if abs(g['bounds'][0][2])<5e-6}
below={n:g['bounds'][0][2] for n,g in geometry.items() if g['bounds'][0][2]<-5e-6}
assert roots
reached=set(roots);pending=list(roots)
while pending:
 n=pending.pop()
 for neighbour in graph[n]-reached:reached.add(neighbour);pending.append(neighbour)
unsupported=sorted(set(names)-reached)
for row in rows:row.update(grounded_path_verified=True,contacts=sorted(graph[row['name']]))
assert len(objects)==83
for role,count in [('preserved_stake',16),('preserved_platform',17),('mast_stump',1),('perimeter_stump',16),('fallen_bench_seat',12),('fallen_mast',1),('fallen_perimeter',16),('fallen_lectern',4)]:
 assert sum(roles[o.name]==role for o in objects)==count,role
from mathutils.kdtree import KDTree
# All loose pieces must be independent of each other and unrelated supports.
debris=[n for n in names if roles[n].startswith('fallen_')];debris_issues=[]
for i,a in enumerate(debris):
 if roles[a]=='fallen_lectern':
  assert any(n.startswith('Platform floor plank')for n in graph[a]),('No platform contact',a)
 else:
  assert a in roots,('Loose timber not on ground',a,geometry[a]['bounds'])
 for b in debris[i+1:]:
  if geometry[a]['tree'].overlap(geometry[b]['tree']):debris_issues.append((a,b))
 for n in graph[a]:
  if roles[n].startswith('fallen_'):continue
  if not (roles[a]=='fallen_lectern'and n.startswith('Platform floor plank')):debris_issues.append((a,n))
from PIL import Image
import numpy as np
charred=np.asarray(Image.open(out/'RevivalTent_Ruin_BaseColor.png').convert('RGB'))
assert np.all(charred[:,:,0]>=charred[:,:,1])and np.all(charred[:,:,1]>=charred[:,:,2])and float(charred.mean())<65
project=out/'RevivalTent-Ruin.blend';assert sha(project)==record['project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(meshes)==1;mesh=meshes[0]
actual=[tuple(mesh.matrix_world@v.co) for v in mesh.data.vertices];assert len(actual)==len(expected)
kd=KDTree(len(actual))
for i,p in enumerate(actual):kd.insert(Vector(p),i)
kd.balance();error=max(kd.find(Vector(p))[2] for p in expected);assert error<1e-5
kd=KDTree(len(expected))
for i,p in enumerate(expected):kd.insert(Vector(p),i)
kd.balance();assert max(kd.find(Vector(p))[2] for p in actual)<1e-5
mesh.data.calc_loop_triangles();assert len(mesh.data.loop_triangles)==record['triangles']<30000
assert len(mesh.data.materials)==1 and mesh.data.uv_layers
assert all(math.isfinite(c) for p in mesh.data.uv_layers.active.data for c in p.uv)
assert not bpy.data.actions and not any(o.type=='ARMATURE' for o in bpy.data.objects)
images=[n.image for n in mesh.data.materials[0].node_tree.nodes if n.type=='TEX_IMAGE'];assert len(images)==1 and images[0].packed_file and tuple(images[0].size)==(2048,2048)
lo=[min(p[k] for p in actual) for k in range(3)];hi=[max(p[k] for p in actual) for k in range(3)]
manifest=json.loads((B/brief['preservation']['reviewed_mesh']).with_name('manifest.json').read_text())
assert abs(lo[2])<1e-5 and hi[2]<manifest['size_m'][2]
assert all(lo[k]>=manifest['bounds_m']['min'][k]-1e-5 and hi[k]<=manifest['bounds_m']['max'][k]+1e-5 for k in range(2))
sig=signature(mesh);uv=[tuple(x.uv) for x in mesh.data.uv_layers.active.data];name=mesh.name
bpy.ops.wm.open_mainfile(filepath=str(B/brief['preservation']['base']),use_scripts=False)
base_geometry={n:signature(bpy.data.objects[n]) for n in ['Holding_Base_Ground','Holding_Base_Tuft']}
def colours(o):
 return {a.name:[tuple(item.color) for item in a.data] for a in o.data.color_attributes}
base_colours={n:colours(bpy.data.objects[n]) for n in base_geometry}
review=out/'RevivalTent-Ruin-Review.blend';assert sha(review)==record['review_project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(review),use_scripts=False)
assert signature(bpy.data.objects[name])==sig
assert [tuple(x.uv) for x in bpy.data.objects[name].data.uv_layers.active.data]==uv
for n,s in base_geometry.items():
 assert signature(bpy.data.objects[n])==s,n
 assert colours(bpy.data.objects[n])==base_colours[n],n
assert set(record['views'])=={'front','rear','right','overhead'}
for view,h in record['views'].items():
 assert sha(out/(view+'.png'))==h
 cam=bpy.data.objects['Review_'+view]
 assert all(0<=p.x<=1 and 0<=p.y<=1 and p.z>0 for p in [world_to_camera_view(bpy.context.scene,cam,o.matrix_world@v.co) for o in bpy.context.scene.objects if o.type=='MESH' for v in o.data.vertices]),view
 # Containment alone allowed an unreadably tiny first view. Require the scene
 # to occupy a substantial fraction of at least one image dimension as well.
 projected=[world_to_camera_view(bpy.context.scene,cam,o.matrix_world@v.co) for o in bpy.context.scene.objects if o.type=='MESH' for v in o.data.vertices]
 assert max(max(p.x for p in projected)-min(p.x for p in projected),max(p.y for p in projected)-min(p.y for p in projected))>.70,view
baseline=json.loads((B.parent/'baseline.json').read_text());assert all(sha(R/p)==h for p,h in baseline['protected_sha256'].items());assert str((R/'dist/current').resolve())==baseline['selected_package']
mechanics=json.loads((B.parent/'mechanics-baseline.json').read_text())['sha256'];assert all(sha(R/p)==h for p,h in mechanics.items())
# All original grass stays outside the ruin; compare actual surfaces.
ruin_obj=bpy.data.objects[name]
ruin_tree=BVHTree.FromPolygons([ruin_obj.matrix_world@v.co for v in ruin_obj.data.vertices],[tuple(p.vertices)for p in ruin_obj.data.polygons])
grass=bpy.data.objects['Holding_Base_Tuft']
grass_tree=BVHTree.FromPolygons([grass.matrix_world@v.co for v in grass.data.vertices],[tuple(p.vertices)for p in grass.data.polygons])
assert not ruin_tree.overlap(grass_tree),'Ruin intersects unchanged grass'
# Actual ground support under each root, using the same source normalization.
ground=bpy.data.objects['Holding_Base_Ground']
ground_tree=BVHTree.FromPolygons([ground.matrix_world@v.co for v in ground.data.vertices],[tuple(p.vertices)for p in ground.data.polygons])
base_contacts={}
for n in roots:
 pts=geometry[n]['points'];low=min(p.z for p in pts);gaps=[]
 for p in pts:
  if p.z-low>1e-6:continue
  q=transform@p;hit=ground_tree.ray_cast(q+Vector((0,0,.1)),Vector((0,0,-1)),.2)[0]
  assert hit is not None and abs(hit.z-q.z)<5e-6,(n,q,hit)
  gaps.append(abs(hit.z-q.z))
 base_contacts[n]=max(gaps)
report=dict(status='failed' if unsupported or below or debris_issues or preservation_diffs else 'passed',scope='Saved static mesh, actual surface support, independent loose debris and source/base preservation; not historical or native approval',project_sha256=sha(project),review_project_sha256=sha(review),components_project_sha256=sha(components),triangles=record['triangles'],components=len(rows),bounds_m=dict(min=lo,max=hi),inside_healthy_footprint=True,healthy_source_and_base_unchanged=True,base_geometry_unchanged=True,loose_debris_contact_and_nonintersection_verified=not debris_issues,preservation_coordinate_differences=preservation_diffs,unsupported_objects=unsupported,below_ground=below,debris_intersections=debris_issues,base_vertex_colours_unchanged=True,brown_black_char_sampled=True,preserved_geometry=list(original),maximum_join_coordinate_error_m=error,no_rigs_or_animation=True,game_exported=False,game_imported=False,protected_files_unchanged=len(baseline['protected_sha256']),mechanics_files_unchanged=len(mechanics),selected_package_unchanged=baseline['selected_package'],views=record['views'],support_checks=rows,assembly_contacts=contacts,grounded_roots=sorted(roots),actual_base_contacts=base_contacts,grass_ruin_intersections=0,limitations=['Surface contact graph, not structural engineering, fastener strength or a Boolean-union audit.','Fictional damage, not an actual event or a fire simulation.'])
(out/'validator-source.py').write_bytes(Path(__file__).read_bytes())
(out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print('REVIVAL_TENT_RUIN_AUDIT',record['triangles'],len(rows),len(contacts),json.dumps(dict(preservation_diffs=preservation_diffs,unsupported=unsupported,below=below,debris_issues=debris_issues)),flush=True)
assert report['status']=='passed'
