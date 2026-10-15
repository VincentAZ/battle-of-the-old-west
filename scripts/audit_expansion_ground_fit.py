"""Read-only Mixar audit of a dry expansion base using a native transform.

Compares undeformed and shader-predicted triangles with the exact terrain.
This is independent source arithmetic, not GPU readback or continuous proof.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state', type=Path, required=True)
parser.add_argument('--base', type=Path, required=True)
parser.add_argument('--card-id', required=True)
parser.add_argument('--extent', type=float, nargs=3, required=True)
parser.add_argument('--covered-extent', type=float, nargs=2, required=True,
                    help='Local half-width/depth of the area covered by the structure')
parser.add_argument('--apron-clearance', type=float, default=.5,
                    help='Proposed outer apron lift in world centimetres; must match the reviewed material')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
assert 0 <= args.apron_clearance <= 5
terrain = ROOT/'art/world/ContinuousTerrain_Collision.blend'
texture = ROOT/'art/western/holdings/ground-fit-v001/T_ArenaGroundHeight.tga'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
protected = {p: sha(p) for p in (args.state, args.base, terrain, texture)}
state = json.loads(args.state.read_text())
cinematic = state.get('before_request', state)['cinematic']
terrain_pose = cinematic['terrain_renderer']
assert terrain_pose['location'] == [0, 0, 0] and terrain_pose['scale'] == [1, 1, 1]
assert all(abs(v) < 1.e-5 for v in terrain_pose['rotation_degrees'])
unit = next(u for u in cinematic['units'] if u.get('card_id') == args.card_id)
component = next(c for c in unit['holding_components'] if '/SM_HoldingBase_' in c['mesh'])
if component['ground_fit']:
    assert component['ground_fit']['foundation_extent'] == args.extent
x, y, z, w = component['quaternion_xyzw']
pose = Matrix.LocRotScale(Vector(component['location']), Quaternion((w, x, y, z)), Vector(component['scale']))
origin = Vector(component['location'])
raw = texture.read_bytes()
assert struct.unpack('<BBBHHBHHHHBB', raw[:18])[8:12] == (261, 261, 24, 32)


def at(i, j):
    b, g, r = raw[18+(j*261+i)*3:21+(j*261+i)*3]
    return (r*256+g-32768)/16, b > 127


def height(p):
    x, y = (p.x+6500)/50, (p.y+6500)/50
    assert 0 <= x < 260 and 0 <= y < 260
    i, j = int(x), int(y)
    fx, fy = x-i, y-j
    a, rising = at(i, j)
    b, _ = at(i+1, j); c, _ = at(i, j+1); d, _ = at(i+1, j+1)
    if rising:
        return a+(b-a)*fx+(d-b)*fy if fy <= fx else a+(d-c)*fx+(c-a)*fy
    return a+(b-a)*fx+(c-a)*fy if fx+fy <= 1 else d+(c-d)*(1-fx)+(b-d)*(1-fy)


def project(obj, vertex):
    p = obj.matrix_world @ vertex.co
    local = Vector((-100*p.x, 100*p.y, 100*p.z))
    world = pose @ local
    outside = math.hypot(max(abs(local.x)-args.extent[0], 0), max(abs(local.y)-args.extent[1], 0))
    t = min(1, outside/args.extent[2]); weight = t*t*(3-2*t)
    delta = height(world)-origin.z
    offset = max(delta, delta*weight)+args.apron_clearance*weight
    assert abs(offset) < 200, 'Required displacement exceeds material bounds'
    return world, world+Vector((0, 0, offset)), local


bpy.ops.wm.open_mainfile(filepath=str(args.base), use_scripts=False)
ground = bpy.data.objects['Holding_Base_Ground']
ground.data.calc_loop_triangles()
triples = [project(ground, v) for v in ground.data.vertices]
original, fitted, local = [list(v) for v in zip(*triples)]
triangles = [tuple(t.vertices) for t in ground.data.loop_triangles]
fitted_tree = BVHTree.FromPolygons(fitted, triangles, all_triangles=True)
original_tree = BVHTree.FromPolygons(original, triangles, all_triangles=True)
roots = []
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH' or 'Tuft' not in obj.name:
        continue
    # Each disconnected ribbon is one blade; inspect its lowest vertices.
    parent = list(range(len(obj.data.vertices)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i

    for edge in obj.data.edges:
        a, b = map(find, edge.vertices); parent[a] = b
    groups = {}
    for v in obj.data.vertices:
        groups.setdefault(find(v.index), []).append(v)
    for vertices in groups.values():
        low = min((obj.matrix_world @ v.co).z for v in vertices)
        for v in vertices:
            if (obj.matrix_world @ v.co).z > low+.001:
                continue
            before, p, _ = project(obj, v)
            hit, _, _, _ = fitted_tree.ray_cast(Vector((p.x, p.y, 10000)), Vector((0, 0, -1)), 20000)
            original_hit, _, _, _ = original_tree.ray_cast(Vector((before.x, before.y, 10000)), Vector((0, 0, -1)), 20000)
            assert hit is not None, 'Grass root has no setting-base support'
            assert original_hit is not None
            roots.append(dict(world_cm=list(p), clearance_above_fitted_ground_cm=p.z-hit.z,
                              original_clearance_cm=before.z-original_hit.z,
                              clearance_change_cm=(p.z-hit.z)-(before.z-original_hit.z)))

# Branches share the same position-based deformation as their leaves and soil.
# Measure whole shrub root collars, not the low end of every elevated twig.
shrubs = []
shrub_name, shrub_count = ('Holding_Base_Juniper', 2) if args.card_id == 'robbers_roost' else ('Holding_Base_Shrub', 4)
for obj in bpy.context.scene.objects:
    if obj.type != 'MESH' or obj.name != shrub_name or args.card_id not in ('pony_express_station', 'robbers_roost'):
        continue
    projected = [project(obj, v) for v in obj.data.vertices]
    shifts = [after.z-before.z for before, after, _ in projected]
    row = dict(object=obj.name, vertices=len(projected),
               displacement_variation_cm=max(shifts)-min(shifts), root_samples=[])
    if obj.name == shrub_name:
        low = min(local.z for _, _, local in projected)
        for before, after, shrub_local in projected:
            if shrub_local.z > low+(3 if args.card_id == 'robbers_roost' else 1.5):
                continue
            hit, _, _, _ = fitted_tree.ray_cast(Vector((after.x, after.y, 10000)), Vector((0, 0, -1)), 20000)
            original_hit, _, _, _ = original_tree.ray_cast(Vector((before.x, before.y, 10000)), Vector((0, 0, -1)), 20000)
            assert hit is not None and original_hit is not None, 'Shrub root has no base support'
            row['root_samples'].append(dict(world_cm=list(after),
                original_clearance_cm=before.z-original_hit.z,
                fitted_clearance_cm=after.z-hit.z,
                clearance_change_cm=(after.z-hit.z)-(before.z-original_hit.z)))
        assert row['root_samples']
        collars = []
        for sample in row['root_samples']:
            p = Vector(sample['world_cm'])
            collar_radius = 20 if args.card_id == 'robbers_roost' else 10
            group = next((g for g in collars if (p.xy-g[0].xy).length < collar_radius), None)
            if group is None:
                collars.append([p])
            else:
                group.append(p)
        assert len(collars) == shrub_count, 'Saved setting must contain every separate root collar'
        centres = [sum(g, Vector())/len(g) for g in collars]
        plant_shifts = [[] for _ in centres]
        for before, after, _ in projected:
            index = min(range(len(centres)), key=lambda i: (after.xy-centres[i].xy).length)
            plant_shifts[index].append(after.z-before.z)
        row['plants'] = [dict(root_centre_world_cm=list(c), root_vertices=len(g),
            displacement_variation_cm=max(values)-min(values))
            for c, g, values in zip(centres, collars, plant_shifts)]
    shrubs.append(row)
if args.card_id == 'pony_express_station':
    assert len(shrubs) == 1 and len(shrubs[0]['plants']) == 4, 'Station shrub audit was empty'
if args.card_id == 'robbers_roost':
    assert len(shrubs) == 1 and len(shrubs[0]['plants']) == 2, 'Juniper root audit was empty'

bpy.ops.wm.open_mainfile(filepath=str(terrain), use_scripts=False)
obj = next(o for o in bpy.context.scene.objects if o.type == 'MESH')
obj.data.calc_loop_triangles()
tree = BVHTree.FromPolygons([obj.matrix_world @ v.co for v in obj.data.vertices],
    [tuple(t.vertices) for t in obj.data.loop_triangles], all_triangles=True)
samples = []
for tri in triangles:
    for weights in ((1/3, 1/3, 1/3), (.5, .5, 0), (0, .5, .5), (.5, 0, .5)):
        q = sum((local[i]*weight for i, weight in zip(tri, weights)), Vector())
        # Zero covered extents audit the entire base, including central gaps.
        if abs(q.x) < args.covered_extent[0] and abs(q.y) < args.covered_extent[1]:
            continue
        before, after = [sum((points[i]*weight for i, weight in zip(tri, weights)), Vector())
                         for points in (original, fitted)]
        hit, _, _, _ = tree.ray_cast(Vector((after.x/100, -after.y/100, 100)), Vector((0, 0, -1)), 200)
        assert hit is not None
        samples.append(dict(world_cm=list(after), original_clearance_cm=before.z-hit.z*100,
                            fitted_clearance_cm=after.z-hit.z*100))
assert samples
assert all(sha(p) == digest for p, digest in protected.items())
report = dict(scope=__doc__.strip(), native_component=component, foundation_extent_cm=args.extent,
    apron_clearance_cm=args.apron_clearance,
    covered_extent_cm=args.covered_extent, auditor_sha256=sha(Path(__file__)),
    source_sha256={str(p): digest for p, digest in protected.items()}, sources_unchanged=True,
    triangles=len(triangles), exposed_surface_samples=len(samples),
    original_minimum_clearance_cm=min(s['original_clearance_cm'] for s in samples),
    original_below_terrain_samples=sum(s['original_clearance_cm'] < 0 for s in samples),
    fitted_minimum_clearance_cm=min(s['fitted_clearance_cm'] for s in samples),
    fitted_maximum_clearance_cm=max(s['fitted_clearance_cm'] for s in samples),
    fitted_below_terrain_samples=sum(s['fitted_clearance_cm'] < 0 for s in samples),
    worst_samples=sorted(samples, key=lambda s: s['fitted_clearance_cm'])[:20],
    grass_root_samples=len(roots), grass_root_minimum_clearance_cm=min((r['clearance_above_fitted_ground_cm'] for r in roots), default=None),
    grass_root_maximum_clearance_cm=max((r['clearance_above_fitted_ground_cm'] for r in roots), default=None),
    grass_original_root_minimum_clearance_cm=min((r['original_clearance_cm'] for r in roots), default=None),
    grass_root_maximum_absolute_clearance_change_cm=max((abs(r['clearance_change_cm']) for r in roots), default=None),
    shrub_support=shrubs,
    limitations='One native placement; source triangle samples and predicted root positions, not GPU readback. Only a nonzero covered rectangle is excluded; zero extents audit the entire base. Other identities, placements and conditions remain separate.')
args.output.parent.mkdir(parents=True, exist_ok=True)
assert not args.output.exists(), 'Preserve earlier audit evidence'
args.output.write_text(json.dumps(report, indent=2)+'\n')
print('EXPANSION_GROUND_AUDIT', report['original_below_terrain_samples'], report['fitted_below_terrain_samples'],
      report['fitted_minimum_clearance_cm'], report['grass_root_samples'], flush=True)
