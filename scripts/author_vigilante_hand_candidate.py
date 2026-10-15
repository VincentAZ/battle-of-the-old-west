"""Correct the isolated ring-finger weight in a separate Vigilante source.

Blender --background --python this_file -- --output <new source root>.
Changes one vertex's bone weights; preserves all geometry and expressions.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from author_vigilante_neck_candidate import coordinates, weights


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def correct_ring_vertex(body):
    index = 11876
    vertex = body.data.vertices[index]
    before = dict(weights(body)[index])
    assert before == {'mixamorig:RightHandPinky1': 1.0}
    neighbors = sorted({i for e in body.data.edges if index in e.vertices for i in e.vertices if i != index})
    assert neighbors == [11846, 11863, 11864, 11868, 11870, 11871, 11873, 11875]
    all_weights = weights(body)
    blended = {}
    total = 0.
    for i in neighbors:
        influence = 1. / (vertex.co - body.data.vertices[i].co).length
        total += influence
        ring = dict(all_weights[i])
        assert set(ring) == {'mixamorig:RightHandRing2', 'mixamorig:RightHandRing3'}
        for name, weight in ring.items():
            blended[name] = blended.get(name, 0.) + weight * influence
    for group in list(vertex.groups):
        body.vertex_groups[group.group].remove([index])
    for name, weight in blended.items():
        body.vertex_groups[name].add([index], weight / total, 'REPLACE')
    after = dict(weights(body)[index])
    assert abs(sum(after.values()) - 1.) < 1e-6
    return {'vertex': index, 'neighbors': neighbors, 'before': before, 'after': after,
            'method': 'Inverse-edge-length interpolation from all eight connected ring-finger neighbors'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    folder = args.output.resolve() / 'vigilante'
    folder.mkdir(parents=True, exist_ok=False)
    source = ROOT / 'art/characters/identity-jaw-neck-vigilante-v3/vigilante/Vigilante.blend'
    assert sha(source) == 'b97606555a1f57c98b7869d4e89dcd081a191ba62b185da47ae31f3c0f89af20'
    originals = {str(p): sha(p) for p in source.parent.rglob('*') if p.is_file()}
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    for image in bpy.data.images:
        if image.filepath:
            image.filepath = bpy.path.abspath(image.filepath)
    arm = bpy.data.objects['Survivor_Rig']
    body = bpy.data.objects['Survivor_Body']
    rig = [(b.name, b.parent.name if b.parent else None, tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == arm]
    protected = {o.name: (coordinates(o), weights(o), [tuple(n.vector) for n in o.data.corner_normals]) for o in meshes}
    correction = correct_ring_vertex(body)
    for obj in meshes:
        before, old_weights, normals = protected[obj.name]
        assert coordinates(obj) == before, (obj.name, 'geometry, expressions, UVs or materials changed')
        assert normals == [tuple(n.vector) for n in obj.data.corner_normals], obj.name
        changed = [i for i, (a, b) in enumerate(zip(old_weights, weights(obj))) if a != b]
        assert changed == ([11876] if obj == body else []), (obj.name, changed)
    assert rig == [(b.name, b.parent.name if b.parent else None, tuple(tuple(r) for r in b.matrix_local)) for b in arm.data.bones]
    correction.update(changed_vertices=1, geometry_uvs_normals_expressions_preserved=True,
                      other_weights_and_meshes_preserved=True, rig_preserved=True)
    spec = json.loads((source.parent / 'manifest.json').read_text())
    spec.update(hand_correction=correction, status='Hand weight source candidate; source and native review required')
    blend = folder / 'Vigilante.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    scale = Matrix.Scale(100, 4)
    for obj in [arm] + meshes:
        obj.data.transform(scale, shape_keys=True) if obj.type == 'MESH' else obj.data.transform(scale)
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
    assert all(sha(Path(p)) == digest for p, digest in originals.items())
    spec['fbx_sha256'] = sha(fbx)
    (folder / 'manifest.json').write_text(json.dumps(spec, indent=2) + '\n')
    report = {'source_sha256': sha(source), 'blend_sha256': sha(blend), 'fbx_sha256': sha(fbx),
              'correction': correction, 'source_files_unchanged': True, 'native_imported': False}
    (folder.parent / 'authoring-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('HAND_CANDIDATE', json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
