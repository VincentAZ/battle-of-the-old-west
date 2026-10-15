"""Read-only base/terrain clearance audit using a native captured transform.

Mixar --background --factory-startup --python-exit-code 1 --python SCRIPT
    -- NATIVE_STATE OUTPUT_JSON
The exact arena collision source shares the visible terrain's triangulation.
"""
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
state_path, output = map(Path, sys.argv[sys.argv.index('--')+1:])
cinematic = json.loads(state_path.read_text())['before_request']['cinematic']
terrain_state = cinematic['terrain_renderer']
assert terrain_state['location'] == [0, 0, 0]
assert terrain_state['scale'] == [1, 1, 1]
assert all(abs(v) < 1e-5 for v in terrain_state['rotation_degrees'])
unit = next(u for u in cinematic['units'] if u.get('card_id') == 'post_office')
component = next(c for c in unit['holding_components'] if '/SM_HoldingBase_' in c['mesh'])
x, y, z, w = component['quaternion_xyzw']
transform = Matrix.LocRotScale(Vector(component['location']), Quaternion((w, x, y, z)), Vector(component['scale']))
base = ROOT/'art/western/holdings/expansion-review-v001/post-office/base-v001/post-office-Base.blend'
terrain = ROOT/'art/world/ContinuousTerrain_Collision.blend'
sources = [base, terrain, state_path]
hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
bpy.ops.wm.open_mainfile(filepath=str(base), use_scripts=False)
obj = bpy.data.objects['Holding_Base_Ground']
edge_uses = {}
for face in obj.data.polygons:
    for a, b in face.edge_keys:
        key = tuple(sorted((a, b)))
        edge_uses[key] = edge_uses.get(key, 0)+1
boundary = sorted({v for edge, count in edge_uses.items() if count == 1 for v in edge})
points = []
for index in boundary:
    p = obj.matrix_world @ obj.data.vertices[index].co
    # Holding export rotates 180 degrees, then FBX/Unreal reverses Y.
    points.append(transform @ Vector((-100*p.x, 100*p.y, 100*p.z)))
bpy.ops.wm.open_mainfile(filepath=str(terrain), use_scripts=False)
obj = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
obj.data.calc_loop_triangles()
verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
tree = BVHTree.FromPolygons(verts, [tuple(t.vertices) for t in obj.data.loop_triangles], all_triangles=True)
samples = []
for index, p in zip(boundary, points):
    # Terrain FBX has no holding-specific 180-degree turn.
    hit, normal, face, distance = tree.ray_cast(Vector((p.x/100, -p.y/100, 100)), Vector((0, 0, -1)), 200)
    assert hit is not None
    samples.append(dict(vertex=index, world_cm=list(p), terrain_z_cm=hit.z*100, clearance_cm=p.z-hit.z*100))
assert all(hashlib.sha256(p.read_bytes()).hexdigest() == hashes[str(p)] for p in sources)
report = dict(scope='Post Office outer ground rim at one native placement; positive clearance is above terrain.',
    source_sha256=hashes, native_component=component, terrain_transform=terrain_state,
    boundary_samples=len(samples), minimum_clearance_cm=min(s['clearance_cm'] for s in samples),
    maximum_clearance_cm=max(s['clearance_cm'] for s in samples),
    samples=samples, sources_unchanged=True)
output.write_text(json.dumps(report, indent=2)+'\n')
print('POST_OFFICE_GROUND_AUDIT', report['minimum_clearance_cm'], report['maximum_clearance_cm'], flush=True)
