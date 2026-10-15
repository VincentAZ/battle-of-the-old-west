"""Rebuild the reviewed, authored Punk guard on its preserved reference rig.

The recipe is source geometry, not a dependency on a local Blender file or QA
run directory. Refit it when the underlying garment changes. The normal atlas
bake assigns fresh UVs and materials when used by the character generator.
"""
import hashlib
import json
from pathlib import Path

from author_vigilante_headgear_candidate import Geometry


def chest_guard(arm, cloth, rubber, steel):
    path = Path(__file__).resolve().parent / 'data/punk_chest_guard.json'
    payload = path.read_bytes()
    recipe = json.loads(payload)
    assert recipe['version'] == 1
    assert {b.name for b in arm.data.bones} == {b['name'] for b in recipe['reference_rig']}
    for expected in recipe['reference_rig']:
        bone = arm.data.bones[expected['name']]
        assert (bone.parent.name if bone.parent else None) == expected['parent']
        assert max(abs(bone.matrix_local[i][j] - expected['matrix'][i][j])
                   for i in range(4) for j in range(4)) < 1e-5, bone.name
    materials = {'cloth': cloth, 'rubber': rubber, 'steel': steel}
    parts = []
    for spec in recipe['parts']:
        geometry = Geometry()
        for point in spec['vertices']:
            geometry.vertex(point)
        for face in spec['faces']:
            geometry.face(face)
        obj = geometry.object(spec['name'], materials[spec['material']], arm)
        obj.vertex_groups.clear()
        for index, binding_index in enumerate(spec['vertex_bindings']):
            binding = spec['bindings'][binding_index]
            assert abs(sum(weight for _, weight in binding) - 1.) < 1e-6
            for name, weight in binding:
                group = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
                group.add([index], weight, 'REPLACE')
        parts.append(obj)
    return parts, {
        'method': 'Reviewed shaped guard, continuous edge binding and four seated mounts',
        'recipe': 'scripts/data/punk_chest_guard.json',
        'recipe_sha256': hashlib.sha256(payload).hexdigest(),
        'source_blend_sha256': recipe['source_blend_sha256'],
        'parts': [part.name for part in parts],
        'reference_rig_verified': True,
    }
