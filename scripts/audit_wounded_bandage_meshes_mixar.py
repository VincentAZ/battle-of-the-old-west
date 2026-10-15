"""Check saved bandage surfaces against unchanged body triangles in bind pose."""
import json
import os
from pathlib import Path
import bpy
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_ray_tri

ROOT = Path(__file__).resolve().parents[1]
BASE = Path(os.environ.get('OLDWEST_BANDAGE_SOURCE', str(ROOT / 'art/western/bandages/review-v002')))


def triangles(obj):
    obj.data.calc_loop_triangles()
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    indices = [tuple(t.vertices) for t in obj.data.loop_triangles]
    return points, indices, BVHTree.FromPolygons(points, indices, all_triangles=True)


def crosses(a, b):
    for origin, end in zip(a, a[1:] + a[:1]):
        direction = end - origin
        length = direction.length
        if length < 1e-8:
            continue
        direction /= length
        point = intersect_ray_tri(*b, direction, origin, True)
        if point is not None and 1e-6 < (point-origin).dot(direction) < length-1e-6:
            return True
    return False


report = []
for path in sorted(BASE.glob('*/authoring.json')):
    data = json.loads(path.read_text())
    bpy.ops.wm.open_mainfile(filepath=str(path.parent / ('Bandage_'+data['name']+'.blend')), use_scripts=False)
    wrap = bpy.data.objects['Bandage_'+data['name']]
    body = next(o for o in bpy.context.scene.objects if o != wrap and o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers))
    wp, wt, wb = triangles(wrap)
    bp, bt, bb = triangles(body)
    candidates = wb.overlap(bb)
    intersections = []
    for wi, bi in candidates:
        a, b = [wp[i] for i in wt[wi]], [bp[i] for i in bt[bi]]
        if crosses(a, b) or crosses(b, a):
            intersections.append([wi, bi])
    report.append(dict(slug=data['slug'], intersecting_pairs=len(intersections), pairs=intersections))
    print('BANDAGE_MESH', data['slug'], len(intersections), flush=True)
(BASE/'source-fit-mesh-audit.json').write_text(json.dumps(report, indent=2)+'\n')
