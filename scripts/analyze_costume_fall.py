#!/usr/bin/env python3
"""Read retained costume evidence; never loads or changes the physics asset."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHYSICS = ROOT / 'art/characters/oldwest_survivor/physics'
SPEC = importlib.util.spec_from_file_location('retained_contacts', PHYSICS / 'forearm-chest-contact-audit/reconstruct_contacts.py')
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


def read(path):
    return json.loads(path.read_text())


def signature(path):
    return {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def inverse(q):
    return [-x for x in q[:3]] + [q[3]]


def angle(q, r):
    cosine = abs(C.dot(q, r)) / math.sqrt(C.dot(q, q) * C.dot(r, r))
    return math.degrees(2 * math.acos(min(1., cosine)))


def wrapped(v):
    return (v + 180) % 360 - 180


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--sequence', type=int, default=103)
    parser.add_argument('--target', type=int, default=82)
    args = parser.parse_args()
    folder = args.run.resolve()
    rig_path = PHYSICS / 'fresh-validation.json'
    C.RIG = read(rig_path)  # Explicitly replace the helper's historical rig.
    reference_path = ROOT / 'art/characters/survivor_variants/deformation-v3/native-reference-audit.json'
    reference = read(reference_path)
    reference_bones = {b['name']: b for b in reference['variants'][0]['bones']}
    assert reference_bones['LeftHand']['parent'] == 'LeftForeArm'
    parent_local_anchor = reference_bones['LeftHand']['translation']
    asset = ROOT / 'game/OldWest/Content/Art/Survivors/SurvivorA/PA_Survivor_Anatomical.uasset'
    assert signature(asset)['sha256'] == C.RIG['asset_sha256']
    build = read(folder / 'build.json')
    assert signature(reference_path)['sha256'] == build['costume_reference_audit']['sha256']
    disabled = {frozenset(pair) for pair in C.RIG['disabled_collision_pair_names']}
    wrist = next(j for j in C.RIG['constraints'] if j['child'] == 'LeftHand')
    all_completions = read(folder / 'completed-falls.json')
    completion = next(c for c in all_completions if c['sequence'] == args.sequence)
    final_physics = next(t['physics'] for t in completion['targets'] if t['target'] == args.target)
    inputs = [folder / 'build.json', folder / 'completed-falls.json', rig_path, reference_path,
              Path(__file__).resolve(), Path(C.__file__), asset]
    records = []

    def add(cinematic, origin):
        if cinematic.get('sequence') != args.sequence:
            return
        physics = cinematic.get('physics')
        if not physics or len(physics.get('bodies', [])) != 16:
            return
        records.append({'origin': origin, 'elapsed': cinematic['elapsed'],
                        'frame_timing': cinematic.get('frame_timing'),
                        'settle_hold': cinematic.get('settle_hold'), 'physics': physics})

    for path in sorted(folder.glob(f'*-{args.sequence}-*.state.json')):
        inputs.append(path)
        value = read(path)
        for endpoint in ('before_request', 'after_completion'):
            add(value[endpoint]['cinematic'], f'{path.name}:{endpoint}')
    for name in ('late-fall-samples.jsonl', 'costume-full-fall-samples.jsonl'):
        path = folder / name
        if path.exists():
            inputs.append(path)
            for line in path.read_text().splitlines():
                add(json.loads(line), name)
    add(dict(sequence=args.sequence, elapsed=completion['elapsed'], physics=final_physics,
             frame_timing=completion['frame_timing']), 'completed-falls.json:final')
    records.sort(key=lambda r: r['elapsed'])
    samples, seen = [], set()
    for row in records:
        physics = row['physics']
        pose = physics['pose_motion']
        key = pose['query_frame']
        if key in seen:
            continue
        seen.add(key)
        bodies = {b['bone']: b for b in physics['bodies']}
        hand_shape = C.shape('LeftHand', bodies)
        hand, forearm = bodies['LeftHand'], bodies['LeftForeArm']
        shape_positions = {}
        for name in ('LeftHand', 'LeftForeArm'):
            body = bodies[name]
            authored = next(b for b in C.RIG['bodies'] if b['bone'] == name)
            primitive = (authored['boxes'] or authored['capsules'])[0]
            shape_positions[name] = C.sub(body['position_cm'], C.rotate(body['rotation_xyzw'], primitive['center_local_cm']))
        frames = {role: C.multiply(bodies[wrist[role]]['rotation_xyzw'], C.quaternion(wrist[role+'_frame_rotation_degrees']))
                  for role in ('child', 'parent')}
        relative = C.multiply(inverse(frames['parent']), frames['child'])
        raw = [wrapped(math.degrees(2 * math.atan2(relative[i], relative[3]))) for i in (2, 1, 0)]
        live_wrist = next(j for j in physics['joints'] if j['joint'] == 'LeftHand')
        error = max(abs(wrapped(a - live_wrist[k])) for a, k in zip(raw, ('swing1_degrees', 'swing2_degrees', 'twist_degrees')))
        assert error < .01, ('joint frame reconstruction differs from native', error)
        anchors = {'child_cm': shape_positions['LeftHand'],
                   'parent_cm': C.add(shape_positions['LeftForeArm'], C.rotate(forearm['rotation_xyzw'], parent_local_anchor))}
        anchors['separation_cm'] = math.dist(anchors['child_cm'], anchors['parent_cm'])
        assert abs(anchors['separation_cm'] - live_wrist['anchor_separation_cm']) < .001
        neighbors = []
        for name in bodies:
            if name == 'LeftHand':
                continue
            other = C.shape(name, bodies)
            if other['kind'] == 'box':
                gap = C.box_box(hand_shape, other)
                method = 'maximum_SAT_axis_gap_not_Euclidean_distance'
            else:
                gap = C.capsule_box(other, hand_shape)['surface_clearance_cm']
                method = 'capsule_segment_to_box_distance_minus_radius'
            neighbors.append({'bone': name, 'collision_enabled': frozenset(('LeftHand', name)) not in disabled,
                              'gap_cm': gap, 'method': method, 'world_shape': other})
        independent = []
        if pose['valid']:
            assert pose['sample_frame'] == pose['previous_frame'] + 1
            for b in pose['bodies']:
                speed = math.dist(b['current_com_cm'], b['previous_com_cm']) / pose['delta_seconds']
                angular = angle(b['current_rotation_xyzw'], b['previous_rotation_xyzw']) / pose['delta_seconds']
                assert math.isclose(speed, b['speed_cm_s'], abs_tol=.001)
                assert math.isclose(angular, b['angular_speed_deg_s'], abs_tol=.01)
                independent.append({'bone': b['bone'], 'actual_com_speed_cm_s': speed, 'actual_inertia_quaternion_speed_deg_s': angular})
        extent = [sum(abs(axis[i]) * half for axis, half in zip(hand_shape['axes'], hand_shape['half'])) for i in range(3)]
        bottom = hand['position_cm'][2] - extent[2]
        ground = physics.get('ground_hit_cm')
        samples.append({**row, 'pose_sample_current_query_frame': pose['sample_frame'] == pose['query_frame'],
                        'left_hand_world_shape': hand_shape, 'neighbor_geometry': neighbors,
                        'wrist_world_frames_xyzw': frames, 'wrist_world_anchors': anchors,
                        'body_bone_origins_cm': shape_positions,
                        'raw_wrist_angles_reconstructed_degrees': raw, 'raw_wrist_max_error_degrees': error,
                        'left_hand_shape_bottom_z_cm': bottom,
                        'reported_bounds_extent_minus_reconstructed_cm': C.sub(hand['extent_cm'], extent),
                        'pelvis_ray_ground_height_proximity_only': {
                            'vertical_bottom_minus_ray_hit_cm': bottom - ground[2],
                            'lateral_hand_com_to_ray_cm': math.dist(hand['position_cm'][:2], ground[:2])} if ground else None,
                        'independent_adjacent_frame_motion': independent})
    scene_path = folder / 'scene-samples.jsonl'
    inputs.append(scene_path)
    timeline = [json.loads(line) for line in scene_path.read_text().splitlines()]
    timeline = [{k: row.get(k) for k in ('elapsed', 'frame_timing', 'settle_hold', 'camera_location', 'camera_focus')} |
                {'unit': next((u for u in row['units'] if u['id'] == args.target), None)}
                for row in timeline if row['sequence'] == args.sequence]
    gaps = [(b['elapsed'] - a['elapsed'], a['elapsed'], b['elapsed']) for a, b in zip(samples, samples[1:])]
    report = {
        'status': 'real_settling_failure_contact_hypothesis_requires_native_validation',
        'run': str(folder.relative_to(ROOT)), 'sequence': args.sequence, 'target': args.target,
        'inputs': [signature(p) for p in inputs], 'recorded_native_build': build,
        'provenance_limits': 'PA hash matches the retained fresh asset audit and current unchanged file. The build09 run did not separately hash its loaded PA; no new native read was performed.',
        'method': 'All retained full collider samples plus native completion; exact postphysics adjacent-frame inertia quaternion/COM motion independently recomputed. Analytic geometry is not a native contact manifold.',
        'assumptions': ['Unit collider scale one, one centrally symmetric primitive per body, COM at primitive center.',
                        'Wrist child anchor is the Hand bone origin; parent anchor is its unchanged native reference translation in ForeArm space. Reconstructed separation is checked against every native sample.',
                        'Body-frame quaternion and mass/inertia-frame quaternion are different coordinate frames and are retained separately.'],
        'limitations': ['No manifold, friction impulse, contact margin or terrain normal at the actual hand is retained.',
                        'The ground ray is under the pelvis; its height only indicates proximity at the hand, not proven hand-ground contact.',
                        'Current joint uses the nonlinear solver. Raw angle projections are reproduced only; old linear-pyramid limit analysis is not applicable.',
                        'The full 16-body sequence has gaps; 12Hz scene samples do not supply missing body rotations. No continuous frame trajectory is claimed.',
                        'No settled-corpse screenshot was requested by the original observer. Early fall images cannot certify the final contact.'],
        'native_completion': completion,
        'thresholds_unchanged': {'linear_cm_s': 20, 'angular_deg_s': 45, 'stable_seconds': .25, 'maximum_shot_seconds': 6},
        'full_physics_sample_count': len(samples), 'coarse_scene_sample_count': len(timeline),
        'largest_full_sample_gap': {'seconds': max(gaps)[0], 'from_seconds': max(gaps)[1], 'to_seconds': max(gaps)[2]},
        'full_physics_samples': samples, 'coarse_full_shot_timeline': timeline,
        'interpretation': [
            'At completion LeftHand exceeds the unchanged 45deg/s test in both reported velocity (64.99) and actual adjacent-frame inertia rotation (122.61). This is actual movement, not a scalar-only false alarm.',
            'The hand is adjacent to the Hips collider with enabled pair collision and close to the terrain height sampled under the pelvis. A physical hand/hips/ground pinch is plausible, not established causation.',
            'LeftHand/LeftForeArm overlap is expected at the joint and their pair collision is disabled; the wrist anchors remain joined.',
            'Costume geometry adds no collision and the rifle is hidden/noncolliding during ragdoll. Sleeve/weapon appearance cannot itself create this physical contact.']}
    destination = folder / 'assassin-fall-audit.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'report': str(destination), 'samples': len(samples), 'coarse': len(timeline),
                      'maximum_gap': report['largest_full_sample_gap'], 'timing': completion['frame_timing']}))


if __name__ == '__main__':
    main()
