"""Reopen Wagon Fort and measure closed solids and grounded assembly contacts."""
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
project=folder/'WagonFort.blend'
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

for o in objects:
    assert len(o.data.materials)==1 and o.data.uv_layers
    assert all(math.isfinite(c) for v in o.data.uv_layers.active.data for c in v.uv)
material=objects[0].data.materials[0]
assert all(o.data.materials[0]==material for o in objects)
images=[n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE']
assert len(images)==1 and all(i.packed_file and tuple(i.size)==(2048,2048) for i in images)
wagons={i:[o for o in objects if o.get('wagon_index')==i] for i in range(8)}
assert all(wagons.values())
wheel_roots=[n for n in roots if 'Iron wheel tire' in n]
assert len(wheel_roots)==32,(len(wheel_roots),roots)
# Distinct wagon meshes may connect through chains, never collide with each
# other. Surface BVHs, not merely axis-aligned boxes, determine collision.
collisions=[]
for edge in edges:
    a,b=(bpy.data.objects[edge[k]] for k in ('a','b'))
    wa,wb=a.get('wagon_index'),b.get('wagon_index')
    if wa is not None and wb is not None and wa!=wb:collisions.append(edge)
counts={i:dict(parts=len(obs),bows=sum('Wood canvas bow' in o.name for o in obs),tires=sum('Iron wheel tire' in o.name for o in obs),spokes=sum('Red dished spoke' in o.name for o in obs)) for i,obs in wagons.items()}
assert all(c['bows']==6 and c['tires']==4 and c['spokes']==48 for c in counts.values())
report=dict(status='failed' if unsupported or collisions or below_ground else 'passed',scope='Saved static positive closed solids, measured assembly contacts, grounded tires and inter-wagon collision checks; not user approval or engineering certification',project_sha256=sha(project),script_sha256=sha(Path(__file__)),closed_positive_volume_objects=len(objects),triangles=sum(r['triangles'] for r in rows),objects=rows,grounded_roots=sorted(roots),below_ground=below_ground,unsupported_objects=unsupported,assembly_contacts=edges,wagons=counts,inter_wagon_collisions=collisions,rigs=0,animations=0)
(folder/'geometry-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print('ISSUES',json.dumps(dict(unsupported=unsupported,collisions=collisions,below_ground=below_ground)),flush=True)
assert not unsupported,unsupported[:50]
assert not below_ground,below_ground
assert not collisions,collisions[:30]
assert report['triangles']<=30000
print('WAGON_FORT_SOURCE_AUDIT',len(objects),report['triangles'],len(edges),flush=True)
