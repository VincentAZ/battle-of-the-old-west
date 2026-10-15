"""Reopen Packer’s Cabin and measure closed solids and grounded assembly contacts."""
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
folder=Path(sys.argv[sys.argv.index('--')+1]).resolve()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record=json.loads((folder/'authoring.json').read_text())
project=folder/'PackersCabin.blend'
assert sha(project)==record['project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
assert len(objects)==record['objects']
assert not bpy.data.actions and not any(o.type=='ARMATURE' for o in bpy.data.objects)
rows=[];geometry={}
for o in objects:
    bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world);bm.normal_update()
    assert all(e.is_manifold for e in bm.edges),o.name
    assert all(f.calc_area()>1e-10 for f in bm.faces),o.name
    volume=bm.calc_volume(signed=True)
    assert volume>1e-10,(o.name,volume)
    assert all(math.isfinite(v) for p in bm.verts for v in p.co)
    assert o.data.uv_layers
    points=[v.co.copy() for v in bm.verts]
    samples=points+[f.calc_center_median() for f in bm.faces]
    bm.verts.index_update();faces=[[v.index for v in f.verts] for f in bm.faces]
    bounds=([min(p[k] for p in points) for k in range(3)],[max(p[k] for p in points) for k in range(3)])
    geometry[o.name]=dict(points=points,samples=samples,bounds=bounds,tree=BVHTree.FromPolygons(points,faces,epsilon=1e-6))
    o.data.calc_loop_triangles()
    rows.append(dict(name=o.name,closed=True,volume_m3=volume,triangles=len(o.data.loop_triangles)))
    bm.free()
graph={n:set() for n in geometry};names=list(graph);edges=[]
for i,a in enumerate(names):
    ga=geometry[a];alo,ahi=ga['bounds']
    for b in names[i+1:]:
        gb=geometry[b];blo,bhi=gb['bounds']
        if any(ahi[k]<blo[k]-1e-5 or bhi[k]<alo[k]-1e-5 for k in range(3)):continue
        method='surface_intersection' if ga['tree'].overlap(gb['tree']) else None
        if not method:
            for samples,tree in [(ga['samples'],gb['tree']),(gb['samples'],ga['tree'])]:
                if any(tree.find_nearest(p,1e-5)[0] is not None for p in samples):method='surface_contact';break
        if method:graph[a].add(b);graph[b].add(a);edges.append(dict(a=a,b=b,method=method))
roots={n for n,g in geometry.items() if abs(g['bounds'][0][2])<1e-6}
below_ground={n:g['bounds'][0][2] for n,g in geometry.items() if g['bounds'][0][2]<-1e-6}
assert roots
reached=set(roots);pending=list(roots)
while pending:
    n=pending.pop()
    for nb in graph[n]-reached:reached.add(nb);pending.append(nb)
unsupported=sorted(set(names)-reached)

material_slot_issues=[]
for o in objects:
    if len(o.data.materials)!=1:material_slot_issues.append(dict(name=o.name,slots=len(o.data.materials)))
    assert o.data.uv_layers,o.name
    assert all(math.isfinite(c) for v in o.data.uv_layers.active.data for c in v.uv)
material=objects[0].data.materials[0]
assert all(o.data.materials[0]==material for o in objects)
images=[n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE']
assert len(images)==1 and all(i.packed_file and tuple(i.size)==(2048,2048) for i in images)
# This contact graph establishes attachment, not an engineering load analysis.
flue=[]
for x in (-2.4,-2.29,-2.18):
    for y in (-.1,0,.1):
        origin=Vector((x,y,4));hits=[]
        for n,g in geometry.items():
            h=g['tree'].ray_cast(origin,Vector((0,0,-1)),1.6)
            if h[0] is not None:hits.append(n)
        flue.append(dict(x=x,y=y,obstructions=hits))
roof_support=[]
for n in names:
    if n.startswith(('Roof board','Transverse roof retaining pole','Roof supporting purlin')):
        roof_support.append(dict(name=n,contacts=sorted(graph[n])))
roof_violations=[];roof_samples=0
roof_trees=[g['tree']for n,g in geometry.items()if n.startswith('Roof board')]
for n,g in geometry.items():
    if not n.startswith(('Wall ','Sloped gable','Recessed ')):continue
    for point in g['points']:
        hits=[tree.ray_cast(Vector((point.x,point.y,5)),Vector((0,0,-1)),5)[0]for tree in roof_trees]
        hits=[h for h in hits if h is not None]
        if not hits:continue
        roof_samples+=1;top=max(h.z for h in hits)
        if point.z>top+1e-4:roof_violations.append(dict(object=n,point=list(point),above_roof_m=point.z-top))
report=dict(status='failed' if unsupported or below_ground or any(f['obstructions']for f in flue) else 'passed',scope='Saved original normals, closed positive solids, ground-connected actual surface graph and upper flue clearance; not user approval or engineering certification',project_sha256=sha(project),script_sha256=sha(Path(__file__)),closed_positive_volume_objects=len(objects),triangles=sum(r['triangles']for r in rows),objects=rows,grounded_roots=sorted(roots),below_ground=below_ground,unsupported_objects=unsupported,assembly_contacts=edges,roof_contacts=roof_support,upper_flue_clearance=flue,rigs=0,animations=0)
gable_closure=[]
for i in range(31):
    y=-1.5+i*.1;z=2.975-.45*abs(y)-.03
    hits=[n for n,g in geometry.items()if n.startswith(('Wall Y log','Sloped gable'))and g['tree'].ray_cast(Vector((3,y,z)),Vector((-1,0,0)),1.5)[0]is not None]
    gable_closure.append(dict(y=y,z=z,timber_hits=hits))
report['gable_closure']=gable_closure
report['material_slot_issues']=material_slot_issues
report['roof_exterior_clearance']={'samples':roof_samples,'violations':roof_violations}
if material_slot_issues or roof_violations or any(not r['timber_hits']for r in gable_closure):report['status']='failed'
(folder/'geometry-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print('PACKERS_CABIN_AUDIT',report['status'],len(objects),report['triangles'],'unsupported',unsupported,'belowground',below_ground,'flue',flue,flush=True)
assert report['status']=='passed'
