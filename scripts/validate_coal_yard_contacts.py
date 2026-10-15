"""Read-only source checks for Coal Yard's coal and timber assembly.

Mixar --background --python scripts/validate_coal_yard_contacts.py -- SOURCE_DIR
This complements actual renders; it is not structural engineering analysis.
"""
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

source = Path(sys.argv[sys.argv.index('--')+1]).resolve()
project = source/'CoalYard.blend'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
record = json.loads((source/'authoring.json').read_text())
assert sha(project) == record['project_sha256']
bpy.ops.wm.open_mainfile(filepath=str(project), use_scripts=False)
heaps = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('Wall-restrained shallow coal heap')]
assert len(heaps) == 3
trees = []
for heap in heaps:
    verts = [heap.matrix_world @ v.co for v in heap.data.vertices]
    cx = (min(v.x for v in verts)+max(v.x for v in verts))/2
    trees.append((cx, BVHTree.FromPolygons(verts, [p.vertices for p in heap.data.polygons])))
    assert max(v.z for v in verts) < .975, 'Coal exceeds retaining walls'
fragments = [o for o in bpy.data.objects if o.name.startswith('Angular coal fragment embedded in heap')]
assert len(fragments) == 570
issues = []
worst_protrusion = 0
for obj in fragments:
    cx, tree = min(trees, key=lambda item: abs(item[0]-obj.location.x))
    vertices = [obj.matrix_world @ v.co for v in obj.data.vertices]
    gaps = []
    for v in vertices:
        hit, _, _, _ = tree.ray_cast(Vector((v.x, v.y, 2)), Vector((0, 0, -1)))
        if hit is not None:
            gaps.append(v.z-hit.z)
    # The solid pile underlies each fragment and intersects its vertical extent.
    if not gaps or min(gaps) > 0 or max(gaps) <= 0:
        issues.append(dict(object=obj.name, reason='not visibly bedded in heap', gaps=gaps))
    # Keep fragments behind the OUTER face of the retaining boards. The inner
    # face can intersect coal as it would in a filled wooden bin.
    protrusion = max(max(abs(v.x-cx)-.795, -.34-v.y, v.y-1.70) for v in vertices)
    worst_protrusion = max(worst_protrusion, protrusion)
    if protrusion > .001:
        issues.append(dict(object=obj.name, reason='visible bin-wall protrusion', metres=protrusion))
posts = [o for o in bpy.data.objects if o.name.startswith('Grounded frame post')]
assert len(posts) == 8
for obj in posts:
    zs = [(obj.matrix_world @ v.co).z for v in obj.data.vertices]
    assert abs(min(zs)-.10) < 1e-6 and abs(max(zs)-1.99) < 1e-6
result = dict(status='passed' if not issues else 'revision_required', project_sha256=sha(project),
              scope='Coal fragment bedding, visible retaining-wall envelope, pile height and post/plate butt height; not a whole-scene Boolean or engineering analysis',
              heaps=len(heaps), fragments=len(fragments), grounded_posts=len(posts),
              maximum_visible_wall_protrusion_m=worst_protrusion, issues=issues)
(source/'contact-validation.json').write_text(json.dumps(result, indent=2)+'\n')
assert not issues, issues[:5]
print('COAL_YARD_CONTACTS_VALIDATED', len(fragments), flush=True)
