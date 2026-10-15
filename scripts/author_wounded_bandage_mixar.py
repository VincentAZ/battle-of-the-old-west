"""Fit a separate circular muslin dressing to an existing, unmodified Crew rig.

Local Mixar only; no generation/upload. Run after the sourced research brief.
Example: mixar --background --factory-startup --python-exit-code 1 --python
scripts/author_wounded_bandage_mixar.py -- doc-holliday
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/western/bandages/review-v002'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('slug')
    parser.add_argument('--side', choices=['Left', 'Right'], default='Left')
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--recenter', action='store_true', help='Fit each cross-section around the weighted sleeve surface when the bone axis lies outside it')
    parser.add_argument('--complete-surface', action='store_true', help='Include sleeve triangles whose skin weights extend beyond arm bones; requires individual prop-clearance review')
    parser.add_argument('--center', type=float, default=.65)
    parser.add_argument('--turns', type=int, choices=[2, 3], default=3)
    parser.add_argument('--inside-out', action='store_true', help='Use the nearest surface from the limb axis to avoid a separate prop/torso beyond the sleeve')
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--clearance', type=float, default=.0018)
    parser.add_argument('--segments', type=int, choices=[96, 192], default=96)
    parser.add_argument('--across', type=int, choices=[8, 24], default=8)
    parser.add_argument('--pitch', type=float, default=.026)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    brief = ROOT / 'research/western-presentation/wounded-bandage.json'
    assert json.loads(brief.read_text())['sources'][0]['actual_page_images_reviewed']
    records = json.loads((ROOT / 'art/western/crew/playable-v001/manifest.json').read_text())['characters']
    if args.slug == 'drifter':
        approval = json.loads((ROOT / 'art/western/drifter/animation-v001/approval.json').read_text())
        approved_source = (ROOT / 'art/western/drifter/animation-v001' / approval['approved_appearance']).resolve()
        record = dict(asset_name='Drifter', sha256=approval['source_sha256'], path=str(approved_source.relative_to(ROOT)))
    else:
        assert args.slug in records, 'Use an approved Crew source'
        record = records[args.slug]
    name = record['asset_name']
    special = {
        'quanah-parker': ('art/western/native/quanah-game-v001', 'Quanah'),
        'lozen': ('art/western/native/lozen-cloth-v004', 'Lozen'),
        'sarah-winnemucca': ('art/western/native/playable-v001/sarah-winnemucca', 'Sarah'),
        'drifter': ('art/western/drifter/animation-v001', 'Drifter'),
    }
    if args.slug in special:
        folder, name = special[args.slug]
        source = ROOT / folder / (name + '-Rigged.blend')
    else:
        source = ROOT / 'art/western/crew/playable-v001' / args.slug / (name + '-Rigged.blend')
    validation = json.loads((source.parent / 'rig-validation.json').read_text())
    before = sha(source)
    assert before == validation['project_sha256']
    if 'path' in record:
        assert sha(ROOT / record['path']) == record['sha256']
    assert args.output.resolve().is_relative_to(ROOT/'art/western/bandages')
    assert .001 <= args.clearance <= .005
    output = args.output / args.slug
    assert not (output / ('Bandage_' + name + '.blend')).exists(), 'Preserve earlier source revisions'
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    obj = next(o for o in bpy.context.scene.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers))
    arm = next(m.object for m in obj.modifiers if m.type == 'ARMATURE')
    arm.data.pose_position = 'REST'
    bone = arm.data.bones[args.side + 'ForeArm']
    start, end = (arm.matrix_world @ p for p in (bone.head_local, bone.tail_local))
    axis = (end - start).normalized()
    # Local circular dressing, clear of both elbow and wrist articulations.
    # Some approved guide wrists lie above the visible wrist; extrapolate the
    # sampling axis only. Surface positions and weights still come from Body.
    assert .25 <= args.center <= 1.3 and .008 <= args.pitch <= .026
    center = start.lerp(end, args.center)
    u = axis.cross(Vector((0, 1, 0))).normalized()
    v = axis.cross(u).normalized()
    points = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    groups = {g.index: g.name for g in obj.vertex_groups}
    weights = [{groups[g.group]: g.weight for g in vertex.groups} for vertex in obj.data.vertices]
    allowed = {args.side + suffix for suffix in ('Arm', 'ForeArm', 'Hand')}
    obj.data.calc_loop_triangles()
    triangles = [tuple(t.vertices) for t in obj.data.loop_triangles
                 if args.complete_surface or all(sum(weights[i].get(n, 0) for n in allowed) > .5 for i in t.vertices)]
    assert triangles, 'No weighted forearm surface'
    tree = BVHTree.FromPolygons(points, triangles, all_triangles=True)
    arm_points = [p for p, row in zip(points, weights) if row.get(args.side + 'ForeArm', 0) > .5]
    vertices, faces, skin, radii = [], [], [], []
    segments, across, width = args.segments, args.across, .052
    for turn in range(args.turns):
        base = len(vertices)
        for a in range(segments + 1):
            theta = 2 * math.pi * a / segments
            radial = u * math.cos(theta) + v * math.sin(theta)
            for j in range(across + 1):
                along = (j / across - .5) * width + (turn - (args.turns-1)/2) * args.pitch
                origin = center + axis * along
                if args.recenter:
                    section = [p - origin for p in arm_points if abs((p-origin).dot(axis)) < .015]
                    assert len(section) >= 8, 'Insufficient sleeve cross-section'
                    us, vs = sorted(p.dot(u) for p in section), sorted(p.dot(v) for p in section)
                    origin += u * ((us[0]+us[-1])/2) + v * ((vs[0]+vs[-1])/2)
                if args.inside_out:
                    hit, normal, face, distance = tree.ray_cast(origin, radial, .11)
                else:
                    hit, normal, face, distance = tree.ray_cast(origin + radial * .13, -radial, .13)
                assert hit is not None, (args.slug, 'Open/offset forearm surface', turn, a, j)
                radius = (hit - origin).dot(radial)
                assert .012 < radius < .11, (args.slug, 'Unreasonable wrap radius', radius)
                radii.append(radius)
                # Thin layered cloth, with a small raised selvage-free cut edge.
                edge = .0005 * abs(2 * j / across - 1) ** 8
                point = hit + radial * (args.clearance + turn * .0012 + edge)
                vertices.append(point)
                tri = triangles[face]
                bary = barycentric_transform(hit, *(points[i] for i in tri),
                                             Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
                blended = {}
                for index, amount in zip(tri, bary):
                    for key, value in weights[index].items():
                        blended[key] = blended.get(key, 0) + max(0, amount) * value
                blended = dict(sorted(blended.items(), key=lambda p: p[1], reverse=True)[:4])
                total = sum(blended.values())
                skin.append({key: value / total for key, value in blended.items() if value > 0})
        for a in range(segments):
            for j in range(across):
                p = base + a * (across + 1) + j
                faces.append((p, p + across + 1, p + across + 2, p + 1))
    mesh = bpy.data.meshes.new('Bandage_' + name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    wrap = bpy.data.objects.new('Bandage_' + name, mesh)
    bpy.context.collection.objects.link(wrap)
    for key in sorted({key for row in skin for key in row}):
        group = wrap.vertex_groups.new(name=key)
        for i, row in enumerate(skin):
            if row.get(key, 0) > 0:
                group.add([i], row[key], 'REPLACE')
    modifier = wrap.modifiers.new('Follow existing approved skeleton', 'ARMATURE')
    modifier.object = arm
    wrap.parent = arm
    wrap.matrix_world = Matrix.Identity(4)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    mat = bpy.data.materials.new('Muslin_Undyed_Reconstruction')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (.72, .69, .61, 1)
    bsdf.inputs['Roughness'].default_value = .88
    mesh.materials.append(mat)
    project = output / ('Bandage_' + name + '.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(project))
    report = dict(status='authored_unreviewed', slug=args.slug, name=name,
                  source=str(source.relative_to(ROOT)), source_sha256=before,
                  approved_appearance_sha256=record['sha256'], research_sha256=sha(brief),
                  project_sha256=sha(project), arm=args.side, strip_width_cm=width * 100,
                  cross_section_recentered=args.recenter,
                  complete_surface=args.complete_surface,
                  forearm_fraction=args.center, turns=args.turns,
                  inside_out=args.inside_out,
                  clearance_m=args.clearance,
                  angular_segments=segments, across_segments=across,
                  turn_spacing_m=args.pitch,
                  radius_cm=[min(radii)*100, max(radii)*100], vertices=len(vertices),
                  triangles=len(faces)*2, bones=len(arm.data.bones),
                  maximum_influences=max(map(len, skin)),
                  placement='Short circular status dressing over the unchanged forearm surface; not a complete clinical dressing')
    exports = output / 'exports'
    exports.mkdir(exist_ok=True)
    # Export only the accessory and existing skeleton. Never export/change Body.
    unit = Matrix.Scale(100, 4)
    for item in (wrap, arm):
        item.data.transform(unit)
        item.location *= 100
    bpy.context.scene.unit_settings.scale_length = .01
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    wrap.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    fbx = exports / ('SK_Bandage_' + name + '.fbx')
    bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True,
        object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False, bake_anim=False,
        use_armature_deform_only=True, use_mesh_modifiers=False, mesh_smooth_type='FACE',
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Y', axis_up='Z')
    report['fbx_sha256'] = sha(fbx)
    assert sha(source) == before
    if args.render:
        bpy.ops.wm.open_mainfile(filepath=str(project), use_scripts=False)
        scene = bpy.context.scene
        scene.render.engine = 'CYCLES'
        scene.cycles.samples = 32
        scene.render.resolution_x = 900
        scene.render.resolution_y = 900
        scene.render.resolution_percentage = 100
        scene.view_settings.view_transform = 'Standard'
        scene.world.color = (.3, .3, .3)
        # Existing source staging may hide the bandage; use a fresh close camera.
        for o in list(scene.objects):
            if o.type in ('LIGHT', 'CAMERA'):
                bpy.data.objects.remove(o, do_unlink=True)
        for position, energy, size in [((2, -3, 4), 240, 3), ((-2, 0, 3), 140, 2)]:
            data = bpy.data.lights.new('ReviewLight', 'AREA')
            data.energy, data.shape, data.size = energy, 'DISK', size
            lamp = bpy.data.objects.new('ReviewLight', data)
            scene.collection.objects.link(lamp)
            lamp.location = position
            lamp.rotation_euler = (center - lamp.location).to_track_quat('-Z', 'Y').to_euler()
        data = bpy.data.cameras.new('ReviewCamera')
        camera = bpy.data.objects.new('ReviewCamera', data)
        scene.collection.objects.link(camera)
        scene.camera = camera
        data.type = 'ORTHO'
        for label, target, scale, offset in [('full', Vector((0, 0, .9)), 2.05, Vector((2, -4, 1))),
                                             ('close', center, .34, Vector((1, -3, .8)))]:
            camera.location = target + offset
            camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
            data.ortho_scale = scale
            scene.render.filepath = str(output / (label + '.png'))
            bpy.ops.render.render(write_still=True)
    (output / 'authoring.json').write_text(json.dumps(report, indent=2) + '\n')
    print('BANDAGE_AUTHORED', json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
