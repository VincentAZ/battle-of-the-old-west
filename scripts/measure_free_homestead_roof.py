"""Read exact reviewed roof intersections for cosmetic damage emitters."""
import hashlib
import json
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'art/western/holdings/expansion-review-v001/free-homestead'
project = BASE / 'review-v003/free-homestead-Review.blend'
digest = hashlib.sha256(project.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(project), use_scripts=False)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
vertices, polygons = [], []
for obj in meshes:
    offset = len(vertices)
    vertices.extend(obj.matrix_world @ v.co for v in obj.data.vertices)
    polygons.extend(tuple(offset + i for i in p.vertices) for p in obj.data.polygons)
bvh = BVHTree.FromPolygons(vertices, polygons)
points = []
for x, y in [(-80, -85), (80, 85)]:
    hit, normal, index, distance = bvh.ray_cast(Vector((-x/100, y/100, 10)), Vector((0, 0, -1)))
    assert hit is not None and hit.z > 2 and normal.z > .5, (hit, normal)
    points.append([x, y, round(hit.z*100, 4)])
assert hashlib.sha256(project.read_bytes()).hexdigest() == digest
(BASE / 'damage-roof-points.json').write_text(json.dumps(dict(
    source_project=str(project.relative_to(ROOT)), source_sha256=digest,
    method='Downward exact-triangle BVH rays at mesh-space centimetre XY. Native X is negative review X; native Y equals review Y after the baked 180-degree turn and handedness conversion. Points lie on the two roof slopes away from the ridge.',
    points_cm=points), indent=2)+'\n')
print('FREE_HOMESTEAD_ROOF_POINTS', points, flush=True)
