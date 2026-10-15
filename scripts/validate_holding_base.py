"""Read back a saved static holding base and verify geometry and camera framing.

Mixar --background --python scripts/validate_holding_base.py -- REVIEW BASE EVIDENCE
This is structural validation, not historical or visual approval.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def geometry(obj):
    return ([tuple(v.co) for v in obj.data.vertices],
            [tuple(p.vertices) for p in obj.data.polygons],
            [tuple(x.uv) for x in obj.data.uv_layers.active.data])


def main():
    review, base, evidence = map(Path, sys.argv[sys.argv.index('--')+1:])
    manifest = json.loads((review/'manifest.json').read_text())
    record = json.loads((base/'base.json').read_text())
    source = review/manifest['project']
    assert sha(source) == manifest['project_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(source.resolve()), use_scripts=False)
    original = geometry(bpy.data.objects[manifest['mesh_object']])
    project = base/(record['slug']+'-Base.blend')
    bpy.ops.wm.open_mainfile(filepath=str(project.resolve()), use_scripts=False)
    holding = bpy.data.objects[manifest['mesh_object']]
    assert geometry(holding) == original, 'Base authoring changed source geometry or UVs'
    assert not bpy.data.actions and not any(o.type == 'ARMATURE' for o in bpy.data.objects)
    objects = [bpy.data.objects[n] for n in record['objects']]
    triangles = 0
    for obj in objects:
        assert obj.type == 'MESH' and obj.data.color_attributes
        assert all(math.isfinite(c) for v in obj.data.vertices for c in v.co)
        obj.data.calc_loop_triangles()
        triangles += len(obj.data.loop_triangles)
    assert triangles == record['base_triangles']
    points = [o.matrix_world @ v.co for o in objects+[holding] for v in o.data.vertices]
    views = {}
    for name in ('three-quarter', 'game-camera', 'overhead'):
        camera = bpy.data.objects['Review_'+name]
        projected = [world_to_camera_view(bpy.context.scene, camera, p) for p in points]
        assert all(0 <= p.x <= 1 and 0 <= p.y <= 1 and p.z > 0 for p in projected), name
        views[name] = {'image_sha256': sha(base/(name+'.png')), 'all_geometry_in_frame': True}
    report = dict(status='passed', scope='Saved geometry and framing, not native or historical approval',
                  project_sha256=sha(project), source_review_project_sha256=sha(source),
                  evidence_sha256=sha(evidence), holding_geometry_and_uvs_unchanged=True,
                  base_triangles=triangles, no_rigs_or_animation=True, views=views)
    (base/'validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print('HOLDING_BASE_VALIDATED', json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
