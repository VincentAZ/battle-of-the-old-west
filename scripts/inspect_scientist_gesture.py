"""CPU-only inspection of the saved study, including actual deformed skin.

Run Blender --python this_file -- --source candidate-directory. This is a
sampled geometric audit, not a native physics or continuous collision test.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

parser = argparse.ArgumentParser()
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--blend', type=Path, help='Explicit branch study when its saved filename differs from the core study.')
parser.add_argument('--all-frames', action='store_true', help='Inspect every authored30Hz frame, retaining the same geometry predicate.')
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
source = args.source.resolve()
blend = args.blend.resolve() if args.blend else source / 'Scientist_Analysis_Candidate.blend'
digest = hashlib.sha256(blend.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(blend), use_scripts=False)
arm = bpy.data.objects['Survivor_Rig']
body = bpy.data.objects['Survivor_Body']
coat = bpy.data.objects['Scientist_Outfit_Assembly']
hand_indices = {}
for side in ('Left', 'Right'):
    groups = {g.index for g in body.vertex_groups if g.name.startswith('mixamorig:'+side+'Hand')}
    hand_indices[side] = [v.index for v in body.data.vertices if sum(g.weight for g in v.groups if g.group in groups) > .5]
    assert len(hand_indices[side]) > 100
props = [o for o in bpy.data.objects if o.type == 'MESH' and o.parent and o.parent.type == 'EMPTY']


def geometry(obj, deps):
    evaluated = obj.evaluated_get(deps)
    mesh = evaluated.to_mesh()
    vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    triangles = [list(p.vertices) for p in mesh.polygons]
    evaluated.to_mesh_clear()
    tree = BVHTree.FromPolygons(vertices, triangles)
    low = Vector(tuple(min(v[i] for v in vertices) for i in range(3)))
    high = Vector(tuple(max(v[i] for v in vertices) for i in range(3)))
    return vertices, tree, low, high


def within(point, low, high):
    return all(low[i] <= point[i] <= high[i] for i in range(3))


records = []
last_frame = bpy.context.scene.frame_end
frames = sorted(set(range(1,last_frame+1,5)) | {frame for frame in (25,30,55,60,80,94,125,145,157,176,185,198,205,215,245,258,265,271,last_frame) if frame<=last_frame})
if args.all_frames: frames = list(range(1,last_frame+1))
for frame in frames:
    bpy.context.scene.frame_set(frame)
    deps = bpy.context.evaluated_depsgraph_get()
    evaluated = body.evaluated_get(deps)
    mesh = evaluated.to_mesh()
    assert len(mesh.vertices) == len(body.data.vertices), 'Hand vertex correspondence changed'
    vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    evaluated.to_mesh_clear()
    row = {'frame': frame, 'seconds': (frame-1)/30, 'hands': {}, 'elbows': {},
           'world_bone_heads_m': {bone.name: list(arm.matrix_world @ bone.head) for bone in arm.pose.bones}}
    for side, indices in hand_indices.items():
        points = [vertices[i] for i in indices]
        low = Vector(tuple(min(v[i] for v in points) for i in range(3)))
        high = Vector(tuple(max(v[i] for v in points) for i in range(3)))
        contacts = []
        for obj in props:
            _, tree, a, b = geometry(obj, deps)
            if any(high[i] < a[i] or b[i] < low[i] for i in range(3)):
                continue
            deepest, count = 0., 0
            for point in points:
                if not within(point, a, b):
                    continue
                location, normal, _, distance = tree.find_nearest(point)
                if location is not None and (point-location).dot(normal) < -1e-6:
                    deepest = max(deepest, distance * 100); count += 1
            if count:
                contacts.append({'part': obj.name, 'root': obj.parent.name,
                                 'skin_vertices_inside_convex_part': count, 'maximum_depth_cm': deepest})
        row['hands'][side] = {'skin_vertex_count': len(indices), 'world_bounds_m': [list(low), list(high)],
                              'convex_part_intersections': contacts}
    _, coat_tree, _, _ = geometry(coat, deps)
    for side in ('Left', 'Right'):
        elbow = arm.matrix_world @ arm.pose.bones['mixamorig:'+side+'ForeArm'].head
        points = [v for v in vertices if (v-elbow).length < .065]
        outside = []
        for v in points:
            location, normal, _, distance = coat_tree.find_nearest(v)
            if location is not None and (v-location).dot(normal) > 1e-5:
                outside.append(distance * 100)
        row['elbows'][side] = {'near_elbow_skin_vertices': len(points), 'outside_nearest_coat_surface': len(outside),
                              'maximum_positive_normal_gap_cm': max(outside, default=0.)}
    records.append(row)
    print('SCIENTIST_SKIN_SAMPLE', frame, flush=True)
assert hashlib.sha256(blend.read_bytes()).hexdigest() == digest
report = {'status': 'sampled_geometry_requires_visual_interpretation', 'source_blend': str(blend), 'source_sha256': digest,
          'frames': len(records), 'source_unchanged': True,
          'all_authored_30hz_frames': args.all_frames,
          'method': 'Evaluated skinned hand vertices against individual closed convex prop pieces; nearest geometric surface normal gives signed containment. Elbow vertices within6.5cm compared to nearest outfit surface.',
          'limitations': ['Sampled frames, not continuous collision detection.',
                          'Tiny grip penetration may represent surface contact; depths and actual images need review.',
                          'Nearest coat normal is diagnostic; open cuffs/seams can give ambiguous inside/outside labels.',
                          'No native import, gameplay, cloth simulation or physics proof.'], 'samples': records}
(source / 'skin-contact-audit.json').write_text(json.dumps(report, indent=2)+'\n')
print('SCIENTIST_SKIN_AUDIT_COMPLETE', str(source), flush=True)
