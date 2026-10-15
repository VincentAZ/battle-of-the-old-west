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
original={n:signature(bpy.data.objects[n]) for n in record['preserved_geometry']}
components=out/'Apothecary-Ruin-Components.blend';assert sha(components)==record['components_project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(components),use_scripts=False)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(objects)==record['component_count']
for n,s in original.items():assert signature(bpy.data.objects[n])==s,n
roles={x['name']:x['role'] for x in record['component_solids']}
transform=Matrix.Scale(record['normalization']['scale'],4)@Matrix.Translation(Vector(record['normalization']['shift']))
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
roots={n for n,g in geometry.items() if abs(g['bounds'][0][2])<1e-6}
assert roots and all(g['bounds'][0][2]>=-1e-6 for g in geometry.values())
reached=set(roots);pending=list(roots)
while pending:
 n=pending.pop()
 for neighbour in graph[n]-reached:reached.add(neighbour);pending.append(neighbour)
assert reached==set(names),sorted(set(names)-reached)
for row in rows:row.update(grounded_path_verified=True,contacts=sorted(graph[row['name']]))
assert sum(roles[o.name]=='fallen' for o in objects)==35
project=out/'Apothecary-Ruin.blend';assert sha(project)==record['project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(meshes)==1;mesh=meshes[0]
actual=[tuple(mesh.matrix_world@v.co) for v in mesh.data.vertices];assert len(actual)==len(expected)
error=max(abs(a-b) for p,q in zip(sorted(actual),sorted(expected)) for a,b in zip(p,q));assert error<1e-5
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
base_geometry={n:signature(bpy.data.objects[n]) for n in ['Holding_Base_Ground','Holding_Base_Stone']}
review=out/'Apothecary-Ruin-Review.blend';assert sha(review)==record['review_project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(review),use_scripts=False)
assert signature(bpy.data.objects[name])==sig
assert [tuple(x.uv) for x in bpy.data.objects[name].data.uv_layers.active.data]==uv
for n,s in base_geometry.items():assert signature(bpy.data.objects[n])==s,n
assert set(record['views'])=={'front','rear','right','overhead'}
for view,h in record['views'].items():
 assert sha(out/(view+'.png'))==h
 cam=bpy.data.objects['Review_'+view]
 assert all(0<=p.x<=1 and 0<=p.y<=1 and p.z>0 for p in [world_to_camera_view(bpy.context.scene,cam,o.matrix_world@v.co) for o in bpy.context.scene.objects if o.type=='MESH' for v in o.data.vertices]),view
baseline=json.loads((B.parent/'baseline.json').read_text());assert all(sha(R/p)==h for p,h in baseline['protected_sha256'].items());assert str((R/'dist/current').resolve())==baseline['selected_package']
mechanics=json.loads((B.parent/'mechanics-baseline.json').read_text())['sha256'];assert all(sha(R/p)==h for p,h in mechanics.items())
report=dict(status='passed',scope='Saved static mesh, closed solids, sampled assembly contacts, preservation and view framing; not historical or native approval',project_sha256=sha(project),review_project_sha256=sha(review),components_project_sha256=sha(components),triangles=record['triangles'],components=len(rows),bounds_m=dict(min=lo,max=hi),inside_healthy_footprint=True,healthy_source_and_base_unchanged=True,base_geometry_unchanged=True,preserved_geometry=list(original),maximum_join_coordinate_error_m=error,no_rigs_or_animation=True,game_exported=False,game_imported=False,protected_files_unchanged=len(baseline['protected_sha256']),mechanics_files_unchanged=len(mechanics),selected_package_unchanged=baseline['selected_package'],views=record['views'],support_checks=rows,assembly_contacts=contacts,grounded_roots=sorted(roots),limitations=['Surface intersection/contact graph, not structural engineering, fastener strength or a Boolean-union audit.','Fictional damage, not an actual event or a fire simulation.'])
(out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print('APOTHECARY_RUIN_VALIDATED',record['triangles'],len(rows),flush=True)
