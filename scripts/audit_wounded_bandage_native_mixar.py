"""Intersect exported native CPU-skinned body/bandage triangles in local Mixar.

OLDWEST_BANDAGE_NATIVE_EVIDENCE selects an existing preview evidence directory.
No source meshes, native assets, animation or gameplay state are changed.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri

BASE=Path(os.environ['OLDWEST_BANDAGE_NATIVE_EVIDENCE'])


def crosses(a,b):
    for origin,end in zip(a,a[1:]+a[:1]):
        direction=end-origin
        length=direction.length
        if length<1e-8:
            continue
        direction/=length
        point=intersect_ray_tri(*b,direction,origin,True)
        if point is not None and 1e-6<(point-origin).dot(direction)<length-1e-6:
            return True
    return False


evidence=json.loads((BASE/'result.json').read_text())
report=dict(ok=False,scope='Sampled native CPU-skinned surfaces; does not prove clearance between samples',
            input_complete=evidence['ok'],expected_samples=11*len(evidence['slugs']),samples=[],failures=[])
for state in evidence['states']:
    if 'geometry' not in state:
        continue
    path=BASE/state['geometry']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==state['geometry_sha256']
    with gzip.open(path,'rt') as stream:
        geometry=json.load(stream)['geometry']
    meshes={}
    for key in ('body','bandage'):
        data=geometry[key]
        assert data['space']=='actor-relative world-axis meters'
        points=[Vector(p) for p in data['vertices']]
        triangles=data['triangles']
        assert points and triangles and all(len(t)==3 and all(0<=i<len(points) for i in t) for t in triangles)
        meshes[key]=(points,triangles,BVHTree.FromPolygons(points,triangles,all_triangles=True))
    bp,bt,bb=meshes['body']
    wp,wt,wb=meshes['bandage']
    intersecting=[]
    for wi,bi in wb.overlap(bb):
        a,b=[wp[i] for i in wt[wi]],[bp[i] for i in bt[bi]]
        if crosses(a,b) or crosses(b,a):
            intersecting.append([wi,bi])
    row=dict(slug=state['slug'],pose=state['pose'],fraction=state['fraction'],geometry=state['geometry'],
             intersecting_pairs=len(intersecting),pairs=intersecting,
             body_vertices=len(bp),bandage_vertices=len(wp))
    report['samples'].append(row)
    if intersecting:
        report['failures'].append({k:v for k,v in row.items() if k!='pairs'})
    print('NATIVE_WOUND_CLEARANCE',state['slug'],state['pose'],state['fraction'],len(intersecting),flush=True)
report['ok']=report['input_complete'] and len(report['samples'])==report['expected_samples'] and not report['failures']
name = 'mesh-clearance.json' if report['input_complete'] else f'mesh-clearance-partial-{len(report["samples"]):03}.json'
(BASE/name).write_text(json.dumps(report,indent=2)+'\n')
