"""Apply exported native animation transforms to a preserved Blender rest rig.

The export must use compressed animation and the runtime root-lock setting.
This is a source deformation study; native rendering remains a separate check.
"""
import itertools

from mathutils import Matrix, Quaternion, Vector


def transform(record):
    x, y, z, w = record['rotation_xyzw']
    return Matrix.LocRotScale(Vector(record['translation']),
                             Quaternion((w, x, y, z)), Vector(record['scale']))


def native_reference(export):
    result = {}

    def visit(name):
        if name not in result:
            local = transform(export['ref_local'][name])
            parent = export['parents'][name]
            result[name] = visit(parent) @ local if parent in export['ref_local'] else local
        return result[name]

    for name in export['ref_local']:
        visit(name)
    return result


def coordinate_map(arm, reference):
    """Find and verify the signed axis/unit conversion from the actual rig."""
    pairs = [(arm.matrix_world @ b.head_local, reference[b.name.split(':')[-1]].translation)
             for b in arm.data.bones]
    candidates = []
    for axes in itertools.permutations(range(3)):
        for signs in itertools.product((-1, 1), repeat=3):
            matrix = Matrix.Identity(4)
            for row in range(3):
                for col in range(3):
                    matrix[row][col] = 100 * signs[row] if axes[row] == col else 0
            error = max((matrix @ source - native).length for source, native in pairs)
            candidates.append((error, matrix))
    error, matrix = min(candidates, key=lambda candidate: candidate[0])
    assert error < .001, ('Source/native rest-bone positions differ', error)
    return matrix, error


def apply_pose(arm, export, pose_name):
    import bpy
    reference = native_reference(export)
    convert, error = coordinate_map(arm, reference)
    inverse = convert.inverted()
    pose = next(p for p in export['poses'] if p['name'] == pose_name)
    arm.animation_data_clear()
    # Parents precede their children in the source armature.
    for bone in arm.pose.bones:
        name = bone.name.split(':')[-1]
        deformation = inverse @ transform(pose['world_bones_cm'][name]) @ reference[name].inverted() @ convert
        bone.matrix = arm.matrix_world.inverted() @ deformation @ arm.matrix_world @ bone.bone.matrix_local
        bpy.context.view_layer.update()
    return {'source_to_native': [list(row) for row in convert],
            'maximum_reference_bone_error_cm': error,
            'animation': pose['animation'], 'time_seconds': pose['time']}
