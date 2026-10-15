"""Read back Coal Yard ruin components, contacts and exact joined geometry."""
import hashlib
import json
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

out=Path(sys.argv[sys.argv.index('--')+1]).resolve()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record=json.loads((out/'authoring.json').read_text())
components=out/'CoalYard-Ruin-Components.blend'
bpy.ops.wm.open_mainfile(filepath=str(components),use_scripts=False)
objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
assert len(objects)==record['component_count']
vertices={o.name:[o.matrix_world@v.co for v in o.data.vertices] for o in objects}
trees={o.name:BVHTree.FromPolygons(vertices[o.name],[p.vertices for p in o.data.polygons]) for o in objects}
heaps=[o for o in objects if o.name.startswith('Low spilled coal heap')]
ties=[o for o in objects if o.name.startswith('Sawn timber rail tie')]
assert len(heaps)==3 and len(ties)==11
rows=[]
expected=[]
transform=Matrix.Scale(record['normalization']['scale'],4)@Matrix.Translation(Vector(record['normalization']['shift']))
for o in objects:
    points=vertices[o.name]
    expected.extend(tuple(transform@p) for p in points)
    bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world)
    # Translation to local centre avoids volume cancellation on small distant pieces.
    centre=sum((v.co for v in bm.verts),Vector())/len(bm.verts)
    for v in bm.verts:v.co-=centre
    bm.normal_update()
    volume=bm.calc_volume(signed=True)
    assert volume>0 and all(e.is_manifold for e in bm.edges),o.name
    assert all(f.calc_area()>1e-12 for f in bm.faces),o.name
    bm.free()
    bottom=min(p.z for p in points);top=max(p.z for p in points)
    supports=[]
    if bottom<1e-6:
        assert bottom>-.0001,o.name
        supports=['ground plane']
    elif o.name.startswith('Coal fragment'):
        for heap in heaps:
            gaps=[]
            for p in points:
                hit,*_=trees[heap.name].ray_cast(Vector((p.x,p.y,2)),Vector((0,0,-1)))
                if hit is not None:gaps.append(p.z-hit.z)
            if gaps and min(gaps)<0<max(gaps):supports.append(heap.name)
    elif o.name.startswith(('Closed flat-bottom iron rail','Plain rail spike head')):
        # Test rail underside at every tie centre; spike centre against its tie.
        xmid=(min(p.x for p in points)+max(p.x for p in points))/2
        ymid=(min(p.y for p in points)+max(p.y for p in points))/2
        for tie in ties:
            tx=sum(p.x for p in vertices[tie.name])/len(vertices[tie.name])
            x=tx if o.name.startswith('Closed') else xmid
            hit,*_=trees[tie.name].ray_cast(Vector((x,ymid,2)),Vector((0,0,-1)))
            if hit is not None and bottom-.00001<=hit.z<top:supports.append(tie.name)
        if o.name.startswith('Closed'):assert len(supports)==11,(o.name,supports)
    assert supports,('Unsupported component',o.name,bottom)
    rows.append(dict(name=o.name,positive_volume_m3=volume,closed=True,minimum_z_m=bottom,supports=supports))
project=out/'CoalYard-Ruin.blend'
assert sha(project)==record['project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(project),use_scripts=False)
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(meshes)==1
actual=[tuple(meshes[0].matrix_world@v.co) for v in meshes[0].data.vertices]
assert len(actual)==len(expected)
error=max(abs(a-b) for p,q in zip(sorted(actual),sorted(expected)) for a,b in zip(p,q))
assert error<.00001,error
(out/'support-validation.json').write_text(json.dumps(dict(status='passed',project_sha256=sha(project),components_project_sha256=sha(components),components=len(rows),maximum_joined_coordinate_error_m=error,checks=rows,scope='Saved closed outward components, ground or assembly support, coal bedding, railway support and joined-coordinate preservation. Not engineering strength, Boolean overlap or native terrain validation.'),indent=2)+'\n')
print('COAL_YARD_RUIN_SUPPORT_VALIDATED',len(rows),flush=True)
