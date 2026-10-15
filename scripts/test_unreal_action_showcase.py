#!/usr/bin/env python3
"""Record real action presentations reached through ordinary legal native play.

This is a coverage-seeking visual showcase, not a fabricated all-card fixture.
Two native peers submit only actions offered by their current public snapshots.
No state injection, physics override, forced animation hold or image synthesis
is used. Missing kinds and screenshot phases remain explicitly missing.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import random
import struct
import subprocess
import sys
import time
import wave
from pathlib import Path

from native_launch import create_native_run_directory, stop_owned_process_groups
from native_runtime_checks import assert_runtime_assets
from test_unreal_hud import resolution
from test_unreal_interactions import EDITOR, ROOT, InteractionScenario, write_json
from analyze_game_audio import analyze


FIXED_KINDS = {
    'ability', 'camp_advance', 'damage', 'destroy', 'discard', 'draw_card', 'draw_game',
    'enter', 'event_advance', 'event_play', 'event_resolve', 'expose_all', 'junk', 'move',
    'raid_launch', 'rearrange', 'remove_ruin', 'reshuffle', 'restore', 'return',
    'reveal_discard', 'reveal_person', 'store_water', 'turn_end', 'turn_start', 'victory', 'water',
}
DYNAMIC_KINDS = {'recruit_id', 'hospital_id'}
PUBLIC_METADATA_KINDS = {'analysis_choice'}
INTERNAL_PRESENTATION_KINDS = {'analysis_close'}
INVENTORY = FIXED_KINDS | DYNAMIC_KINDS | PUBLIC_METADATA_KINDS
DEFAULT_MANIFEST = ROOT / 'game/tests/action-showcase/scenarios.json'


def signature(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def phase_of(cinematic):
    if not cinematic.get('busy') or not cinematic.get('kind'):
        return 'tactical'
    if not cinematic.get('impact_resolved'):
        return 'before-impact'
    return 'impact' if cinematic.get('elapsed', 0) < .65 else 'after-impact'


def capture_subject(cinematic):
    """Keep camp/person evidence distinct without revealing a hidden face."""
    target = next((unit for unit in cinematic.get('units', [])
                   if unit.get('id') == cinematic.get('target')), {})
    category = ('camp' if target.get('camp') else 'event' if target.get('event_token')
                else 'person' if target else 'resource')
    identity = target.get('card_id')
    character = identity if identity in ('prospector', 'gatling_gunner', 'bounty_hunter', 'blacksmith') else None
    return category, character


def delivery_has_arrived(cinematic):
    # The ox team blends to its resting pose after the wheels stop. A settled
    # capture must include that completed transition, not just a stopped axle.
    deliveries=cinematic.get('deliveries',[])
    if deliveries and any(d['walking'] or any(a.get('entry_alpha',0)<.999 for a in d['animals']) for d in deliveries):
        return False
    wheels = [effect for effect in cinematic.get('action_effects', [])
              if effect.get('visible') and effect.get('wheel_radius_cm', 0) > 0]
    return bool(wheels and all(effect.get('age', 0) >= effect.get('duration', math.inf) + .05
                               for effect in wheels))


def painted_beat(state):
    """Return the most recent actual child-paint identity, not cached layout."""
    paint = state.get('hud', {}).get('paint', {})
    transitions = paint.get('transitions', [])
    if not transitions:
        return None
    last = transitions[-1]
    if not isinstance(last.get('frame'), int) or paint.get('last_frame', -1) < last['frame']:
        return None
    return {**last, 'last_frame': paint['last_frame']}


def validate_lens(cinematic):
    """Check camera requests independently; pixel exposure still needs review."""
    lens = cinematic['lens']
    aperture, shutter = lens['aperture'], lens['shutter_speed']
    assert all(math.isfinite(value) and value > 0 for value in (aperture, shutter))
    product = aperture * aperture * shutter
    assert math.isclose(product, 3840., rel_tol=1e-5, abs_tol=.02), 'Aperture changed physical exposure'
    assert math.isclose(product, lens['exposure_product'], rel_tol=1e-5, abs_tol=.02)
    assert lens['shutter_override'] and math.isclose(lens['postprocess_blend_weight'], 1., abs_tol=1e-5)
    active = bool(cinematic.get('busy') and cinematic.get('kind'))
    if active:
        assert lens['focus_method'] == 'manual', 'Active cinematic focus is not manual'
        origin, target, forward = cinematic['camera_location'], cinematic['camera_focus'], lens['camera_forward']
        assert len(origin) == len(target) == len(forward) == 3
        assert all(math.isfinite(value) for value in [*origin, *target, *forward])
        assert math.isclose(math.sqrt(sum(value * value for value in forward)), 1., abs_tol=1e-4)
        depth = sum((b - a) * direction for a, b, direction in zip(origin, target, forward))
        assert depth > 0 and math.isclose(depth, lens['manual_focus_distance_cm'], rel_tol=1e-4, abs_tol=.1), \
            'Manual focus misses the current camera target depth'
    else:
        assert lens['focus_method'] == 'disabled', 'Tactical depth of field was not restored'
        assert math.isclose(aperture, 8., abs_tol=1e-4) and math.isclose(shutter, 60., abs_tol=1e-3), \
            'Tactical exposure settings were not restored'
    return {'active': active, 'aperture': aperture, 'shutter_speed': shutter, 'independent_exposure_product': product}


def validate_completed_fall(completion):
    """Independently reconstruct actual motion; keep the original strict limits.

    The ordinary cinematic regression remains unchanged and is still required.
    This duplicate observer prevents a showcase from silently endorsing an
    unstable fall simply because the capture looks plausible.
    """
    assert completion.get('reason') == 'settled', 'Death reached its safety timeout'
    assert completion.get('stable_seconds', 0) >= .25 and completion.get('all_ragdolls_settled'), \
        'Death completion lacks a sustained stable interval'
    assert 1.95 <= completion.get('elapsed', 0) <= 6.15, 'Death exceeds the production time contract'
    targets = [target for target in completion.get('targets', []) if target.get('ragdoll')]
    assert targets, 'Settled completion has no actual ragdoll'
    maxima = []
    for target in targets:
        physics = target['physics']
        assert physics.get('thigh_collision_enabled') is True, 'Ragdoll thighs can pass through each other'
        assert physics['ground_found'] and -5 <= physics['pelvis_ground_clearance_cm'] <= 65
        assert physics['max_speed_cm_s'] <= 20 and physics['max_angular_speed_deg_s'] <= 45
        bodies, joints = physics['bodies'], physics['joints']
        assert len(bodies) == 16 and len(joints) == 15
        assert all(joint.get('linear_solver_profile') is False and
                   joint.get('mass_conditioning_enabled') is False and
                   joint.get('projection_enabled') is False for joint in joints)
        assert physics.get('forearm_chest_collision_enabled') == {'LeftForeArm': True, 'RightForeArm': True}
        assert all(body.get('physics_body_blocked') and body.get('world_static_blocked') for body in bodies)
        pose = physics['pose_motion']
        assert pose['valid'] and pose['body_count'] == 16
        assert pose['sample_frame'] == pose['query_frame'] == pose['previous_frame'] + 1
        dt = pose['delta_seconds']
        assert math.isfinite(dt) and dt > 0
        assert len(pose['bodies']) == 16 and {body['bone'] for body in pose['bodies']} == {body['bone'] for body in bodies}
        speeds, spins = [], []
        for body in pose['bodies']:
            previous, current = body['previous_com_cm'], body['current_com_cm']
            qa, qb = body['previous_rotation_xyzw'], body['current_rotation_xyzw']
            assert len(previous) == len(current) == 3 and len(qa) == len(qb) == 4
            assert all(math.isfinite(value) for value in [*previous, *current, *qa, *qb])
            na, nb = math.sqrt(sum(value * value for value in qa)), math.sqrt(sum(value * value for value in qb))
            assert na > 0 and nb > 0
            speed = math.dist(previous, current) / dt
            dot = min(1., abs(sum(a * b for a, b in zip(qa, qb)) / (na * nb)))
            spin = math.degrees(2 * math.acos(dot)) / dt
            assert math.isclose(speed, body['speed_cm_s'], rel_tol=1e-4, abs_tol=.02)
            assert math.isclose(spin, body['angular_speed_deg_s'], rel_tol=1e-4, abs_tol=.02)
            assert speed <= 20.02 and spin <= 45.02, 'Actual body pose still moves at completion'
            speeds.append(speed); spins.append(spin)
        assert pose['max_speed_cm_s'] <= 20 and pose['max_angular_speed_deg_s'] <= 45
        assert math.isclose(max(speeds), pose['max_speed_cm_s'], rel_tol=1e-4, abs_tol=.02)
        assert math.isclose(max(spins), pose['max_angular_speed_deg_s'], rel_tol=1e-4, abs_tol=.02)
        maxima.append({'target': target['target'], 'linear_cm_s': max(speeds), 'angular_deg_s': max(spins)})
    return maxima


class ActionShowcase(InteractionScenario):
    def __init__(self, args, output, dimensions, index):
        super().__init__(args, output, dimensions, index)
        self.random = random.Random(args.seed + 17)
        self.seen_kinds, self.logged_kinds, self.before_types = set(), set(), set()
        self.logged_events, self.frames, self.actions, self.shots = [], [], [], {}
        self.capture_records, self.issues, self.completions = [], [], []
        self.log_keys, self.frame_keys, self.completion_keys, self.capture_attempts = set(), set(), set(), set()
        self.valid_captures, self.public_people, self.public_events = set(), set(), set()
        self.valid_mapped_captures = set()
        self.valid_subject_captures, self.valid_delivery_captures = set(), set()
        self.late_physics_keys = set()
        self.late_physics_sample_count = 0
        self.paint_keys, self.painted_shots = set(), set()
        self.paint_transitions, self.prepaint_visibility = [], []
        self.paint_telemetry_seen = False
        self.performance_keys, self.performance_reports = set(), []
        self.performance_enabled_peers = set()
        self.lens_checks = {'active_samples': 0, 'tactical_samples': 0, 'apertures': set()}
        self.tactical_lens_samples, self.finale_samples = [], []
        self.tactical_lens_keys = set()
        self.camp_selections = []
        self.scenario = args.scenario_config
        self.preferred_camps = set(self.scenario.get('preferred_camps', [])) | set(args.prefer_camp)
        self.preferred_cards = set(self.scenario.get('preferred_cards', []))
        self.last_progress = time.monotonic()
        self.audio_started = False
        self.audio_report = None
        self.build = {'mode': 'packaged' if self.runtime.package_root else 'editor_game'}
        if self.runtime.package_root:
            binaries = self.runtime.package_root / 'OldWest/Binaries/Linux'
            executable = next(path for path in (binaries / 'OldWestGame', binaries / 'OldWestGame-Linux-Development') if path.is_file())
            self.build.update(executable=signature(executable),
                              manifest=signature(self.runtime.package_root / 'package-manifest.json'))
        else:
            self.build.update(module=signature(ROOT / 'game/OldWest/Binaries/Linux/libUnrealEditor-OldWestGame.so'),
                              sources=[signature(ROOT / 'game/OldWest/Source/OldWestGame' / name) for name in (
                                  'Public/OldWestBattlefield.h', 'Private/OldWestBattlefield.cpp', 'Private/OldWestHUD.cpp')])
        self.build['harness'] = signature(__file__)
        write_json(self.folder / 'build.json', self.build)
        write_json(self.folder / 'scenario-manifest.json', {'manifest': signature(args.manifest),
            'scenario': self.scenario, 'effective_seed': args.seed, 'effective_ruleset': args.ruleset,
            'effective_max_actions': args.max_actions, 'preferred_camps': sorted(self.preferred_camps),
            'selection_inputs': 'Both acting players own public camp offers and legal selection commands only',
            'scope': 'Planned coverage, not a claim that target actions were reached'})

    def launch(self, name, url, rendered=False):
        if not getattr(self.args, 'profile_renderer', False):
            super().launch(name, url, rendered)
        else:
            stream = (self.folder / f'{name}-console.log').open('w')
            self.streams.append(stream)
            width, height = self.dimensions
            graphics = ['-RenderOffscreen', '-windowed', '-ForceRes', f'-ResX={width}', f'-ResY={height}'] if rendered else ['-nullrhi']
            sound = ['-AudioMixer'] if rendered and getattr(self.args, 'audio', False) else ['-nosound']
            render_commands = ','.join(['t.MaxFPS 60', *getattr(self.args, 'extra_render_commands', [])])
            # Keep the ordinary launch, cadence, graphics and rules settings;
            # this flag only enables timing observations in the same binary.
            arguments = self.runtime.argv + [url, '-game', *graphics,
                '-OldWestLifecycleTest', '-OldWestVisualTest', '-OldWestPresentationProfile',
                f'-OldWestTestSeed={self.args.seed}', f'-OldWestLifecycleControl={self.folder}/{name}.control.json',
                f'-OldWestLifecycleReport={self.folder}/{name}.json', f'-port={self.port}', '-MULTIHOME=127.0.0.1',
                f'-OldWestProfileRoot={self.folder}/profiles', f'-OldWestProfile={name}',
                f'-GameUserSettingsINI={self.folder}/{name}.settings.ini', f'-abslog={self.folder}/{name}.log',
                '-ExecCmds='+render_commands, *sound, '-unattended', '-nosplash', '-NoLiveCoding',
                '-stdout', '-FullStdOutLogOutput']
            self.processes[name] = subprocess.Popen(arguments, cwd=self.runtime.cwd, env=self.runtime.env,
                stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        write_json(self.folder / 'native-launches.json', {peer: process.args for peer, process in self.processes.items()})

    def read(self, name='a'):
        state = super().read(name)
        if getattr(self.args, 'profile_renderer', False):
            if state.get('cinematic', {}).get('frame_performance', {}).get('enabled'):
                self.performance_enabled_peers.add(name)
            profile = state.get('lifecycle_profile_previous_report')
            if isinstance(profile, dict):
                key = (name, profile.get('match_id'), profile.get('native_frame'), profile.get('command_sequence'))
                if key not in self.performance_keys:
                    self.performance_keys.add(key)
                    record = {'peer': name, **profile,
                        'observed_snapshot_revision': state.get('snapshot', {}).get('view', {}).get('revision'),
                        'observed_cinematic_sequence': state.get('cinematic', {}).get('sequence')}
                    self.performance_reports.append(record)
                    with (self.folder / 'lifecycle-performance.jsonl').open('a') as stream:
                        stream.write(json.dumps(record) + '\n')
                    times = [value for field, value in profile.items() if field.endswith('_ms')]
                    if not all(isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 for value in times):
                        self.issue('Lifecycle performance report contains invalid timing', sequence=profile.get('cinematic_sequence'))
        return state

    def submit(self, name, action):
        if action['command']['type'] == 'select_camps':
            snapshot = self.snapshot(name)
            if self.preferred_camps:
                action = max(snapshot['actions'], key=lambda option: (
                    sum(card in self.preferred_camps for card in option['command']['camps']),
                    sum(self.defs[card]['starting_cards'] for card in option['command']['camps'])))
            self.camp_selections.append({'peer': name, 'seat': snapshot['seat'],
                'public_offers': [card['id'] for card in snapshot['view']['players'][snapshot['seat']]['offers']],
                'command': action['command'],
                'legal_actions_sha256': hashlib.sha256(json.dumps(snapshot['actions'], sort_keys=True).encode()).hexdigest()})
            write_json(self.folder / 'legal-camp-selection-journal.json', self.camp_selections)
        super().submit(name, action)

    def issue(self, message, **evidence):
        key = (message, evidence.get('sequence'))
        if not any((entry['message'], entry.get('sequence')) == key for entry in self.issues):
            self.issues.append({'message': message, **evidence})
            print(f'{self.folder.name}: ISSUE {message}', flush=True)

    def mapped_trigger(self, match, sequence, kind):
        event = next((entry for entry in self.logged_events if entry['match_id'] == match and
                      entry['sequence'] == sequence), None)
        if not event:
            return None
        if kind == 'move' and event['type'] == 'rearrange':
            return {'kind': 'rearrange', 'public_event': event}
        if kind == 'turn_start' and event['type'] == 'turn_start':
            command = next((entry for entry in self.actions if entry['match_id'] == match and
                            entry['command']['type'] == 'end_turn' and
                            entry.get('accepted_revision') == event['revision'] == entry['revision'] + 1 and
                            entry.get('turn', -2) + 1 == event['turn'] and
                            entry.get('seat') == 1 - event['player'] and
                            entry.get('last_public_sequence', sequence) < sequence), None)
            if command:
                return {'kind': 'turn_end', 'legal_command': command, 'public_event': event,
                        'note': 'The prior-turn turn_end log is filtered from the public view; the accepted legal command and exact next-turn record establish the mapping.'}
        return None

    def observe_paint(self, state):
        paint = state.get('hud', {}).get('paint')
        if not isinstance(paint, dict):
            return
        self.paint_telemetry_seen = True
        for transition in paint.get('transitions', []):
            key = (transition.get('match_id'), transition.get('view_generation'), transition.get('frame'))
            if key in self.paint_keys:
                continue
            self.paint_keys.add(key)
            retained = copy.deepcopy(transition)
            self.paint_transitions.append(retained)
            if not transition.get('busy'):
                continue
            match, sequence = transition.get('match_id'), transition.get('sequence')
            if isinstance(sequence, int) and sequence >= 0:
                self.painted_shots.add((match, sequence))
            # The history retains the first paint of every visibility change.
            # A one-frame flash fails even if a later paint hides the dock.
            if transition.get('visible_docks'):
                self.issue('An actual painted action frame contains dashboard or response docks',
                           sequence=sequence, paint=retained)
            if transition.get('end_panel_visible'):
                self.issue('An actual painted action frame contains the match-end/rematch panel',
                           sequence=sequence, paint=retained)

    def observe(self, state):
        snapshot, cinematic = state.get('snapshot', {}), state.get('cinematic', {})
        view, match = snapshot.get('view', {}), snapshot.get('match_id')
        self.observe_paint(state)
        if 'busy' in cinematic:
            try:
                lens_check = validate_lens(cinematic)
                self.lens_checks['active_samples' if lens_check['active'] else 'tactical_samples'] += 1
                self.lens_checks['apertures'].add(round(lens_check['aperture'], 3))
                identity = (match, view.get('revision'))
                if not lens_check['active'] and identity not in self.tactical_lens_keys:
                    self.tactical_lens_keys.add(identity)
                    self.tactical_lens_samples.append({'match_id': match, 'revision': view.get('revision'),
                                                      'lens': cinematic['lens'], 'independent': lens_check})
            except (AssertionError, KeyError, TypeError, ValueError) as error:
                self.issue(f'Cinematic lens validation failed: {error}', sequence=cinematic.get('sequence'))
        if view.get('status') in ('won', 'draw'):
            end = state.get('hud', {}).get('end_panel', {})
            finale = {'status': view['status'], 'sequence': cinematic.get('sequence'), 'kind': cinematic.get('kind'),
                      'busy': cinematic.get('busy'), 'end_panel': end}
            if not self.finale_samples or self.finale_samples[-1] != finale:
                self.finale_samples.append(finale)
        for player in view.get('players', []):
            for column in player['columns']:
                self.public_people.update(card['id'] for card in column if card.get('type') == 'person')
            self.public_events.update(card['id'] for card in player['queue'] if card)
        for event in view.get('log', []):
            key = (match, event['sequence'])
            if key not in self.log_keys:
                self.log_keys.add(key); self.logged_events.append({'match_id': match, **event})
                self.logged_kinds.add(event['type'])
        for completion in cinematic.get('completion_history', []):
            key = (completion.get('match_id'), completion.get('sequence'))
            if key in self.completion_keys:
                continue
            self.completion_keys.add(key)
            retained = copy.deepcopy(completion)
            if completion.get('waited_for_settling') and completion.get('reason') != 'skipped':
                try:
                    retained['independent_reconstruction'] = validate_completed_fall(completion)
                except (AssertionError, KeyError, TypeError, ValueError) as error:
                    self.issue(f'Strict completed-fall validation failed: {error}', sequence=completion.get('sequence'))
            self.completions.append(retained)
        if not cinematic.get('busy') or not cinematic.get('kind'):
            return
        kind, sequence = cinematic['kind'], cinematic['sequence']
        # Native reports arrive less often than native frames. Each retained
        # pose still contains an exact adjacent-frame pair; do not call this a
        # complete frame trajectory or infer unmeasured CPU/GPU attribution.
        if cinematic.get('settle_hold', {}).get('required') and cinematic.get('elapsed', 0) >= 5.:
            pose = (cinematic.get('physics') or {}).get('pose_motion', {})
            if pose.get('query_frame') is None:
                pose = next(((target.get('physics') or {}).get('pose_motion', {})
                             for target in cinematic.get('simultaneous_targets', [])
                             if (target.get('physics') or {}).get('pose_motion', {}).get('query_frame') is not None), {})
            sample_key = (match, sequence, pose.get('query_frame'))
            if pose.get('query_frame') is not None and sample_key not in self.late_physics_keys:
                self.late_physics_keys.add(sample_key)
                late = {key: cinematic.get(key) for key in (
                    'sequence', 'kind', 'elapsed', 'target', 'frame_timing', 'settle_hold',
                    'physics', 'simultaneous_targets', 'camera_location', 'camera_focus')}
                late['match_id'] = match
                with (self.folder / 'late-fall-samples.jsonl').open('a') as stream:
                    stream.write(json.dumps(late) + '\n')
                self.late_physics_sample_count += 1
        self.seen_kinds.add(kind)
        key = (match, sequence, int(cinematic.get('elapsed', 0) * 12))
        if key in self.frame_keys:
            return
        self.frame_keys.add(key)
        units = cinematic.get('units', [])
        hidden_punks = {card['id'] for player in view.get('players', []) for column in player['columns']
                        for card in column if card.get('punk')}
        # Public event equipment is intentionally excluded from human pose/rig
        # checks; its equipment parts, bounds and public identity still matter.
        for unit in units:
            if unit.get('event_token'):
                herd = unit.get('stampede', {})
                visible_herd = (unit.get('raider') and herd.get('animal_count') == 3 and
                                len(herd.get('animals', [])) == 3 and
                                all(a.get('visible') and a.get('mesh', '').endswith('SK_Longhorn.SK_Longhorn')
                                    for a in herd['animals']))
                if unit.get('ragdoll') or (unit.get('event_parts', 0) <= 0 and not visible_herd) or 'bounds' not in unit:
                    self.issue('Public event equipment lacks a stable visible equipment scene', sequence=sequence, unit=unit)
                # Immediate events need not enter a queue. Their public resolve
                # log must already identify this exact source and card; a hand
                # identity, future beat or unrelated public event is insufficient.
                public_resolution = any(
                    event['match_id'] == match and event['type'] == 'event_resolve'
                    and event.get('source') == unit['id'] and event['sequence'] <= sequence
                    and event.get('detail', '').lower().replace(' ', '_') == unit.get('card_id')
                    for event in self.logged_events)
                if unit['id'] not in self.public_events and not public_resolution:
                    self.issue('Event equipment appeared without a public queue or resolution identity', sequence=sequence, unit=unit)
            elif not unit.get('camp'):
                if unit['id'] == 0:
                    self.issue('A resource-only action fabricated a person with entity0', sequence=sequence)
                if not unit.get('ragdoll') and unit.get('root_drift_cm', 0) >= 3:
                    self.issue('Animated person root drift exceeds3cm', sequence=sequence, unit=unit)
                if unit['id'] in hidden_punks and ('RepairBot' in unit.get('visual_mesh', '') or
                                                 unit.get('card_id') not in ('', 'punk')):
                    self.issue('A hidden punk uses a face-specific public visual', sequence=sequence, unit=unit)
        effects = cinematic.get('action_effects', [])
        if any(effect.get('collision_enabled') != 0 for effect in effects):
            self.issue('Transient action prop participates in collision', sequence=sequence)
        if any(len(effect.get('location', [])) != 3 or not all(math.isfinite(value) for value in effect['location']) for effect in effects):
            self.issue('An action prop has an invalid world position', sequence=sequence)
        if cinematic.get('camera_obstructed'):
            self.issue('Native action camera reports scenery obstruction', sequence=sequence, kind=kind,
                       detail=cinematic.get('camera_obstruction_detail'),post_tick=cinematic.get('camera_post_tick'))
        post_tick=cinematic.get('camera_post_tick',{})
        if post_tick.get('sequence')==sequence and post_tick.get('obstructed_frames',0):
            self.issue('Final camera tick reports scenery obstruction',sequence=sequence,kind=kind,post_tick=post_tick)
        if cinematic.get('service_layout_failures', 0):
            self.issue('Delivery mechanism has no clear staging layout', sequence=sequence, kind=kind)
        frame = {'match_id': match, 'sequence': sequence, 'kind': kind, 'elapsed': cinematic.get('elapsed'),
                 'camera_post_tick': copy.deepcopy(post_tick),
                 'source_revision': next((event['revision'] for event in self.logged_events
                     if event['match_id'] == match and event['sequence'] == sequence), None),
                 'snapshot_revision': view.get('revision'),
                 'phase': phase_of(cinematic), 'source': cinematic.get('source'), 'target': cinematic.get('target'),
                 'known_target': cinematic.get('known_target'), 'camera_focus': cinematic.get('camera_focus'),
                 'camera_location': cinematic.get('camera_location'), 'effects': effects,
                 'frame_timing': cinematic.get('frame_timing'), 'settle_hold': cinematic.get('settle_hold'),
                 'lens': cinematic.get('lens'), 'service_layouts': cinematic.get('service_layouts', []),
                 'service_layout_failures': cinematic.get('service_layout_failures', 0),
                 'units': [{key: unit[key] for key in ('id', 'card_id', 'camp', 'event_token', 'location', 'bounds',
                            'travelling', 'active_clip', 'idle_clip', 'animation_position', 'pose_samples', 'ragdoll', 'visual_mesh') if key in unit}
                           for unit in units],
                 'hud': {key: state.get('hud', {}).get(key) for key in
                         ('chrome_visible', 'controls_visible', 'cinematic_busy', 'end_panel', 'dock_panels')},
                 'last_painted_beat': painted_beat(state),
                 'pending_choice': view.get('choice') is not None, 'status': view.get('status')}
        self.frames.append(frame)
        self.shots.setdefault((match, sequence), []).append(frame)
        with (self.folder / 'scene-samples.jsonl').open('a') as stream:
            stream.write(json.dumps(frame) + '\n')
        paint = frame['last_painted_beat'] or {}
        # Cached Slate visibility can still describe the preceding tactical
        # frame before the new shot is painted. Actual child traversal above
        # remains strict, including a one-frame flash on the first busy paint.
        if (frame['hud']['chrome_visible'] and paint.get('busy') and
                paint.get('sequence') == sequence and paint.get('match_id') == match):
            self.issue('Gameplay chrome remains visible during an action', sequence=sequence, kind=kind)
        visible_docks = [dock.get('id') for dock in (frame['hud']['dock_panels'] or []) if dock.get('visible')]
        if visible_docks:
            # Keep prepaint discrepancies as evidence, but only actual child
            # traversal establishes whether a dock appeared over the world.
            self.prepaint_visibility.append({'match_id': match, 'sequence': sequence, 'kind': kind,
                'elapsed': cinematic.get('elapsed'), 'cached_visible_docks': visible_docks,
                'last_painted_beat': painted_beat(state)})

    def capture_phase(self, state):
        cinematic = state['cinematic']
        kind, phase = cinematic['kind'], phase_of(cinematic)
        painted = painted_beat(state)
        if not (painted and painted.get('busy') and
                painted.get('match_id') == state['snapshot']['match_id'] and
                painted.get('sequence') == cinematic['sequence']):
            # Wait for this shot's first paint before requesting a screenshot.
            # observe_paint still checks every retained first-frame transition.
            return
        identity = (kind, phase)
        subject = capture_subject(cinematic)
        subject_identity = (kind, *subject, phase)
        arrived = delivery_has_arrived(cinematic)
        needs_delivery = arrived and kind not in self.valid_delivery_captures
        attempt = (state['snapshot']['match_id'], cinematic['sequence'], phase,
                   'arrived' if needs_delivery else 'ordinary')
        mapping = self.mapped_trigger(attempt[0], attempt[1], kind)
        needs_mapping = mapping and (mapping['kind'], phase) not in self.valid_mapped_captures
        needs_subject = subject_identity not in self.valid_subject_captures
        if (identity in self.valid_captures and not needs_mapping and not needs_subject and not needs_delivery) or attempt in self.capture_attempts:
            return
        self.capture_attempts.add(attempt)
        label = f'{len(self.capture_records) + 1:03d}-{kind}-{cinematic["sequence"]}-{phase}'
        path = self.folder / f'{label}.png'
        before = copy.deepcopy(state)
        capture_begin = time.monotonic()
        self.command('a', 'screenshot', filename=str(path))
        capture_acknowledged = time.monotonic()

        def image_complete():
            self.observe(self.read())
            try:
                data = path.read_bytes()
                return data if data.startswith(b'\x89PNG\r\n\x1a\n') and b'IEND' in data[-16:] else None
            except FileNotFoundError:
                return None

        data = self.wait(f'{kind} actual screenshot', image_complete, 20)
        capture_file_complete = time.monotonic()
        assert struct.unpack('>II', data[16:24]) == self.dimensions
        after = copy.deepcopy(self.read())
        current = after.get('cinematic', {})
        same_beat = (current.get('busy') and current.get('sequence') == cinematic['sequence'] and
                     after.get('snapshot', {}).get('match_id') == before['snapshot']['match_id'])
        # Screenshot capture is asynchronous. Both native telemetry endpoints
        # must bracket the same beat AND phase before we call that phase valid.
        native_phase_valid = bool(same_beat and phase_of(current) == phase)
        before_paint, after_paint = painted_beat(before), painted_beat(after)
        def owns_paint(paint):
            return bool(paint and paint.get('busy') and paint.get('match_id') == attempt[0] and
                        paint.get('sequence') == cinematic['sequence'])
        paint_bracket_valid = bool(owns_paint(before_paint) and owns_paint(after_paint) and
                                   after_paint['last_frame'] >= before_paint['last_frame'])
        valid = native_phase_valid and paint_bracket_valid
        delivery_valid = bool(valid and needs_delivery and delivery_has_arrived(current))
        if delivery_valid:
            prior_effects, current_effects = cinematic.get('action_effects', []), current.get('action_effects', [])
            delivery_valid = len(prior_effects) == len(current_effects) and all(
                math.dist(a['location'], b['location']) < .1
                for a, b in zip(prior_effects, current_effects) if a.get('visible') and b.get('visible'))
        record = {'match_id': state['snapshot']['match_id'], 'kind': kind, 'sequence': cinematic['sequence'], 'requested_phase': phase,
                  'actual_phase_bracket_valid': valid, 'image': str(path),
                  'native_phase_bracket_valid': native_phase_valid,
                  'painted_beat_bracket_valid': paint_bracket_valid,
                  'before_paint': before_paint, 'after_paint': after_paint,
                  'target_category': subject[0], 'public_character': subject[1],
                  'delivery_arrived_capture_requested': needs_delivery,
                  'delivery_arrived_capture_valid': delivery_valid,
                  'external_capture_timing': {
                      'request_to_ack_ms': (capture_acknowledged - capture_begin) * 1000.,
                      'ack_to_complete_png_ms': (capture_file_complete - capture_acknowledged) * 1000.,
                      'request_to_complete_png_ms': (capture_file_complete - capture_begin) * 1000.,
                      'semantics': 'External wall time including report polling and file availability; not CPU-only capture cost.'},
                  'before_seconds': cinematic.get('elapsed'), 'after_seconds': current.get('elapsed'),
                  'after_kind': current.get('kind'), 'after_phase': phase_of(current)}
        self.capture_records.append(record); self.captures[label] = str(path)
        write_json(self.folder / f'{label}.state.json', {'capture': record, 'before_request': before, 'after_completion': after})
        if valid:
            self.valid_captures.add(identity)
            if capture_subject(current) == subject:
                self.valid_subject_captures.add(subject_identity)
            if delivery_valid:
                self.valid_delivery_captures.add(kind)
            if mapping:
                self.valid_mapped_captures.add((mapping['kind'], phase))
            print(f'{self.folder.name}: captured {kind} / {phase}', flush=True)

    def choose_action(self, name, snapshot):
        """Favor unobserved public effects, then progress an ordinary match.

        The score reads only this acting player's legal actions, own hand,
        public board and published card rules. It cannot inspect the deck or
        another player's hand, nor construct an unoffered command.
        """
        options = snapshot.get('actions', [])
        hand = self.own_hand(name)
        board = {card['id']: card for player in snapshot['view']['players'] for column in player['columns'] for card in column}
        want = INVENTORY - self.seen_kinds
        scenario_want = set(self.scenario['target_kinds']) - self.seen_kinds
        prompt = (snapshot['view'].get('choice') or {}).get('prompt', '').lower()
        def score(action):
            command, category = action['command'], action.get('category', '')
            kind = command['type']; value = 0.
            card = hand.get(command.get('card'), board.get(command.get('source'), {}))
            definition = self.defs.get(card.get('card_id'), {})
            label = action.get('label', '').lower()
            if self.scenario['policy'] == 'depletion':
                # An exhausted-deck ending is mutually exclusive with victory.
                # Avoid attacks and deployments; use only offered safe draws,
                # water junk, discard payments and ordinary pass turns.
                if kind == 'choose':
                    return 200 if label == 'skip' else 100 if label.startswith('discard ') else 0
                if kind == 'draw': return 150
                if kind == 'junk': return 170 if self.junk_kind(card) == 'draw' else 130 if self.junk_kind(card) == 'water' else -50
                if kind == 'activate':
                    return 180 if card.get('card_id') in ('post_office', 'horse_trader') else -50
                return 10 if kind == 'end_turn' else -100
            if kind == 'choose':
                placement = action.get('placement', {})
                value = 25 if label != 'skip' else -40
                if placement:
                    value += 12
                    moving = placement.get('moving')
                    if moving and 'move' in want:
                        value += 20
                    if moving or 'row' in placement:
                        subject = placement.get('card')
                        old_column = next((index for player in snapshot['view']['players']
                                           for index, column in enumerate(player['columns'])
                                           if any(card['id'] == subject for card in column)), None)
                        if old_column is not None and placement.get('column') != old_column:
                            value += 15
                    # Different legal placements get deterministic variety,
                    # preventing Box Canyon repeatedly choosing its old row.
                    value += self.random.random() * 8
                for phrase, event in (('restore', 'restore'), ('destroy', 'destroy'), ('return', 'return'), ('damage', 'damage')):
                    if phrase in label and event in want: value += 15
                if ('damage target' in prompt or 'card to destroy' in prompt) and 'victory' in scenario_want:
                    for target in board.values():
                        if target.get('type') == 'camp' and target.get('name', '').lower() in label:
                            value += 30 + target.get('damage', 0) * 25
                if label.startswith('discard ') and any(self.defs[identity]['name'].lower() in label for identity in self.preferred_cards if identity in self.defs):
                    value -= 60
            elif kind == 'silo': value = 100 if 'store_water' in want else -3
            elif kind == 'draw': value = 75 if 'draw_card' in want else 1
            elif kind == 'junk':
                junk = self.junk_kind(card)
                value = 45 if 'junk' in want else 0
                if junk == 'water' and 'water' in want: value += 90
                if junk == 'raid' and 'raid_launch' in want: value += 75
                if junk == 'restore' and 'restore' in want: value += 55
                if junk == 'punk' and 'enter' in want: value += 40
                if card.get('card_id') == 'hip_flask': value += 10
                if card.get('card_id') in self.preferred_cards: value -= 80
            elif kind == 'play':
                value = 10
                if 'column' in command:
                    value += 50 if 'enter' in want else 8
                    if 'replace' in command: value -= 4
                else:
                    value += 65 if 'event_play' in want or 'event_resolve' in want else 13
                    identity = card.get('card_id')
                    if identity == 'curfew' and 'return' in want: value += 35
                    if identity == 'box_canyon':
                        own = snapshot['view']['players'][snapshot['seat']]
                        if not any(person.get('type') == 'person' or person.get('punk')
                                   for column in own['columns'] for person in column):
                            return -120
                        if 'move' in want: value += 35
                if card.get('card_id') in self.preferred_cards: value += 45
            elif kind == 'activate':
                value = 20 + (60 if 'ability' in want else 0)
                abilities = definition.get('abilities', [])
                index = command.get('ability', 0)
                text = json.dumps(abilities[index] if isinstance(index, int) and 0 <= index < len(abilities) else definition).lower()
                for phrase, event in (('restore', 'restore'), ('destroy', 'destroy'), ('damage', 'damage'),
                                      ('return', 'return'), ('move', 'move'), ('raid', 'raid_launch'), ('water', 'water')):
                    if phrase in text and event in want: value += 23
                specific = {
                    ('riverboat', 0): 'camp_advance', ('lookout_ridge', 0): 'expose_all',
                    ('jailhouse', 0): 'recruit_id', ('army_surgeon_s_tent', 0): 'hospital_id',
                    ('boarding_house', 0): 'remove_ruin', ('pony_express_station', 0): 'return',
                }.get((card.get('card_id'), index))
                if specific in scenario_want: value += 180
            elif kind == 'flip': value = 60 if 'reveal_person' in want else 12
            elif kind == 'end_turn': value = 2
            # Repeated zero-cost choices must not starve later turns. Public
            # legal activation limits remain authoritative; this only changes
            # which offered command the test player prefers.
            same_type = sum(entry['command']['type'] == kind for entry in self.actions[-5:])
            return value - same_type * 2 + self.random.random() * 2
        return max(options, key=score)

    def coverage(self):
        # Unknown/new kinds still produce evidence instead of preventing the
        # report (and process cleanup). Internal close beats are explicitly
        # separate from the inventory of authoritative public events.
        kinds = INVENTORY | self.seen_kinds | self.logged_kinds
        motion = {kind: {'maximum_effect_motion_cm': 0., 'maximum_target_motion_cm': 0.,
                         'maximum_target_pose_change_cm': 0., 'observed_shots': 0} for kind in kinds}
        mapped_evidence = {'turn_end': [], 'rearrange': []}
        directed_shots = {}
        for identity, samples in self.shots.items():
            for sample in samples:
                # analysis_close reuses its ability's public sequence; those
                # are two presentations, not one mixed-motion trajectory.
                directed_shots.setdefault((*identity, sample['kind']), []).append(sample)
        for samples in directed_shots.values():
            first = samples[0]; kind = first['kind']
            row = {'maximum_effect_motion_cm': 0., 'maximum_target_motion_cm': 0.,
                   'maximum_target_pose_change_cm': 0., 'observed_shots': 1}
            # Components retain a stable array index for their current shot.
            for previous, current in zip(samples, samples[1:]):
                for a, b in zip(previous['effects'], current['effects']):
                    if a.get('visible') and b.get('visible'):
                        row['maximum_effect_motion_cm'] = max(row['maximum_effect_motion_cm'], math.dist(a['location'], b['location']))
                old = next((unit for unit in previous['units'] if unit['id'] == first['target']), None)
                new = next((unit for unit in current['units'] if unit['id'] == first['target']), None)
                if old and new:
                    row['maximum_target_motion_cm'] = max(row['maximum_target_motion_cm'], math.dist(old['location'], new['location']))
                    action_pose = new.get('ragdoll') or new.get('active_clip') != new.get('idle_clip')
                    if not old.get('event_token') and not new.get('event_token') and action_pose:
                        for a, b in zip(old.get('pose_samples', []), new.get('pose_samples', [])):
                            row['maximum_target_pose_change_cm'] = max(row['maximum_target_pose_change_cm'], math.dist(a, b))
            total = motion[kind]
            total['observed_shots'] += 1
            for key in ('maximum_effect_motion_cm', 'maximum_target_motion_cm', 'maximum_target_pose_change_cm'):
                total[key] = max(total[key], row[key])
            mapping = self.mapped_trigger(first['match_id'], first['sequence'], kind)
            if mapping:
                captures = [capture for capture in self.capture_records if capture.get('match_id') == first['match_id'] and
                            capture['sequence'] == first['sequence'] and capture['kind'] == kind and
                            capture['actual_phase_bracket_valid']]
                geometric_motion = (row['maximum_effect_motion_cm'] > 2 or row['maximum_target_motion_cm'] > 2 or
                                    row['maximum_target_pose_change_cm'] > 1)
                mapped_evidence[mapping['kind']].append({**mapping, 'match_id': first['match_id'],
                    'sequence': first['sequence'], 'source_revision': first.get('source_revision'),
                    'presented_kind': kind, 'motion': row,
                    'valid_captures': captures, 'rendered_motion_evidence': geometric_motion and any(
                        capture['requested_phase'] in ('impact', 'after-impact') for capture in captures)})
        result = {}
        for kind in sorted(kinds):
            phases = sorted(phase for observed_kind, phase in self.valid_captures if observed_kind == kind)
            row = motion[kind]
            geometric_motion = (row['maximum_effect_motion_cm'] > 2 or row['maximum_target_motion_cm'] > 2 or
                                row['maximum_target_pose_change_cm'] > 1)
            result[kind] = {'public_log_observed': kind in self.logged_kinds, 'active_presentation_observed': kind in self.seen_kinds,
                            'kind_scope': ('internal_presentation' if kind in INTERNAL_PRESENTATION_KINDS else
                                           'public_metadata' if kind in PUBLIC_METADATA_KINDS else
                                           'public_action' if kind in INVENTORY else 'unrecognized'),
                            'valid_native_capture_phases': phases, 'missing_capture_phases': sorted({'before-impact', 'impact', 'after-impact'} - set(phases)),
                            'actual_motion_observed': geometric_motion,
                            'rendered_motion_evidence': geometric_motion and bool({'impact', 'after-impact'} & set(phases)), **row}
            if kind in ('turn_end', 'rearrange'):
                result[kind]['presentation_mapping'] = 'turn_start handover' if kind == 'turn_end' else 'grouped move shots'
        for kind, evidence in mapped_evidence.items():
            result[kind]['mapped_evidence'] = evidence
            result[kind]['mapped_presentation_observed'] = any(entry['rendered_motion_evidence'] for entry in evidence)
        return result

    def finish_audio_recording(self, inspect=True):
        self.command('a', 'stop_audio_capture', name='action-showcase-mix', directory=str(self.folder))
        self.audio_started = False
        path = self.folder / 'action-showcase-mix.wav'

        def complete():
            try:
                with wave.open(str(path), 'rb') as wav:
                    expected = wav.getnframes() * wav.getnchannels() * wav.getsampwidth()
                    return expected > 0 and len(wav.readframes(wav.getnframes())) == expected
            except (OSError, EOFError, wave.Error):
                return False

        self.wait('complete showcase audio export', complete, 30)
        self.audio_report = {'recording': signature(path),
                             'start_ack_elapsed_seconds': self.audio_start_elapsed,
                             'stop_ack_elapsed_seconds': time.monotonic() - self.started,
                             'limitations': ['Native output mix from this legal-action run; human listening approval remains open.',
                                             'Control acknowledgement times are not sample-accurate synchronization evidence.']}
        if not inspect:
            return
        print(f'{self.folder.name}: analyzing recorded action audio', flush=True)
        self.audio_report['levels'] = analyze(path)
        events = self.folder / 'action-audio-events.json'
        with (self.folder / 'audio-correlation-console.log').open('w') as log:
            completed = subprocess.run([sys.executable, str(ROOT / 'scripts/check_game_audio_events.py'),
                                        str(path), '--subtract-ambience', '--report', str(events)],
                                       stdout=log, stderr=subprocess.STDOUT)
        assert completed.returncode in (0, 1) and events.is_file(), 'Audio correlation analysis failed'
        self.audio_report['events'] = json.loads(events.read_text())
        if not self.audio_report['levels']['ok']:
            self.issue('Recorded action mix failed signal checks', errors=self.audio_report['levels']['errors'])
        detected = set(self.audio_report['events']['detected_one_shots'])
        for name in getattr(self.args, 'require_sound', []):
            if name not in detected:
                self.issue('Required sound not detected in native mix', sound=name)
        write_json(self.folder / 'action-audio-review.json', self.audio_report)

    def run(self):
        result = None
        try:
            self.boot()
            if getattr(self.args, 'audio', False):
                self.command('a', 'start_audio_capture')
                self.audio_started = True
                self.audio_start_elapsed = time.monotonic() - self.started
            while time.monotonic() - self.started < self.args.timeout - 20:
                for name, process in self.processes.items():
                    assert process.poll() is None, f'Owned native peer {name} exited unexpectedly'
                state = self.read(); self.observe(state)
                snapshot, cinematic = state['snapshot'], state.get('cinematic', {})
                if cinematic.get('busy') and cinematic.get('kind'):
                    self.capture_phase(state)
                elif snapshot['view']['status'] in ('won', 'draw') or len(self.actions) >= self.args.max_actions:
                    if snapshot['view']['status'] in ('won', 'draw'):
                        def finale_visible():
                            current = self.read(); self.observe(current)
                            end = current.get('hud', {}).get('end_panel', {})
                            painted = painted_beat(current)
                            return (not current.get('cinematic', {}).get('busy') and end.get('present') and end.get('visible') and
                                    painted and not painted.get('busy') and painted.get('end_panel_visible') and
                                    painted.get('match_id') == current.get('snapshot', {}).get('match_id'))
                        self.wait('match result appears after natural final presentation', finale_visible, 10)
                    self.capture('final-tactical-state')
                    break
                elif self.agree():
                    acting = next((name for name in ('a', 'b') if self.snapshot(name).get('actions')), None)
                    if acting:
                        current = self.snapshot(acting)
                        action = self.choose_action(acting, current)
                        kind = action['command']['type']
                        if kind not in self.before_types:
                            self.before_types.add(kind)
                            self.capture(f'before-submit-{kind}')
                        record = {'peer': acting, 'revision': current['view']['revision'], 'match_id': current['match_id'],
                                  'seat': current['seat'], 'turn': current['view']['turn'],
                                  'last_public_sequence': max((event['sequence'] for event in current['view'].get('log', [])), default=-1),
                                  'command': action['command'], 'public_label': action.get('label'),
                                  'legal_actions_sha256': hashlib.sha256(json.dumps(current['actions'], sort_keys=True).encode()).hexdigest()}
                        self.actions.append(record)
                        write_json(self.folder / 'legal-action-journal.json', self.actions)
                        self.submit(acting, action)
                        record['accepted_revision'] = self.snapshot(acting)['view']['revision']
                        write_json(self.folder / 'legal-action-journal.json', self.actions)
                if time.monotonic() - self.last_progress >= 25:
                    print(f'{self.folder.name}: {len(self.actions)} legal actions; visible kinds {sorted(self.seen_kinds)}; missing {sorted(INVENTORY-self.seen_kinds)}', flush=True)
                    self.last_progress = time.monotonic()
                time.sleep(.018)
            else:
                self.issue('Showcase time budget ended; unobserved actions remain missing')
            if self.audio_started:
                # Let the last naturally completed presentation's sound tail
                # finish before exporting the same rendered client's mix.
                time.sleep(1.5)
                self.finish_audio_recording()
            runtime_assets = assert_runtime_assets([self.folder / 'a.log', self.folder / 'b.log'])
            if not self.paint_telemetry_seen:
                self.issue('Actual HUD paint telemetry is missing from this build')
            missing_paint = sorted(set(self.shots) - self.painted_shots)
            if missing_paint:
                self.issue('Observed action shots have no correlated native paint identity', shots=missing_paint)
            if getattr(self.args, 'profile_renderer', False) and (
                    'a' not in self.performance_enabled_peers or not any(record['peer'] == 'a' for record in self.performance_reports)):
                self.issue('Requested renderer/report performance telemetry was not observed')
            coverage = self.coverage()
            for kind in self.args.require_kind:
                if not (coverage[kind]['rendered_motion_evidence'] or coverage[kind].get('mapped_presentation_observed')):
                    self.issue(f'Required action lacks observed native motion and a valid capture: {kind}')
            result = {'ok': not self.issues, 'coverage_complete': all(coverage[kind]['rendered_motion_evidence'] or
                      coverage[kind].get('mapped_presentation_observed') for kind in INVENTORY), 'coverage': coverage, 'issues': self.issues,
                      'scenario_targets': self.scenario['target_kinds'],
                      'scenario_missing': [kind for kind in self.scenario['target_kinds'] if not (
                          coverage[kind]['rendered_motion_evidence'] or coverage[kind].get('mapped_presentation_observed'))],
                      'runtime_assets': runtime_assets, 'match_status': self.snapshot()['view']['status']}
        except Exception as error:
            result = {'ok': False, 'failure': str(error), 'coverage_complete': False,
                      'coverage': {}, 'issues': self.issues}
            raise
        finally:
            result = result or {'ok': False, 'failure': 'Showcase interrupted', 'coverage': {}}
            if self.audio_started and self.processes.get('a') and self.processes['a'].poll() is None:
                try:
                    self.finish_audio_recording(inspect=False)
                except Exception as error:
                    result.update(ok=False, audio_export_error=str(error))
            result['audio'] = self.audio_report
            # Report construction can itself fail (bad telemetry, I/O, or a
            # newly added kind). Owned processes must still be stopped.
            try:
                if not result.get('coverage'):
                    try:
                        result['coverage'] = self.coverage()
                    except Exception as error:
                        result.update(ok=False, coverage_error=str(error))
                result.update(build=self.build, resolution=list(self.dimensions), seed=self.args.seed, ruleset=self.args.ruleset,
                              scenario=self.scenario, camp_selections=self.camp_selections,
                              legal_action_count=len(self.actions), logged_kinds=sorted(self.logged_kinds), active_kinds=sorted(self.seen_kinds),
                              unknown_public_log_kinds=sorted(self.logged_kinds - INVENTORY),
                              internal_presentation_kinds=sorted(self.seen_kinds & INTERNAL_PRESENTATION_KINDS),
                              public_event_inventory=sorted(INVENTORY), captures=self.capture_records,
                              screenshots=self.captures, completed_falls=self.completions, logs=str(self.folder),
                              lens_checks={**self.lens_checks, 'apertures': sorted(self.lens_checks['apertures'])},
                              subject_capture_coverage=[{'kind': kind, 'target_category': category,
                                  'public_character': character, 'phase': phase}
                                  for kind, category, character, phase in sorted(self.valid_subject_captures,
                                      key=lambda entry: tuple(value or '' for value in entry))],
                              arrived_delivery_capture_kinds=sorted(self.valid_delivery_captures),
                              late_physics_sample_count=self.late_physics_sample_count,
                              paint_telemetry_seen=self.paint_telemetry_seen,
                              paint_transition_count=len(self.paint_transitions),
                              painted_shots=[{'match_id': match, 'sequence': sequence}
                                             for match, sequence in sorted(self.painted_shots)],
                              prepaint_visibility_discrepancy_count=len(self.prepaint_visibility),
                              profile_renderer=getattr(self.args, 'profile_renderer', False),
                              extra_render_commands=getattr(self.args, 'extra_render_commands', []),
                              performance_enabled_peers=sorted(self.performance_enabled_peers),
                              lifecycle_performance_report_count=len(self.performance_reports),
                              tactical_lens_samples=self.tactical_lens_samples, finale_samples=self.finale_samples,
                              elapsed_seconds=round(time.monotonic() - self.started, 2),
                              limitations=['Only ordinary legal actions reached in this run are covered.',
                                           'Kind-label sightings alone are not rendered-motion evidence.',
                                           'Screenshots require human visual review; telemetry cannot certify AAA quality.',
                                           'The separate strict ordinary cinematic regression remains required.',
                                           'Both peers run on one computer; this is not remote internet testing.'])
                write_json(self.folder / 'public-log-journal.json', self.logged_events)
                write_json(self.folder / 'paint-transitions.json', self.paint_transitions)
                write_json(self.folder / 'prepaint-visibility-observations.json', self.prepaint_visibility)
                write_json(self.folder / 'completed-falls.json', self.completions)
                write_json(self.folder / 'result.json', result)
            except Exception as error:
                result.update(ok=False, report_error=str(error))
                raise
            finally:
                try:
                    stop_owned_process_groups(self.processes.values(), self.streams)
                    result['owned_process_cleanup_complete'] = True
                except Exception as error:
                    result.update(ok=False, cleanup_error=str(error))
                    raise
                finally:
                    write_json(self.folder / 'result.json', result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, default=EDITOR)
    parser.add_argument('--package-dir', type=Path)
    parser.add_argument('--resolutions', nargs='+', type=resolution, default=[(1280, 720)])
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--scenario', default='general')
    parser.add_argument('--prefer-camp', action='append', default=[])
    parser.add_argument('--ruleset', choices=['base_2024', 'boomtown'])
    parser.add_argument('--seed', type=int)
    parser.add_argument('--port', type=int, default=19519)
    parser.add_argument('--timeout', type=float, default=1200)
    parser.add_argument('--max-actions', type=int)
    parser.add_argument('--audio', action='store_true', help='Record and analyze the rendered client output mix throughout legal play')
    parser.add_argument('--require-sound', action='append', default=[], help='Require an authored SW_ name to be detected in the recorded mix; needs --audio')
    parser.add_argument('--profile-renderer', action='store_true',
                        help='Observe native frame and lifecycle report costs; changes no physics/render settings')
    parser.add_argument('--extra-render-command', dest='extra_render_commands', action='append', default=[],
                        help='Explicit additional startup console command for a retained diagnostic comparison')
    parser.add_argument('--require-kind', action='append', choices=sorted(INVENTORY), default=[])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.require_sound and not args.audio:
        parser.error('--require-sound needs --audio')
    if args.audio and importlib.util.find_spec('numpy') is None:
        parser.error('--audio analysis needs NumPy; run with a Python environment that provides it')
    sounds = json.loads((ROOT / 'art/audio/audio-manifest.json').read_text())['assets']
    if set(args.require_sound) - set(sounds):
        parser.error('Unknown sound names: ' + ', '.join(sorted(set(args.require_sound) - set(sounds))))
    manifest = json.loads(args.manifest.read_text())
    scenarios = {scenario['name']: scenario for scenario in manifest['scenarios']}
    if args.scenario not in scenarios:
        parser.error(f'Unknown scenario; choose from {", ".join(scenarios)}')
    args.scenario_config = scenarios[args.scenario]
    planned = {kind for scenario in scenarios.values() for kind in scenario['target_kinds']}
    if planned != INVENTORY:
        parser.error(f'Manifest must account for all29 kinds: missing={sorted(INVENTORY-planned)}, unknown={sorted(planned-INVENTORY)}')
    args.ruleset = args.ruleset or manifest['ruleset']
    args.seed = args.seed if args.seed is not None else args.scenario_config.get('seed')
    args.max_actions = args.max_actions if args.max_actions is not None else args.scenario_config['max_actions']
    if args.seed is None:
        parser.error('This scenario needs a public-draft seed; pass --seed or run the public draft probe')
    args.settle = 0.0
    if not 0 <= args.seed < 2**64 or args.timeout < 60 or args.max_actions < 1:
        parser.error('Use an unsigned64-bit seed, timeout>=60 and max-actions>=1')
    output = args.output.resolve() if args.output else create_native_run_directory('oldwest-action-showcase-')
    output.mkdir(parents=True, exist_ok=True)
    report = {'ok': False, 'results': [], 'logs': str(output), 'scope': 'ordinary legal native action showcase'}
    print(f'Native action showcase evidence: {output}', flush=True)
    try:
        for index, dimensions in enumerate(args.resolutions):
            report['results'].append(ActionShowcase(args, output, dimensions, index).run())
        report['ok'] = all(result['ok'] for result in report['results'])
    except Exception as error:
        report['failure'] = str(error)
        raise
    finally:
        write_json(output / 'result.json', report)
        write_json(ROOT / 'game/tests/reports/latest-native-action-showcase.json', report)
        print(json.dumps({'ok': report['ok'], 'logs': str(output), 'failure': report.get('failure')}, indent=2), flush=True)
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
