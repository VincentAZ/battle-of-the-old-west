"""Derive hair surface candidates without changing the accepted source models.

Blender --background --python this_file -- --source-root <folder>
    --output <new folder> --cards muse
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Matrix


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trim_fringe(hair):
    """Clip the small central forehead fringe to a continuous curved hairline.

    Keep the long side/back curtains and the existing strand UVs. New edge
    vertices interpolate the original UVs; every hair vertex retains Head skin.
    """
    mesh = hair.data
    assert mesh.shape_keys is None and len(mesh.uv_layers) == 1
    group_ids = {g.group for v in mesh.vertices for g in v.groups}
    assert len(group_ids) == 1
    assert all(len(v.groups) == 1 and abs(v.groups[0].weight - 1) < 1e-6 for v in mesh.vertices)
    group = next(iter(group_ids))
    group_name = hair.vertex_groups[group].name
    mesh.calc_loop_triangles()
    old_triangles = len(mesh.loop_triangles)

    def distance(point):
        x, y, z = point
        # Source coordinates are meters. The parabola removes the rectangular
        # central patch, descending into the existing side part within 3 cm.
        line = 1.705 - .020 * (x / .027) ** 2
        return max(z - line, 2 * (y + .035))

    def intersection(a, b):
        lo, hi = 0., 1.
        sign = distance(a[0]) >= 0
        for _ in range(22):
            middle = (lo + hi) * .5
            if (distance(a[0].lerp(b[0], middle)) >= 0) == sign:
                lo = middle
            else:
                hi = middle
        t = (lo + hi) * .5
        return a[0].lerp(b[0], t), a[1].lerp(b[1], t)

    vertices, faces, uv_values = [], [], []
    cut_faces = removed_faces = 0
    for polygon in mesh.polygons:
        points = [(mesh.vertices[mesh.loops[i].vertex_index].co.copy(),
                   mesh.uv_layers.active.data[i].uv.copy()) for i in polygon.loop_indices]
        kept = []
        for a, b in zip(points[-1:] + points[:-1], points):
            inside_a, inside_b = distance(a[0]) >= 0, distance(b[0]) >= 0
            if inside_a != inside_b:
                kept.append(intersection(a, b))
            if inside_b:
                kept.append(b)
        if len(kept) < 3:
            removed_faces += 1
            continue
        if len(kept) != len(points) or any(distance(p[0]) < 0 for p in points):
            cut_faces += 1
        start = len(vertices)
        vertices.extend(p[0] for p in kept)
        uv_values.extend(p[1] for p in kept)
        faces.append(tuple(range(start, start + len(kept))))
    assert cut_faces > 0 and removed_faces > 0
    replacement = bpy.data.meshes.new(mesh.name + '_CurvedFringe')
    replacement.from_pydata(vertices, [], faces)
    uv = replacement.uv_layers.new(name=mesh.uv_layers.active.name)
    for loop in replacement.loops:
        uv.data[loop.index].uv = uv_values[loop.vertex_index]
    for material in mesh.materials:
        replacement.materials.append(material)
    hair.data = replacement
    hair.vertex_groups.clear()
    hair.vertex_groups.new(name=group_name).add(list(range(len(vertices))), 1., 'REPLACE')
    replacement.update()
    replacement.calc_loop_triangles()
    return dict(cut_faces=cut_faces, removed_faces=removed_faces, before_triangles=old_triangles,
                after_triangles=len(replacement.loop_triangles), center_height_m=1.705,
                curve_drop_m=.020, curve_width_m=.027, rear_exclusion_y_m=-.035,
                original_uvs_interpolated=True, head_weights_preserved=True)


def refresh_hair_surface(hair):
    mesh = hair.data
    assert mesh.shape_keys is None, 'Hair expression geometry needs separate handling'
    assert all(len(v.groups) == 1 and abs(v.groups[0].weight - 1) < 1e-6 for v in mesh.vertices)
    groups = {v.groups[0].group for v in mesh.vertices}
    assert len(groups) == 1
    mesh.calc_loop_triangles()
    before = dict(vertices=len(mesh.vertices), triangles=len(mesh.loop_triangles),
                  custom_normals=mesh.has_custom_normals)
    uv_sets = defaultdict(set)
    for loop in mesh.loops:
        uv_sets[loop.vertex_index].add(tuple(round(c, 7) for c in mesh.uv_layers.active.data[loop.index].uv))
    matching = defaultdict(list)
    for vertex in mesh.vertices:
        matching[(tuple(round(c, 7) for c in vertex.co), tuple(sorted(uv_sets[vertex.index])))].append(vertex.index)
    # Do not join coincident roots belonging to different texture strips. Their
    # UV seams must retain independently oriented normals.
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    targetmap = {bm.verts[index]: bm.verts[indices[0]]
                 for indices in matching.values() for index in indices[1:]}
    merged = len(targetmap)
    bmesh.ops.weld_verts(bm, targetmap=targetmap)
    bm.to_mesh(mesh)
    bm.free()
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    hair.select_set(True)
    bpy.context.view_layer.objects.active = hair
    if mesh.has_custom_normals:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    mesh.update()
    mesh.calc_loop_triangles()
    assert len(mesh.loop_triangles) == before['triangles'], 'Seam weld changed the rendered triangle inventory'
    assert len(mesh.vertices) == before['vertices'] - merged
    assert not mesh.has_custom_normals
    assert all(len(v.groups) == 1 and v.groups[0].group in groups
               and abs(v.groups[0].weight - 1) < 1e-6 for v in mesh.vertices)
    return dict(before=before, after=dict(vertices=len(mesh.vertices), triangles=len(mesh.loop_triangles),
                                         custom_normals=mesh.has_custom_normals),
                merged_vertices=merged, position_rounding_m=1e-7,
                uv_seams_preserved=True, skin_weights_preserved=True,
                status='candidate; source and native rendered comparison required')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cards', nargs='+', choices=['bartender', 'quanah_parker', 'charles_goodnight'], required=True)
    parser.add_argument('--trim-fringe', action='store_true', help='Curve the central forehead edge before refreshing normals')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    args.output.mkdir(parents=True, exist_ok=False)
    reports = []
    for card in args.cards:
        folder = args.source_root.resolve() / card
        spec = json.loads((folder / 'manifest.json').read_text())
        source = folder / (spec['name'] + '.blend')
        source_hash = sha(source)
        bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
        for image in bpy.data.images:
            if image.filepath:
                image.filepath = bpy.path.abspath(image.filepath)
        arm = bpy.data.objects['Survivor_Rig']
        reference = [(b.name, b.parent.name if b.parent else None, tuple(tuple(row) for row in b.matrix_local))
                     for b in arm.data.bones]
        hair = next(obj for obj in bpy.data.objects if obj.type == 'MESH' and 'HairCards' in obj.name)
        fringe = trim_fringe(hair) if args.trim_fringe else None
        details = refresh_hair_surface(hair)
        if fringe:
            details['fringe'] = fringe
            spec['total_triangles'] += fringe['after_triangles'] - fringe['before_triangles']
        assert reference == [(b.name, b.parent.name if b.parent else None, tuple(tuple(row) for row in b.matrix_local))
                             for b in arm.data.bones]
        out = args.output / card
        out.mkdir()
        blend = out / (spec['name'] + '.blend')
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj.find_armature() == arm]
        assert hair in meshes
        scale = Matrix.Scale(100, 4)
        for obj in [arm] + meshes:
            if obj.type == 'MESH':
                obj.data.transform(scale, shape_keys=True)
            else:
                obj.data.transform(scale)
            obj.location *= 100
            inverse = obj.matrix_parent_inverse.copy()
            inverse.translation *= 100
            obj.matrix_parent_inverse = inverse
        bpy.context.scene.unit_settings.scale_length = .01
        bpy.context.view_layer.update()
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        for obj in [arm] + meshes:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = arm
        fbx = out / (spec['name'] + '_Cm.fbx')
        bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True,
            object_types={'ARMATURE', 'MESH'}, add_leaf_bones=False, bake_anim=False,
            use_armature_deform_only=True, use_mesh_modifiers=False, mesh_smooth_type='FACE',
            apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
            axis_forward='-Y', axis_up='Z', path_mode='RELATIVE')
        spec.update(hair_surface=details, hair_surface_source_blend=str(source),
                    hair_surface_source_sha256=source_hash, fbx_sha256=sha(fbx),
                    status='hair surface candidate; source and native review required')
        assert sha(source) == source_hash
        (out / 'manifest.json').write_text(json.dumps(spec, indent=2) + '\n')
        reports.append(dict(card_id=card, source_sha256=source_hash, blend_sha256=sha(blend),
                            fbx_sha256=sha(fbx), hair_surface=details))
    (args.output / 'authoring-report.json').write_text(json.dumps(reports, indent=2) + '\n')


if __name__ == '__main__':
    main()
