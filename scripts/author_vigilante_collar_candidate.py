"""Match the shirt neckline's deformation to the adjacent preserved neck.

Derives a separate source candidate; never edits the prior source or native mesh.
Run in Blender background mode with -- --output <new directory>.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from author_vigilante_neck_candidate import coordinates, weights
from character_native_pose import apply_pose


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def surface(obj):
    obj.data.calc_loop_triangles()
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    triangles = [tuple(t.vertices) for t in obj.data.loop_triangles]
    return BVHTree.FromPolygons(points, triangles, all_triangles=True), points, triangles


def interpolated_weights(obj, points, triangles, tree, point):
    hit, _, index, _ = tree.find_nearest(point)
    ids = triangles[index]
    a, b, c = (points[i] for i in ids)
    u, v, q = b - a, c - a, hit - a
    uu, uv, vv = u.dot(u), u.dot(v), v.dot(v)
    determinant = uu * vv - uv * uv
    assert abs(determinant) > 1e-18
    w1 = (vv * q.dot(u) - uv * q.dot(v)) / determinant
    w2 = (uu * q.dot(v) - uv * q.dot(u)) / determinant
    values = {}
    for i, fraction in zip(ids, (1 - w1 - w2, w1, w2)):
        for group in obj.data.vertices[i].groups:
            name = obj.vertex_groups[group.group].name
            values[name] = values.get(name, 0) + max(0, fraction) * group.weight
    total = sum(values.values())
    assert total > .99
    return {name: value / total for name, value in values.items()}


def pose_clearance(arm, face, outfit, collar, native, body=None, body_region=None):
    rows = []
    for pose in native['poses']:
        conversion = apply_pose(arm, native, pose['name'])
        deps = bpy.context.evaluated_depsgraph_get()
        evaluated_face = face.evaluated_get(deps)
        evaluated_outfit = outfit.evaluated_get(deps)
        skin, _, _ = surface(evaluated_face)
        mesh = evaluated_outfit.data
        assert len(mesh.vertices) == len(outfit.data.vertices)
        points = [evaluated_outfit.matrix_world @ v.co for v in mesh.vertices]
        samples = [points[i] for i in sorted(collar)]
        mesh.calc_loop_triangles()
        for triangle in mesh.loop_triangles:
            if all(i in collar for i in triangle.vertices):
                a, b, c = (points[i] for i in triangle.vertices)
                samples += [(a + b + c) / 3, (a + b) / 2, (b + c) / 2, (c + a) / 2]
        distances = []
        for point in samples:
            hit, normal, _, _ = skin.find_nearest(point)
            distances.append((point - hit).dot(normal) * 100)
        row = {'pose': pose['name'], 'sample_count': len(samples),
                     'signed_face_clearance_cm': [min(distances), max(distances)],
                     'samples_inside_face': sum(d < 0 for d in distances),
                     'conversion': conversion}
        if body is not None:
            body_skin, _, _ = surface(body.evaluated_get(deps))
            body_samples = [points[i] for i in sorted(body_region)]
            for triangle in mesh.loop_triangles:
                if all(i in body_region for i in triangle.vertices):
                    a, b, c = (points[i] for i in triangle.vertices)
                    body_samples += [(a + b + c) / 3, (a + b) / 2, (b + c) / 2, (c + a) / 2]
            body_distances = []
            for point in body_samples:
                hit, normal, _, _ = body_skin.find_nearest(point)
                body_distances.append((point - hit).dot(normal) * 100)
            row.update(body_sample_count=len(body_samples),
                       signed_body_clearance_cm=[min(body_distances), max(body_distances)],
                       samples_inside_body=sum(d < 0 for d in body_distances))
        rows.append(row)
    for bone in arm.pose.bones:
        bone.matrix_basis.identity()
    bpy.context.view_layer.update()
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--weight-surface', choices=['face', 'body'], default='body')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    destination = args.output.resolve()
    folder = destination / 'vigilante'
    folder.mkdir(parents=True, exist_ok=False)
    source_root = ROOT / 'art/characters/identity-neck-vigilante-v1'
    source = source_root / 'vigilante/Vigilante.blend'
    assert sha(source) == 'e6c604ee7aa61fb82116b009c082f05ba43e3341665b7925b1edb55505aee4bb'
    audit_root = ROOT / 'game/tests/runs/polish-vigilante-collar-audit-20260909'
    inspection = json.loads((audit_root / 'source-neck-boundaries.json').read_text())
    assert inspection['source_sha256'] == sha(source)
    native = json.loads((audit_root / 'native-runtime-poses.json').read_text())
    originals = {str(p): sha(p) for p in (source_root / 'vigilante').rglob('*') if p.is_file()}
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    for image in bpy.data.images:
        if image.filepath:
            image.filepath = bpy.path.abspath(image.filepath)
    arm = bpy.data.objects['Survivor_Rig']
    outfit = bpy.data.objects['Vigilante_Outfit_Assembly']
    face = bpy.data.objects['Survivor_Face_27Shapes']
    body = bpy.data.objects['Survivor_Body']
    protected = {o.name: (coordinates(o), weights(o)) for o in bpy.data.objects
                 if o.type == 'MESH' and o != outfit}
    geometry_before = coordinates(outfit)
    normals_before = [tuple(n.vector) for n in outfit.data.corner_normals]
    weights_before = weights(outfit)
    components = next(o for o in inspection['objects'] if o['name'] == outfit.name)['neck_components']
    bands = [c for c in components if c['count'] == 85]
    panels = [c for c in components if c['count'] == 3201]
    assert len(bands) == len(panels) == 4
    collar = {i for c in bands for i in c['indices']}
    garment = {i for c in bands + panels for i in c['indices']}
    outfit_points = [outfit.matrix_world @ v.co for v in outfit.data.vertices]
    band_faces = [list(p.vertices) for p in outfit.data.polygons if all(i in collar for i in p.vertices)]
    band_surface = BVHTree.FromPolygons(outfit_points, band_faces)
    region = {i for i in garment if band_surface.find_nearest(outfit_points[i])[3] < .055}
    before = pose_clearance(arm, face, outfit, collar, native, body, region)
    print('BEFORE_CLEARANCE', json.dumps(before), flush=True)
    weight_source = face if args.weight_surface == 'face' else body
    skin, skin_points, skin_triangles = surface(weight_source)
    changed = []
    for i in sorted(garment):
        point = outfit_points[i]
        _, _, _, distance = band_surface.find_nearest(point)
        if distance >= .055:
            continue
        t = max(0, min(1, (distance - .004) / .051))
        blend = 1 - t * t * (3 - 2 * t)
        target = interpolated_weights(weight_source, skin_points, skin_triangles, skin, point)
        current = dict(weights_before[i])
        values = {name: current.get(name, 0) * (1 - blend) + target.get(name, 0) * blend
                  for name in current.keys() | target.keys()}
        for name, value in values.items():
            group = outfit.vertex_groups.get(name) or outfit.vertex_groups.new(name=name)
            if value > 1e-7:
                group.add([i], value, 'REPLACE')
            else:
                group.remove([i])
        assert abs(sum(g.weight for g in outfit.data.vertices[i].groups) - 1) < .001
        updated = [(outfit.vertex_groups[g.group].name, g.weight)
                   for g in outfit.data.vertices[i].groups]
        if updated != weights_before[i]:
            changed.append(i)
    assert changed and set(changed) <= garment
    after = pose_clearance(arm, face, outfit, collar, native, body, region)
    print('AFTER_CLEARANCE', json.dumps(after), flush=True)
    assert coordinates(outfit) == geometry_before
    assert [tuple(n.vector) for n in outfit.data.corner_normals] == normals_before
    assert protected == {name: (coordinates(bpy.data.objects[name]), weights(bpy.data.objects[name]))
                         for name in protected}
    actual_weights = weights(outfit)
    assert all(actual_weights[i] == weights_before[i] for i in range(len(actual_weights)) if i not in garment)
    blend = folder / 'Vigilante.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    spec = json.loads((source.parent / 'manifest.json').read_text())
    detail = {'method': f'Interpolate preserved {args.weight_surface} weights onto the collar, blending to existing garment weights over 5.5 cm.',
              'collar_vertices': len(collar), 'changed_vertices': len(changed),
              'all_geometry_uvs_normals_preserved': True, 'all_other_meshes_preserved': True,
              'patch_and_other_equipment_weights_preserved': True,
              'before_native_pose_clearance': before, 'after_native_pose_clearance': after,
              'clearance_limitations': 'Signed nearest-surface samples include open boundaries; they supplement source/native visual review.'}
    spec.update(collar_correction=detail, status='collar skin-weight candidate; source and native visual review required')
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == arm]
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
    bpy.ops.object.select_all(action='DESELECT')
    for obj in [arm] + meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = arm
    fbx = folder / 'Vigilante_Cm.fbx'
    bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'ARMATURE', 'MESH'},
        add_leaf_bones=False, bake_anim=False, use_armature_deform_only=True, use_mesh_modifiers=False,
        mesh_smooth_type='FACE', apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
        axis_forward='-Y', axis_up='Z', path_mode='RELATIVE')
    assert all(sha(Path(p)) == h for p, h in originals.items())
    spec['fbx_sha256'] = sha(fbx)
    (folder / 'manifest.json').write_text(json.dumps(spec, indent=2) + '\n')
    report = {'source_sha256': sha(source), 'blend_sha256': sha(blend), 'fbx_sha256': sha(fbx),
              'source_files_unchanged': True, 'native_imported': False,
              'changed_vertex_indices': changed, 'collar_correction': detail}
    (destination / 'authoring-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('COLLAR_CANDIDATE_SAVED', len(changed), flush=True)


if __name__ == '__main__':
    main()
