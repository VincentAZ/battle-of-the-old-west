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
project=folder/'CattlemensClub.blend'
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
glass=[o for o in objects if 'glazing' in o.name]
opaque_walls=[o for o in objects if 'masonry' in o.name or 'mansard slate' in o.name or 'Tower front mansard' in o.name]
transmission=Image.open(folder/'CattlemensClub_Transmission.png')
roughness=Image.open(folder/'CattlemensClub_Roughness.png')
assert len(glass)==22
for o in glass:
    for face in o.data.polygons:
        uvs=[o.data.uv_layers.active.data[i].uv for i in face.loop_indices]
        u=sum(v.x for v in uvs)/len(uvs);v=sum(v.y for v in uvs)/len(uvs)
        pixel=(int(u*2048),int((1-v)*2048))
        assert transmission.getpixel(pixel)[0]==255,o.name
        assert roughness.getpixel(pixel)[0]<26,o.name
    # Arched openings have overlapping bounding boxes. Check rays through the
    # actual pane triangles, not rectangular bounds that include empty corners.
    o.data.calc_loop_triangles()
    lo,hi=geometry[o.name]['bounds']
    thin_axis=min(range(3),key=lambda k:hi[k]-lo[k])
    for triangle in o.data.loop_triangles:
        pts=[o.matrix_world@o.data.vertices[i].co for i in triangle.vertices]
        normal=(pts[1]-pts[0]).cross(pts[2]-pts[0]).normalized()
        if abs(normal[thin_axis])<.99:continue
        for weights in ((1/3,1/3,1/3),(.8,.1,.1),(.1,.8,.1),(.1,.1,.8)):
            p=sum((v*w for v,w in zip(pts,weights)),Vector())
            for wall in opaque_walls:
                hit=geometry[wall.name]['tree'].ray_cast(p-normal*.38,normal,.76)[0]
                assert hit is None,(o.name,wall.name,tuple(p))
for o in objects:
    assert len(o.data.materials)==1,(o.name,[m.name if m else None for m in o.data.materials])
    assert all(math.isfinite(c) for v in o.data.uv_layers.active.data for c in v.uv)
material=objects[0].data.materials[0]
assert all(o.data.materials[0]==material for o in objects)
assert material.node_tree.nodes.get('Principled BSDF').inputs['Transmission Weight'].is_linked
images=[n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE']
assert len(images)==4 and all(i.packed_file and tuple(i.size)==(2048,2048) for i in images)
# Reject same-facing coincident masonry surfaces that produce black z-fighting.
# Opposed faces are legitimate assembly contacts and excluded here.
def area(poly):
    return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly,poly[1:]+poly[:1])))*.5
def clip(subject,edge):
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    sign=1 if cross(*edge)>0 else -1
    for a,b in zip(edge,edge[1:]+edge[:1]):
        old=subject;subject=[]
        if not old:break
        p=old[-1];dp=sign*cross(a,b,p)
        for q in old:
            dq=sign*cross(a,b,q)
            if (dp>=-1e-9)!=(dq>=-1e-9):
                t=dp/(dp-dq);subject.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
            if dq>=-1e-9:subject.append(q)
            p,dp=q,dq
    return subject
groups={};masonry_triangles=0;overlap_comparisons=0
for o in objects:
    if not ('masonry' in o.name or 'parapet' in o.name or 'roof infill' in o.name or 'eave fascia' in o.name or 'veranda deck' in o.name or 'veranda joist' in o.name):continue
    for tri in o.data.loop_triangles:
        pts=[o.matrix_world@o.data.vertices[i].co for i in tri.vertices]
        normal=(pts[1]-pts[0]).cross(pts[2]-pts[0]).normalized()
        axis=max(range(3),key=lambda k:abs(normal[k]))
        if abs(normal[axis])<.99999:continue
        # Horizontal masonry ends interlock below the roof; this check covers
        # vertical facades, where same-facing overlap remains visible.
        if axis==2:continue
        key=(axis,1 if normal[axis]>0 else -1,round(pts[0][axis],5))
        axes=[k for k in range(3) if k!=axis];poly=[tuple(round(p[k],5) for k in axes) for p in pts]
        for name,other in groups.get(key,[]):
            if name==o.name:continue
            overlap_comparisons+=1
            intersection=clip(poly,other)
            assert not intersection or area(intersection)<1e-7,('Coincident masonry faces',o.name,name,area(intersection))
        groups.setdefault(key,[]).append((o.name,poly));masonry_triangles+=1
report=dict(status='failed' if unsupported else 'passed',scope='Saved closed positive solids, actual assembly surface contacts, glass texture and masonry clearance; not user approval or a structural engineering analysis',project_sha256=sha(project),script_sha256=sha(Path(__file__)),closed_positive_volume_objects=len(objects),triangles=sum(r['triangles'] for r in rows),objects=rows,grounded_roots=sorted(roots),unsupported_objects=unsupported,assembly_contacts=edges,transparent_window_openings_checked=len(glass),glass_maps_sampled=True,rigs=0,animations=0)
report.update(masonry_triangles_checked_for_coplanar_overlap=masonry_triangles,coplanar_face_comparisons=overlap_comparisons)
(folder/'geometry-audit.json').write_text(json.dumps(report,indent=2)+'\n')
assert not unsupported,unsupported[:50]
assert report['triangles']<=30000
print('CATTLEMENS_CLUB_SOURCE_AUDIT',len(objects),report['triangles'],len(edges),flush=True)
