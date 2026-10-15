#!/usr/bin/env python3
"""Measure leg collider overlap in retained native fall samples.

Uses recorded body transforms and a matching physics-asset description. This is
analytic geometry, not a native contact manifold or a visual acceptance test.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'art/characters/oldwest_survivor/physics/forearm-chest-contact-audit/reconstruct_contacts.py'
spec = importlib.util.spec_from_file_location('collider_geometry', HELPER)
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)


def signature(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('observations', type=Path)
    parser.add_argument('--rig', type=Path, required=True)
    parser.add_argument('--asset', type=Path, required=True)
    parser.add_argument('--sequence', type=int, required=True)
    parser.add_argument('--target', type=int, required=True)
    parser.add_argument('--match-id')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    geometry.RIG = json.loads(args.rig.read_text())
    assert signature(args.asset)['sha256'] == geometry.RIG['asset_sha256'], 'Rig description does not match the supplied asset'
    disabled = {frozenset(pair) for pair in geometry.RIG['disabled_collision_pair_names']}
    pairs = [('LeftUpLeg', 'RightUpLeg'), ('LeftUpLeg', 'RightLeg'),
             ('RightUpLeg', 'LeftLeg'), ('LeftLeg', 'RightLeg')]
    rows = json.loads(args.observations.read_text())
    samples = []
    for row in rows:
        c = row['cinematic']
        if c.get('sequence') != args.sequence or (args.match_id and row['match_id'] != args.match_id):
            continue
        for member in [c, *c.get('simultaneous_targets', [])]:
            if member.get('target') != args.target or not member.get('ragdoll'):
                continue
            physics = member['physics']
            bodies = {body['bone']: body for body in physics['bodies']}
            assert len(bodies) == 16
            clearances = []
            for a, b in pairs:
                shapes = [geometry.shape(name, bodies) for name in (a, b)]
                assert all(shape['kind'] == 'capsule' for shape in shapes)
                clearances.append({'pair': [a, b], 'collision_enabled': frozenset((a, b)) not in disabled,
                                   'surface_gap_cm': geometry.capsule_capsule(*shapes)})
            samples.append({'match_id': row['match_id'], 'elapsed_seconds': c['elapsed'],
                            'max_linear_cm_s': physics['max_speed_cm_s'],
                            'max_angular_deg_s': physics['max_angular_speed_deg_s'],
                            'pose_max_angular_deg_s': physics['pose_motion']['max_angular_speed_deg_s'],
                            'clearances': clearances})
    assert samples, 'No matching native ragdoll samples'
    report = {'inputs': [signature(p) for p in (args.observations, args.rig, args.asset, HELPER, Path(__file__))],
              'sequence': args.sequence, 'target': args.target, 'sample_count': len(samples),
              'deepest_thigh_overlap_cm': max(0., -min(s['clearances'][0]['surface_gap_cm'] for s in samples)),
              'samples': samples,
              'limitations': ['Capsule geometry uses unit scale and symmetric mass centers from the retained native poses.',
                              'A negative surface gap indicates geometric interpenetration; it does not measure solver contact impulses.',
                              'A matching supplied asset hash does not independently establish that a historical run loaded it.',
                              'No ground contact manifold or unsampled intervening pose is reconstructed.']}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('sequence', 'target', 'sample_count', 'deepest_thigh_overlap_cm')}))


if __name__ == '__main__':
    main()
