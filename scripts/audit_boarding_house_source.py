"""Reopen the house and measure closed solids and grounded assembly contacts."""
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
project=folder/'BoardingHouse.blend'
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
glass=[o for o in objects if 'clear sash glazing' in o.name]
opaque_walls=[o for o in objects if 'wall backing' in o.name or 'green clapboard' in o.name]
transmission=Image.open(folder/'BoardingHouse_Transmission.png')
roughness=Image.open(folder/'BoardingHouse_Roughness.png')
assert len(glass)==19
for o in glass:
    for face in o.data.polygons:
        uvs=[o.data.uv_layers.active.data[i].uv for i in face.loop_indices]
        u=sum(v.x for v in uvs)/len(uvs);v=sum(v.y for v in uvs)/len(uvs)
        pixel=(int(u*2048),int((1-v)*2048))
        assert transmission.getpixel(pixel)[0]==255,o.name
        assert roughness.getpixel(pixel)[0]<26,o.name
    lo,hi=geometry[o.name]['bounds']
    for wall in opaque_walls:
        wl,wh=geometry[wall.name]['bounds']
        assert not all(min(hi[k],wh[k])-max(lo[k],wl[k])>1e-5 for k in range(3)),(o.name,wall.name)
for o in objects:
    assert len(o.data.materials)==1
    assert all(math.isfinite(c) for v in o.data.uv_layers.active.data for c in v.uv)
material=objects[0].data.materials[0]
assert all(o.data.materials[0]==material for o in objects)
assert material.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].is_linked
images=[n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE']
assert len(images)==3 and all(i.packed_file and tuple(i.size)==(2048,2048) for i in images)
# These porch pieces have rectangular XY footprints. Measure their actual upper
# face planes to reject positive-area coplanar overlaps that render as black bands.
porch=[o for o in objects if any(o.name.startswith(n) for n in ('Porch wood shingle','Porch floor plank','Entrance step'))]
tops={}
for o in porch:
    face=max((f for f in o.data.polygons if f.normal.z>.8),key=lambda f:f.center.z)
    pts=[o.matrix_world@o.data.vertices[i].co for i in face.vertices]
    normal=(pts[1]-pts[0]).cross(pts[2]-pts[0]).normalized()
    tops[o.name]=(pts,normal)
for i,a in enumerate(porch):
    ap,an=tops[a.name]
    for b in porch[i+1:]:
        bp,bn=tops[b.name]
        overlap=[min(max(p[k] for p in ap),max(p[k] for p in bp))-max(min(p[k] for p in ap),min(p[k] for p in bp)) for k in range(2)]
        if min(overlap)<=1e-6:continue
        coplanar=abs(abs(an.dot(bn))-1)<1e-6 and max(abs(an.dot(p-ap[0])) for p in bp)<1e-6
        assert not coplanar,('Coplanar porch surfaces',a.name,b.name)
report=dict(status='failed' if unsupported else 'passed',scope='Saved static closed solids, actual assembly surface contacts, transparent unobstructed sash glazing and porch overlap audit; not structural engineering or user approval',project_sha256=sha(project),script_sha256=sha(Path(__file__)),closed_positive_volume_objects=len(objects),triangles=sum(r['triangles'] for r in rows),objects=rows,grounded_roots=sorted(roots),unsupported_objects=unsupported,assembly_contacts=edges,transparent_window_openings_checked=len(glass),glass_maps_sampled=True,porch_components_checked_for_coplanar_overlap=len(porch),rigs=0,animations=0)
(folder/'geometry-audit.json').write_text(json.dumps(report,indent=2)+'\n')
assert not unsupported,unsupported[:30]
assert report['triangles']<=30000
print('BOARDING_HOUSE_SOURCE_AUDIT',len(objects),report['triangles'],len(edges),flush=True)
