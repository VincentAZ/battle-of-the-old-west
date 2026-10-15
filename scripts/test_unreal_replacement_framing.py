#!/usr/bin/env python3
"""Replay the retained legal replacement and inspect its actual presentation.

The original journal is read-only. Every camp and gameplay command must still
be offered by the acting player's live view. Queue-log additions may renumber
shots; target identities and accepted revisions provide the causal match.
No state injection, animation hold, physics override or camera override.
"""
import argparse
import copy
import hashlib
import itertools
import json
import math
import time
from pathlib import Path

from native_launch import create_native_run_directory
from test_unreal_action_showcase import ActionShowcase, capture_subject, painted_beat, phase_of, signature
from test_unreal_hud import resolution
from test_unreal_interactions import EDITOR, ROOT, write_json

REFERENCE = ROOT / 'game/tests/runs/oldwest-action-showcase-nkak5udy/1280x720'
OUTGOING, REPLACEMENT = 87, 93


def project_bounds(cinematic, unit):
    """Independent zero-roll pinhole projection of all rendered AABB corners."""
    origin, forward = cinematic['camera_location'], cinematic['lens']['camera_forward']
    frame = cinematic['subject_frame']
    right = [-forward[1], forward[0], 0.]
    length = math.sqrt(sum(v*v for v in right))
    assert length > .001, 'This audit expects the normal nonvertical, zero-roll action camera'
    right = [v / length for v in right]
    up = [forward[1]*right[2] - forward[2]*right[1],
          forward[2]*right[0] - forward[0]*right[2],
          forward[0]*right[1] - forward[1]*right[0]]
    focal = cinematic['lens']['focal_length_mm']
    points = []
    for point in itertools.product(*zip(*unit['bounds'])):
        relative = [a-b for a, b in zip(point, origin)]
        depth = sum(a*b for a, b in zip(relative, forward))
        assert depth > 1., 'A subject bounding-box corner is behind the camera'
        points.append([.5 + sum(a*b for a, b in zip(relative, right)) * focal / (depth * frame['sensor_width_mm']),
                       .5 - sum(a*b for a, b in zip(relative, up)) * focal / (depth * frame['sensor_height_mm'])])
    low = [min(point[axis] for point in points) for axis in range(2)]
    high = [max(point[axis] for point in points) for axis in range(2)]
    assert frame['target'] == unit['id'] and frame['all_corners_in_front']
    assert all(math.isclose(a, b, abs_tol=1e-5) for a, b in zip(low + high, frame['normalized_min'] + frame['normalized_max'])), \
        'Independent target-bounds projection disagrees with native telemetry'
    return {'min': low, 'max': high}


class ReplacementFraming(ActionShowcase):
    def __init__(self, args, output, dimensions, index):
        super().__init__(args, output, dimensions, index)
        self.reference = args.reference
        self.replay = json.loads((self.reference / 'legal-action-journal.json').read_text())[:args.max_actions]
        self.camp_plan = json.loads((self.reference / 'legal-camp-selection-journal.json').read_text())
        self.samples, self.sample_keys, self.developed_captures = [], set(), []
        self.developed_attempted = set()
        self.build['replacement_harness'] = signature(__file__)
        self.build['replay_inputs'] = [signature(self.reference / name) for name in
                                      ('legal-action-journal.json', 'legal-camp-selection-journal.json', 'build.json')]
        write_json(self.folder / 'build.json', self.build)

    def boot(self):
        super().boot()
        baseline = [copy.deepcopy(self.snapshot(name)) for name in ('a', 'b')]
        camera = self.camera_identity(self.camera_state())
        self.event('move', (10, 100))
        time.sleep(.25)
        header = next(panel['header'] for panel in self.hud()['dock_panels'] if panel['id'] in ('master','crew'))
        point = (header['min'][0] + (header['max'][0] - header['min'][0]) * .25,
                 (header['min'][1] + header['max'][1]) * .5)
        self.event('move', point)
        time.sleep(1.3)
        self.capture('title-tooltip-hover')
        self.event('move', (10, 100))
        assert [self.snapshot(name) for name in ('a', 'b')] == baseline
        assert self.camera_identity(self.camera_state()) == camera
        write_json(self.folder / 'title-tooltip-hover.json', {
            'image': self.captures['title-tooltip-hover'], 'ordinary_away_and_back_pointer': True,
            'pointer': point, 'unchanged_authoritative_views': True, 'unchanged_camera': True,
            'manual_popup_visibility_review': 'pending; a hover command alone is not proof of a visible tooltip'})

    def submit(self, name, action):
        if action['command']['type'] == 'select_camps':
            current = self.snapshot(name)
            planned = next(row for row in self.camp_plan if row['seat'] == current['seat'])
            offered = [row for row in current['actions'] if row['command'] == planned['command']]
            assert len(offered) == 1, 'Original camp selection is no longer a legal offer'
            assert hashlib.sha256(json.dumps(current['actions'], sort_keys=True).encode()).hexdigest() == planned['legal_actions_sha256']
            action = offered[0]
        super().submit(name, action)

    def choose_action(self, name, snapshot):
        planned = self.replay[len(self.actions)]
        assert snapshot['seat'] == planned['seat'] and snapshot['view']['revision'] == planned['revision'], \
            'Acting player or authoritative revision diverged from the retained journal'
        assert snapshot['view']['turn'] == planned['turn']
        offered = [row for row in snapshot['actions'] if row['command'] == planned['command']]
        assert len(offered) == 1, f'Original command is not currently legal: {planned["command"]}'
        assert hashlib.sha256(json.dumps(snapshot['actions'], sort_keys=True).encode()).hexdigest() == planned['legal_actions_sha256'], \
            'The complete legal-action offer differs from the original policy run'
        return offered[0]

    def observe(self, state):
        super().observe(state)
        cine = state.get('cinematic', {})
        if not cine.get('busy') or (cine.get('kind'), cine.get('target')) not in (('destroy', OUTGOING), ('enter', REPLACEMENT)):
            return
        key = (state['snapshot']['match_id'], cine['sequence'], cine.get('frame_timing', {}).get('frames'))
        if key in self.sample_keys:
            return
        self.sample_keys.add(key)
        units = {unit['id']: unit for unit in cine.get('units', [])}
        target = units[cine['target']]
        record = {'match_id': key[0], 'sequence': cine['sequence'], 'kind': cine['kind'],
                  'elapsed': cine.get('elapsed'), 'frame_timing': cine.get('frame_timing'),
                  'camera_location': cine.get('camera_location'), 'camera_focus': cine.get('camera_focus'),
                  'camera_obstructed': cine.get('camera_obstructed'), 'lens': cine.get('lens'),
                  'subject_frame': cine.get('subject_frame'), 'target': copy.deepcopy(target),
                  'replacement': copy.deepcopy(units.get(REPLACEMENT)),
                  'outgoing_present': OUTGOING in units, 'paint': painted_beat(state)}
        try:
            assert 'hidden' in target and 'deferred_enter_sequence' in target
            assert not target['hidden'], 'The current action subject is hidden'
            record['independent_projected_bounds'] = project_bounds(cine, target)
            rect = record['independent_projected_bounds']
            # Empty AABB corners can project over the caption while the entire
            # actual person remains clear. Keep this conservative margin as a
            # diagnostic; projection math and manual silhouette review remain
            # separate requirements. The original failed results are retained.
            record['conservative_AABB_margin_clear'] = (rect['min'][0] >= .02 and rect['max'][0] <= .98 and
                                                        rect['min'][1] >= .02 and rect['max'][1] <= .88)
            if cine['kind'] == 'destroy':
                replacement = units.get(REPLACEMENT)
                assert replacement and replacement['hidden'], 'Replacement appears before outgoing fall finishes'
                assert replacement['deferred_enter_sequence'] > cine['sequence'], 'Replacement lacks its later entrance sequence'
            else:
                assert target['deferred_enter_sequence'] is None, 'Entrance did not release its deferred visibility'
                assert not record['outgoing_present'], 'Outgoing actor still overlaps the replacement entrance'
                assert target.get('card_id') in ('', 'punk') and target.get('unarmed'), 'Punk leaked a private face or acquired a rifle'
                if target.get('travelling'):
                    assert target['active_clip'] == 'MF_Unarmed_Walk_Fwd', 'Punk did not use its baked unarmed walk'
                    assert math.isclose(target['travel_stride_speed_cm_s'], 311.45707194, abs_tol=.01)
                    assert target.get('root_drift_cm', 0) < 3
        except (AssertionError, KeyError, TypeError, ValueError) as error:
            self.issue(f'Replacement framing: {error}', sequence=cine['sequence'], evidence=record)
        self.samples.append(record)
        with (self.folder / 'replacement-scene-samples.jsonl').open('a') as stream:
            stream.write(json.dumps(record) + '\n')

    def capture_phase(self, state):
        cine = state['cinematic']
        targeted = (cine.get('kind'), cine.get('target')) in (('destroy', OUTGOING), ('enter', REPLACEMENT))
        # The base showcase deduplicates generic people. These two identities
        # must each have actual images, including the newly unarmed Punk.
        prior_subjects = set(self.valid_subject_captures)
        if targeted:
            phase = phase_of(cine)
            self.valid_subject_captures.discard((cine['kind'], *capture_subject(cine), phase))
        try:
            super().capture_phase(state)
        finally:
            # A repeated poll can return immediately after an earlier attempt.
            # Forcing this subject must not erase already accumulated evidence.
            self.valid_subject_captures.update(prior_subjects)
        state = self.read(); self.observe(state)
        cine, paint = state.get('cinematic', {}), painted_beat(state)
        sequence = cine.get('sequence')
        if not (cine.get('busy') and cine.get('kind') == 'destroy' and cine.get('target') == OUTGOING and
                cine.get('elapsed', 0) >= 1.55 and sequence not in self.developed_attempted and
                paint and paint.get('busy') and paint.get('sequence') == sequence):
            return
        self.developed_attempted.add(sequence)
        before = copy.deepcopy(state)
        label = f'replacement-fall-{sequence}-developed'
        self.capture(label)
        after = self.read(); self.observe(after)
        current, after_paint = after.get('cinematic', {}), painted_beat(after)
        valid = bool(current.get('busy') and current.get('sequence') == sequence and after_paint and
                     after_paint.get('busy') and after_paint.get('sequence') == sequence and
                     after_paint.get('match_id') == paint.get('match_id'))
        record = {'sequence': sequence, 'image': self.captures[label], 'same_active_fall_bracket': valid,
                  'before_seconds': cine['elapsed'], 'after_seconds': current.get('elapsed'),
                  'semantics': 'Ordinary ongoing fall; no animation hold and no claim of a settled corpse.'}
        self.developed_captures.append(record)
        write_json(self.folder / f'{label}.state.json', {'capture': record, 'before_request': before, 'after_completion': after})

    def run(self):
        result = None
        try:
            result = super().run()
        finally:
            retained = result or json.loads((self.folder / 'result.json').read_text())
            falls = [row for row in self.completions if row.get('independent_reconstruction') and
                     any(target.get('target') == OUTGOING and target.get('ragdoll') for target in row.get('targets', []))]
            walking = [row for row in self.samples if row['kind'] == 'enter' and row['target'].get('travelling')]
            movement = max((math.dist(a['target']['location'], b['target']['location'])
                            for a, b in zip(walking, walking[1:])), default=0.)
            pose_change = max((math.dist(a, b) for previous, current in zip(walking, walking[1:])
                               for a, b in zip(previous['target'].get('pose_samples', []), current['target'].get('pose_samples', []))), default=0.)
            targets = {row['sequence']: row['target']['id'] for row in self.samples}
            captures = [row for row in self.capture_records if targets.get(row['sequence']) in (OUTGOING, REPLACEMENT) and
                        row['actual_phase_bracket_valid'] and row['requested_phase'] in ('impact', 'after-impact')]
            final = self.read().get('cinematic', {})
            final_units = {unit['id']: unit for unit in final.get('units', [])}
            checks = {'exact_retained_legal_prefix': len(self.actions) == len(self.replay) and all(
                          all(a[field] == b[field] for field in ('command', 'seat', 'revision', 'accepted_revision', 'turn', 'legal_actions_sha256'))
                          for a, b in zip(self.actions, self.replay)),
                      'deferred_replacement_observed_during_fall': any(row['kind'] == 'destroy' for row in self.samples),
                      'outgoing_strict_natural_completion': bool(falls),
                      'replacement_unarmed_walk_changes_position_and_pose': len(walking) >= 2 and movement > 1 and pose_change > .5,
                      'both_subjects_have_actual_action_capture': {targets[row['sequence']] for row in captures} == {OUTGOING, REPLACEMENT},
                      'developed_fall_actual_capture': any(row['same_active_fall_bracket'] for row in self.developed_captures),
                      'tactical_state_restores_only_visible_replacement': not final.get('busy') and OUTGOING not in final_units and
                          REPLACEMENT in final_units and not final_units[REPLACEMENT].get('hidden', True) and
                          final_units[REPLACEMENT].get('deferred_enter_sequence') is None}
            retained.update(replay_reference=str(self.reference), replacement_checks=checks,
                            replacement_sample_count=len(self.samples), developed_fall_captures=self.developed_captures,
                            replacement_max_adjacent_translation_cm=movement, replacement_max_adjacent_pose_change_cm=pose_change,
                            conservative_AABB_margin_diagnostics=[{
                                'sequence': row['sequence'], 'kind': row['kind'], 'elapsed': row['elapsed'],
                                'independent_projected_bounds': row.get('independent_projected_bounds')}
                                for row in self.samples if row.get('conservative_AABB_margin_clear') is False],
                            manual_visual_review='required_pending', manual_silhouette_review_required=True,
                            automated_silhouette_coverage=False,
                            ok=retained.get('ok', False) and all(checks.values()))
            retained['limitations'].append('The framing projection measures a rendered AABB, not actual visible pixels; review both subjects and their occluders in the screenshots.')
            write_json(self.folder / 'result.json', retained)
            result = retained
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--reference', type=Path, default=REFERENCE)
    parser.add_argument('--resolutions', nargs='+', type=resolution, default=[(1280, 720)])
    parser.add_argument('--port', type=int, default=19637)
    parser.add_argument('--timeout', type=float, default=420)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    original = json.loads((args.reference / 'result.json').read_text())
    args.seed, args.ruleset = original['seed'], original['ruleset']
    args.max_actions, args.settle = 21, 0.
    args.prefer_camp, args.require_kind, args.extra_render_commands = [], [], []
    args.profile_renderer = False
    args.manifest = args.reference / 'legal-action-journal.json'
    args.scenario_config = {'name': 'retained-replacement-prefix', 'policy': 'exact_legal_replay',
                            'target_kinds': ['destroy', 'enter'], 'preferred_camps': []}
    output = args.output.resolve() if args.output else create_native_run_directory('oldwest-replacement-framing-')
    output.mkdir(parents=True, exist_ok=True)
    report = {'ok': False, 'results': [], 'logs': str(output)}
    print(f'Replacement framing evidence: {output}', flush=True)
    try:
        for index, dimensions in enumerate(args.resolutions):
            report['results'].append(ReplacementFraming(args, output, dimensions, index).run())
        report['ok'] = all(row['ok'] for row in report['results'])
    except Exception as error:
        report['failure'] = str(error)
        raise
    finally:
        write_json(output / 'result.json', report)
        write_json(ROOT / 'game/tests/reports/latest-native-replacement-framing.json', report)
        print(json.dumps({'ok': report['ok'], 'logs': str(output), 'failure': report.get('failure')}, indent=2), flush=True)
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
