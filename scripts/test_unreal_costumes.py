#!/usr/bin/env python3
"""Replay a public legal match and retain actual costume/weapon/fall evidence.

No state injection, forced pose, clip hold, physics override or camera teleport.
Close views use ordinary mouse pan/orbit/zoom and must leave both rule views
unchanged. Missing poses/capture phases remain failures, not inferred coverage.
"""
import argparse
import copy
import hashlib
import json
import math
import time
from pathlib import Path

from native_launch import create_native_run_directory, game_net_driver_ports
from test_unreal_action_showcase import ActionShowcase, painted_beat, signature
from test_unreal_hud import resolution
from test_unreal_interactions import EDITOR, ROOT, center, write_json

BASE = ROOT / 'art/characters/survivor_variants/deformation-v3'
DEFAULT_PLAN = BASE / 'legal-gameplay-plan.json'
TARGETS = ('prospector', 'gatling_gunner', 'bounty_hunter')
MESHES = {card: f'/Game/Art/Survivors/Variants/SKM_{card.title()}_Cm.SKM_{card.title()}_Cm' for card in TARGETS}


def pose_class(unit):
    clip = unit.get('active_clip', '')
    if unit.get('ragdoll'):
        return 'fall'
    if unit.get('dead'):
        return 'dead'
    if unit.get('travelling'):
        return 'walk'
    if 'HitReact' in clip:
        return 'hit'
    if 'Fire' in clip or 'Attack' in clip:
        return 'attack'
    if unit.get('playing') and unit.get('looping') and clip == unit.get('idle_clip'):
        return 'idle'
    return 'other'


def pose_delta(first, second):
    a, b = first.get('pose_samples', []), second.get('pose_samples', [])
    if len(a) != 4 or len(b) != 4 or any(len(v) != 3 for v in a + b):
        return 0.
    return max(math.dist(x, y) for x, y in zip(a, b))


def validate_grip(unit):
    """The same calibrated live-palm limit as the existing world input suite."""
    grip = unit['weapon_alignment']
    assert grip['two_hand_pose'] and grip['native_forward_axis'] == '+Y'
    assert 'M_Portrait_Weapon' in grip['material']
    assert len(grip['scale']) == 3 and all(math.isclose(s, 1., abs_tol=.001) for s in grip['scale'])
    for hand in ('right', 'left'):
        measured = math.dist(grip[f'{hand}_palm_world'], grip[f'{hand}_grip_world'])
        reported = grip[f'{hand}_contact_gap_cm']
        assert math.isfinite(measured) and math.isclose(measured, reported, rel_tol=1e-4, abs_tol=.02)
        assert 0 <= grip[f'live_{hand}_palm_gap_cm'] < 1.5, f'{hand} actual animated palm left the rifle'
    return max(grip[f'live_{hand}_palm_gap_cm'] for hand in ('right', 'left'))


def completed_grip_identity(unit, state, logged_events):
    """Validate the completed sample's identity independently of this query's beat."""
    sample = unit['completed_weapon_observation']
    assert isinstance(sample, dict), 'Missing completed actor-tick observation'
    assert sample['semantics'] == 'last_completed_world_post_actor_tick'
    assert sample['match_id'] == state['snapshot']['match_id'], 'Previous-match grip cache'
    assert (sample['id'], sample['card_id'], sample['side']) == (unit['id'], unit['card_id'], unit['side']), \
        'Previous-unit grip cache'
    query, frame = unit['weapon_observation_query_frame'], sample['sample_frame']
    assert type(query) is int and type(frame) is int and 0 <= frame <= query
    assert query - frame == unit['completed_weapon_observation_age_frames'] and query - frame <= 1, \
        'Stale completed grip observation'
    assert isinstance(sample['active_clip'], str) and sample['active_clip']
    assert math.isfinite(sample['animation_position']) and sample['animation_position'] >= 0
    assert all(type(sample[field]) is bool for field in ('playing', 'looping', 'travelling', 'eligible', 'busy'))
    assert all(type(sample[field]) is int and sample[field] >= 0 for field in ('bone_revision', 'bone_frame'))
    if sample['kind']:
        events = [event for event in logged_events if event['match_id'] == sample['match_id']
                  and event['sequence'] == sample['sequence']]
        assert len(events) == 1 and (events[0]['type'] == sample['kind'] or
            (events[0]['type'], sample['kind']) == ('rearrange', 'move')), 'Completed grip beat lacks its own public log'
        assert sample['busy'], 'Completed active beat marked idle'
    else:
        assert sample['sequence'] == -1, 'Inactive completed grip sample borrowed a log sequence'
    if sample['eligible']:
        assert not any(sample[field] for field in ('preview_only', 'hidden', 'camp', 'event_token', 'unarmed', 'dead', 'ragdoll'))
        assert type(sample['alignment_frame']) is int and 0 <= sample['alignment_frame'] <= frame
        assert all(type(sample[field]) is int and sample[field] >= 0
                   for field in ('alignment_bone_revision', 'alignment_bone_frame'))
        assert isinstance(sample['weapon_alignment'], dict)
    else:
        assert sample['weapon_alignment'] is None
    return sample


class CostumeScenario(ActionShowcase):
    def __init__(self, args, output, dimensions, index):
        super().__init__(args, output, dimensions, index)
        self.plan = json.loads(args.manifest.read_text())
        self.costume_samples, self.costume_keys, self.close_views = [], set(), {}
        self.completed_grip_samples, self.completed_grip_keys = [], set()
        self.completed_grip_waiting = {}
        self.full_fall_keys, self.late_costume_capture_keys = set(), set()
        self.late_costume_captures = []
        self.target_entities = {item['entity']: item['card_id'] for item in self.plan['targets']}
        self.replay = self.plan['journal'][2:]
        self.build['costume_harness'] = signature(__file__)
        self.build['costume_plan'] = signature(args.manifest)
        self.build['costume_reference_audit'] = signature(BASE / 'native-reference-audit.json')
        self.build['costume_cpu_study'] = signature(BASE / 'deformation-preflight/manual-review.json')
        self.build['costume_assets'] = [signature(path) for path in sorted(
            (ROOT / 'game/OldWest/Content/Art/Survivors/Variants').rglob('*.uasset'))]
        self.build['costume_asset_provenance_scope'] = (
            'Current editor input assets; for a package these source files are not proof of cooked contents. '
            'The package manifest/executable and observed native mesh paths remain separate.')
        write_json(self.folder / 'build.json', self.build)

    def boot(self):
        # Preserve the public rehearsal's seat order so camp/entity allocation
        # is identical. Both commands are re-selected from live legal offers.
        self.launch('b', f'/Game/Maps/WaterDepotV2?listen?Match=1?game=/Script/OldWestGame.OldWestGameMode?Ruleset={self.args.ruleset}')
        log = self.folder / 'b.log'
        self.wait('listen server', lambda: log.exists() and self.port in game_net_driver_ports(log.read_text(errors='replace')), 120)
        self.launch('a', '/Game/Maps/WaterDepotV2', rendered=True)
        self.wait('rendered menu', lambda: self.snapshot().get('hosted') is False and self.hud(), 120)
        self.command('a', 'join', address=f'127.0.0.1:{self.port}')
        self.wait('both peers in selection', self.agree, 100)
        self.capture('01-public-camp-selection')
        for planned in self.plan['journal'][:2]:
            peer = next(name for name in ('a', 'b') if self.snapshot(name)['seat'] == planned['seat'])
            current = self.snapshot(peer)
            assert current['view']['revision'] == planned['revision']
            options = [a for a in current['actions'] if a['command'] == planned['command']]
            assert len(options) == 1, 'Rehearsed camp selection is not offered in this build'
            self.submit(peer, options[0])
        self.wait('ordinary match begins', lambda: self.snapshot()['view']['status'] == 'actions')
        self.settle_presentation()  # Setup only; no deployment/action is skipped.
        for planned in self.plan['own_opening_hands']:
            peer = next(name for name in ('a', 'b') if self.snapshot(name)['seat'] == planned['seat'])
            expected = [(card['id'], card.get('card_id')) for card in planned['own_hand']]
            observed = [(card['id'], card.get('card_id')) for card in self.own_hand(peer).values()]
            assert observed == expected, 'Authorized opening hand differs from the legal rehearsal'

    def observe_completed_grip(self, unit, state):
        match, entity = state['snapshot']['match_id'], unit['id']
        query = unit.get('weapon_observation_query_frame')
        sample = unit.get('completed_weapon_observation')
        key = (match, entity, query, sample.get('sample_frame') if isinstance(sample, dict) else None)
        if key in self.completed_grip_keys:
            return
        self.completed_grip_keys.add(key)
        record = dict(match_id=match, entity=entity, card_id=unit['card_id'], query_frame=query,
                      query_sequence=state['cinematic'].get('sequence'),
                      query_clip=unit.get('active_clip'), observation=copy.deepcopy(sample),
                      instantaneous_alignment=copy.deepcopy(unit.get('weapon_alignment')),
                      counted_for_completed_coverage=False)
        current_eligible = not any(unit.get(field) for field in
            ('preview_only', 'hidden', 'camp', 'event_token', 'unarmed', 'dead', 'ragdoll'))
        try:
            assert type(query) is int, 'Native completed-grip telemetry unavailable'
            # ResetPose clears the cache; a newly spawned/reset actor has not
            # completed its first tick yet. Permit at most one native frame,
            # retain the pending record and award no coverage for it.
            if sample is None:
                first = self.completed_grip_waiting.setdefault((match, entity), query)
                record['pending_first_completed_tick'] = True
                assert 0 <= query - first <= 1, 'Completed grip cache did not initialize after one frame'
            else:
                sample = completed_grip_identity(unit, state, self.logged_events)
                record.update(sample_frame=sample['sample_frame'], sequence=sample['sequence'], kind=sample['kind'],
                              active_clip=sample['active_clip'], classification=pose_class(sample))
                if current_eligible and not sample['eligible']:
                    first = self.completed_grip_waiting.setdefault((match, entity), query)
                    record['pending_first_eligible_tick'] = True
                    assert 0 <= query - first <= 1, 'Visible armed actor lacks an eligible completed observation'
                else:
                    self.completed_grip_waiting.pop((match, entity), None)
                if sample['eligible'] and 'Rifle' in sample['active_clip']:
                    record['verified_max_completed_palm_gap_cm'] = validate_grip(sample)
                    for hand in ('right', 'left'):
                        grip = sample['weapon_alignment']
                        assert math.isclose(grip[f'{hand}_contact_gap_cm'], grip[f'live_{hand}_palm_gap_cm'],
                                            rel_tol=1e-4, abs_tol=.02), 'Completed report mixes two palm poses'
                    record['counted_for_completed_coverage'] = True
        except (AssertionError, KeyError, TypeError, ValueError) as error:
            record['failure'] = str(error)
            self.issue(f'{unit["card_id"]}: completed-frame grip failed: {error}',
                       sequence=record.get('sequence'), completed_observation=copy.deepcopy(sample),
                       query_frame=query, instantaneous_alignment=record['instantaneous_alignment'])
        # Previous-beat observations keep their own sequence and clip. They
        # never become current-beat motion/capture evidence.
        self.completed_grip_samples.append(record)
        with (self.folder / 'costume-completed-grip-samples.jsonl').open('a') as stream:
            stream.write(json.dumps(record) + '\n')

    def observe(self, state):
        super().observe(state)
        cinematic = state.get('cinematic', {})
        frame = cinematic.get('frame_timing', {}).get('frames')
        physics = cinematic.get('physics') or {}
        pose = physics.get('pose_motion', {})
        fall_key = (state.get('snapshot', {}).get('match_id'), cinematic.get('sequence'), pose.get('query_frame'))
        if (cinematic.get('busy') and cinematic.get('target') in self.target_entities and physics.get('bodies')
                and pose.get('query_frame') is not None and fall_key not in self.full_fall_keys):
            self.full_fall_keys.add(fall_key)
            # Retain every observed full report throughout the fall. Reports
            # are less frequent than native frames: no continuous trace claim.
            retained = {key: cinematic.get(key) for key in ('sequence', 'kind', 'elapsed', 'target',
                        'frame_timing', 'settle_hold', 'physics', 'simultaneous_targets', 'camera_location', 'camera_focus')}
            retained['match_id'] = fall_key[0]
            with (self.folder / 'costume-full-fall-samples.jsonl').open('a') as stream:
                stream.write(json.dumps(retained) + '\n')
        # Tactical reports do not always have frame_timing. Advancing animation
        # time provides a deduplication key; it is never relabeled a frame id.
        for unit in cinematic.get('units', []):
            if unit.get('preview_only') or unit.get('card_id') not in TARGETS:
                continue
            self.observe_completed_grip(unit, state)
            card, entity = unit['card_id'], unit['id']
            key = (entity, frame, unit.get('active_clip'), unit.get('animation_position'),
                   cinematic.get('sequence'), cinematic.get('elapsed'))
            if key in self.costume_keys:
                continue
            self.costume_keys.add(key)
            record = dict(card_id=card, entity=entity, observed_frame=frame, classification=pose_class(unit),
                          sequence=cinematic.get('sequence'), kind=cinematic.get('kind'),
                          source=cinematic.get('source'), target=cinematic.get('target'),
                          elapsed=cinematic.get('elapsed'), unit=copy.deepcopy(unit))
            self.costume_samples.append(record)
            try:
                assert self.target_entities.get(entity) == card, 'Unexpected public costume identity'
                assert unit['visual_mesh'] == MESHES[card], 'Runtime selected the wrong costume mesh'
                assert unit['mesh_lod_count'] >= 1
                assert 0 <= unit['predicted_lod'] < unit['mesh_lod_count'], 'Renderer selected an unavailable LOD'
                if not unit.get('ragdoll'):
                    assert math.isfinite(unit['root_drift_cm']) and unit['root_drift_cm'] < 3
                    assert len(unit['pose_samples']) == 4
                    assert all(math.isfinite(v) for point in unit['pose_samples'] for v in point)
                if record['classification'] == 'idle':
                    assert unit['root_drift_cm'] < 1
                if not unit.get('unarmed') and not unit.get('ragdoll') and 'Rifle' in unit.get('active_clip', ''):
                    # Preserve the old mixed-phase observation as a diagnostic;
                    # strict grip acceptance uses the separately validated
                    # completed snapshot, never these current-query values.
                    try:
                        record['instantaneous_max_live_palm_gap_cm'] = validate_grip(unit)
                    except (AssertionError, KeyError, TypeError, ValueError) as error:
                        record['instantaneous_grip_diagnostic'] = str(error)
            except (AssertionError, KeyError, TypeError, ValueError) as error:
                self.issue(f'{card}: costume/weapon telemetry failed: {error}', sequence=record['sequence'], unit=unit)
            with (self.folder / 'costume-pose-samples.jsonl').open('a') as stream:
                stream.write(json.dumps(record) + '\n')

    def capture_phase(self, state):
        super().capture_phase(state)
        state = self.read()
        cinematic = state.get('cinematic', {})
        sequence, target = cinematic.get('sequence'), cinematic.get('target')
        if not cinematic.get('busy') or target not in self.target_entities or not (cinematic.get('physics') or {}).get('bodies'):
            return
        elapsed = cinematic.get('elapsed', 0)
        phase = 'late-fall' if elapsed >= 5.15 else 'developed-fall' if elapsed >= 2. else None
        key = (sequence, phase)
        paint = painted_beat(state)
        if not phase or key in self.late_costume_capture_keys or not paint or not paint.get('busy') or paint.get('sequence') != sequence:
            return
        self.late_costume_capture_keys.add(key)
        before = copy.deepcopy(state)
        label = f'costume-{self.target_entities[target]}-{sequence}-{phase}'
        self.capture(label)
        after = self.read(); self.observe(after)
        after_cinematic, after_paint = after.get('cinematic', {}), painted_beat(after)
        valid = bool(after_cinematic.get('busy') and after_cinematic.get('sequence') == sequence and
                     after_paint and after_paint.get('busy') and after_paint.get('sequence') == sequence and
                     after_paint.get('match_id') == paint.get('match_id') == state['snapshot']['match_id'])
        record = dict(sequence=sequence, target=target, phase=phase, image=self.captures[label],
                      same_active_fall_bracket=valid, before_seconds=elapsed, after_seconds=after_cinematic.get('elapsed'),
                      semantics='Natural ongoing fall; not a claim of settled corpse or an animation hold.')
        self.late_costume_captures.append(record)
        write_json(self.folder / f'{label}.state.json', dict(capture=record, before_request=before, after_completion=after))
        write_json(self.folder / 'costume-late-fall-captures.json', self.late_costume_captures)

    def panel(self, identity):
        return next(p for p in self.hud().get('dock_panels', []) if p['id'] == identity)

    def move_panel(self, identity, destination):
        panel = self.panel(identity)
        scale = self.hud_dimensions()[0] / 1920.
        start = center(panel['header'])
        delta = [(value - old) * scale for value, old in zip(destination, panel['position'])]
        self.event('down', start)
        self.event('move', (start[0] + delta[0], start[1] + delta[1]))
        self.event('up')
        self.wait('ordinary panel drag completes', lambda: not self.panel(identity)['interacting'])
        assert math.dist(self.panel(identity)['position'], destination) < 2

    def collapse_panel(self, identity, collapsed):
        if self.panel(identity)['collapsed'] == collapsed:
            return
        spot = center(self.panel(identity)['collapse_button'])
        self.event('down', spot); self.event('up', spot)
        self.wait('ordinary panel collapse/expand completes', lambda: self.panel(identity)['collapsed'] == collapsed)

    def clear_hand_for_review(self):
        original = copy.deepcopy(self.panel('hand'))
        camera = self.camera_identity(self.camera_state())
        self.collapse_panel('hand', True)
        panel = self.panel('hand')
        self.move_panel('hand', (panel['position'][0], panel['bounds']['max'][1] - panel['header_height']))
        assert self.panel('hand')['content'] is None
        assert self.camera_identity(self.camera_state()) == camera, 'Hand panel gesture leaked into the camera'
        return original

    def restore_hand_after_review(self, original):
        camera = self.camera_identity(self.camera_state())
        self.move_panel('hand', original['position'])
        self.collapse_panel('hand', original['collapsed'])
        restored = self.panel('hand')
        assert restored['expanded_size'] == original['expanded_size']
        assert math.dist(restored['position'], original['position']) < 2
        assert self.camera_identity(self.camera_state()) == camera, 'Hand panel restoration moved the camera'

    def gesture_origin(self):
        width, height = self.hud_dimensions()
        boxes = [item['panel'] for item in self.hud().get('dock_panels', []) if item.get('visible') and item.get('panel')]
        for x, y in ((.58, .28), (.52, .35), (.65, .35), (.45, .45), (.7, .45)):
            spot = (width * x, height * y)
            if not any(len(box.get('min', [])) == 2 and len(box.get('max', [])) == 2 and
                       all(low <= value <= high for low, value, high in zip(box['min'], spot, box['max'])) for box in boxes):
                return spot
        raise AssertionError('No unobstructed ordinary camera gesture origin')

    def frame_costume(self, entity, card):
        unit = next(u for u in self.read()['cinematic']['units'] if u['id'] == entity)
        assert not unit.get('dead') and not unit.get('ragdoll')
        before = [copy.deepcopy(self.snapshot(name)) for name in ('a', 'b')]
        original_hand = self.clear_hand_for_review()
        width, height = self.hud_dimensions()
        viewport = self.hud()['viewport_size']
        spot = self.gesture_origin()
        for _ in range(3):
            camera = self.camera_state()
            delta = [unit['location'][axis] - camera['focus'][axis] for axis in range(2)]
            if max(abs(value) for value in delta) < 2:
                break
            yaw = math.radians(camera['yaw'])
            right, forward = (-math.sin(yaw), math.cos(yaw)), (-math.cos(yaw), -math.sin(yaw))
            pan_x = -sum(a*b for a, b in zip(delta, right)) / (camera['distance'] * .0012)
            pan_y = sum(a*b for a, b in zip(delta, forward)) / (camera['distance'] * .0012)
            self.event('down', spot, button='middle')
            self.event('move', (spot[0] + pan_x * width / viewport[0], spot[1] + pan_y * height / viewport[1]), button='middle')
            self.event('up', button='middle')
        requested_distance = self.camera_state()['minimum_distance']
        assert requested_distance == 650, 'Ordinary tactical camera minimum changed; review framing assumptions'
        # NavigateCamera limits one ordinary wheel event to ten steps. The
        # 4375.11 -> 650 move needs10.94, so deliver bounded events and reread the
        # actual camera instead of asserting an unclamped one-event prediction.
        for _ in range(3):
            distance = self.camera_state()['distance']
            if abs(distance - requested_distance) < 2:
                break
            steps = math.log(requested_distance / distance) / math.log(.84)
            self.event('wheel', spot, wheel=max(-10., min(10., steps)))
        assert abs(self.camera_state()['distance'] - requested_distance) < 2, \
            f'Ordinary wheel inputs did not reach the requested distance: {self.camera_state()}'
        front = -90 if unit['side'] == 0 else 90
        views = []
        # The rear camera looks over the actual protecting camp; a shallow
        # rear view would hide the costume behind Bonfire/Memorial geometry.
        for name, yaw, requested_pitch in (('front', front, 15), ('side', front + 75, 15), ('rear', front + 180, 60)):
            for _ in range(3):
                current = self.camera_state()
                delta = (yaw - current['yaw'] + 180) % 360 - 180
                pitch_delta = requested_pitch - current['pitch']
                if abs(delta) < .1 and abs(pitch_delta) < .1:
                    break
                px, py = max(-500, min(500, -delta / .22)), max(-500, min(500, pitch_delta / .18))
                self.event('down', spot, button='right')
                self.event('move', (spot[0] + px * width / viewport[0], spot[1] + py * height / viewport[1]), button='right')
                self.event('up', button='right')
            for _ in range(6):
                time.sleep(.14)
                self.observe(self.read())
            camera = self.camera_state()
            assert abs((yaw - camera['yaw'] + 180) % 360 - 180) < 1, 'Real orbit did not reach requested angle'
            assert abs(camera['pitch'] - requested_pitch) < 1 and abs(camera['distance'] - requested_distance) < 2
            assert math.dist(camera['focus'][:2], unit['location'][:2]) < 3, 'Real pan did not frame the public person'
            label = f'costume-{card}-{entity}-{name}'
            self.capture(label)
            current = self.read(); self.observe(current)
            actual = next(u for u in current['cinematic']['units'] if u['id'] == entity)
            assert pose_class(actual) == 'idle', 'Close view does not contain a live ordinary idle'
            views.append(dict(angle=name, image=self.captures[label], camera=camera, unit=actual))
        self.reset_camera()
        self.restore_hand_after_review(original_hand)
        assert [self.snapshot(name) for name in ('a', 'b')] == before, 'Costume camera review changed authoritative state'
        self.close_views[card] = dict(entity=entity, unchanged_authoritative_views=True,
                                     hand_dock_cleared_with_real_pointer_and_restored=True, views=views)
        write_json(self.folder / 'costume-close-views.json', self.close_views)

    def choose_action(self, name, snapshot):
        for unit in self.read()['cinematic']['units']:
            card = unit.get('card_id')
            if card in TARGETS and card not in self.close_views and pose_class(unit) == 'idle':
                self.frame_costume(unit['id'], card)
        expected = self.replay[len(self.actions)]
        assert snapshot['seat'] == expected['seat'] and snapshot['view']['revision'] == expected['revision'], \
            'Live revision/acting player diverged from the public legal rehearsal'
        offered = [action for action in snapshot['actions'] if action['command'] == expected['command']]
        assert len(offered) == 1, f'Rehearsed action is not currently offered: {expected}'
        return offered[0]

    def costume_coverage(self):
        result = {}
        for card in TARGETS:
            samples = [row for row in self.costume_samples if row['card_id'] == card]
            entities = {row['entity'] for row in samples}
            poses = {}
            for classification in ('idle', 'walk', 'hit', 'attack', 'fall'):
                selected = [row for row in samples if row['classification'] == classification]
                # Compare the pose with the preceding sample as well: short
                # hit/fire clips can fit between two report intervals. The
                # exact active-clip sighting is still required, never inferred.
                deltas = [pose_delta(previous['unit'], current['unit']) for previous, current in zip(samples, samples[1:])
                          if previous['entity'] == current['entity'] and current['classification'] == classification]
                poses[classification] = dict(sample_count=len(selected), max_observed_pose_delta_cm=max(deltas, default=0.),
                    active_clips=sorted({row['unit'].get('active_clip', '') for row in selected}),
                    actual_motion_observed=bool(selected and max(deltas, default=0.) > .01))
            captures = [row for row in self.capture_records if row.get('public_character') == card and row['actual_phase_bracket_valid']]
            captured_kinds = {row['kind'] for row in captures if row['requested_phase'] in ('impact', 'after-impact')}
            falls = [completion for completion in self.completions if completion.get('independent_reconstruction') and any(
                target.get('target') in entities and target.get('ragdoll') for target in completion.get('targets', []))]
            requirements = {f'{kind}_actual_pose_motion': poses[kind]['actual_motion_observed'] for kind in ('idle', 'walk', 'hit', 'fall')}
            requirements.update({f'{kind}_actual_capture': kind in captured_kinds for kind in ('enter', 'ability', 'damage', 'destroy')})
            requirements['three_mouse_close_views'] = len(self.close_views.get(card, {}).get('views', [])) == 3
            requirements['strict_natural_completed_fall'] = bool(falls)
            completed = [row for row in self.completed_grip_samples if row['card_id'] == card
                         and row['counted_for_completed_coverage'] and not row.get('failure')]
            # MM_HitReact_Front_Lgt_01 is explicitly not a two-hand rifle clip;
            # its actual pose/capture coverage above remains independently required.
            required_grips = ['idle', 'walk'] + (['attack'] if card in ('gatling_gunner', 'bounty_hunter') else [])
            completed_grip_poses = {kind: [row for row in completed if row['classification'] == kind]
                                    for kind in required_grips}
            requirements['calibrated_live_rifle_contact'] = all(completed_grip_poses.values())
            if card in ('gatling_gunner', 'bounty_hunter'):
                requirements['printed_attack_actual_pose_motion'] = poses['attack']['actual_motion_observed']
            result[card] = dict(requirements=requirements, missing=[key for key, passed in requirements.items() if not passed],
                                poses=poses, valid_captures=captures, strict_fall_sequences=[fall['sequence'] for fall in falls],
                                completed_grip_poses={kind: dict(sample_count=len(rows),
                                    sample_frames=sorted({row['sample_frame'] for row in rows}),
                                    sequences=sorted({row['sequence'] for row in rows}),
                                    maximum_gap_cm=max((row['verified_max_completed_palm_gap_cm'] for row in rows), default=None))
                                    for kind, rows in completed_grip_poses.items()},
                                close_views=self.close_views.get(card), sampled_entities=sorted(entities))
        return result

    def run(self):
        result = None
        try:
            result = super().run()
            return result
        finally:
            # super.run closes both owned processes even on a failed assertion.
            retained = result or json.loads((self.folder / 'result.json').read_text())
            coverage = self.costume_coverage()
            complete = len(self.actions) == len(self.replay) and not any(row['missing'] for row in coverage.values())
            retained.update(costume_coverage=coverage, costume_coverage_complete=complete,
                            planned_legal_action_count=len(self.replay), manual_visual_review='pending',
                            ok=retained.get('ok', False) and complete)
            retained['limitations'].extend([
                'The current runtime has no ordinary crouch action; deep-knee coverage remains the separate CPU pose study.',
                'Prospector has a nonoffensive printed ability, so this run does not require a fabricated Prospector fire animation.',
                'Numerical garment/weapon checks do not prove absence of cloth intersection or natural finger contact; inspect the actual frames.',
                'Close views are ordinary tactical camera gestures and do not alter authoritative state.',
                'Grip acceptance uses the last completed actor-tick snapshot and its own identity/clip; '
                'instantaneous PrePhysics gaps remain in retained diagnostics. This is not GPU readback.'])
            write_json(self.folder / 'result.json', retained)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_PLAN)
    parser.add_argument('--resolutions', nargs='+', type=resolution, default=[(1280, 720)])
    parser.add_argument('--port', type=int, default=19659)
    parser.add_argument('--timeout', type=float, default=1500)
    parser.add_argument('--extra-render-command', dest='extra_render_commands', action='append', default=[],
                        help='Repeatable rendered-client diagnostic console command; ordinary default launch stays unchanged')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_text())
    assert plan['ok'] and plan['catalog_sha256'] == hashlib.sha256((ROOT / 'game/data/cards.json').read_bytes()).hexdigest()
    assert {target['card_id'] for target in plan['targets']} == set(TARGETS)
    assert json.loads((BASE / 'native-reference-audit.json').read_text())['ok']
    args.seed, args.ruleset = plan['seed'], plan['ruleset']
    args.max_actions, args.settle = len(plan['journal']) - 2, 0.
    args.prefer_camp, args.require_kind, args.profile_renderer = [], [], False
    args.scenario_config = dict(name='three-costume-public-replay', policy='public_replay',
                                target_kinds=['enter', 'ability', 'damage', 'destroy'], preferred_cards=list(TARGETS))
    output = args.output.resolve() if args.output else create_native_run_directory('oldwest-native-costumes-')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(ok=False, logs=str(output), results=[], scope='Ordinary legal native costume observer')
    print(f'Native costume evidence: {output}', flush=True)
    try:
        for index, dimensions in enumerate(args.resolutions):
            report['results'].append(CostumeScenario(copy.copy(args), output, dimensions, index).run())
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
