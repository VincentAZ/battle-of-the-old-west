"""Bake declared prop/grip constraints into existing Crew animation tracks."""
import math
import unreal


def frozen_bones(validation, available):
    result = set(validation.get('freeze_bones', []))
    for constraint in validation.get('motion_constraints', []):
        if isinstance(constraint, str):
            continue  # Legacy explanatory note, never treated as enforcement evidence.
        assert constraint['type'] == 'preserve_bind_local_transform', 'Unsupported motion constraint'
        result.update(constraint['bones'])
    assert result <= set(available), 'Constraint references unknown bones: '+str(result-set(available))
    return sorted(result)


def apply(animation, skeleton, bones):
    if not bones:
        return
    reference = unreal.AnimPoseExtensions.get_reference_pose(skeleton)
    assert unreal.AnimPoseExtensions.is_valid(reference)
    controller = animation.get_editor_property('controller')
    model = animation.get_editor_property('data_model_interface')
    count = model.get_number_of_keys()
    assert count > 0
    controller.open_bracket('Preserve approved Crew bind transforms', False)
    try:
        for bone in bones:
            transform = unreal.AnimPoseExtensions.get_bone_pose(reference, bone, unreal.AnimPoseSpaces.LOCAL)
            if not model.is_valid_bone_track_name(bone):
                assert controller.add_bone_curve(bone, False), bone
            assert controller.set_bone_track_keys(bone, [transform.translation]*count,
                [transform.rotation]*count, [transform.scale3d]*count, False), bone
    finally:
        controller.close_bracket(False)


def audit(animation, skeleton, bones):
    reference = unreal.AnimPoseExtensions.get_reference_pose(skeleton)
    maxima = {'translation_cm': 0., 'quaternion_error': 0., 'scale': 0.}
    for fraction in (0, .25, .5, .75, .99):
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(animation, animation.get_play_length()*fraction, unreal.AnimPoseEvaluationOptions())
        for bone in bones:
            expected = unreal.AnimPoseExtensions.get_bone_pose(reference, bone, unreal.AnimPoseSpaces.LOCAL)
            actual = unreal.AnimPoseExtensions.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.LOCAL)
            xyz = lambda v: (v.x, v.y, v.z)
            quat = lambda q: (q.x, q.y, q.z, q.w)
            maxima['translation_cm'] = max(maxima['translation_cm'], math.dist(xyz(expected.translation), xyz(actual.translation)))
            maxima['scale'] = max(maxima['scale'], math.dist(xyz(expected.scale3d), xyz(actual.scale3d)))
            # Quaternions q and -q describe the same rotation.
            delta = min(math.dist(quat(expected.rotation), quat(actual.rotation)),
                        math.dist(quat(expected.rotation), tuple(-v for v in quat(actual.rotation))))
            maxima['quaternion_error'] = max(maxima['quaternion_error'], delta)
    assert all(math.isfinite(v) for v in maxima.values())
    assert maxima['translation_cm'] < .01 and maxima['quaternion_error'] < .001 and maxima['scale'] < .001, maxima
    return {'bones': bones, 'type': 'preserve_bind_local_transform', 'maximum_errors': maxima, 'sample_count': 5}
