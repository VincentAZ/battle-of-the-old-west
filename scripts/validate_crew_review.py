"""Reopen a Western Crew character appearance candidate in Mixar and audit preservation."""
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
from mathutils import Vector


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    review = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
    manifest = json.loads((review / 'manifest.json').read_text())
    baseline = json.loads((review.parent.parent / 'baseline.json').read_text())
    assert 'mixar' in Path(bpy.app.binary_path).name.lower()
    project = review / manifest['project']
    assert sha(project) == manifest['project_sha256']
    assert sha(Path(manifest['source_glb'])) == manifest['source_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(project), use_scripts=False)
    character = bpy.data.objects[manifest['mesh_object']]
    mesh = character.data
    mesh.calc_loop_triangles()
    assert len(mesh.loop_triangles) == manifest['triangles'] <= 30000
    assert len(mesh.materials) == 1
    assert mesh.uv_layers and all(math.isfinite(v) for uv in mesh.uv_layers.active.data for v in uv.uv)
    assert all(math.isfinite(v) for vertex in mesh.vertices for v in vertex.co)
    assert not any(ob.type == 'ARMATURE' for ob in bpy.data.objects)
    assert not bpy.data.actions
    points = [character.matrix_world @ Vector(corner) for corner in character.bound_box]
    bottom, top = min(p.z for p in points), max(p.z for p in points)
    assert abs(bottom) < .0001 and abs(top - manifest['height_m']) < .0001
    images = {node.image.name: node.image for node in mesh.materials[0].node_tree.nodes
              if node.type == 'TEX_IMAGE' and node.image}
    assert len(images) == len(manifest['textures']) == 3
    for image in images.values():
        assert tuple(image.size) == (2048, 2048) and image.packed_file, image.name
    assert len(manifest['previews']) == 8, 'Full eight-view review required'
    for item in manifest['textures'] + manifest['previews']:
        assert sha(review / item['file']) == item['sha256'], item['file']
    changed = [p for p, digest in baseline['protected_sha256'].items()
               if not (root / p).is_file() or sha(root / p) != digest]
    assert not changed, changed
    assert str((root / 'dist/current').resolve()) == baseline['selected_package']
    report = {
        'status': 'passed', 'scope': 'saved asset structure and file preservation, not historical approval',
        'character': manifest['character'], 'project_sha256': sha(project),
        'triangles': len(mesh.loop_triangles), 'material_count': 1, 'packed_textures_2048': 3,
        'height_m': top - bottom, 'ground_z_m': bottom, 'unrigged': True,
        'unreal_imported': False, 'protected_files_unchanged': len(baseline['protected_sha256']),
        'selected_package_unchanged': baseline['selected_package'],
        'preview_scope': manifest['preview_scope'],
    }
    (review / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print('CREW_REVIEW_VALIDATED', json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
