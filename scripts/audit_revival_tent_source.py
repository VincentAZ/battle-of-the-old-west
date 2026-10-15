"""Reopen Revival Tent and measure closed solids and grounded assembly contacts."""
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
project=folder/'RevivalTent.blend'
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
# Count actual authored features, then test interior geometry independently.
assert sum(n.startswith('Perimeter pole ')for n in names)==16
assert sum(n.startswith('Wooden stake ')for n in names)==16
assert sum(n.startswith('Guy rope ')for n in names)==16
assert sum(n.startswith('Rear canvas wall ')for n in names)==8
assert sum(' seat' in n and n.startswith('Bench ')for n in names)==12
assert sum(n.startswith('Central timber mast')for n in names)==1
assert len(roots)>=81,(len(roots),sorted(roots))
# Distinct benches cannot touch; guys stay outside the seating and stand.
collisions=[]
for edge in edges:
    a,b=edge['a'],edge['b']
    if a.startswith('Bench ')and b.startswith('Bench '):
        if a.split()[:3]!=b.split()[:3]:collisions.append(edge)
    if (a.startswith('Guy rope ')and b.startswith(('Bench ','Lectern','Platform')))or (b.startswith('Guy rope ')and a.startswith(('Bench ','Lectern','Platform'))):collisions.append(edge)
# Each pole reaches the roof, every guy reaches its pole and stake.
required_contacts=[]
for i in range(16):
    pole=f'Perimeter pole {i:02}';guy=f'Guy rope {i:02}';stake=f'Wooden stake {i:02}'
    for a,b in [(pole,'Circular canvas roof'),(guy,pole),(guy,stake)]:
        assert b in graph[a],(a,b,'missing actual contact')
        required_contacts.append([a,b])
assert 'Central timber mast' in graph['Circular canvas roof']
roof=geometry['Circular canvas roof']['tree'];clearance=[]
mast_clearance=[]
for p in geometry['Central timber mast']['points']:
    if p.z<4:continue
    hit=roof.ray_cast(Vector((p.x,p.y,10)),Vector((0,0,-1)),10)
    assert hit[0] is not None and hit[0].z-p.z>.004,(p,hit)
    mast_clearance.append(hit[0].z-p.z)
entrance_clearance=[]
for x in (-.25,0,.25):
    for z in (.15,.70,1.4):
        p=Vector((x,-5.8,z));blocked=[]
        for n,g in geometry.items():
            if g['tree'].ray_cast(p,Vector((0,1,0)),5.5)[0] is not None:blocked.append(n)
        assert not blocked,(list(p),blocked)
        entrance_clearance.append(dict(origin=list(p),clear=True))
for rr in (.65,1.4,2.3,3.4):
    for i in range(12):
        a=math.tau*(i+.37)/12;p=Vector((rr*math.cos(a),rr*math.sin(a),1.4))
        hit=roof.ray_cast(p,Vector((0,0,1)),8)
        assert hit[0] is not None and hit[0].z>2.25,(p,hit)
        clearance.append(dict(origin=list(p),roof_z=hit[0].z))
# Check a clear open-front sightline at shoulder height, against canvas only.
front_sight=[]
for x in (-2,-1,0,1,2):
    p=Vector((x,-5,1.5));direction=Vector((0,1,0));hits=[]
    for n,g in geometry.items():
        if n.startswith(('Circular canvas','Rear canvas','Canvas valance')):
            hit=g['tree'].ray_cast(p,direction,4.8)
            if hit[0] is not None:hits.append(n)
    assert not hits,(x,hits)
    front_sight.append(dict(x=x,clear=True))
report=dict(status='failed' if unsupported or collisions or below_ground else 'passed',scope='Saved static solids, actual surface contacts, canvas interior clearance and basic furnishing interference; not structural engineering certification or user approval',project_sha256=sha(project),script_sha256=sha(Path(__file__)),closed_positive_volume_objects=len(objects),triangles=sum(r['triangles']for r in rows),objects=rows,grounded_roots=sorted(roots),below_ground=below_ground,unsupported_objects=unsupported,assembly_contacts=edges,required_pole_and_guy_contacts=required_contacts,interior_roof_clearance=clearance,open_front_sightlines=front_sight,unwanted_collisions=collisions,rigs=0,animations=0)
report['mast_below_exterior_roof_m']=mast_clearance
report['entrance_clearance']=entrance_clearance
(folder/'geometry-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print('ISSUES',json.dumps(dict(unsupported=unsupported,collisions=collisions,below_ground=below_ground)),flush=True)
assert not unsupported,unsupported
assert not below_ground,below_ground
assert not collisions,collisions
assert report['triangles']<=30000
print('REVIVAL_TENT_SOURCE_AUDIT',len(objects),report['triangles'],len(edges),len(roots),flush=True)
