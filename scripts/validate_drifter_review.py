"""Reopen the Drifter appearance source in Mixar and verify the saved review.

Run with Mixar --background --factory-startup --python-exit-code 1
    --python scripts/validate_drifter_review.py -- REVIEW_DIRECTORY
"""

import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    review = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
    manifest = json.loads((review / 'manifest.json').read_text())
    baseline = json.loads((review.parent / 'baseline.json').read_text())
    assert 'mixar' in Path(bpy.app.binary_path).name.lower()
    project = review / manifest['project']
    assert sha(project) == manifest['project_sha256']
    assert sha(Path(manifest['source_glb'])) == manifest['source_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(project), use_scripts=False)
    character = bpy.data.objects['Drifter_Appearance_Review']
    mesh = character.data
    mesh.calc_loop_triangles()
    assert len(mesh.loop_triangles) == manifest['triangles'] <= 30000
    assert len(mesh.materials) == 1
    assert mesh.uv_layers and all(
        math.isfinite(value) for uv in mesh.uv_layers.active.data for value in uv.uv)
    assert all(math.isfinite(value) for vertex in mesh.vertices for value in vertex.co)
    assert not any(ob.type == 'ARMATURE' for ob in bpy.data.objects)
    assert not bpy.data.actions
    revision_checks = {}
    if manifest.get('source_project'):
        # Compare this saved revision against its retained editable predecessor.
        # Geometry and UVs are exact, not merely equal in triangle count.
        sys.path.insert(0, str(root / 'scripts'))
        from weather_drifter_review import geometry_hash
        import numpy as np
        revised_geometry = geometry_hash(character)
        assert revised_geometry == manifest['geometry_uv_sha256']
        source_project = Path(manifest['source_project'])
        assert sha(source_project) == manifest['source_project_sha256']
        with bpy.data.libraries.load(str(source_project), link=False) as (src, dst):
            dst.objects = ['Drifter_Appearance_Review']
        old_character = dst.objects[0]
        assert geometry_hash(old_character) == revised_geometry
        old_images = {n.image.name.split('.')[0]: n.image
                      for n in old_character.data.materials[0].node_tree.nodes
                      if n.type == 'TEX_IMAGE' and n.image}
        new_images = {n.image.name: n.image for n in mesh.materials[0].node_tree.nodes
                      if n.type == 'TEX_IMAGE' and n.image}
        for channel in ('Normal', 'ORM'):
            old = old_images['T_Drifter_' + channel]
            new = new_images['T_Drifter_' + channel]
            a = np.empty(len(old.pixels), dtype=np.float32)
            b = np.empty(len(new.pixels), dtype=np.float32)
            old.pixels.foreach_get(a)
            new.pixels.foreach_get(b)
            assert np.array_equal(a, b), channel
        revision_checks = {'geometry_and_uvs_match_previous': True,
                           'normal_and_orm_pixels_match_previous': True,
                           'protected_head_bandana_pixels_unchanged_at_authoring':
                               manifest['protected_head_bandana_pixels_unchanged']}
    points = [character.matrix_world @ Vector(corner) for corner in character.bound_box]
    bottom = min(p.z for p in points)
    top = max(p.z for p in points)
    assert abs(bottom) < .0001 and abs(top - 1.85) < .0001
    images = {node.image.name: node.image for node in mesh.materials[0].node_tree.nodes
              if node.type == 'TEX_IMAGE' and node.image}
    assert len(images) == len(manifest['textures']) == 3
    for image in images.values():
        assert tuple(image.size) == (2048, 2048), (image.name, tuple(image.size))
        assert image.packed_file, image.name
    for item in manifest['textures'] + manifest['previews']:
        assert sha(review / item['file']) == item['sha256'], item['file']
    changed = [p for p, digest in baseline['protected_sha256'].items()
               if not (root / p).is_file() or sha(root / p) != digest]
    assert not changed, changed
    assert str((root / 'dist/current').resolve()) == baseline['current_package']
    report = {
        'status': 'passed', 'stage': 'appearance; user approval pending',
        'project_sha256': sha(project), 'triangles': len(mesh.loop_triangles),
        'material_count': 1, 'packed_textures_2048': len(images),
        'height_including_hat_m': top - bottom, 'ground_z_m': bottom,
        'unrigged': True, 'unreal_imported': False,
        'protected_files_unchanged': len(baseline['protected_sha256']),
        'selected_package_unchanged': baseline['current_package'],
        'preview_scope': manifest['preview_scope'],
        **revision_checks,
    }
    (review / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print('DRIFTER_REVIEW_VALIDATED', json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
