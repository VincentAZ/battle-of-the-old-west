#!/usr/bin/env python3
"""Observe the detailed fuel cart during the existing ordinary queue replay."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from native_launch import create_native_run_directory
from test_unreal_event_queue import DEFAULT_PLAN, QueueScenario, signature
from test_unreal_interactions import EDITOR, ROOT, resolution, write_json


def quat_multiply(a, b):
    x, y, z, w = a; X, Y, Z, W = b
    return [w*X + x*W + y*Z - z*Y, w*Y - x*Z + y*W + z*X,
            w*Z + x*Y - y*X + z*W, w*W - x*X - y*Y - z*Z]


def audit_cart_samples(records, plan, captures):
    """Check each public Prairie Fire beat and the same cart across beat rebuilds."""
    identities = {card['id'] for hand in plan['own_opening_hands'] for card in hand['own_hand']
                  if card.get('card_id') == 'prairie_fire'}
    expected = {event['sequence']: event for step in plan['journal'] for event in step['public_events']
                if event['source'] in identities and event['type'] in ('event_play', 'event_advance')}
    assert expected, 'Plan has no public Prairie Fire movement'
    proof_path = ROOT / 'art/action_props/supply_kit/unreal-import.json'
    proof = json.loads(proof_path.read_text())
    mesh = next(m for m in proof['meshes'] if m['path'].endswith('.SM_Action_CartWheel'))
    asset = next(a for a in proof['asset_files'] if a['path'].endswith('/SM_Action_CartWheel.uasset'))
    assert signature(ROOT / asset['path'])['sha256'] == asset['sha256'], 'Wheel mesh changed since measured import'
    radii = [(mesh['bounds_max_cm'][i] - mesh['bounds_min_cm'][i]) / 2 for i in (0, 1)]
    assert math.isclose(*radii, abs_tol=1e-5) and radii[0] > 0
    radius = radii[0]
    previous, seen = {}, set()
    moving_pairs = {sequence: 0 for sequence in expected}
    boundaries, travel_errors, rotation_errors = [], [], []
    for record in records:
        event = expected[record['sequence']]
        unit = record['unit']
        assert record['kind'] == event['type'] and unit['id'] == event['source']
        assert unit['side'] == event['player'] and unit['card_id'] == 'prairie_fire'
        seen.add(record['sequence'])
        equipment = unit['event_equipment']
        names = [part['mesh'].split('.')[-1] for part in equipment]
        assert len(equipment) == 7 and names.count('SM_Action_CartChassis1') == 1
        assert names.count('SM_Action_CartWheel') == 4 and names.count('SM_Action_StorageBarrel') == 2
        assert all(part['visible'] and part['collision_enabled'] == 0 for part in equipment)
        assert math.isclose(unit['event_wheel_radius_cm'], radius, abs_tol=1e-5)
        wheels = [part for part in equipment if part['wheel']]
        assert len(wheels) == 4
        for wheel in wheels:
            assert wheel['mesh'] == mesh['path']
            assert all(math.isclose(s, 1, abs_tol=1e-6) for s in wheel['scale']), 'Wheel is scaled away from measured radius'
            assert math.isclose(math.dist(wheel['quaternion_xyzw'], [0]*4), 1, abs_tol=1e-5)
        identity = (record['match_id'], unit['id'])
        before_record = previous.get(identity)
        if before_record:
            before = before_record['unit']
            movement = unit['location'][1] - before['location'][1]
            travel = unit['event_wheel_travel_cm'] - before['event_wheel_travel_cm']
            travel_errors.append(abs(travel - movement))
            assert math.isclose(travel, movement, abs_tol=.002), 'Wheel travel discontinuity'
            angle = -movement / radius
            rotation = [math.sin(angle / 2), 0, 0, math.cos(angle / 2)]
            for old, new in zip((p for p in before['event_equipment'] if p['wheel']), wheels):
                prediction = quat_multiply(rotation, old['quaternion_xyzw'])
                dot = abs(sum(a*b for a, b in zip(prediction, new['quaternion_xyzw'])))
                rotation_errors.append(abs(dot - 1))
                assert math.isclose(dot, 1, abs_tol=1e-5), 'Wheel rotation discontinuity'
            if before_record['sequence'] != record['sequence']:
                boundaries.append(dict(from_sequence=before_record['sequence'], to_sequence=record['sequence'],
                                       movement_cm=movement, travel_cm=travel))
            elif abs(movement) > .1:
                moving_pairs[record['sequence']] += 1
        previous[identity] = record
    captured = {c['sequence'] for c in captures if c['actual_phase_bracket_valid'] and
                c['requested_phase'] in ('impact', 'after-impact') and c['sequence'] in expected and
                c['kind'] == expected[c['sequence']]['type']}
    assert seen == set(expected) and seen <= captured, 'Missing expected Prairie Fire beat or painted capture'
    assert all(count >= 2 for count in moving_pairs.values()), 'Missing movement pairs for a Prairie Fire beat'
    assert {(b['from_sequence'], b['to_sequence']) for b in boundaries} == set(zip(sorted(expected), sorted(expected)[1:])), 'Missing cross-beat observations'
    return dict(coverage_complete=True, sequences=sorted(seen), samples=len(records),
                moving_pairs_by_sequence=moving_pairs, boundaries=boundaries,
                max_travel_error_cm=max(travel_errors), max_quaternion_abs_dot_error=max(rotation_errors),
                measured_wheel_radius_cm=radius, wheel_import_provenance=signature(proof_path), wheel_asset=asset,
                limits='Retained sampled motion; terrain contact and material quality require actual image review.')


class NapalmCartScenario(QueueScenario):
    def __init__(self, *args):
        super().__init__(*args)
        self.cart_samples, self.cart_keys = [], set()
        self.build['napalm_cart_harness'] = signature(__file__)
        write_json(self.folder / 'build.json', self.build)

    def observe(self, state):
        super().observe(state)
        scene = state.get('cinematic', {})
        if not scene.get('busy') or scene.get('kind') not in ('event_play', 'event_advance'):
            return
        unit = next((u for u in scene.get('units', []) if u.get('id') == scene.get('target') and u.get('card_id') == 'prairie_fire'), None)
        if not unit:
            return
        identity = (state['snapshot']['match_id'], scene['sequence'])
        key = (*identity, scene['frame_timing']['frames'])
        if key in self.cart_keys:
            return
        self.cart_keys.add(key)
        record = dict(match_id=identity[0], sequence=identity[1], elapsed=scene['elapsed'], kind=scene['kind'], unit=copy.deepcopy(unit))
        self.cart_samples.append(record)
        with (self.folder / 'napalm-cart-samples.jsonl').open('a') as stream:
            stream.write(json.dumps(record) + '\n')

    def run(self):
        result = None
        try:
            result = super().run()
            return result
        finally:
            retained = result or json.loads((self.folder / 'result.json').read_text())
            try:
                audit = audit_cart_samples(self.cart_samples, self.plan, self.capture_records)
            except (AssertionError, KeyError, TypeError, ValueError, StopIteration) as error:
                audit = dict(coverage_complete=False, failure=f'{type(error).__name__}: {error}')
            audit['manual_contact_material_and_first_frame_review'] = 'pending'
            retained.update(napalm_cart=audit, ok=retained['ok'] and audit['coverage_complete'])
            write_json(self.folder / 'result.json', retained)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_PLAN)
    parser.add_argument('--resolutions', nargs='+', type=resolution, default=[(1280, 720)])
    parser.add_argument('--port', type=int, default=19957)
    parser.add_argument('--timeout', type=float, default=500)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    assert plan['ok']
    for path, expected in plan['provenance'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
    args.seed, args.ruleset = plan['seed'], plan['ruleset']
    args.max_actions, args.settle = len(plan['journal']) - 2, 0.
    args.package_dir = None
    args.prefer_camp, args.require_kind, args.extra_render_commands, args.profile_renderer = [], ['event_advance'], [], False
    args.scenario_config = dict(name='napalm-cart-public-queue-replay', policy='public_replay', target_kinds=['event_advance'])
    output = args.output.resolve() if args.output else create_native_run_directory('oldwest-napalm-cart-')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(ok=False, results=[], logs=str(output))
    print(f'Native Prairie Fire cart evidence: {output}', flush=True)
    try:
        for index, dimensions in enumerate(args.resolutions):
            report['results'].append(NapalmCartScenario(copy.copy(args), output, dimensions, index).run())
        report['ok'] = all(result['ok'] for result in report['results'])
    except Exception as error:
        report['failure'] = str(error)
        raise
    finally:
        write_json(output / 'result.json', report)
        print(json.dumps(dict(ok=report['ok'], logs=str(output), failure=report.get('failure')), indent=2), flush=True)
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
