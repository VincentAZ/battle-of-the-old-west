"""Reopen the horse-sale yard and measure closed solids and grounded assembly contacts."""
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
project=folder/'HorseTrader.blend'
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
assert roots and all(g['bounds'][0][2]>=-1e-6 for g in geometry.values())
reached=set(roots);pending=list(roots)
while pending:
    n=pending.pop()
    for nb in graph[n]-reached:reached.add(nb);pending.append(nb)
unsupported=sorted(set(names)-reached)
for o in objects:
    assert len(o.data.materials)==1
    assert all(math.isfinite(c) for v in o.data.uv_layers.active.data for c in v.uv)
material=objects[0].data.materials[0]
assert all(o.data.materials[0]==material for o in objects)
images=[n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE']
assert len(images)==1 and all(i.packed_file and tuple(i.size)==(2048,2048) for i in images)
# The primitive cube's untouched default UV map previously sampled empty atlas
# space. Check the actual active/render layer and all corner texels after reopen.
atlas=Image.open(folder/'HorseTrader_BaseColor.png')
texel_samples=0
for o in objects:
    assert len(o.data.uv_layers)==1,o.name
    for loop in o.data.uv_layers.active.data:
        u,v=loop.uv
        assert 0<u<1 and 0<v<1,(o.name,u,v)
        rgb=atlas.getpixel((min(2047,int(u*2048)),min(2047,int((1-v)*2048))))
        assert max(rgb)>10,(o.name,rgb)
        texel_samples+=1
# Roof clearance is measured against the saved boarding surfaces, not the
# author's roof formula. This catches the visible eave/lime protrusion defect.
roofs=[g['tree'] for n,g in geometry.items() if n.startswith('Closed roof boarding')]
roof_clearance_samples=0
for name,g in geometry.items():
    if not name.startswith(('Eave timber plate','Hewn horizontal wall log','Hewn side wall log','Recessed pale lime joint')):continue
    for p in g['points']:
        hits=[tree.ray_cast(Vector((p.x,p.y,20)),Vector((0,0,-1)),40)[0] for tree in roofs]
        hits=[hit for hit in hits if hit is not None]
        assert hits,('Outside roof',name,tuple(p))
        assert p.z<=max(hit.z for hit in hits)+1e-5,('Protrudes above roof',name,tuple(p))
        roof_clearance_samples+=1
assert len([o for o in objects if o.name.startswith('Grounded corral post')])==8
assert all(geometry[o.name]['bounds'][0][2]<1e-6 for o in objects if o.name.startswith('Grounded corral post'))
report=dict(status='failed' if unsupported else 'passed',scope='Saved static closed solids and actual assembly surface contacts; not structural engineering or user approval',project_sha256=sha(project),script_sha256=sha(Path(__file__)),closed_positive_volume_objects=len(objects),triangles=sum(r['triangles'] for r in rows),objects=rows,grounded_roots=sorted(roots),unsupported_objects=unsupported,assembly_contacts=edges,active_uv_texel_samples=texel_samples,roof_clearance_samples=roof_clearance_samples,rigs=0,animations=0)
(folder/'geometry-audit.json').write_text(json.dumps(report,indent=2)+'\n')
(folder/'auditor-source.py').write_bytes(Path(__file__).read_bytes())
assert not unsupported,unsupported[:40]
assert report['triangles']<=30000
print('HORSE_TRADER_SOURCE_AUDIT',len(objects),report['triangles'],len(edges),flush=True)
