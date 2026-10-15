"""Reopen the saved playable character sources in Mixar and verify preservation."""
import bpy
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from weather_drifter_review import geometry_hash

OUT = ROOT / 'art/western/native/playable-v001'
results = []
for slug, name, directory in [
    ('lozen', 'Lozen', ROOT / 'art/western/native/lozen-cloth-v004'),
    ('sarah-winnemucca', 'Sarah', OUT / 'sarah-winnemucca'),
]:
    report = json.loads((directory / 'rig-validation.json').read_text())
    source = directory / (name + '-Rigged.blend')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == report['project_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    obj = bpy.data.objects[slug.replace('-', '_') + '_Appearance_Review']
    assert geometry_hash(obj) == report['source_geometry_uv_sha256']
    maximum = 0
    for vertex in obj.data.vertices:
        weights = [g.weight for g in vertex.groups if g.weight > 0]
        assert weights and all(math.isfinite(w) and 0 <= w <= 1 for w in weights)
        assert abs(sum(weights) - 1) < .00001
        maximum = max(maximum, len(weights))
    assert maximum <= 4
    textures = [i for i in bpy.data.images if i.type == 'IMAGE']
    assert len(textures) == 3
    assert all(i.packed_file and tuple(i.size) == (2048, 2048) for i in textures)
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    error = max((a.co-b.co).length for a,b in zip(obj.data.vertices, mesh.vertices))
    evaluated.to_mesh_clear()
    assert error < .00001
    for filename, digest in report['files'].items():
        assert hashlib.sha256((directory / 'exports' / filename).read_bytes()).hexdigest() == digest
    results.append(dict(character=slug, project_sha256=report['project_sha256'],
        approved_geometry_uv_sha256=geometry_hash(obj), vertices=len(obj.data.vertices),
        maximum_vertex_influences=maximum, normalized=True, packed_2k_textures=len(textures),
        bind_pose_max_error_m=error))
(OUT/'source-validation.json').write_text(json.dumps({'ok':True,'characters':results},indent=2)+'\n')
print('NATIVE_SAVED_SOURCE_VALIDATION', json.dumps(results), flush=True)
